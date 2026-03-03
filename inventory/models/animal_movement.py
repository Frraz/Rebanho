"""
Animal Movement Model - Ledger (Fonte da Verdade).

ATENÇÃO:
- O ledger é append-only para operações de negócio (não usar ORM direto para editar).
- Edições controladas via service podem ocorrer para correções operacionais e devem
  ser auditadas por trilha de histórico.
"""
import uuid
from django.db import models
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.utils import timezone
from simple_history.models import HistoricalRecords

from ..domain.value_objects import MovementType, OperationType

User = get_user_model()


class AnimalMovement(models.Model):
    """
    Movimentação de Animais - Registro no Ledger.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Identificador único universal"
    )

    farm_stock_balance = models.ForeignKey(
        'inventory.FarmStockBalance',
        on_delete=models.PROTECT,
        related_name='movements',
        verbose_name="Saldo de Estoque",
        help_text="Registro de saldo afetado por esta movimentação"
    )

    movement_type = models.CharField(
        max_length=20,
        choices=MovementType.choices(),
        verbose_name="Tipo de Movimento",
        help_text="ENTRADA (aumenta saldo) ou SAÍDA (diminui saldo)"
    )

    operation_type = models.CharField(
        max_length=30,
        choices=OperationType.choices(),
        verbose_name="Tipo de Operação",
        help_text="Operação específica que gerou esta movimentação"
    )

    quantity = models.PositiveIntegerField(
        verbose_name="Quantidade",
        help_text="Quantidade de animais movimentados (sempre positiva)"
    )

    timestamp = models.DateTimeField(
        default=timezone.now,
        verbose_name="Data/Hora da Operação",
        help_text="Momento em que a operação foi realizada",
        db_index=True
    )

    related_movement = models.ForeignKey(
        'self',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='reverse_related_movement',
        verbose_name="Movimento Relacionado",
        help_text="Movimento vinculado (saída/entrada em operações compostas)"
    )

    client = models.ForeignKey(
        'operations.Client',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='movements',
        verbose_name="Cliente",
        help_text="Cliente envolvido na operação (vendas/doações)"
    )

    death_reason = models.ForeignKey(
        'operations.DeathReason',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='movements',
        verbose_name="Motivo da Morte",
        help_text="Causa da morte do animal"
    )

    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Metadados",
        help_text=(
            "Dados adicionais da operação em formato JSON. "
            "Exemplos: peso, preço, observações, lote, etc."
        )
    )

    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='animal_movements',
        verbose_name="Registrado Por",
        help_text="Usuário que registrou esta operação"
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Data de Registro",
        help_text="Timestamp de criação do registro no sistema",
        db_index=True
    )

    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name="Endereço IP",
        help_text="IP de origem da requisição"
    )

    # 🔍 Trilho de auditoria de mudanças (inclui edições via service)
    history = HistoricalRecords(
        inherit=True,
        excluded_fields=['created_at'],
    )

    class Meta:
        db_table = 'animal_movements'
        verbose_name = 'Movimentação de Animal'
        verbose_name_plural = 'Movimentações de Animais'
        ordering = ['-timestamp', '-created_at']
        indexes = [
            models.Index(fields=['farm_stock_balance', 'timestamp']),
            models.Index(fields=['farm_stock_balance', 'created_at']),
            models.Index(fields=['operation_type', 'timestamp']),
            models.Index(fields=['timestamp']),
            models.Index(fields=['created_at']),
            models.Index(fields=['created_by', 'created_at']),
            models.Index(fields=['client', 'timestamp']),
        ]
        permissions = [
            ("view_movement_audit", "Pode visualizar auditoria de movimentações"),
            ("recalculate_stock", "Pode recalcular saldos a partir do histórico"),
        ]

    def __str__(self):
        return (
            f"{self.get_operation_type_display()} - "
            f"{self.farm_stock_balance.farm.name} - "
            f"{self.farm_stock_balance.animal_category.name} - "
            f"{self.quantity} ({self.timestamp.strftime('%d/%m/%Y')})"
        )

    def clean(self):
        super().clean()

        if self.quantity <= 0:
            raise ValidationError({'quantity': 'Quantidade deve ser maior que zero'})

        operation_enum = OperationType(self.operation_type)
        expected_movement_type = operation_enum.get_movement_type()

        if self.movement_type != expected_movement_type.value:
            raise ValidationError({
                'movement_type': (
                    f"Tipo de movimento inconsistente. "
                    f"Operação '{self.operation_type}' requer movimento '{expected_movement_type.value}'"
                )
            })

        if operation_enum.requires_client() and not self.client:
            raise ValidationError({
                'client': f"Operação '{self.operation_type}' requer cliente informado"
            })

        if operation_enum.requires_death_reason() and not self.death_reason:
            raise ValidationError({
                'death_reason': f"Operação '{self.operation_type}' requer motivo de morte"
            })

    def save(self, *args, **kwargs):
        """
        Mantém validação forte.

        OBS:
        - Não bloqueamos UPDATE no model para permitir fluxos controlados de edição
          via service com auditoria histórica.
        - Integridade de negócio deve ser protegida no MovementService.
        """
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError(
            "Movimentações não podem ser deletadas. "
            "Para corrigir erros, use cancelamento/estorno."
        )

    def get_farm(self):
        return self.farm_stock_balance.farm

    def get_category(self):
        return self.farm_stock_balance.animal_category

    def is_entrada(self):
        return self.movement_type == MovementType.ENTRADA.value

    def is_saida(self):
        return self.movement_type == MovementType.SAIDA.value