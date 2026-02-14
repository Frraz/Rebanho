"""
Core App Configuration.
"""
from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'
    verbose_name = 'Core - Sistema Central'
    
    def ready(self):
        """
        Importar signals quando o app estiver pronto.
        """
        # Importar signals aqui se houver
        pass