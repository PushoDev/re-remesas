"""Recharge catalog and promotion detection (HU-TOP-01).

The server decides which promotion is current; the browser only draws what it is given.
"""
import logging
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.utils import timezone

from apps.common.phone import normalize_cuban_mobile
from apps.exchange_rates.services import user_gets_vip_rate
from apps.memberships.models import Subscription
from apps.payments.models import Payment, PaymentPurpose
from apps.payments.providers.base import PaymentSession
from apps.payments.providers.registry import provider_for_method

from .models import Promotion, RechargeOrder, RechargePackage
from .providers.base import ProviderOutcome
from .providers.registry import get_provider

logger = logging.getLogger(__name__)

MONEY = Decimal('0.01')
HUNDRED = Decimal('100')


@dataclass(frozen=True)
class CatalogEntry:
    package: RechargePackage
    active_promotion: Promotion | None


def current_promotions(now=None) -> list[Promotion]:
    """Promotions that are switched on and whose window contains `now` (start included, end excluded)."""
    now = now or timezone.now()
    return list(Promotion.objects.filter(is_active=True, starts_at__lte=now, ends_at__gt=now))


def pick_promotion(package: RechargePackage, promotions: list[Promotion]) -> Promotion | None:
    """The promotion to show for a package: one made for that package beats one for everything;
    between equals, the one that ends first (the most urgent) wins."""
    applicable = [promo for promo in promotions if promo.package_id in (None, package.pk)]
    if not applicable:
        return None
    return min(applicable, key=lambda promo: (promo.package_id is None, promo.ends_at, promo.pk))


def get_catalog(now=None) -> list[CatalogEntry]:
    """Every purchasable package with its current promotion, if any. Two queries however many packages."""
    promotions = current_promotions(now)
    packages = RechargePackage.objects.filter(is_active=True)
    return [CatalogEntry(package, pick_promotion(package, promotions)) for package in packages]


# --- Price and order (HU-TOP-01) ------------------------------------------------------------------


class PackageNotAvailable(ValueError):
    """The package is switched off, so it cannot be bought."""


@dataclass(frozen=True)
class RechargeQuote:
    package: RechargePackage
    phone_number: str  # normalized: +53XXXXXXXX
    price_base: Decimal
    discount_percent: Decimal
    discount_amount: Decimal
    amount_total: Decimal
    currency: str
    is_vip: bool
    active_promotion: Promotion | None  # informational: it never changes the price


def vip_discount_percent(user, now=None) -> Decimal:
    """The recharge discount a user gets right now.

    Only real VIPs (active, not expired) get one, and it is the one stored in the subscription
    they bought (the plan may have changed since). When several subscriptions are running at
    once, the best one applies. A VIP granted by hand, with no subscription, gets no discount.
    """
    if not user_gets_vip_rate(user):
        return Decimal('0')
    now = now or timezone.now()
    running = Subscription.objects.filter(
        user=user, status=Subscription.Status.ACTIVE, starts_at__lte=now, expires_at__gt=now,
    ).values_list('recharge_discount_percent', flat=True)
    return max(running, default=Decimal('0'))


def quote_recharge(user, package: RechargePackage, phone_number: str, now=None) -> RechargeQuote:
    """What the customer would pay. The price is the package's, read on the server; the
    created order repeats this calculation, so a quote is informative and never trusted back.

    Raises InvalidCubanPhone (bad number) or PackageNotAvailable.
    """
    if not package.is_active:
        raise PackageNotAvailable('Este paquete no está disponible.')
    phone = normalize_cuban_mobile(phone_number)

    discount_percent = vip_discount_percent(user, now)
    discount_amount = (package.price * discount_percent / HUNDRED).quantize(
        MONEY, rounding=ROUND_HALF_UP,
    )
    amount_total = max(package.price - discount_amount, MONEY)
    return RechargeQuote(
        package=package, phone_number=phone, price_base=package.price, discount_percent=discount_percent,
        discount_amount=package.price - amount_total, amount_total=amount_total, currency=package.currency,
        is_vip=user_gets_vip_rate(user),
        active_promotion=pick_promotion(package, current_promotions(now)),
    )


