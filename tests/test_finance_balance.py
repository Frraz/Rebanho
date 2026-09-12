"""
Testes de pagamentos, ajustes manuais e saldo do cliente.

A convenção de sinal é o coração deste módulo e vale repetir:
    negativo → o cliente deve
    zero     → quitado
    positivo → o cliente tem crédito a favor

Os cenários abaixo são exatamente os que o cliente descreveu ao pedir o
sistema: comprar e ficar devendo, quitar, pagar a mais, e pagar adiantado
sem dever nada.
"""
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from finance.models import EntryType, FinancialEntry, PaymentType
from finance.services import AdjustmentService, BalanceService, PaymentService, SaleService
from finance.services.balance_service import BalanceType


def _item(category, quantity, peso, preco_kg, total):
    return {
        'animal_category': category,
        'quantity': quantity,
        'total_weight': Decimal(peso),
        'price_per_kg': Decimal(preco_kg),
        'total_amount': Decimal(total),
    }


# ══════════════════════════════════════════════════════════════════════════
# OS QUATRO ESTADOS DE SALDO
# ══════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
def test_comprando_o_cliente_fica_negativo(
    farm, category, operation_client, db_user, stock_balance_with_animals
):
    SaleService.create(
        client=operation_client, farm=farm, date='2026-09-10',
        items=[_item(category, 5, '1000.00', '10.00', '10000.00')],
        user=db_user,
    )
    assert BalanceService.get_balance(operation_client.id) == Decimal('-10000.00')


@pytest.mark.django_db
def test_pagando_tudo_o_saldo_zera(
    farm, category, operation_client, db_user, stock_balance_with_animals
):
    SaleService.create(
        client=operation_client, farm=farm, date='2026-09-10',
        items=[_item(category, 5, '1000.00', '10.00', '10000.00')],
        user=db_user,
    )
    PaymentService.create(
        client=operation_client, date='2026-09-15',
        amount=Decimal('10000.00'), payment_type=PaymentType.PIX, user=db_user,
    )
    assert BalanceService.get_balance(operation_client.id) == Decimal('0.00')


@pytest.mark.django_db
def test_pagando_a_mais_o_saldo_fica_positivo(
    farm, category, operation_client, db_user, stock_balance_with_animals
):
    SaleService.create(
        client=operation_client, farm=farm, date='2026-09-10',
        items=[_item(category, 5, '1000.00', '10.00', '10000.00')],
        user=db_user,
    )
    PaymentService.create(
        client=operation_client, date='2026-09-15',
        amount=Decimal('12000.00'), payment_type=PaymentType.DINHEIRO, user=db_user,
    )
    assert BalanceService.get_balance(operation_client.id) == Decimal('2000.00')


@pytest.mark.django_db
def test_pagamento_antecipado_e_abatido_na_compra_seguinte(
    farm, category, operation_client, db_user, stock_balance_with_animals
):
    """O cenário do pagamento adiantado, sem dívida nenhuma no momento."""
    PaymentService.create(
        client=operation_client, date='2026-09-01',
        amount=Decimal('5000.00'), payment_type=PaymentType.TRANSFERENCIA, user=db_user,
    )
    assert BalanceService.get_balance(operation_client.id) == Decimal('5000.00')

    SaleService.create(
        client=operation_client, farm=farm, date='2026-09-10',
        items=[_item(category, 5, '1000.00', '8.00', '8000.00')],
        user=db_user,
    )
    # Devia 8.000, tinha 5.000 de crédito → sobra devendo 3.000.
    assert BalanceService.get_balance(operation_client.id) == Decimal('-3000.00')


# ══════════════════════════════════════════════════════════════════════════
# PAGAMENTOS
# ══════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
def test_pagamento_gera_um_credito(operation_client, db_user):
    pagamento = PaymentService.create(
        client=operation_client, date='2026-09-15', amount=Decimal('1500.00'),
        payment_type=PaymentType.CHEQUE, user=db_user, description='Cheque 001',
    )
    entry = FinancialEntry.objects.get(payment=pagamento)
    assert entry.entry_type == EntryType.CREDITO
    assert entry.amount == Decimal('1500.00')
    assert entry.description == 'Cheque 001'


@pytest.mark.django_db
def test_editar_pagamento_refaz_o_credito(operation_client, db_user):
    pagamento = PaymentService.create(
        client=operation_client, date='2026-09-15', amount=Decimal('1500.00'),
        payment_type=PaymentType.PIX, user=db_user,
    )
    PaymentService.update(
        payment=pagamento, client=operation_client, date='2026-09-16',
        amount=Decimal('2000.00'), payment_type=PaymentType.DINHEIRO, user=db_user,
    )

    assert FinancialEntry.objects.filter(payment=pagamento).count() == 1
    assert BalanceService.get_balance(operation_client.id) == Decimal('2000.00')


