from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.memberships.models import MembershipPlan, Subscription
from apps.payments.models import Payment, PaymentMethod, PaymentPurpose, PaymentStatus
from apps.users.models import User

DEMO_VIP_EMAIL = 'vip@rere.test'


def ensure_demo_vip_subscription(plan: MembershipPlan) -> bool:
    """Give the demo VIP the purchase a real VIP would have, so the plan's benefits (recharge discount)
    apply to them. Without it they would be VIP only on the profile and get no discount. Returns True if created."""
    user = User.objects.filter(email=DEMO_VIP_EMAIL).first()
    now = timezone.now()
    if user is None or user.profile.membership_status != 'VIP':
        return False
    if Subscription.objects.filter(user=user, status=Subscription.Status.ACTIVE, expires_at__gt=now).exists():
        return False
    payment = Payment.objects.create(
        user=user, purpose=PaymentPurpose.MEMBERSHIP, method=PaymentMethod.CASH, provider='MANUAL',
        amount=plan.price, currency=plan.currency, status=PaymentStatus.SUCCEEDED, confirmed_at=now,
    )
    Subscription.objects.create(
        user=user, plan=plan, payment=payment, status=Subscription.Status.ACTIVE, duration_days=plan.duration_days,
        recharge_discount_percent=plan.recharge_discount_percent, starts_at=now,
        expires_at=user.profile.membership_expires_at or now + timedelta(days=plan.duration_days),
    )
    return True


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
        monthly = MembershipPlan.objects.get(code='vip-mensual')
        if ensure_demo_vip_subscription(monthly):
            self.stdout.write(f'creada       suscripción de {DEMO_VIP_EMAIL} al plan {monthly.name} (descuento en recargas)')
        self.stdout.write(self.style.WARNING('Planes de demostración: los precios son de ejemplo.'))
