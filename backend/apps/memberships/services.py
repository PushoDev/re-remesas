from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.payments.models import Payment, PaymentPurpose
from apps.payments.providers.base import PaymentSession
from apps.payments.providers.registry import provider_for_method
from apps.users.models import Profile

from .models import MembershipPlan, Subscription


@transaction.atomic
def activate_membership(payment: Payment) -> Subscription:
    """A membership payment succeeded: turn the user VIP or extend their membership.

    * Still VIP: the new period is added after the current expiration.
    * Free, or VIP that lapsed: it starts now.
    * VIP without an expiration date (granted by an administrator, no end): it
      stays that way; the purchase is recorded but never shortens it.
    The profile row is locked so two purchases processed at once cannot overwrite
    each other.
    """
    subscription = Subscription.objects.select_for_update().get(payment=payment)
    profile = Profile.objects.select_for_update().get(user=subscription.user)
    now = timezone.now()
    period = timedelta(days=subscription.duration_days)

    still_vip = profile.membership_status == Profile.VIP
    if still_vip and profile.membership_expires_at is None:
        starts_at, expires_at = now, now + period  # the profile keeps its open-ended VIP
    else:
        starts_at = profile.membership_expires_at if still_vip else now
        expires_at = starts_at + period
        profile.is_membership_active = True
        profile.membership_expires_at = expires_at
        profile.save(update_fields=['is_membership_active', 'membership_expires_at'])

    subscription.status = Subscription.Status.ACTIVE
    subscription.starts_at = starts_at
    subscription.expires_at = expires_at
    subscription.save(update_fields=['status', 'starts_at', 'expires_at'])
    return subscription


@transaction.atomic
def mark_subscription_failed(payment: Payment) -> None:
    Subscription.objects.filter(payment=payment).update(status=Subscription.Status.FAILED)


@transaction.atomic
def subscribe(user, plan: MembershipPlan, method: str) -> tuple[Subscription, PaymentSession]:
    """Start a purchase: a pending payment plus a pending subscription.

    Nothing is activated here. The price is the plan's, read on the server; the
    membership only starts when the payment is confirmed (see activate_membership).
    """
    provider = provider_for_method(method)
    payment = Payment.objects.create(
        user=user, purpose=PaymentPurpose.MEMBERSHIP, method=method, provider=provider.code,
        amount=plan.price, currency=plan.currency,
    )
    session = provider.create_payment(payment)
    payment.external_reference = session.external_reference
    payment.instructions = session.instructions
    subscription = Subscription.objects.create(
        user=user, plan=plan, payment=payment, duration_days=plan.duration_days,
        recharge_discount_percent=plan.recharge_discount_percent,
    )
    payment.target_id = subscription.pk
    payment.save(update_fields=['external_reference', 'instructions', 'target_id', 'updated_at'])
    return subscription, session
