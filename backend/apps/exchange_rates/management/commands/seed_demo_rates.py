from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.exchange_rates.models import ExchangeRate
from apps.exchange_rates.services import save_exchange_rate
from apps.users.models import User

# DEMO DATA, NOT REAL MARKET RATES. USD 700 is the example given in the spec;
# the EUR value is only illustrative.
DEMO_RATES = [
    {'currency': 'USD', 'base_rate': Decimal('700'), 'standard_spread_percent': Decimal('5'),
     'vip_spread_percent': Decimal('2')},
    {'currency': 'EUR', 'base_rate': Decimal('760'), 'standard_spread_percent': Decimal('5'),
     'vip_spread_percent': Decimal('2')},
]
VALUE_FIELDS = ('base_rate', 'standard_spread_percent', 'vip_spread_percent')


class Command(BaseCommand):
    help = (
        'Crea (o restablece) tasas de cambio de DEMOSTRACIÓN para USD y EUR. '
        'No son tasas reales de mercado. Solo para desarrollo.'
    )

    @transaction.atomic
    def handle(self, *args, **options):
        author = User.objects.filter(email='admin@rere.test').first()  # may not exist; that's fine

        for values in DEMO_RATES:
            rate = ExchangeRate.objects.filter(currency=values['currency'], is_active=True).first()
            if rate is None:
                save_exchange_rate(ExchangeRate(**values), author)
                action = 'creada      '
            elif any(getattr(rate, name) != values[name] for name in VALUE_FIELDS):
                for name in VALUE_FIELDS:
                    setattr(rate, name, values[name])
                save_exchange_rate(rate, author)
                action = 'restablecida'
            else:
                action = 'sin cambios '

            self.stdout.write(
                f'{action}  {values["currency"]}→CUP  base {values["base_rate"]}  '
                f'margen {values["standard_spread_percent"]} % / VIP {values["vip_spread_percent"]} %'
            )
        self.stdout.write(self.style.WARNING('Tasas de demostración: no son tasas reales de mercado.'))
