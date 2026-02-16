from django.core.management.base import BaseCommand
import subprocess

class Command(BaseCommand):
    help = 'Popula o banco com dados realistas'

    def handle(self, *args, **options):
        subprocess.run(['python', 'seed_data.py'])
