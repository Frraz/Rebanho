"""
Reporting App Configuration.
"""
from django.apps import AppConfig


class ReportingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'reporting'
    verbose_name = 'Relatórios e Análises'
    
    def ready(self):
        """
        Importar tasks do Celery quando o app estiver pronto.
        """
        # import reporting.tasks  # noqa
        pass