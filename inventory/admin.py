"""
Inventory Admin - Interface administrativa do inventário.
"""
from django.contrib import admin
from django.utils.html import format_html
from .models import AnimalCategory, FarmStockBalance, AnimalMovement


@admin.register(AnimalCategory)
class AnimalCategoryAdmin(admin.ModelAdmin):
    """Admin customizado para Categorias de Animais"""
    
    list_display = ('name', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'description')
    readonly_fields = ('id', 'created_at')
    
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('name', 'description', 'is_active')
        }),
        ('Metadados', {
            'fields': ('id', 'created_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(FarmStockBalance)
class FarmStockBalanceAdmin(admin.ModelAdmin):
    """Admin customizado para Saldos de Estoque"""
    
    list_display = ('farm', 'animal_category', 'current_quantity', 'version', 'updated_at')
    list_filter = ('farm', 'animal_category', 'updated_at')
    search_fields = ('farm__name', 'animal_category__name')
    readonly_fields = ('id', 'version', 'updated_at')
    
    # ⚠️ IMPORTANTE: Não permitir edição direta de saldo via admin
    # Saldos devem ser alterados APENAS via MovementService
    def has_add_permission(self, request):
        return False  # Criação automática via signals
    
    def has_change_permission(self, request, obj=None):
        return False  # Apenas visualização
    
    def has_delete_permission(self, request, obj=None):
        return False  # Proteção contra deleção
    
    fieldsets = (
        ('Fazenda e Categoria', {
            'fields': ('farm', 'animal_category')
        }),
        ('Saldo', {
            'fields': ('current_quantity', 'version')
        }),
        ('Metadados', {
            'fields': ('id', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(AnimalMovement)
class AnimalMovementAdmin(admin.ModelAdmin):
    """Admin customizado para Movimentações (Ledger)"""
    
    list_display = (
        'timestamp',
        'get_farm',
        'get_category',
        'movement_type',
        'operation_type',
        'quantity',
        'created_by'
    )
    list_filter = (
        'movement_type',
        'operation_type',
        'timestamp',
        'created_at',
        'farm_stock_balance__farm',
        'farm_stock_balance__animal_category'
    )
    search_fields = (
        'farm_stock_balance__farm__name',
        'farm_stock_balance__animal_category__name',
        'created_by__username'
    )
    readonly_fields = (
        'id',
        'farm_stock_balance',
        'movement_type',
        'operation_type',
        'quantity',
        'timestamp',
        'related_movement',
        'client',
        'death_reason',
        'metadata',
        'created_by',
        'created_at',
        'ip_address'
    )
    
    # ⚠️ CRÍTICO: Ledger é IMUTÁVEL - apenas visualização no admin
    def has_add_permission(self, request):
        return False  # Criação apenas via MovementService
    
    def has_change_permission(self, request, obj=None):
        return False  # Ledger é imutável
    
    def has_delete_permission(self, request, obj=None):
        return False  # Ledger nunca pode ser deletado
    
    def get_farm(self, obj):
        """Exibir nome da fazenda"""
        return obj.farm_stock_balance.farm.name
    get_farm.short_description = 'Fazenda'
    
    def get_category(self, obj):
        """Exibir nome da categoria"""
        return obj.farm_stock_balance.animal_category.name
    get_category.short_description = 'Categoria'
    
    fieldsets = (
        ('Saldo Afetado', {
            'fields': ('farm_stock_balance',)
        }),
        ('Movimentação', {
            'fields': ('movement_type', 'operation_type', 'quantity', 'timestamp')
        }),
        ('Relacionamentos', {
            'fields': ('related_movement', 'client', 'death_reason'),
            'classes': ('collapse',)
        }),
        ('Metadados e Auditoria', {
            'fields': ('metadata', 'created_by', 'created_at', 'ip_address'),
            'classes': ('collapse',)
        }),
        ('ID', {
            'fields': ('id',),
            'classes': ('collapse',)
        }),
    )