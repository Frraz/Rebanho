"""
finance/models/sale.py

Venda como agregado: um cabeçalho (cliente, fazenda, data) e N linhas de animais.

CONTEXTO HISTÓRICO:
    Antes deste módulo, uma venda era apenas um `AnimalMovement` com
    `operation_type='VENDA'` e o preço guardado como texto dentro do
    `metadata` (JSONField). Isso limitava a venda a um único tipo de animal e
    tornava impossível somar valores em SQL.

    O `Sale` passa a ser o agregado; cada `SaleItem` continua gerando o seu
    `AnimalMovement` para que o ledger de estoque e todos os relatórios
    existentes sigam funcionando sem alteração.

DESIGN:
    - `date` é DateField (e não DateTimeField) para acompanhar
      `AnimalMovement.timestamp`, que foi convertido na migração inventory/0005.
    - Os totais são desnormalizados (cache) para permitir ordenação e filtro por
      valor direto no banco. Quem os mantém é o SaleService — nunca a view.
    - `total_amount` é nullable de propósito: vendas antigas foram cadastradas
      sem preço e precisam continuar existindo até que alguém as complete.
"""
import uuid

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models
from simple_history.models import HistoricalRecords

from .enums import SaleOrigin, SaleStatus

User = get_user_model()


class Sale(models.Model):
    """Venda de animais para um cliente, com um ou mais lotes."""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Identificador único universal",
    )

    client = models.ForeignKey(
        'operations.Client',
        on_delete=models.PROTECT,
        related_name='sales',
        verbose_name="Cliente",
        help_text="Cliente que comprou os animais",
    )

    farm = models.ForeignKey(
        'farms.Farm',
        on_delete=models.PROTECT,
        related_name='sales',
        verbose_name="Fazenda",
        help_text="Fazenda de onde saíram os animais (uma por venda)",
    )

    date = models.DateField(
        verbose_name="Data da Venda",
        db_index=True,
        help_text="Data em que a venda foi realizada",
    )

    notes = models.TextField(
        blank=True,
        default='',
        verbose_name="Observação",
    )

    status = models.CharField(
        max_length=10,
        choices=SaleStatus.choices,
        default=SaleStatus.ATIVA,
        db_index=True,
        verbose_name="Situação",
    )

    # ── Totais desnormalizados (mantidos pelo SaleService) ──────────────────
    total_quantity = models.PositiveIntegerField(
        default=0,
        verbose_name="Quantidade Total",
        help_text="Soma das quantidades de todos os lotes",
    )

    total_weight = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Peso Total (kg)",
        help_text="Soma dos pesos de todos os lotes",
    )

    total_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Preço Total (R$)",
        help_text=(
            "Soma dos valores dos lotes. Vazio quando a venda foi registrada "
            "sem informar preço — o valor pode ser preenchido depois."
        ),
    )

    origin = models.CharField(
        max_length=10,
        choices=SaleOrigin.choices,
        default=SaleOrigin.APP,
        db_index=True,
        verbose_name="Origem do Registro",
        help_text=(
            "BACKFILL identifica vendas criadas pela migração de dados a partir "
            "do ledger antigo. É o que torna a migração reversível com segurança."
        ),
    )

    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='sales_created',
        verbose_name="Registrado Por",
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Data de Registro")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Última Atualização")

    history = HistoricalRecords(excluded_fields=['created_at', 'updated_at'])

    class Meta:
        db_table = 'sales'
        verbose_name = 'Venda'
        verbose_name_plural = 'Vendas'
        ordering = ['-date', '-created_at']
        # Índices nomeados explicitamente: nomes automáticos são hashes, e
        # o deploy roda `makemigrations --check` — nomes fixos garantem que a
        # migração escrita à mão corresponda exatamente ao modelo.
        indexes = [
            models.Index(fields=['client', '-date'], name='fin_sale_client_date_idx'),
            models.Index(fields=['farm', '-date'], name='fin_sale_farm_date_idx'),
            models.Index(fields=['status', '-date'], name='fin_sale_status_date_idx'),
            models.Index(fields=['-date', '-created_at'], name='fin_sale_date_created_idx'),
        ]

    def __str__(self):
        return f"Venda {self.date:%d/%m/%Y} — {self.client.name}"

    def clean(self):
        super().clean()
        if self.total_amount is not None and self.total_amount < 0:
            raise ValidationError({'total_amount': 'O valor da venda não pode ser negativo.'})

    @property
    def is_cancelled(self) -> bool:
        return self.status == SaleStatus.CANCELADA

    @property
    def has_price(self) -> bool:
        """Vendas antigas podem não ter preço — a UI as sinaliza."""
        return self.total_amount is not None and self.total_amount > 0
