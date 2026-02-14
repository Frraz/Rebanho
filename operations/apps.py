"""
Operations App Configuration.
"""
from django.apps import AppConfig


class OperationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'operations'
    verbose_name = 'Operações - Ocorrências e Transações'
    
    def ready(self):
        """
        Importar signals quando o app estiver pronto (se necessário).
        """
        # import operations.signals  # noqa
        pass