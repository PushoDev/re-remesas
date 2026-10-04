import hashlib
import hmac
import json
import uuid
from typing import Mapping

from django.conf import settings

from apps.payments.models import Payment

from .base import InvalidWebhook, PaymentSession, WebhookEvent

SIGNATURE_HEADER = 'X-Mock-Signature'


def sign(body: bytes) -> str:
    return hmac.new(settings.PAYMENT_WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()


class MockPaymentProvider:
    """Stands in for an online gateway (Stripe, PayPal, Mercado Pago, EnZona).

    No money moves and nothing is charged. It sends the customer to a simulated
    checkout page of the app, and "confirms" through a webhook that is signed
    with HMAC-SHA256, exactly like a real gateway would, so the signature
    verification path is real and tested.
    """

    code = 'MOCK'

    def create_payment(self, payment: Payment) -> PaymentSession:
        return PaymentSession(
            external_reference=f'mock_{uuid.uuid4().hex}',
            redirect_url=f'/pay/mock/{payment.reference}',
        )

    def parse_webhook(self, body: bytes, headers: Mapping[str, str]) -> WebhookEvent:
        received = headers.get(SIGNATURE_HEADER, '')
        if not hmac.compare_digest(received, sign(body)):
            raise InvalidWebhook('Firma del webhook no válida.')
        try:
            data = json.loads(body)
            return WebhookEvent(
                external_reference=str(data['external_reference']),
                succeeded=data['status'] == 'succeeded',
                raw=data,
            )
        except (ValueError, KeyError, TypeError):
            raise InvalidWebhook('Cuerpo del webhook no válido.') from None


def build_signed_event(external_reference: str, succeeded: bool) -> tuple[bytes, dict[str, str]]:
    """What the simulated gateway sends: a JSON body plus its HMAC signature header."""
    body = json.dumps({
        'external_reference': external_reference,
        'status': 'succeeded' if succeeded else 'failed',
    }).encode()
    return body, {SIGNATURE_HEADER: sign(body)}
