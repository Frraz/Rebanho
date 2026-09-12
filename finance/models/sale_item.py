"""
finance/models/sale_item.py

Um lote de animais dentro de uma venda.

A mesma categoria pode aparecer em mais de uma linha da mesma venda — é
intencional: o usuário pode querer separar dois lotes com preços por quilo
diferentes. Por isso NÃO existe unique_together em (sale, animal_category), e
por isso a validação de estoque precisa somar as quantidades por categoria
antes de comparar com o saldo (ver SaleService).
"""
import uuid

from django.core.exceptions import ValidationError
from django.db import models


class SaleItem(models.Model):
    """Linha de venda: categoria, quantidade, peso e preço."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    sale = models.ForeignKey(
        'finance.Sale',
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name="Venda",
    )

    animal_category = models.ForeignKey(
        'inventory.AnimalCategory',
        on_delete=models.PROTECT,
        related_name='sale_items',
        verbose_name="Tipo de Animal",
    )

    movement = models.OneToOneField(
        'inventory.AnimalMovement',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='sale_item',
        verbose_name="Movimentação de Estoque",
        help_text="Baixa de estoque gerada por este lote",
    )

    quantity = models.PositiveIntegerField(
        verbose_name="Quantidade",
        help_text="Número de animais neste lote",
    )

    total_weight = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Peso Total (kg)",
    )

    price_per_kg = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        null=True,
        blank=True,
        verbose_name="Preço por kg (R$)",
        help_text="Quatro casas decimais para não perder precisão no rateio",
    )

    total_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Total (R$)",
        help_text=(
            "Peso × preço por kg, mas editável: o usuário pode sobrescrever "
            "para arredondamentos ou valores combinados."
        ),
    )

    line_order = models.PositiveSmallIntegerField(
        default=0,
        verbose_name="Ordem",
        help_text="Preserva a ordem em que o usuário digitou os lotes",
    )

    class Meta:
        db_table = 'sale_items'
        verbose_name = 'Lote da Venda'
        verbose_name_plural = 'Lotes da Venda'
        ordering = ['line_order', 'id']
        indexes = [
            models.Index(fields=['sale', 'line_order'], name='fin_saleitem_sale_ord_idx'),
            models.Index(fields=['animal_category'], name='fin_saleitem_category_idx'),
        ]

    def __str__(self):
        return f"{self.quantity}× {self.animal_category.name}"

    def clean(self):
        super().clean()
        if self.quantity is not None and self.quantity <= 0:
            raise ValidationError({'quantity': 'A quantidade deve ser maior que zero.'})
        if self.total_weight is not None and self.total_weight <= 0:
            raise ValidationError({'total_weight': 'O peso deve ser maior que zero.'})
        if self.price_per_kg is not None and self.price_per_kg < 0:
            raise ValidationError({'price_per_kg': 'O preço por kg não pode ser negativo.'})
        if self.total_amount is not None and self.total_amount < 0:
            raise ValidationError({'total_amount': 'O total não pode ser negativo.'})

    @staticmethod
    def compute_total(total_weight, price_per_kg):
        """
        Total sugerido para a linha (peso × preço/kg), arredondado a 2 casas.

        Devolve None quando falta peso ou preço — o usuário pode registrar a
        venda sem valor e completar depois.
        """
        from decimal import ROUND_HALF_UP, Decimal

        if total_weight is None or price_per_kg is None:
            return None
        return (Decimal(total_weight) * Decimal(price_per_kg)).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )
