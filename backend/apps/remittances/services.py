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

from apps.payments.models import PaymentStatus
from apps.payments.services import settle_payment

from .models import Remittance, RemittanceStatusLog

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
    RemittanceStatusLog.objects.create(
        remittance=remittance, from_status='', to_status=remittance.status,
        source=RemittanceStatusLog.Source.CUSTOMER, changed_by=user,
    )
    return remittance, session


# --- The state machine (HU-REM-02) --------------------------------------------------------------
# One place decides which moves are legal. COMPLETED and CANCELLED are final.

Status = Remittance.Status
Source = RemittanceStatusLog.Source

TRANSITIONS: dict[str, frozenset[str]] = {
    Status.PENDING_PAYMENT: frozenset({Status.PAID, Status.CANCELLED}),
    Status.PAID: frozenset({Status.COMPLETED, Status.CANCELLED}),
    Status.COMPLETED: frozenset(),
    Status.CANCELLED: frozenset(),
}


class InvalidTransition(Exception):
    """The requested move is not allowed from the remittance's current state."""

    def __init__(self, current: str, wanted: str):
        self.current, self.wanted = current, wanted
        super().__init__(
            f'No se puede pasar de «{Status(current).label}» a «{Status(wanted).label}».'
            if wanted in Status.values else f'Estado no válido: {wanted}.'
        )


class NoteRequired(Exception):
    """An administrator must say why a remittance is being cancelled."""


class NotAManualPayment(Exception):
    """Only payments settled by hand (Zelle, Wise, cash) are confirmed by an administrator."""


def _lock(remittance: Remittance) -> Remittance:
    # Only the remittance row ("self"): the payment is locked separately and first (see below).
    return Remittance.objects.select_for_update(of=('self',)).select_related('payment').get(pk=remittance.pk)


def _lock_payment_then_remittance(remittance: Remittance):
    """Lock order is ALWAYS payment first, then remittance. A payment webhook already works
    in that order (settle_payment locks the payment, then its handler touches the remittance);
    an administrator action must do the same or the two could wait on each other forever."""
    payment = Payment.objects.select_for_update().get(pk=remittance.payment_id)
    return _lock(remittance), payment


@transaction.atomic
def change_status(remittance: Remittance, new_status: str, *, user=None, note: str = '',
                  source: str = Source.ADMIN) -> Remittance:
    """Move a remittance to `new_status` if the machine allows it, and record it.

    The row is locked, so two people acting at once cannot both succeed. A
    cancellation by an administrator needs a reason.
    """
    locked = _lock(remittance)
    if new_status not in Status.values or new_status not in TRANSITIONS[locked.status]:
        raise InvalidTransition(locked.status, new_status)

    note = note.strip()
    if new_status == Status.CANCELLED and source == Source.ADMIN and not note:
        raise NoteRequired('Indica el motivo de la cancelación.')

    previous = locked.status
    locked.status = new_status
    locked.save(update_fields=['status', 'updated_at'])
    RemittanceStatusLog.objects.create(
        remittance=locked, from_status=previous, to_status=new_status, source=source, changed_by=user, note=note,
    )
    return locked


# --- Reactions to the payment (registered in apps.py) -------------------------------------------

def mark_paid(payment) -> None:
    """The payment was confirmed (gateway webhook, or an administrator for manual methods)."""
    remittance = Remittance.objects.select_for_update().filter(payment=payment).first()
    if remittance is None:
        return
    if remittance.status == Status.PENDING_PAYMENT:
        by_person = payment.confirmed_by is not None
        change_status(
            remittance, Status.PAID, user=payment.confirmed_by, source=Source.PAYMENT,
            note='Pago verificado por un administrador.' if by_person else 'Pago confirmado.',
        )
    else:
        # Money arrived for something that is no longer waiting for it (e.g. cancelled meanwhile).
        # Do not move the state; leave a visible trace so a person handles it (refund by hand).
        RemittanceStatusLog.objects.create(
            remittance=remittance, from_status=remittance.status, to_status=remittance.status, source=Source.PAYMENT,
            note=f'Se recibió el pago cuando la remesa ya estaba «{remittance.get_status_display()}»: '
                 'requiere revisión y reembolso manual.',
        )


def cancel_after_failed_payment(payment) -> None:
    """A payment that failed ends the request; the customer can simply create a new one."""
    remittance = Remittance.objects.select_for_update().filter(payment=payment).first()
    if remittance is not None and remittance.status == Status.PENDING_PAYMENT:
        change_status(remittance, Status.CANCELLED, source=Source.PAYMENT, note='El pago no se completó.')


# --- What an administrator can do -----------------------------------------------------------------

@transaction.atomic
def confirm_manual_payment(remittance: Remittance, admin) -> Remittance:
    """After checking the proof of a Zelle/Wise/cash payment: settle it, which marks the remittance PAID."""
    locked, payment = _lock_payment_then_remittance(remittance)
    if locked.status != Status.PENDING_PAYMENT:
        raise InvalidTransition(locked.status, Status.PAID)
    if payment.provider != 'MANUAL':
        raise NotAManualPayment('Este pago se confirma solo, por la pasarela; un administrador no puede marcarlo.')
    settle_payment(payment.pk, succeeded=True, confirmed_by=admin)
    return _lock(locked)


@transaction.atomic
def complete_remittance(remittance: Remittance, admin, note: str = '') -> Remittance:
    """The money was delivered in Cuba."""
    return change_status(remittance, Status.COMPLETED, user=admin, note=note, source=Source.ADMIN)


@transaction.atomic
def cancel_remittance(remittance: Remittance, admin, note: str) -> Remittance:
    """Cancel it, with a reason. A payment still pending is closed so it cannot be paid later.
    If it had already been paid, the refund is manual (documented limitation)."""
    _locked, payment = _lock_payment_then_remittance(remittance)
    cancelled = change_status(remittance, Status.CANCELLED, user=admin, note=note, source=Source.ADMIN)
    if payment.status == PaymentStatus.PENDING:
        settle_payment(payment.pk, succeeded=False, confirmed_by=admin)  # its handler is now a no-op
    return _lock(cancelled)
