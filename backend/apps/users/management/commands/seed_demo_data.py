from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Carga todos los datos de demostración (usuarios y tasas). Solo para desarrollo.'

    def handle(self, *args, **options):
        # Users first: the rates are attributed to the demo admin.
        call_command('seed_demo_users', stdout=self.stdout)
        call_command('seed_demo_rates', stdout=self.stdout)
