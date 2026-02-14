"""
Inventory App Configuration.
"""
from django.apps import AppConfig


class InventoryConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'inventory'
    verbose_name = 'Inventário - Controle de Estoque'
    
    def ready(self):
        """
        Importar signals quando o app estiver pronto.
        
        IMPORTANTE: Quando uma nova categoria é criada, automaticamente
        devem ser criados registros de saldo (FarmStockBalance) para
        todas as fazendas ativas.
        """
        import inventory.signals  # noqa