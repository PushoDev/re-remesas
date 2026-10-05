from decimal import Decimal

import pytest
from django.test import Client
from django.urls import reverse

from apps.memberships.models import MembershipPlan
from apps.memberships.services import subscribe
from apps.users.models import User

from .models import PaymentStatus

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin_client():
    admin = User.objects.create_superuser(username='admin@example.com', email='admin@example.com', password='x')
    client = Client()
    client.force_login(admin)
    return client


@pytest.fixture
def plan():
    return MembershipPlan.objects.create(
        code='vip-mensual', name='VIP Mensual', period='MONTHLY', price=Decimal('9.99'), duration_days=30,
    )


def buy(plan, method, email='ana@example.com'):
    user = User.objects.get_or_create(email=email, defaults={'username': email})[0]
    return user, subscribe(user, plan, method)[0].payment


def run_action(client, action, *payments):
    return client.post(reverse('admin:payments_payment_changelist'), {
        'action': action, '_selected_action': [p.pk for p in payments],
    }, follow=True)


class TestConfirmManualPayments:
    def test_confirming_a_zelle_payment_makes_the_user_vip(self, admin_client, plan):
        user, payment = buy(plan, 'ZELLE')

        run_action(admin_client, 'confirm_manual_payments', payment)

        payment.refresh_from_db(), user.profile.refresh_from_db()
        assert payment.status == PaymentStatus.SUCCEEDED
        assert user.profile.membership_status == 'VIP'

    def test_it_records_which_administrator_confirmed(self, admin_client, plan):
        _, payment = buy(plan, 'ZELLE')

        run_action(admin_client, 'confirm_manual_payments', payment)

        payment.refresh_from_db()
        assert payment.confirmed_by.email == 'admin@example.com'

    def test_rejecting_leaves_the_user_free(self, admin_client, plan):
        user, payment = buy(plan, 'CASH')

        run_action(admin_client, 'reject_manual_payments', payment)

        payment.refresh_from_db(), user.profile.refresh_from_db()
        assert payment.status == PaymentStatus.FAILED
        assert user.profile.membership_status == 'FREE'

    def test_confirming_twice_does_not_extend_twice(self, admin_client, plan):
        user, payment = buy(plan, 'WISE')
        run_action(admin_client, 'confirm_manual_payments', payment)
        user.profile.refresh_from_db()
        expires = user.profile.membership_expires_at

        run_action(admin_client, 'confirm_manual_payments', payment)

        user.profile.refresh_from_db()
        assert user.profile.membership_expires_at == expires

    def test_gateway_payments_cannot_be_confirmed_by_hand(self, admin_client, plan):
        user, payment = buy(plan, 'STRIPE')

        response = run_action(admin_client, 'confirm_manual_payments', payment)

        payment.refresh_from_db()
        assert payment.status == PaymentStatus.PENDING
        assert 'omitido' in response.content.decode()

    def test_a_customer_cannot_use_the_action(self, plan):
        _, payment = buy(plan, 'ZELLE')
        customer = Client()
        customer.force_login(User.objects.create_user(username='c@e.com', email='c@e.com', password='x'))

        response = customer.post(reverse('admin:payments_payment_changelist'), {
            'action': 'confirm_manual_payments', '_selected_action': [payment.pk],
        })

        payment.refresh_from_db()
        assert response.status_code == 302  # sent to the admin login
        assert payment.status == PaymentStatus.PENDING


class TestAdminPages:
    def test_payments_and_plans_pages_open(self, admin_client, plan):
        buy(plan, 'ZELLE')

        for name in ('payments_payment_changelist', 'memberships_membershipplan_changelist',
                     'memberships_subscription_changelist'):
            assert admin_client.get(reverse(f'admin:{name}')).status_code == 200

    def test_payments_cannot_be_edited_or_deleted_from_the_admin(self, admin_client, plan):
        _, payment = buy(plan, 'ZELLE')
        change = admin_client.get(reverse('admin:payments_payment_change', args=[payment.pk]))

        assert b'name="_save"' not in change.content
        assert admin_client.get(reverse('admin:payments_payment_delete', args=[payment.pk])).status_code == 403
        assert admin_client.get(reverse('admin:payments_payment_add')).status_code == 403
