from django.apps import AppConfig


class RechargesConfig(AppConfig):
    name = 'apps.recharges'

    def ready(self):
        from apps.payments.models import PaymentPurpose
        from apps.payments.services import register_handler

        from .services import fail_order_after_failed_payment, mark_order_paid

        register_handler(PaymentPurpose.RECHARGE, mark_order_paid, fail_order_after_failed_payment)
