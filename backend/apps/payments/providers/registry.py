"""The only place that knows which provider serves which payment method.

Methods that would need a live gateway account we do not have (Stripe, PayPal,
Mercado Pago, EnZona) are served by the Mock provider and are labelled as such
in the documentation. Wise, Zelle and cash are settled by an administrator.
Swapping one in for a real implementation is a one-line change here.
"""
from apps.payments.models import PaymentMethod

from .base import PaymentProvider
from .manual import ManualPaymentProvider
from .mock import MockPaymentProvider

_PROVIDERS: dict[str, PaymentProvider] = {
    provider.code: provider for provider in (MockPaymentProvider(), ManualPaymentProvider())
}

METHOD_TO_PROVIDER: dict[str, str] = {
    PaymentMethod.STRIPE: 'MOCK',
    PaymentMethod.PAYPAL: 'MOCK',
    PaymentMethod.MERCADO_PAGO: 'MOCK',
    PaymentMethod.ENZONA: 'MOCK',
    PaymentMethod.WISE: 'MANUAL',
    PaymentMethod.ZELLE: 'MANUAL',
    PaymentMethod.CASH: 'MANUAL',
}


def get_provider(code: str) -> PaymentProvider:
    return _PROVIDERS[code]


def provider_for_method(method: str) -> PaymentProvider:
    return _PROVIDERS[METHOD_TO_PROVIDER[method]]
