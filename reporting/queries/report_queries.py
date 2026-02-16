"""
ReportQueries — Camada de queries reutilizável para relatórios.

Extrai queries complexas dos services para uso direto,
inclusive nos testes automatizados.

Métodos:
  - calculate_opening_stock(): estoque inicial de um período
  - calculate_closing_stock(): estoque final de um período
  - get_period_movements(): movimentos de um período
  - get_movements_before(): movimentos anteriores a uma data
"""
from django.db.models import Sum
from django.utils import timezone
from datetime import date, datetime, time
from typing import Optional

from inventory.models import AnimalMovement
from inventory.domain.value_objects import MovementType


class ReportQueries:

    @staticmethod
    def calculate_opening_stock(
        farm_id,
        animal_category_id,
        start_date: date,
    ) -> int:
        """
        Calcula o estoque inicial de um período.

        Regra: soma de TODOS os movimentos ANTERIORES ao primeiro dia
        do período — calculado pelo ledger, nunca pelo snapshot.

        Args:
            farm_id: UUID da fazenda (str ou UUID)
            animal_category_id: UUID da categoria (str ou UUID)
            start_date: Primeiro dia do período

        Returns:
            Quantidade de animais no início do período (nunca negativo)
        """
        start_datetime = timezone.make_aware(
            datetime.combine(start_date, time.min)
        )

        base_qs = AnimalMovement.objects.filter(
            farm_stock_balance__farm_id=farm_id,
            farm_stock_balance__animal_category_id=animal_category_id,
            timestamp__lt=start_datetime,
        )

        entradas = base_qs.filter(
            movement_type=MovementType.ENTRADA.value
        ).aggregate(total=Sum('quantity'))['total'] or 0

        saidas = base_qs.filter(
            movement_type=MovementType.SAIDA.value
        ).aggregate(total=Sum('quantity'))['total'] or 0

        return max(0, entradas - saidas)

    @staticmethod
    def calculate_closing_stock(
        farm_id,
        animal_category_id,
        start_date: date,
        end_date: date,
    ) -> int:
        """
        Calcula o estoque final de um período.

        Fórmula: estoque_inicial + entradas_período - saídas_período

        Args:
            farm_id: UUID da fazenda
            animal_category_id: UUID da categoria
            start_date: Primeiro dia do período
            end_date: Último dia do período

        Returns:
            Quantidade de animais no fim do período
        """
        opening = ReportQueries.calculate_opening_stock(
            farm_id=farm_id,
            animal_category_id=animal_category_id,
            start_date=start_date,
        )

        start_datetime = timezone.make_aware(datetime.combine(start_date, time.min))
        end_datetime   = timezone.make_aware(datetime.combine(end_date, time.max))

        period_qs = AnimalMovement.objects.filter(
            farm_stock_balance__farm_id=farm_id,
            farm_stock_balance__animal_category_id=animal_category_id,
            timestamp__gte=start_datetime,
            timestamp__lte=end_datetime,
        )

        entradas = period_qs.filter(
            movement_type=MovementType.ENTRADA.value
        ).aggregate(total=Sum('quantity'))['total'] or 0

        saidas = period_qs.filter(
            movement_type=MovementType.SAIDA.value
        ).aggregate(total=Sum('quantity'))['total'] or 0

        return max(0, opening + entradas - saidas)

    @staticmethod
    def get_period_movements(
        farm_id,
        animal_category_id,
        start_date: date,
        end_date: date,
    ):
        """
        Retorna todos os movimentos de um período específico.

        Args:
            farm_id: UUID da fazenda
            animal_category_id: UUID da categoria
            start_date: Primeiro dia do período
            end_date: Último dia do período

        Returns:
            QuerySet de AnimalMovement ordenados por timestamp
        """
        start_datetime = timezone.make_aware(datetime.combine(start_date, time.min))
        end_datetime   = timezone.make_aware(datetime.combine(end_date, time.max))

        return (
            AnimalMovement.objects
            .filter(
                farm_stock_balance__farm_id=farm_id,
                farm_stock_balance__animal_category_id=animal_category_id,
                timestamp__gte=start_datetime,
                timestamp__lte=end_datetime,
            )
            .select_related(
                'farm_stock_balance__farm',
                'farm_stock_balance__animal_category',
                'client',
                'death_reason',
                'created_by',
            )
            .order_by('timestamp')
        )

    @staticmethod
    def get_movements_before(
        farm_id,
        animal_category_id,
        before_date: date,
    ):
        """
        Retorna todos os movimentos ANTERIORES a uma data.

        Útil para auditoria e verificação de histórico.

        Args:
            farm_id: UUID da fazenda
            animal_category_id: UUID da categoria
            before_date: Data limite (exclusive)

        Returns:
            QuerySet de AnimalMovement ordenados por timestamp
        """
        before_datetime = timezone.make_aware(
            datetime.combine(before_date, time.min)
        )

        return (
            AnimalMovement.objects
            .filter(
                farm_stock_balance__farm_id=farm_id,
                farm_stock_balance__animal_category_id=animal_category_id,
                timestamp__lt=before_datetime,
            )
            .select_related(
                'farm_stock_balance__farm',
                'farm_stock_balance__animal_category',
                'created_by',
            )
            .order_by('timestamp')
        )