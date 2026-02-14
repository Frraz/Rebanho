"""
Farms Admin - Interface administrativa de fazendas.
"""
from django.contrib import admin
from .models import Farm


@admin.register(Farm)
class FarmAdmin(admin.ModelAdmin):
    """Admin customizado para Fazendas"""
    
    list_display = ('name', 'is_active', 'created_at', 'updated_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name',)
    readonly_fields = ('id', 'created_at', 'updated_at')
    
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('name', 'is_active')
        }),
        ('Metadados', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        """Otimizar queryset com prefetch se necessário"""
        qs = super().get_queryset(request)
        return qs