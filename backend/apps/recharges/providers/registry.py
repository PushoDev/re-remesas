"""The only place that knows which provider serves top-ups.

Swapping in a real ETECSA integration is a one-line change of ACTIVE_PROVIDER here.
"""
from .base import RechargeProvider
from .mock import MockRechargeProvider

_PROVIDERS: dict[str, RechargeProvider] = {provider.code: provider for provider in (MockRechargeProvider(),)}

ACTIVE_PROVIDER = 'MOCK'


def get_provider(code: str | None = None) -> RechargeProvider:
    return _PROVIDERS[code or ACTIVE_PROVIDER]
