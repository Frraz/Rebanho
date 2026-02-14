"""
Farms App Configuration.
"""
from django.apps import AppConfig


class FarmsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'farms'
    verbose_name = 'Fazendas'
    
    def ready(self):
        """
        Importar signals quando o app estiver pronto.
        
        IMPORTANTE: Quando uma nova fazenda é criada, automaticamente
        devem ser criados registros de saldo (FarmStockBalance) para
        todas as categorias de animais ativas.
        """
        import farms.signals  # noqa