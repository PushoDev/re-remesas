from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.recharges.models import Promotion, RechargePackage

Kind = RechargePackage.Kind

# DEMO DATA: names, contents and prices are examples, not ETECSA's real offer.
DEMO_PACKAGES = [
    dict(code='saldo-5', name='Recarga de saldo 5 USD', kind=Kind.BALANCE, price=Decimal('5.00'),
         description='Saldo directo para llamadas y mensajes.', sort_order=1),
    dict(code='saldo-10', name='Recarga de saldo 10 USD', kind=Kind.BALANCE, price=Decimal('10.00'),
         description='Saldo directo para llamadas y mensajes.', sort_order=2),
    dict(code='saldo-20', name='Recarga de saldo 20 USD', kind=Kind.BALANCE, price=Decimal('20.00'),
         description='Saldo directo para llamadas y mensajes.', sort_order=3),
    dict(code='datos-3gb', name='Paquete de datos 3 GB', kind=Kind.DATA, price=Decimal('8.00'),
         description='3 GB de datos móviles.', sort_order=4),
    dict(code='voz-60', name='Paquete de voz 60 minutos', kind=Kind.VOICE, price=Decimal('6.00'),
         description='60 minutos para llamadas.', sort_order=5),
    dict(code='combo-datos-voz', name='Combo datos y voz', kind=Kind.COMBO, price=Decimal('15.00'),
         description='5 GB de datos y 100 minutos de voz.', sort_order=6),
]

# One promotion that is current (to show the automatic detection) and one that already ended
# (to show it is not drawn). Windows are measured from the moment the command runs.
DEMO_PROMOTIONS = [
    dict(code='bono-saldo-demo', title='Bonificación: +50 % de saldo', package_code='saldo-10',
         description='Recibe saldo extra en la recarga de 10 USD.', starts_days=-1, ends_days=30),
    dict(code='bono-vencido-demo', title='Promoción terminada', package_code=None,
         description='Esta promoción ya no está vigente.', starts_days=-20, ends_days=-1),
]


class Command(BaseCommand):
    help = (
        'Crea (o restablece) los paquetes de recarga y las promociones de DEMOSTRACIÓN. '
        'Nombres y precios son de ejemplo, no la oferta real de ETECSA. Solo para desarrollo.'
    )

    @transaction.atomic
    def handle(self, *args, **options):
        for values in DEMO_PACKAGES:
            package, created = RechargePackage.objects.update_or_create(
                code=values['code'],
                defaults={**{k: v for k, v in values.items() if k != 'code'}, 'is_active': True, 'is_demo': True},
            )
            self.stdout.write(
                f'{"creado      " if created else "restablecido"}  {package.name:<28} {package.price} {package.currency}'
            )

        now = timezone.now()
        for values in DEMO_PROMOTIONS:
            package = RechargePackage.objects.get(code=values['package_code']) if values['package_code'] else None
            promotion, created = Promotion.objects.update_or_create(
                code=values['code'],
                defaults={
                    'title': values['title'], 'description': values['description'], 'package': package,
                    'starts_at': now + timedelta(days=values['starts_days']),
                    'ends_at': now + timedelta(days=values['ends_days']), 'is_active': True,
                },
            )
            state = 'vigente' if promotion.starts_at <= now < promotion.ends_at else 'terminada'
            self.stdout.write(f'{"creada      " if created else "restablecida"}  {promotion.title:<32} {state}')
        self.stdout.write(self.style.WARNING('Paquetes y promociones de demostración: nombres y precios de ejemplo.'))
