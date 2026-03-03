"""
inventory/models/animal_movement_cancellation.py
════════════════════════════════════════════════

Model para registrar cancelamentos/estornos sem apagar movimentações.

PRINCÍPIO:
- O movimento original continua existindo.
- O cancelamento é um evento 1:1 separado e auditável.
- Não se altera nem se remove um cancelamento após criado.
"""
import uuid
from django.db import models
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from simple_history.models import HistoricalRecords

User = get_user_model()


class AnimalMovementCancellation(models.Model):
    """
    Registro de cancelamento de uma movimentação.

    Relacionamento 1:1 com AnimalMovement:
    - cada movimentação pode ter no máximo um cancelamento.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    movement = models.OneToOneField(
        'inventory.AnimalMovement',
        on_delete=models.PROTECT,   # nunca cascade — preserva auditoria
        related_name='cancellation',
        verbose_name="Movimentação cancelada",
    )

    cancelled_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='cancellations_made',
        verbose_name="Cancelado por",
    )

    cancelled_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Cancelado em",
        db_index=True,
    )

    quantity_restored = models.PositiveIntegerField(
        verbose_name="Quantidade estornada",
    )

    balance_before = models.PositiveIntegerField(
        verbose_name="Saldo antes do estorno",
    )

    balance_after = models.PositiveIntegerField(
        verbose_name="Saldo após o estorno",
    )

    notes = models.TextField(
        blank=True,
        default='',
        verbose_name="Observações",
    )

    # Histórico também do evento de cancelamento (opcional, mas útil na auditoria)
    history = HistoricalRecords(
        inherit=True,
    )

    class Meta:
        db_table = 'animal_movement_cancellations'
        verbose_name = 'Cancelamento de Movimentação'
        verbose_name_plural = 'Cancelamentos de Movimentações'
        ordering = ['-cancelled_at']
        indexes = [
            models.Index(fields=['cancelled_at']),
            models.Index(fields=['cancelled_by', 'cancelled_at']),
        ]

    def __str__(self):
        return (
            f"Cancelamento de {self.movement} "
            f"por {self.cancelled_by} em {self.cancelled_at:%d/%m/%Y %H:%M}"
        )

    def clean(self):
        super().clean()

        if not self.movement_id:
            raise ValidationError({'movement': 'Movimentação é obrigatória.'})

        if not self.cancelled_by_id:
            raise ValidationError({'cancelled_by': 'Usuário que cancelou é obrigatório.'})

        if self.quantity_restored <= 0:
            raise ValidationError({'quantity_restored': 'Quantidade estornada deve ser maior que zero.'})

        if self.balance_after < 0 or self.balance_before < 0:
            raise ValidationError('Saldos de auditoria não podem ser negativos.')

        # Regra de consistência: para cancelamentos comuns, quantity_restored
        # deve ser igual à quantidade original da movimentação.
        # (se houver exceção de negócio no futuro, tratar no service e ajustar esta validação)
        if self.movement and self.quantity_restored != self.movement.quantity:
            raise ValidationError({
                'quantity_restored': (
                    f"Quantidade estornada ({self.quantity_restored}) deve ser igual "
                    f"à quantidade da movimentação ({self.movement.quantity})."
                )
            })

    def save(self, *args, **kwargs):
        # append-only: se já existe, não permite update
        if self.pk and self.__class__.objects.filter(pk=self.pk).exists():
            raise ValidationError(
                "Cancelamentos são imutáveis e não podem ser alterados após criação."
            )

        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError(
            "Cancelamentos não podem ser removidos. "
            "Para corrigir, registre uma nova movimentação de ajuste."
        )