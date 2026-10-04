"""Contract every payment provider implements.

Business code (memberships, remittances, recharges) only talks to this
interface through `registry.provider_for_method()`; it never branches on a
specific provider.
"""
from dataclasses import dataclass, field
from typing import Mapping, Protocol

from apps.payments.models import Payment


class InvalidWebhook(Exception):
    """The webhook could not be trusted (bad signature) or understood."""


class WebhookNotSupported(Exception):
    """This provider confirms payments by other means (e.g. an administrator)."""


@dataclass(frozen=True)
class PaymentSession:
    """What the customer must do next to pay."""

    external_reference: str = ''
    redirect_url: str | None = None  # online gateways: where to send the customer
    instructions: str = ''  # manual methods: what to do and what to keep
    requires_manual_confirmation: bool = False


@dataclass(frozen=True)
class WebhookEvent:
    external_reference: str
    succeeded: bool
    raw: Mapping = field(default_factory=dict)


class PaymentProvider(Protocol):
    code: str

    def create_payment(self, payment: Payment) -> PaymentSession: ...

    def parse_webhook(self, body: bytes, headers: Mapping[str, str]) -> WebhookEvent:
        """Verify authenticity and return the event. Raise InvalidWebhook otherwise."""
        ...
