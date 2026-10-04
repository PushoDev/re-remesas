from typing import Mapping

from apps.payments.models import Payment, PaymentMethod

from .base import PaymentSession, WebhookEvent, WebhookNotSupported

INSTRUCTIONS = {
    PaymentMethod.ZELLE: 'Realiza la transferencia por Zelle y conserva el comprobante.',
    PaymentMethod.WISE: 'Realiza la transferencia por Wise y conserva el comprobante.',
    PaymentMethod.CASH: 'Entrega el efectivo según te indique el equipo de Re & Re y conserva el recibo.',
}
FOOTER = ' Un administrador verificará el pago y lo confirmará; recibirás el aviso en la aplicación.'


class ManualPaymentProvider:
    """Methods settled outside the app (Zelle, Wise, cash): an administrator
    verifies the proof and confirms. There is no webhook and no live integration."""

    code = 'MANUAL'

    def create_payment(self, payment: Payment) -> PaymentSession:
        base = INSTRUCTIONS.get(payment.method, 'Realiza el pago y conserva el comprobante.')
        return PaymentSession(instructions=base + FOOTER, requires_manual_confirmation=True)

    def parse_webhook(self, body: bytes, headers: Mapping[str, str]) -> WebhookEvent:
        raise WebhookNotSupported('Este método se confirma manualmente por un administrador.')
