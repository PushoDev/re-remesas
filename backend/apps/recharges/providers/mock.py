import uuid
from decimal import Decimal

from .base import ProviderOutcome, RechargeResult

# Last digit of the phone decides the answer, so the three paths can be tried on purpose.
FAILS_ON = '0'
PROCESSES_ON = '1'


class MockRechargeProvider:
    """Stands in for ETECSA's top-up service. Nothing is sent to anyone.

    The answer depends only on the last digit of the number: 0 → FAILED, 1 → PROCESSING,
    anything else → SUCCESS. The messages say nothing about being simulated: the customer
    sees what a real provider would say, and the documentation is what discloses the mock.
    """

    code = 'MOCK'

    def recharge(self, phone_number: str, package_code: str, amount: Decimal) -> RechargeResult:
        last_digit = phone_number[-1:]
        if not last_digit.isdigit():
            raise ValueError(f'Número no válido para recargar: {phone_number!r}')

        reference = f'RC-{uuid.uuid4().hex[:12].upper()}'
        if last_digit == FAILS_ON:
            return RechargeResult(ProviderOutcome.FAILED, reference, 'El operador no pudo completar la recarga.')
        if last_digit == PROCESSES_ON:
            return RechargeResult(ProviderOutcome.PROCESSING, reference, 'La recarga está en proceso.')
        return RechargeResult(ProviderOutcome.SUCCESS, reference, 'Recarga entregada.')
