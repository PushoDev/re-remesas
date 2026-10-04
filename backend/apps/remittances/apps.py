from django.apps import AppConfig


class RemittancesConfig(AppConfig):
    name = 'apps.remittances'

    def ready(self):
        from apps.payments.models import PaymentPurpose
        from apps.payments.services import register_handler

        from .services import cancel_after_failed_payment, mark_paid

        register_handler(PaymentPurpose.REMITTANCE, mark_paid, cancel_after_failed_payment)
