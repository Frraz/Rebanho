"""
finance/admin.py

Registro no Django Admin — para consulta e diagnóstico, não para operação
do dia a dia.

Tudo é somente leitura de propósito. Criar ou alterar uma venda por aqui
passaria por cima do SaleService e deixaria estoque e extrato dessincronizados;
o admin não tem como reproduzir essas regras. Para operar, use as telas do
sistema.
"""
from django.contrib import admin

from finance.models import (
    FinanceDeletionLog,
    FinancialEntry,
    Payment,
    Sale,
    SaleItem,
)


class SomenteLeituraMixin:
    """Bloqueia escrita pelo admin — ver a docstring do módulo."""

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class SaleItemInline(SomenteLeituraMixin, admin.TabularInline):
    model = SaleItem
    extra = 0
    fields = (
        'animal_category', 'quantity', 'total_weight',
        'price_per_kg', 'total_amount', 'movement',
    )
    readonly_fields = fields


@admin.register(Sale)
class SaleAdmin(SomenteLeituraMixin, admin.ModelAdmin):
    list_display = (
        'date', 'client', 'farm', 'total_quantity',
        'total_amount', 'status', 'origin',
    )
    list_filter = ('status', 'origin', 'farm', 'date')
    search_fields = ('client__name', 'farm__name', 'notes')
    date_hierarchy = 'date'
    ordering = ('-date', '-created_at')
    inlines = [SaleItemInline]
    readonly_fields = [f.name for f in Sale._meta.fields]


@admin.register(Payment)
class PaymentAdmin(SomenteLeituraMixin, admin.ModelAdmin):
    list_display = ('date', 'client', 'amount', 'payment_type', 'created_by')
    list_filter = ('payment_type', 'date')
    search_fields = ('client__name', 'description')
    date_hierarchy = 'date'
    ordering = ('-date', '-created_at')
    readonly_fields = [f.name for f in Payment._meta.fields]


@admin.register(FinancialEntry)
class FinancialEntryAdmin(SomenteLeituraMixin, admin.ModelAdmin):
    list_display = ('date', 'client', 'entry_type', 'amount', 'source_type', 'description')
    list_filter = ('entry_type', 'source_type', 'date')
    search_fields = ('client__name', 'description')
    date_hierarchy = 'date'
    ordering = ('-date', '-created_at')
    readonly_fields = [f.name for f in FinancialEntry._meta.fields]


@admin.register(FinanceDeletionLog)
class FinanceDeletionLogAdmin(SomenteLeituraMixin, admin.ModelAdmin):
    list_display = (
        'deleted_at', 'object_type', 'client', 'object_date', 'amount', 'deleted_by',
    )
    list_filter = ('object_type', 'deleted_at')
    search_fields = ('client__name', 'reason', 'deleted_by__username')
    date_hierarchy = 'deleted_at'
    ordering = ('-deleted_at',)
    readonly_fields = [f.name for f in FinanceDeletionLog._meta.fields]
