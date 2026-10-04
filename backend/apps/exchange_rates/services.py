"""Single place where exchange rates are applied to an amount.

Everything here uses Decimal, never float. Remittances (and anything else that
quotes money) must go through `convert()` so the rule lives only here.

Rounding rules (documented in docs/DECISIONS.md):
  * effective rate -> 4 decimals, ROUND_HALF_UP
  * amount in CUP  -> 2 decimals, ROUND_DOWN (the customer is never promised
    more than the rate shown multiplied by the amount)
"""
from dataclasses import dataclass
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal

from django.db import transaction

from .models import ExchangeRate, ExchangeRateHistory

RATE_PLACES = Decimal('0.0001')
CUP_PLACES = Decimal('0.01')
HUNDRED = Decimal('100')


class RateNotAvailable(Exception):
    """There is no active rate configured for the requested currency."""


@dataclass(frozen=True)
class RateQuote:
    currency: str
    amount: Decimal
    base_rate: Decimal
    spread_percent: Decimal
    effective_rate: Decimal
    amount_cup: Decimal
    is_vip_rate: bool


def user_gets_vip_rate(user) -> bool:
    """True only for an authenticated user whose membership is currently VIP."""
    if user is None or not user.is_authenticated:
        return False
    return user.profile.membership_status == 'VIP'


def get_active_rate(currency: str) -> ExchangeRate:
    try:
        return ExchangeRate.objects.get(currency=currency, is_active=True)
    except ExchangeRate.DoesNotExist:
        raise RateNotAvailable(f'No hay una tasa de cambio activa para {currency}.') from None


def spread_for(rate: ExchangeRate, is_vip: bool) -> Decimal:
    return rate.vip_spread_percent if is_vip else rate.standard_spread_percent


def effective_rate(rate: ExchangeRate, is_vip: bool) -> Decimal:
    """Rate the customer actually gets: base rate minus the platform's margin."""
    factor = (HUNDRED - spread_for(rate, is_vip)) / HUNDRED
    return (rate.base_rate * factor).quantize(RATE_PLACES, rounding=ROUND_HALF_UP)


def convert(amount: Decimal, currency: str, is_vip: bool) -> RateQuote:
    if not isinstance(amount, Decimal) or amount <= 0:
        raise ValueError('amount must be a positive Decimal')

    rate = get_active_rate(currency)
    applied = effective_rate(rate, is_vip)
    return RateQuote(
        currency=currency,
        amount=amount,
        base_rate=rate.base_rate,
        spread_percent=spread_for(rate, is_vip),
        effective_rate=applied,
        amount_cup=(amount * applied).quantize(CUP_PLACES, rounding=ROUND_DOWN),
        is_vip_rate=is_vip,
    )


@transaction.atomic
def save_exchange_rate(rate: ExchangeRate, user) -> ExchangeRate:
    """Create/update a rate and record who changed it and what it became."""
    rate.updated_by = user
    # No `exclude`: the "one active rate per pair" rule involves target_currency.
    rate.full_clean()
    rate.save()
    ExchangeRateHistory.objects.create(
        rate=rate,
        base_rate=rate.base_rate,
        standard_spread_percent=rate.standard_spread_percent,
        vip_spread_percent=rate.vip_spread_percent,
        is_active=rate.is_active,
        changed_by=user,
    )
    return rate