@pytest.mark.django_db
def test_apagar_pagamento_remove_o_credito_e_registra_log(operation_client, db_user):
    from finance.models import FinanceDeletionLog

    pagamento = PaymentService.create(
        client=operation_client, date='2026-09-15', amount=Decimal('1500.00'),
        payment_type=PaymentType.PIX, user=db_user,
    )
    PaymentService.delete(pagamento=pagamento, user=db_user, reason='Lançado em duplicidade')

    assert FinancialEntry.objects.count() == 0
    assert BalanceService.get_balance(operation_client.id) == Decimal('0.00')

    log = FinanceDeletionLog.objects.get()
    assert log.object_type == 'PAGAMENTO'
    assert log.amount == Decimal('1500.00')
    assert log.snapshot['pagamento']['tipo'] == 'PIX'


@pytest.mark.django_db
def test_pagamento_com_valor_invalido_e_recusado(operation_client, db_user):
    for valor in (Decimal('0'), Decimal('-10'), None):
        with pytest.raises(ValidationError):
            PaymentService.create(
                client=operation_client, date='2026-09-15', amount=valor,
                payment_type=PaymentType.PIX, user=db_user,
            )


# ══════════════════════════════════════════════════════════════════════════
# AJUSTES MANUAIS
# ══════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
def test_ajuste_de_credito_perdoa_divida(
    farm, category, operation_client, db_user, stock_balance_with_animals
):
    SaleService.create(
        client=operation_client, farm=farm, date='2026-09-10',
        items=[_item(category, 5, '1000.00', '10.00', '10000.00')],
        user=db_user,
    )
    AdjustmentService.create(
        client=operation_client, date='2026-09-20', entry_type=EntryType.CREDITO,
        amount=Decimal('10000.00'), description='Dívida perdoada em acordo', user=db_user,
    )
    assert BalanceService.get_balance(operation_client.id) == Decimal('0.00')


@pytest.mark.django_db
def test_ajuste_exige_descricao(operation_client, db_user):
    """Sem documento de origem, a descrição é a única explicação que sobra."""
    with pytest.raises(ValidationError):
        AdjustmentService.create(
            client=operation_client, date='2026-09-20', entry_type=EntryType.DEBITO,
            amount=Decimal('100.00'), description='   ', user=db_user,
        )


# ══════════════════════════════════════════════════════════════════════════
# CONSULTAS DE SALDO
# ══════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
def test_totais_do_cliente(
    farm, category, operation_client, db_user, stock_balance_with_animals
):
    SaleService.create(
        client=operation_client, farm=farm, date='2026-09-10',
        items=[_item(category, 5, '1000.00', '10.00', '10000.00')],
        user=db_user,
    )
    PaymentService.create(
        client=operation_client, date='2026-09-15', amount=Decimal('4000.00'),
        payment_type=PaymentType.PIX, user=db_user,
    )

    totais = BalanceService.get_totals(operation_client.id)
    assert totais['debitos'] == Decimal('10000.00')
    assert totais['creditos'] == Decimal('4000.00')
    assert totais['saldo'] == Decimal('-6000.00')


@pytest.mark.django_db
def test_anotacao_de_saldo_e_filtro_por_tipo(
    farm, category, operation_client, db_user, stock_balance_with_animals
):
    from operations.models import Client

    devedor = operation_client
    credor = Client.objects.create(name='Maria Souza')
    quitado = Client.objects.create(name='Zero a Zero')

    SaleService.create(
        client=devedor, farm=farm, date='2026-09-10',
        items=[_item(category, 5, '1000.00', '10.00', '10000.00')],
        user=db_user,
    )
    PaymentService.create(
        client=credor, date='2026-09-11', amount=Decimal('700.00'),
        payment_type=PaymentType.PIX, user=db_user,
    )

    anotado = BalanceService.annotate_balance(Client.objects.all())
    saldos = {c.name: c.saldo for c in anotado}
    assert saldos[devedor.name] == Decimal('-10000.00')
    assert saldos[credor.name] == Decimal('700.00')
    assert saldos[quitado.name] == Decimal('0.00')

    negativos = BalanceService.filter_by_balance_type(
        BalanceService.annotate_balance(Client.objects.all()), BalanceType.NEGATIVO
    )
    assert [c.name for c in negativos] == [devedor.name]

    positivos = BalanceService.filter_by_balance_type(
        BalanceService.annotate_balance(Client.objects.all()), BalanceType.POSITIVO
    )
    assert [c.name for c in positivos] == [credor.name]


@pytest.mark.django_db
def test_saldo_anterior_a_uma_data(operation_client, db_user):
    """Ponto de partida do saldo acumulado no relatório de Fluxo Financeiro."""
    PaymentService.create(
        client=operation_client, date='2026-08-01', amount=Decimal('100.00'),
        payment_type=PaymentType.PIX, user=db_user,
    )
    PaymentService.create(
        client=operation_client, date='2026-09-01', amount=Decimal('50.00'),
        payment_type=PaymentType.PIX, user=db_user,
    )

    anterior = BalanceService.get_running_balance_before(operation_client.id, '2026-09-01')
    assert anterior == Decimal('100.00')
