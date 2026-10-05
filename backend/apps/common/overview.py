"""Numbers for the administrator's dashboard (HU-REM-02 overview)."""
from django.apps import apps
from django.db.models import Count, Q
from django.utils import timezone

from apps.remittances.models import Remittance
from apps.users.models import Profile


def remittance_counts() -> dict[str, int]:
    status = Remittance.Status
    counts = Remittance.objects.aggregate(
        total=Count('id'),
        pending_payment=Count('id', filter=Q(status=status.PENDING_PAYMENT)),
        paid=Count('id', filter=Q(status=status.PAID)),
        completed=Count('id', filter=Q(status=status.COMPLETED)),
        cancelled=Count('id', filter=Q(status=status.CANCELLED)),
        # Manual payments (Zelle, Wise, cash) where the customer already sent a reference or file:
        # these are the ones waiting for an administrator to check them.
        needs_review=Count(
            'id',
            filter=Q(status=status.PENDING_PAYMENT, payment__provider='MANUAL')
            & (Q(payment_reference__gt='') | (Q(payment_proof__isnull=False) & ~Q(payment_proof=''))),
        ),
    )
    return counts


def recharge_order_count() -> int:
    """Recharge orders arrive with HU-TOP-01; until that app has its model this is simply 0."""
    try:
        model = apps.get_model('recharges', 'RechargeOrder')
    except LookupError:
        return 0
    return model.objects.count()


def active_vip_count() -> int:
    """Members whose VIP is on and has not expired (an open-ended VIP counts)."""
    return Profile.objects.filter(is_membership_active=True).filter(
        Q(membership_expires_at__isnull=True) | Q(membership_expires_at__gt=timezone.now()),
    ).count()


def build_overview() -> dict:
    return {
        'remittances': remittance_counts(),
        'recharge_orders': {'total': recharge_order_count()},
        'memberships': {'active_vip': active_vip_count()},
        'generated_at': timezone.now(),
    }
