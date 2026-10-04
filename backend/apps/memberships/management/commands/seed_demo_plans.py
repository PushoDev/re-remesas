from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.memberships.models import MembershipPlan


def benefits(discount: Decimal, extra: str) -> list[str]:
    # Only the benefits the specification defines: better exchange rate on
    # remittances and a discount on recharges.
    return [
        'Mejor tipo de cambio en tus remesas (menor margen)',
        f'{discount:g} % de descuento en recargas telefónicas',
        extra,
    ]


# DEMO DATA: the prices are examples, not a real commercial offer.
DEMO_PLANS = [
    dict(
        code='vip-mensual', name='VIP Mensual', period=MembershipPlan.Period.MONTHLY, price=Decimal('9.99'),
        duration_days=30, recharge_discount_percent=Decimal('5'), sort_order=1,
        benefits=benefits(Decimal('5'), 'Se renueva cuando tú quieras: 30 días por compra'),
    ),
    dict(
        code='vip-anual', name='VIP Anual', period=MembershipPlan.Period.ANNUAL, price=Decimal('99.00'),
        duration_days=365, recharge_discount_percent=Decimal('10'), sort_order=2,
        benefits=benefits(Decimal('10'), 'Un año completo: ahorras frente a pagar 12 meses'),
    ),
]


class Command(BaseCommand):
    help = (
        'Crea (o restablece) los planes de membresía de DEMOSTRACIÓN (VIP Mensual y VIP Anual). '
        'Los precios son de ejemplo. Solo para desarrollo.'
    )

    @transaction.atomic
    def handle(self, *args, **options):
        for values in DEMO_PLANS:
            code = values['code']
            plan, created = MembershipPlan.objects.update_or_create(
                code=code, defaults={**{k: v for k, v in values.items() if k != 'code'}, 'is_active': True},
            )
            self.stdout.write(
                f'{"creado      " if created else "restablecido"}  {plan.name:<12} '
                f'{plan.price} {plan.currency} / {plan.duration_days} días · recargas -{plan.recharge_discount_percent:g} %'
            )
        self.stdout.write(self.style.WARNING('Planes de demostración: los precios son de ejemplo.'))
