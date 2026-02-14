"""
Farm Stock Balance Model - Saldo Consolidado (Snapshot/Cache).

AGREGADO RAIZ do sistema de inventário.

Esta tabela armazena o ESTADO ATUAL do saldo de cada combinação
fazenda + categoria. É atualizada transacionalmente junto com o ledger.

IMPORTANTE:
- Esta tabela é um CACHE OTIMIZADO para performance
- A FONTE DA VERDADE é a tabela AnimalMovement (ledger)
- O saldo pode ser recalculado a qualquer momento a partir do histórico
- NUNCA permitir current_quantity < 0 (garantido por constraint no banco)
"""
import uuid
from django.db import models
from django.core.exceptions import ValidationError
from django.db.models import F, Q


class FarmStockBalance(models.Model):
    """
    Saldo Consolidado de Estoque - Fazenda + Categoria.
    
    Representa o saldo ATUAL de animais em uma fazenda específica
    para uma categoria específica.
    
    Atributos:
        id (UUID): Identificador único universal
        farm (FK): Fazenda onde os animais estão localizados
        animal_category (FK): Categoria/tipo dos animais
        current_quantity (int): Quantidade atual em estoque (>= 0)
        version (int): Controle de concorrência otimista
        updated_at (datetime): Última atualização do saldo
        
    Invariante Fundamental:
        current_quantity >= 0 (SEMPRE)
    """
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Identificador único universal"
    )
    
    farm = models.ForeignKey(
        'farms.Farm',
        on_delete=models.PROTECT,  # ❌ NUNCA CASCADE - preserva histórico
        related_name='stock_balances',
        verbose_name="Fazenda",
        help_text="Fazenda onde os animais estão localizados"
    )
    
    animal_category = models.ForeignKey(
        'inventory.AnimalCategory',
        on_delete=models.PROTECT,  # ❌ NUNCA CASCADE - preserva histórico
        related_name='stock_balances',
        verbose_name="Categoria de Animal",
        help_text="Tipo/categoria dos animais"
    )
    
    current_quantity = models.PositiveIntegerField(
        default=0,
        verbose_name="Quantidade Atual",
        help_text="Saldo atual de animais nesta fazenda/categoria"
    )
    
    version = models.IntegerField(
        default=0,
        verbose_name="Versão",
        help_text="Controle de concorrência otimista (incrementado a cada atualização)"
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Última Atualização",
        help_text="Timestamp da última modificação no saldo"
    )
    
    class Meta:
        db_table = 'farm_stock_balances'
        verbose_name = 'Saldo de Estoque'
        verbose_name_plural = 'Saldos de Estoque'
        
        # CONSTRAINT CRÍTICO: Garante unicidade de farm + category
        constraints = [
            models.UniqueConstraint(
                fields=['farm', 'animal_category'],
                name='unique_farm_category_balance'
            ),
            # CONSTRAINT CRÍTICO: Garante saldo nunca negativo (última linha de defesa)
            models.CheckConstraint(
                check=Q(current_quantity__gte=0),
                name='stock_balance_non_negative'
            ),
        ]
        
        indexes = [
            # Índice para consultas por fazenda
            models.Index(fields=['farm', 'animal_category']),
            # Índice para consultas por categoria
            models.Index(fields=['animal_category', 'farm']),
            # Índice para ordenação por quantidade
            models.Index(fields=['current_quantity']),
        ]
        
        ordering = ['farm__name', 'animal_category__name']
    
    def __str__(self):
        return f"{self.farm.name} - {self.animal_category.name}: {self.current_quantity}"
    
    def clean(self):
        """Validações de modelo"""
        super().clean()
        
        # Validar que quantidade não é negativa
        if self.current_quantity < 0:
            raise ValidationError({
                'current_quantity': 'Saldo não pode ser negativo'
            })
    
    def save(self, *args, **kwargs):
        """
        Override para garantir validação.
        
        IMPORTANTE: Em produção, a atualização de saldo DEVE ser feita
        via MovementService, não diretamente via save().
        """
        self.full_clean()
        super().save(*args, **kwargs)
    
    @classmethod
    def get_or_create_for_farm_and_category(cls, farm, animal_category):
        """
        Obtém ou cria um registro de saldo para uma combinação farm + category.
        
        Args:
            farm: Instância de Farm
            animal_category: Instância de AnimalCategory
            
        Returns:
            tuple: (instance, created)
            
        Nota: Usado principalmente em signals quando novas categorias
        são criadas ou quando uma fazenda é criada.
        """
        return cls.objects.get_or_create(
            farm=farm,
            animal_category=animal_category,
            defaults={'current_quantity': 0}
        )
    
    @classmethod
    def initialize_balances_for_farm(cls, farm):
        """
        Inicializa saldos para todas as categorias ativas para uma fazenda.
        
        Args:
            farm: Instância de Farm
            
        Returns:
            int: Número de saldos criados
            
        Usado quando uma nova fazenda é cadastrada.
        """
        from .animal_category import AnimalCategory
        
        active_categories = AnimalCategory.objects.filter(is_active=True)
        created_count = 0
        
        for category in active_categories:
            _, created = cls.get_or_create_for_farm_and_category(farm, category)
            if created:
                created_count += 1
        
        return created_count
    
    @classmethod
    def initialize_balances_for_category(cls, animal_category):
        """
        Inicializa saldos para todas as fazendas ativas para uma categoria.
        
        Args:
            animal_category: Instância de AnimalCategory
            
        Returns:
            int: Número de saldos criados
            
        Usado quando uma nova categoria é cadastrada.
        """
        from farms.models.farm import Farm
        
        active_farms = Farm.objects.filter(is_active=True)
        created_count = 0
        
        for farm in active_farms:
            _, created = cls.get_or_create_for_farm_and_category(farm, animal_category)
            if created:
                created_count += 1
        
        return created_count