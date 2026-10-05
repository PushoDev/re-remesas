from django.apps import AppConfig


class MembershipsConfig(AppConfig):
    name = 'apps.memberships'

    def ready(self):
        from apps.payments.models import PaymentPurpose
        from apps.payments.services import register_handler

        from .services import activate_membership, mark_subscription_failed

        register_handler(PaymentPurpose.MEMBERSHIP, activate_membership, mark_subscription_failed)
