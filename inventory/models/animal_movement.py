"""
Animal Movement Model - Ledger (Fonte da Verdade).

Esta tabela é o CORAÇÃO do sistema de inventário.

PRINCÍPIOS FUNDAMENTAIS:
1. IMUTÁVEL: Registros NUNCA são alterados ou deletados após criação
2. FONTE DA VERDADE: Todo saldo pode ser recalculado a partir desta tabela
3. AUDITÁVEL: Preserva histórico completo de todas as operações
4. APPEND-ONLY: Apenas inserções são permitidas

Esta tabela implementa o padrão Event Sourcing parcial (ledger pattern).
"""
import uuid
from django.db import models
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.utils import timezone

from ..domain.value_objects import MovementType, OperationType

User = get_user_model()


class AnimalMovement(models.Model):
    """
    Movimentação de Animais - Registro no Ledger.
    
    Cada registro representa uma operação que alterou o saldo de estoque
    (entrada ou saída de animais).
    
    Atributos:
        id (UUID): Identificador único universal
        farm_stock_balance (FK): Saldo afetado por esta movimentação
        movement_type (Choice): ENTRADA ou SAÍDA
        operation_type (Choice): Tipo específico (NASCIMENTO, VENDA, etc.)
        quantity (int): Quantidade movimentada (sempre positiva)
        timestamp (datetime): Momento exato da operação
        
        # Relacionamentos opcionais (dependendo da operação)
        related_movement (FK): Movimento relacionado (MANEJO, MUDANÇA_CATEGORIA)
        client (FK): Cliente envolvido (VENDA, DOACAO)
        death_reason (FK): Motivo da morte (MORTE)
        
        # Metadados e auditoria
        metadata (JSON): Dados específicos da operação (peso, preço, obs)
        created_by (FK): Usuário que registrou a operação
        created_at (datetime): Data de criação do registro
        ip_address (IP): IP de origem da operação
    """
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Identificador único universal"
    )
    
    # === RELACIONAMENTO COM SALDO ===
    farm_stock_balance = models.ForeignKey(
        'inventory.FarmStockBalance',
        on_delete=models.PROTECT,  # ❌ NUNCA CASCADE - preserva histórico
        related_name='movements',
        verbose_name="Saldo de Estoque",
        help_text="Registro de saldo afetado por esta movimentação"
    )
    
    # === TIPO DE MOVIMENTAÇÃO ===
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
    
    # === QUANTIDADE ===
    quantity = models.PositiveIntegerField(
        verbose_name="Quantidade",
        help_text="Quantidade de animais movimentados (sempre positiva)"
    )
    
    # === TIMESTAMP DA OPERAÇÃO ===
    timestamp = models.DateTimeField(
        default=timezone.now,
        verbose_name="Data/Hora da Operação",
        help_text="Momento em que a operação foi realizada",
        db_index=True
    )
    
    # === RELACIONAMENTOS OPCIONAIS ===
    
    # Movimento relacionado (para MANEJO e MUDANÇA DE CATEGORIA)
    related_movement = models.ForeignKey(
        'self',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='reverse_related_movement',
        verbose_name="Movimento Relacionado",
        help_text="Movimento vinculado (saída/entrada em operações compostas)"
    )
    
    # Cliente (para VENDA e DOACAO)
    client = models.ForeignKey(
        'operations.Client',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='movements',
        verbose_name="Cliente",
        help_text="Cliente envolvido na operação (vendas/doações)"
    )
    
    # Motivo de morte (para MORTE)
    death_reason = models.ForeignKey(
        'operations.DeathReason',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='movements',
        verbose_name="Motivo da Morte",
        help_text="Causa da morte do animal"
    )
    
    # === METADADOS E AUDITORIA ===
    
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
    
    class Meta:
        db_table = 'animal_movements'
        verbose_name = 'Movimentação de Animal'
        verbose_name_plural = 'Movimentações de Animais'
        
        # IMPORTANTE: Ordenação padrão por timestamp para auditoria
        ordering = ['-timestamp', '-created_at']
        
        indexes = [
            # Índice composto para consultas por saldo + período
            models.Index(fields=['farm_stock_balance', 'timestamp']),
            models.Index(fields=['farm_stock_balance', 'created_at']),
            
            # Índice para filtragem por tipo de operação
            models.Index(fields=['operation_type', 'timestamp']),
            
            # Índice para consultas por período
            models.Index(fields=['timestamp']),
            models.Index(fields=['created_at']),
            
            # Índice para auditoria por usuário
            models.Index(fields=['created_by', 'created_at']),
            
            # Índice para relatórios por cliente
            models.Index(fields=['client', 'timestamp']),
        ]
        
        # Permissões customizadas
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
        """Validações de modelo"""
        super().clean()
        
        # Validar quantidade positiva
        if self.quantity <= 0:
            raise ValidationError({
                'quantity': 'Quantidade deve ser maior que zero'
            })
        
        # Validar consistência entre movement_type e operation_type
        operation_enum = OperationType(self.operation_type)
        expected_movement_type = operation_enum.get_movement_type()
        
        if self.movement_type != expected_movement_type.value:
            raise ValidationError({
                'movement_type': (
                    f"Tipo de movimento inconsistente. "
                    f"Operação '{self.operation_type}' requer movimento '{expected_movement_type.value}'"
                )
            })
        
        # Validar relacionamentos obrigatórios
        operation_enum = OperationType(self.operation_type)
        
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
        Override para garantir validação.
        
        IMPORTANTE: Em produção, movimentos DEVEM ser criados via
        MovementService, não diretamente via save().
        """
        
        # ⚠️ PROTEÇÃO CRÍTICA: Impedir alterações em registros existentes
        if self.pk is not None:
            raise ValidationError(
                "Movimentações são IMUTÁVEIS e não podem ser alteradas após criação. "
                "Esta é uma proteção de integridade do ledger."
            )
        
        self.full_clean()
        super().save(*args, **kwargs)
    
    def delete(self, *args, **kwargs):
        """
        Override para IMPEDIR deleções.
        
        Ledger é APPEND-ONLY: registros nunca são deletados.
        """
        raise ValidationError(
            "Movimentações são IMUTÁVEIS e não podem ser deletadas. "
            "Esta é uma proteção de integridade do ledger. "
            "Para corrigir erros, crie uma movimentação de ajuste."
        )
    
    # === MÉTODOS AUXILIARES ===
    
    def get_farm(self):
        """Retorna a fazenda associada a esta movimentação"""
        return self.farm_stock_balance.farm
    
    def get_category(self):
        """Retorna a categoria associada a esta movimentação"""
        return self.farm_stock_balance.animal_category
    
    def is_entrada(self):
        """Verifica se é uma movimentação de entrada"""
        return self.movement_type == MovementType.ENTRADA.value
    
    def is_saida(self):
        """Verifica se é uma movimentação de saída"""
        return self.movement_type == MovementType.SAIDA.value