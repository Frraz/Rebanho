"""
Operations Admin - Interface administrativa.
"""
from django.contrib import admin
from .models import Client, DeathReason


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    """Admin customizado para Clientes"""
    
    list_display = ('name', 'cpf_cnpj', 'phone', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'cpf_cnpj', 'phone', 'email')
    readonly_fields = ('id', 'created_at', 'updated_at')
    
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('name', 'cpf_cnpj', 'is_active')
        }),
        ('Contato', {
            'fields': ('phone', 'email', 'address')
        }),
        ('Metadados', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(DeathReason)
class DeathReasonAdmin(admin.ModelAdmin):
    """Admin customizado para Tipos de Morte"""
    
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