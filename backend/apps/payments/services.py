"""Settling payments, independent of what they pay for.

A payment is settled exactly once: the first confirmation (webhook, or an
administrator for manual methods) moves it from PENDING to SUCCEEDED/FAILED and
runs the handler registered for its purpose. Any later confirmation of the same
payment is ignored, so a repeated webhook can never apply the effect twice.
"""
from dataclasses import dataclass
from typing import Callable, Mapping

from django.db import transaction
from django.utils import timezone

from .models import Payment, PaymentStatus
from .providers.registry import get_provider


class PaymentNotFound(Exception):
    """A confirmation referred to a payment we do not have."""


class UnknownProvider(Exception):
    """The webhook URL named a provider that does not exist."""


@dataclass(frozen=True)
class SettleResult:
    payment: Payment
    changed: bool  # False when the payment had already been settled


@dataclass(frozen=True)
class PurposeHandler:
    on_success: Callable[[Payment], None]
    on_failure: Callable[[Payment], None] = lambda payment: None


_HANDLERS: dict[str, PurposeHandler] = {}


def register_handler(purpose: str, on_success, on_failure=None) -> None:
    """Called by each app (memberships, remittances, recharges) when it loads."""
    _HANDLERS[purpose] = PurposeHandler(on_success, on_failure or (lambda payment: None))


@transaction.atomic
def settle_payment(payment_id: int, succeeded: bool) -> SettleResult:
    """Settle a payment once. The row is locked so concurrent calls serialize;
    if the handler fails, the whole thing rolls back and the payment stays PENDING."""
    payment = Payment.objects.select_for_update().get(pk=payment_id)
    if payment.status != PaymentStatus.PENDING:
        return SettleResult(payment, changed=False)

    payment.status = PaymentStatus.SUCCEEDED if succeeded else PaymentStatus.FAILED
    payment.confirmed_at = timezone.now()
    payment.save(update_fields=['status', 'confirmed_at', 'updated_at'])

    handler = _HANDLERS.get(payment.purpose)
    if handler:
        (handler.on_success if succeeded else handler.on_failure)(payment)
    return SettleResult(payment, changed=True)


def handle_webhook(provider_code: str, body: bytes, headers: Mapping[str, str]) -> SettleResult:
    """Verify a provider's webhook and settle the payment it refers to.

    Raises InvalidWebhook (bad signature/body), WebhookNotSupported (manual
    providers), UnknownProvider or PaymentNotFound.
    """
    try:
        provider = get_provider(provider_code.upper())
    except KeyError:
        raise UnknownProvider(provider_code) from None

    event = provider.parse_webhook(body, headers)  # verifies authenticity first
    payment = Payment.objects.filter(provider=provider.code, external_reference=event.external_reference).first()
    if payment is None:
        raise PaymentNotFound(event.external_reference)
    return settle_payment(payment.pk, event.succeeded)
