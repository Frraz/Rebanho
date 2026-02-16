"""
test_report_stock.py — Cálculo de estoque inicial e final nos relatórios.

Regra crítica: o estoque inicial de um período = soma de TODOS os movimentos
ANTERIORES ao primeiro dia do período (calculado pelo ledger, não pelo snapshot).

Testa:
  - Estoque inicial correto (soma histórico até dia anterior)
  - Estoque final correto (inicial + entradas - saídas do período)
  - Movimentos do período não contaminam o estoque inicial
  - Períodos sem movimentação retornam estoque correto
  - Recálculo consistente com snapshot atual
"""
import pytest
from datetime import date, timedelta
from django.utils import timezone

from inventory.services import MovementService
from inventory.domain.value_objects import OperationType
from reporting.queries.report_queries import ReportQueries


def _ts(d: date):
    """Converte date para datetime aware no início do dia."""
    return timezone.make_aware(
        timezone.datetime.combine(d, timezone.datetime.min.time())
    )


@pytest.mark.django_db
class TestEstoqueInicial:
    """O estoque inicial deve refletir somente movimentos anteriores ao período."""

    def test_estoque_inicial_correto_para_periodo(
        self, stock_balance, farm, category, db_user
    ):
        """
        Cenário:
          - Mês passado: +10 nascimento, +5 compra → acumulado = 15
          - Mês atual (período): +3 nascimento
          - Estoque inicial do mês atual deve ser 15, não 18
        """
        hoje        = date.today()
        mes_passado = date(hoje.year, hoje.month - 1, 1) if hoje.month > 1 \
                      else date(hoje.year - 1, 12, 1)
        mes_atual   = date(hoje.year, hoje.month, 1)

        # Movimentos no mês passado (antes do período)
        MovementService.execute_entrada(
            farm_id=str(farm.id),
            animal_category_id=str(category.id),
            operation_type=OperationType.NASCIMENTO,
            quantity=10,
            user=db_user,
            timestamp=_ts(mes_passado),
        )
        MovementService.execute_entrada(
            farm_id=str(farm.id),
            animal_category_id=str(category.id),
            operation_type=OperationType.COMPRA,
            quantity=5,
            user=db_user,
            timestamp=_ts(mes_passado + timedelta(days=5)),
        )

        # Movimento no mês atual (DENTRO do período — não deve entrar no inicial)
        MovementService.execute_entrada(
            farm_id=str(farm.id),
            animal_category_id=str(category.id),
            operation_type=OperationType.NASCIMENTO,
            quantity=3,
            user=db_user,
            timestamp=_ts(mes_atual),
        )

        estoque_inicial = ReportQueries.calculate_opening_stock(
            farm_id=farm.id,
            animal_category_id=category.id,
            start_date=mes_atual,
        )

        assert estoque_inicial == 15  # Apenas os 15 do mês passado

    def test_estoque_inicial_zero_sem_historico_anterior(
        self, stock_balance, farm, category, db_user
    ):
        """Sem movimentos anteriores ao período, estoque inicial é zero."""
        hoje      = date.today()
        mes_atual = date(hoje.year, hoje.month, 1)

        # Só cria movimento no mês atual
        MovementService.execute_entrada(
            farm_id=str(farm.id),
            animal_category_id=str(category.id),
            operation_type=OperationType.NASCIMENTO,
            quantity=8,
            user=db_user,
            timestamp=_ts(mes_atual),
        )

        estoque_inicial = ReportQueries.calculate_opening_stock(
            farm_id=farm.id,
            animal_category_id=category.id,
            start_date=mes_atual,
        )

        assert estoque_inicial == 0

    def test_estoque_final_formula_correta(
        self, stock_balance, farm, category, db_user
    ):
        """
        Fórmula: estoque_final = inicial + entradas_período - saídas_período
        Cenário: inicial=20, +5 entrada, -3 saída → final=22
        """
        import calendar
        hoje        = date.today()
        mes_passado = date(hoje.year, hoje.month - 1, 1) if hoje.month > 1 \
                      else date(hoje.year - 1, 12, 1)
        mes_atual   = date(hoje.year, hoje.month, 1)
        ultimo_dia  = date(
            hoje.year, hoje.month,
            calendar.monthrange(hoje.year, hoje.month)[1]
        )

        # Histórico anterior: +20
        MovementService.execute_entrada(
            farm_id=str(farm.id),
            animal_category_id=str(category.id),
            operation_type=OperationType.NASCIMENTO,
            quantity=20,
            user=db_user,
            timestamp=_ts(mes_passado),
        )

        # Período atual: +5 compra, −3 abate
        MovementService.execute_entrada(
            farm_id=str(farm.id),
            animal_category_id=str(category.id),
            operation_type=OperationType.COMPRA,
            quantity=5,
            user=db_user,
            timestamp=_ts(mes_atual),
        )
        MovementService.execute_saida(
            farm_id=str(farm.id),
            animal_category_id=str(category.id),
            operation_type=OperationType.ABATE,
            quantity=3,
            user=db_user,
            timestamp=_ts(mes_atual + timedelta(days=3)),
        )

        estoque_inicial = ReportQueries.calculate_opening_stock(
            farm_id=farm.id,
            animal_category_id=category.id,
            start_date=mes_atual,
        )
        estoque_final = ReportQueries.calculate_closing_stock(
            farm_id=farm.id,
            animal_category_id=category.id,
            start_date=mes_atual,
            end_date=ultimo_dia,
        )

        assert estoque_inicial == 20
        assert estoque_final == 22  # 20 + 5 - 3

    def test_snapshot_consistente_com_ledger(
        self, stock_balance, farm, category, db_user
    ):
        """
        O snapshot (current_quantity) deve sempre ser igual ao
        saldo calculado a partir do ledger completo.
        Cenário: +30, +10, -8, -5 → esperado = 27
        """
        from django.db.models import Sum
        from inventory.models import AnimalMovement

        MovementService.execute_entrada(
            farm_id=str(farm.id),
            animal_category_id=str(category.id),
            operation_type=OperationType.NASCIMENTO,
            quantity=30, user=db_user,
        )
        MovementService.execute_entrada(
            farm_id=str(farm.id),
            animal_category_id=str(category.id),
            operation_type=OperationType.COMPRA,
            quantity=10, user=db_user,
        )
        MovementService.execute_saida(
            farm_id=str(farm.id),
            animal_category_id=str(category.id),
            operation_type=OperationType.ABATE,
            quantity=8, user=db_user,
        )
        MovementService.execute_saida(
            farm_id=str(farm.id),
            animal_category_id=str(category.id),
            operation_type=OperationType.ABATE,
            quantity=5, user=db_user,
        )

        # Calcula via ledger
        entradas = AnimalMovement.objects.filter(
            farm_stock_balance=stock_balance,
            movement_type='ENTRADA'
        ).aggregate(t=Sum('quantity'))['t'] or 0

        saidas = AnimalMovement.objects.filter(
            farm_stock_balance=stock_balance,
            movement_type='SAIDA'
        ).aggregate(t=Sum('quantity'))['t'] or 0

        saldo_ledger = entradas - saidas

        # Compara com snapshot
        stock_balance.refresh_from_db()

        assert saldo_ledger == 27
        assert stock_balance.current_quantity == saldo_ledger