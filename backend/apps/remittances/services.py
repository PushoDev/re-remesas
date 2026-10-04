import re
import secrets
from dataclasses import dataclass
from decimal import Decimal

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.exchange_rates.services import RateQuote, convert, user_gets_vip_rate
from apps.payments.models import Payment, PaymentPurpose
from apps.payments.providers.base import PaymentSession
from apps.payments.providers.registry import provider_for_method

from .models import Remittance

# Letters and digits without the look-alikes (no 0/O, 1/I): easy to read out loud to support.
ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
SUFFIX_LENGTH = 5
TRACKING_ID_RE = re.compile(rf'^RR-\d{{8}}-[{ALPHABET}]{{{SUFFIX_LENGTH}}}$')
MAX_ATTEMPTS = 10


def generate_tracking_id() -> str:
    """RR-YYYYMMDD-XXXXX, e.g. RR-20261004-7KQ2M. The suffix is random, so the
    ids of other customers cannot be guessed from one's own."""
    day = timezone.now().strftime('%Y%m%d')
    suffix = ''.join(secrets.choice(ALPHABET) for _ in range(SUFFIX_LENGTH))
    return f'RR-{day}-{suffix}'


def normalize_tracking_id(raw: str) -> str:
    """What a customer types ("rr-20261004-7kq2m ") -> the canonical form."""
    return raw.strip().upper()


def is_valid_tracking_id(value: str) -> bool:
    return bool(TRACKING_ID_RE.match(value))


class AmountOutOfRange(ValueError):
    """The amount is below the minimum or above the maximum allowed per remittance."""


def amount_limits() -> tuple[Decimal, Decimal]:
    return Decimal(str(settings.REMITTANCE_MIN_AMOUNT)), Decimal(str(settings.REMITTANCE_MAX_AMOUNT))


def check_amount(amount: Decimal) -> None:
    low, high = amount_limits()
    if amount < low:
        raise AmountOutOfRange(f'El monto mínimo es {low:.2f}.')
    if amount > high:
        raise AmountOutOfRange(f'El monto máximo es {high:.2f}.')


@dataclass(frozen=True)
class RemittanceQuote:
    rate: RateQuote
    # Only filled for members: what a standard customer would get, to show the saving.
    standard_effective_rate: Decimal | None = None
    saving_cup: Decimal | None = None


def quote_remittance(user, amount: Decimal, currency: str) -> RemittanceQuote:
    """What the recipient would get. Same calculation the creation will repeat:
    the quote is informative, the created remittance is always recomputed."""
    check_amount(amount)
    is_vip = user_gets_vip_rate(user)
    rate = convert(amount, currency, is_vip)
    if not is_vip:
        return RemittanceQuote(rate)

    standard = convert(amount, currency, is_vip=False)
    return RemittanceQuote(
        rate,
        standard_effective_rate=standard.effective_rate,
        saving_cup=rate.amount_cup - standard.amount_cup,
    )


@transaction.atomic
def create_remittance(user, *, amount: Decimal, currency: str, recipient_name: str, recipient_phone: str,
                      delivery_method: str, recipient_address: str = '', recipient_account: str = '',
                      payment_method: str) -> tuple[Remittance, PaymentSession]:
    """Create a remittance and its pending payment, all or nothing.

    Every figure is computed here from the stored exchange rate and the user's
    membership. Whatever the client believes the rate or the CUP amount is
    never reaches this function.
    """
    quote = quote_remittance(user, amount, currency).rate

    provider = provider_for_method(payment_method)
    payment = Payment.objects.create(
        user=user, purpose=PaymentPurpose.REMITTANCE, method=payment_method, provider=provider.code,
        amount=amount, currency=currency,
    )
    session = provider.create_payment(payment)
    payment.external_reference = session.external_reference
    payment.instructions = session.instructions

    for _attempt in range(MAX_ATTEMPTS):
        tracking_id = generate_tracking_id()
        try:
            with transaction.atomic():  # a savepoint: a clash must not poison the outer transaction
                remittance = Remittance.objects.create(
                    tracking_id=tracking_id, sender=user, amount_sent=amount, currency=currency,
                    base_rate_used=quote.base_rate, spread_percent_used=quote.spread_percent,
                    effective_rate_used=quote.effective_rate, amount_cup=quote.amount_cup,
                    is_vip_rate=quote.is_vip_rate, recipient_name=recipient_name, recipient_phone=recipient_phone,
                    recipient_address=recipient_address, recipient_account=recipient_account,
                    delivery_method=delivery_method, payment_method=payment_method, payment=payment,
                )
            break
        except IntegrityError:
            if not Remittance.objects.filter(tracking_id=tracking_id).exists():
                raise  # not a tracking-id clash: a real problem
    else:
        raise RuntimeError('No se pudo generar un ID de seguimiento único.')

    payment.target_id = remittance.pk
    payment.save(update_fields=['external_reference', 'instructions', 'target_id', 'updated_at'])
    return remittance, session


# --- Reactions to the payment (registered in apps.py) -----------------------------------------
# Kept deliberately small here; the full status machine with its audit log is HU-REM-02.

def mark_paid(payment: Payment) -> None:
    Remittance.objects.filter(payment=payment, status=Remittance.Status.PENDING_PAYMENT).update(
        status=Remittance.Status.PAID, updated_at=timezone.now(),
    )


def cancel_after_failed_payment(payment: Payment) -> None:
    """A payment that failed ends the request; the customer can simply create a new one."""
    Remittance.objects.filter(payment=payment, status=Remittance.Status.PENDING_PAYMENT).update(
        status=Remittance.Status.CANCELLED, updated_at=timezone.now(),
    )
