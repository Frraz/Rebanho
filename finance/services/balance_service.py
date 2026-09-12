"""
finance/services/balance_service.py

Cálculo de saldo dos clientes.

CONVENÇÃO DE SINAL (definida com o cliente):
    saldo negativo → o cliente DEVE
    saldo zero     → quitado
    saldo positivo → o cliente tem CRÉDITO a favor (pagou adiantado ou a mais)

    saldo = Σ(créditos) − Σ(débitos)

Tudo aqui é agregação sobre `FinancialEntry` — não existe tabela de saldo para
manter sincronizada. Ver a justificativa em finance/models/financial_entry.py.
"""
from decimal import Decimal

from django.db.models import Case, DecimalField, F, Q, Sum, Value, When
from django.db.models.functions import Coalesce

from finance.models import EntryType, FinancialEntry

ZERO = Decimal('0.00')

# Expressão reusada em todo o módulo: crédito soma, débito subtrai.
_SIGNED_AMOUNT = Case(
    When(entry_type=EntryType.CREDITO, then=F('amount')),
    default=-F('amount'),
    output_field=DecimalField(max_digits=14, decimal_places=2),
)

_MONEY = DecimalField(max_digits=14, decimal_places=2)


class BalanceType:
    """Filtro de tipo de saldo usado no relatório de Saldos."""

    NEGATIVO = 'NEGATIVO'
    ZERADO = 'ZERADO'
    POSITIVO = 'POSITIVO'

    CHOICES = [
        (NEGATIVO, 'Devedor (negativo)'),
        (ZERADO, 'Quitado (zerado)'),
        (POSITIVO, 'Com crédito (positivo)'),
    ]


class BalanceService:
    """Consultas de saldo. Somente leitura — nunca escreve."""

    @staticmethod
    def get_balance(client_id) -> Decimal:
        """Saldo atual de um cliente."""
        result = FinancialEntry.objects.filter(client_id=client_id).aggregate(
            saldo=Coalesce(Sum(_SIGNED_AMOUNT), Value(ZERO), output_field=_MONEY)
        )
        return result['saldo'] or ZERO

    @staticmethod
    def get_totals(client_id) -> dict:
        """Total comprado, total pago e saldo de um cliente."""
        result = FinancialEntry.objects.filter(client_id=client_id).aggregate(
            debitos=Coalesce(
                Sum('amount', filter=Q(entry_type=EntryType.DEBITO)),
                Value(ZERO), output_field=_MONEY,
            ),
            creditos=Coalesce(
                Sum('amount', filter=Q(entry_type=EntryType.CREDITO)),
                Value(ZERO), output_field=_MONEY,
            ),
        )
        debitos = result['debitos'] or ZERO
        creditos = result['creditos'] or ZERO
        return {
            'debitos': debitos,
            'creditos': creditos,
            'saldo': creditos - debitos,
        }

    @staticmethod
    def annotate_balance(client_queryset):
        """
        Acrescenta `saldo`, `total_debitos` e `total_creditos` a um queryset de
        clientes — uma consulta só, sem N+1.

        Usado na lista de clientes e no relatório de Saldos.
        """
        return client_queryset.annotate(
            total_debitos=Coalesce(
                Sum('financial_entries__amount',
                    filter=Q(financial_entries__entry_type=EntryType.DEBITO)),
                Value(ZERO), output_field=_MONEY,
            ),
            total_creditos=Coalesce(
                Sum('financial_entries__amount',
                    filter=Q(financial_entries__entry_type=EntryType.CREDITO)),
                Value(ZERO), output_field=_MONEY,
            ),
        ).annotate(
            saldo=F('total_creditos') - F('total_debitos'),
        )

    @staticmethod
    def filter_by_balance_type(queryset, balance_type: str):
        """
        Filtra um queryset já anotado por `annotate_balance`.

        Precisa ser aplicado DEPOIS da anotação, porque `saldo` é um campo
        calculado — por isso a operação é separada.
        """
        if balance_type == BalanceType.NEGATIVO:
            return queryset.filter(saldo__lt=ZERO)
        if balance_type == BalanceType.POSITIVO:
            return queryset.filter(saldo__gt=ZERO)
        if balance_type == BalanceType.ZERADO:
            return queryset.filter(saldo=ZERO)
        return queryset

    @staticmethod
    def get_running_balance_before(client_id, date) -> Decimal:
        """
        Saldo do cliente imediatamente antes de uma data.

        É o ponto de partida do saldo acumulado no relatório de Fluxo
        Financeiro quando um único cliente está filtrado.
        """
        result = FinancialEntry.objects.filter(
            client_id=client_id, date__lt=date,
        ).aggregate(
            saldo=Coalesce(Sum(_SIGNED_AMOUNT), Value(ZERO), output_field=_MONEY)
        )
        return result['saldo'] or ZERO
