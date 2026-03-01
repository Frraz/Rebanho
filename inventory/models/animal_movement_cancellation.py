"""
inventory/models/animal_movement_cancellation.py
════════════════════════════════════════════════

Model para registrar cancelamentos de ocorrências SEM tocar no ledger imutável.

PRINCÍPIO: AnimalMovement nunca é alterado (imutável por design).
O cancelamento é um EVENTO SEPARADO que:
1. Registra que aquela ocorrência foi estornada
2. Guarda quem cancelou e quando
3. O service usa este model para saber se a operação já foi revertida

Este model é APPEND-ONLY também: não se cancela um cancelamento.
Para corrigir um cancelamento errado, cria-se uma nova movimentação de entrada.
"""
import uuid
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class AnimalMovementCancellation(models.Model):
    """
    Registro de cancelamento de uma ocorrência.

    Relacionamento 1:1 com AnimalMovement — cada ocorrência
    pode ter no máximo um cancelamento.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    # 1:1 garante que uma ocorrência só pode ser cancelada uma vez
    movement = models.OneToOneField(
        'inventory.AnimalMovement',
        on_delete=models.PROTECT,   # nunca cascade — preserva auditoria
        related_name='cancellation',
        verbose_name="Ocorrência cancelada",
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

    # Quantidade que foi devolvida ao estoque (= movement.quantity)
    quantity_restored = models.PositiveIntegerField(
        verbose_name="Quantidade estornada",
    )

    # Saldo antes e depois para auditoria
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

    class Meta:
        db_table = 'animal_movement_cancellations'
        verbose_name = 'Cancelamento de Ocorrência'
        verbose_name_plural = 'Cancelamentos de Ocorrências'
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


# ─────────────────────────────────────────────────────────────────────────────
# Adicione ao inventory/models/__init__.py:
#
#   from .animal_movement_cancellation import AnimalMovementCancellation
#
# Depois rode:
#   python manage.py makemigrations inventory
#   python manage.py migrate
# ─────────────────────────────────────────────────────────────────────────────