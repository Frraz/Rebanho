"""
finance/models/deletion_log.py

Registro permanente do que foi apagado.

POR QUE ISTO É OBRIGATÓRIO, E NÃO UM LUXO:
    A tela de auditoria (`core/views_audit.py`) consulta a tabela viva de
    movimentações. Quando uma venda é apagada, ela simplesmente desaparece de
    lá — o `django-simple-history` grava a linha de exclusão, mas nenhuma tela
    do sistema lê esse histórico.

    Este log é, portanto, o único lugar onde uma venda ou pagamento apagado
    continua visível para quem precisa auditar. Ele guarda o retrato completo
    do registro no momento da exclusão, incluindo os IDs das movimentações de
    estoque afetadas.

É append-only: não pode ser editado nem apagado.
"""
import uuid

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models

from .enums import DeletedObjectType

User = get_user_model()


class FinanceDeletionLog(models.Model):
    """Retrato de um registro financeiro apagado, preservado para auditoria."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    object_type = models.CharField(
        max_length=12,
        choices=DeletedObjectType.choices,
        verbose_name="Tipo de Registro",
    )

    object_id = models.UUIDField(
        verbose_name="ID do Registro Apagado",
        db_index=True,
    )

    client = models.ForeignKey(
        'operations.Client',
        on_delete=models.PROTECT,
        related_name='finance_deletions',
        verbose_name="Cliente",
    )

    object_date = models.DateField(
        verbose_name="Data do Registro Apagado",
        help_text="Data da venda/pagamento, não a data da exclusão",
    )

    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Valor (R$)",
    )

    snapshot = models.JSONField(
        default=dict,
        verbose_name="Retrato Completo",
        help_text=(
            "Estado integral do registro no momento da exclusão: cabeçalho, "
            "lotes, lançamentos financeiros e IDs das movimentações de estoque."
        ),
    )

    reason = models.TextField(
        blank=True,
        default='',
        verbose_name="Motivo",
    )

    deleted_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='finance_deletions',
        verbose_name="Apagado Por",
    )

    deleted_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name="Apagado em",
    )

    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name="Endereço IP",
    )

    class Meta:
        db_table = 'finance_deletion_logs'
        verbose_name = 'Exclusão Financeira'
        verbose_name_plural = 'Exclusões Financeiras'
        ordering = ['-deleted_at']
        indexes = [
            models.Index(fields=['-deleted_at'], name='fin_del_deleted_at_idx'),
            models.Index(fields=['object_type', '-deleted_at'], name='fin_del_type_date_idx'),
            models.Index(fields=['client', '-deleted_at'], name='fin_del_client_date_idx'),
        ]

    def __str__(self):
        return (
            f"{self.get_object_type_display()} de {self.client.name} "
            f"({self.object_date:%d/%m/%Y}) apagada em {self.deleted_at:%d/%m/%Y}"
        )

    def save(self, *args, **kwargs):
        if self.pk and FinanceDeletionLog.objects.filter(pk=self.pk).exists():
            raise ValidationError("O log de exclusões não pode ser alterado.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("O log de exclusões não pode ser apagado.")
