"""Contract every top-up provider implements (HU-TOP-01).

Business code (`services`) only talks to this interface through `registry.get_provider()`;
it never branches on a specific provider. There is no ETECSA contract or credentials in this
project, so the only implementation is the simulated one (see DECISIONS).
"""
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol


class ProviderOutcome:
    """What a provider can answer to a top-up request."""

    SUCCESS = 'SUCCESS'  # the recipient has the top-up
    PROCESSING = 'PROCESSING'  # accepted, not delivered yet
    FAILED = 'FAILED'  # refused; nothing was delivered


@dataclass(frozen=True)
class RechargeResult:
    status: str  # one of ProviderOutcome
    provider_reference: str = ''
    message: str = ''


class RechargeProvider(Protocol):
    code: str

    def recharge(self, phone_number: str, package_code: str, amount: Decimal) -> RechargeResult:
        """Ask the provider to top up `phone_number` (+53XXXXXXXX) with the package."""
        ...
