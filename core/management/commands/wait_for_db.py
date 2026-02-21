# core/management/commands/wait_for_db.py
"""
Management command para aguardar o PostgreSQL estar pronto antes de continuar.
Necessário porque o Docker não garante que o banco está aceitando conexões
logo após o container 'db' iniciar — mesmo com healthcheck no Compose.

Uso no docker-compose.yml:
    command: sh -c "python manage.py wait_for_db && gunicorn ..."
"""

import time
import logging

from django.core.management.base import BaseCommand
from django.db import connections
from django.db.utils import OperationalError

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Aguarda o banco de dados ficar disponível antes de prosseguir."

    def add_arguments(self, parser):
        parser.add_argument(
            "--timeout",
            type=int,
            default=60,
            help="Tempo máximo de espera em segundos (padrão: 60)",
        )
        parser.add_argument(
            "--interval",
            type=float,
            default=2.0,
            help="Intervalo entre tentativas em segundos (padrão: 2)",
        )

    def handle(self, *args, **options):
        timeout = options["timeout"]
        interval = options["interval"]
        db_conn = connections["default"]

        self.stdout.write("Aguardando banco de dados...")

        elapsed = 0
        while elapsed < timeout:
            try:
                db_conn.ensure_connection()
                self.stdout.write(
                    self.style.SUCCESS(f"✓ Banco disponível após {elapsed:.1f}s")
                )
                return
            except OperationalError:
                self.stdout.write(
                    f"  Banco indisponível — tentando novamente em {interval}s... "
                    f"({elapsed:.0f}/{timeout}s)"
                )
                time.sleep(interval)
                elapsed += interval
            finally:
                db_conn.close()

        self.stderr.write(
            self.style.ERROR(
                f"✗ Banco não ficou disponível após {timeout}s. Abortando."
            )
        )
        raise SystemExit(1)