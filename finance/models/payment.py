"""
finance/models/payment.py

Pagamento recebido de um cliente.

Um pagamento pode ser maior do que a dívida atual — ou existir sem dívida
nenhuma. Nesse caso o saldo do cliente fica positivo e será abatido nas
próximas compras. É por isso que não há nenhuma validação amarrando o valor
do pagamento ao saldo devedor.
"""
import uuid

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models
from simple_history.models import HistoricalRecords

from .enums import PaymentType

User = get_user_model()


class Payment(models.Model):
    """Pagamento de um cliente, que gera um crédito no extrato dele."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    client = models.ForeignKey(
        'operations.Client',
        on_delete=models.PROTECT,
        related_name='payments',
        verbose_name="Cliente",
    )

    date = models.DateField(
        verbose_name="Data do Pagamento",
        db_index=True,
    )

    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        verbose_name="Valor (R$)",
    )

    payment_type = models.CharField(
        max_length=20,
        choices=PaymentType.choices,
        default=PaymentType.DINHEIRO,
        verbose_name="Tipo de Pagamento",
    )

    description = models.TextField(
        blank=True,
        default='',
        verbose_name="Descrição",
        help_text="Opcional",
    )

    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='payments_created',
        verbose_name="Registrado Por",
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Data de Registro")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Última Atualização")

    history = HistoricalRecords(excluded_fields=['created_at', 'updated_at'])

    class Meta:
        db_table = 'payments'
        verbose_name = 'Pagamento'
        verbose_name_plural = 'Pagamentos'
        ordering = ['-date', '-created_at']
        indexes = [
            models.Index(fields=['client', '-date'], name='fin_pay_client_date_idx'),
            models.Index(fields=['-date', '-created_at'], name='fin_pay_date_created_idx'),
            models.Index(fields=['payment_type'], name='fin_pay_type_idx'),
        ]

    def __str__(self):
        return f"Pagamento {self.date:%d/%m/%Y} — {self.client.name} — R$ {self.amount}"

    def clean(self):
        super().clean()
        if self.amount is not None and self.amount <= 0:
            raise ValidationError({'amount': 'O valor do pagamento deve ser maior que zero.'})