def promotion_snapshot(promotion: Promotion | None) -> dict | None:
    if promotion is None:
        return None
    return {
        'code': promotion.code, 'title': promotion.title, 'description': promotion.description,
        'ends_at': promotion.ends_at.isoformat(),
    }


@transaction.atomic
def create_recharge_order(user, *, package: RechargePackage, phone_number: str,
                          payment_method: str) -> tuple[RechargeOrder, PaymentSession]:
    """Create an order and its pending payment, all or nothing.

    Nothing is sent to the provider here: the top-up is only requested once the payment is
    confirmed (see process_paid_order).
    """
    quote = quote_recharge(user, package, phone_number)

    provider = provider_for_method(payment_method)
    payment = Payment.objects.create(
        user=user, purpose=PaymentPurpose.RECHARGE, method=payment_method, provider=provider.code,
        amount=quote.amount_total, currency=quote.currency,
    )
    session = provider.create_payment(payment)
    payment.external_reference = session.external_reference
    payment.instructions = session.instructions

    order = RechargeOrder.objects.create(
        user=user, phone_number=quote.phone_number, package=package, payment=payment,
        price_base=quote.price_base, discount_percent_applied=quote.discount_percent,
        amount_total=quote.amount_total, currency=quote.currency,
        promotion_snapshot=promotion_snapshot(quote.active_promotion),
    )
    payment.target_id = order.pk
    payment.save(update_fields=['external_reference', 'instructions', 'target_id', 'updated_at'])
    return order, session


# --- After the payment (registered in apps.py) -------------------------------------------------------

OUTCOME_TO_STATUS = {
    ProviderOutcome.SUCCESS: RechargeOrder.Status.SUCCESS,
    ProviderOutcome.PROCESSING: RechargeOrder.Status.PROCESSING,
    ProviderOutcome.FAILED: RechargeOrder.Status.FAILED,
}
PROVIDER_UNREACHABLE = 'El operador no pudo completar la recarga.'


@transaction.atomic
def process_paid_order(order: RechargeOrder) -> RechargeOrder:
    """The order's payment was confirmed: ask the provider for the top-up, once.

    Only an order still waiting for its payment is sent; the row is locked, so the same order
    can never be sent twice, however many times the confirmation arrives. If the provider fails
    or cannot be reached the order is FAILED, never retried here: retrying could top up twice.
    The money was taken, so a FAILED order with a SUCCEEDED payment is refunded by hand.
    """
    locked = RechargeOrder.objects.select_for_update().select_related('package').get(pk=order.pk)
    if locked.status != RechargeOrder.Status.PENDING_PAYMENT:
        return locked

    try:
        result = get_provider().recharge(locked.phone_number, locked.package.code, locked.amount_total)
        locked.status = OUTCOME_TO_STATUS[result.status]
        locked.provider_reference = result.provider_reference
        locked.provider_message = result.message
    except Exception:
        logger.exception('Recharge provider failed for order %s', locked.reference)
        locked.status = RechargeOrder.Status.FAILED
        locked.provider_message = PROVIDER_UNREACHABLE
    locked.save(update_fields=['status', 'provider_reference', 'provider_message', 'updated_at'])
    return locked


def mark_order_paid(payment) -> None:
    """Payment handler: the payment was confirmed (gateway webhook, or an administrator)."""
    order = RechargeOrder.objects.filter(payment=payment).first()
    if order is not None:
        process_paid_order(order)


def fail_order_after_failed_payment(payment) -> None:
    """Payment handler: a payment that failed ends the order; the provider is never called."""
    order = RechargeOrder.objects.select_for_update().filter(payment=payment).first()
    if order is not None and order.status == RechargeOrder.Status.PENDING_PAYMENT:
        order.status = RechargeOrder.Status.FAILED
        order.provider_message = 'El pago no se completó.'
        order.save(update_fields=['status', 'provider_message', 'updated_at'])
