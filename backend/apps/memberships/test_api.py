from decimal import Decimal

import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.payments.models import Payment, PaymentStatus
from apps.users.models import User

from .models import MembershipPlan, Subscription

pytestmark = pytest.mark.django_db

PLANS = '/api/memberships/plans/'
SUBSCRIBE = '/api/memberships/subscribe/'


def make_plan(code='vip-mensual', **overrides):
    defaults = dict(
        name='VIP Mensual', period='MONTHLY', price=Decimal('9.99'), duration_days=30,
        recharge_discount_percent=Decimal('5'), benefits=['Mejor tasa de cambio'], sort_order=1,
    )
    return MembershipPlan.objects.create(code=code, **{**defaults, **overrides})


def make_user(email='ana@example.com'):
    return User.objects.create_user(username=email, email=email, password='x')


def client_for(user=None):
    client = APIClient()
    if user:
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return client


class TestPlans:
    def test_anyone_can_see_the_active_plans_with_price_and_benefits(self):
        make_plan()
        response = client_for().get(PLANS)

        assert response.status_code == 200
        plan = response.data[0]
        assert plan['code'] == 'vip-mensual'
        assert plan['price'] == '9.99'
        assert plan['duration_days'] == 30
        assert plan['benefits'] == ['Mejor tasa de cambio']
        assert set(plan) == {
            'code', 'name', 'period', 'price', 'currency', 'duration_days', 'recharge_discount_percent', 'benefits',
        }

    def test_inactive_plans_are_hidden_and_the_order_is_stable(self):
        make_plan('anual', sort_order=2, price=Decimal('99'))
        make_plan('mensual', sort_order=1)
        make_plan('viejo', is_active=False)

        assert [p['code'] for p in client_for().get(PLANS).data] == ['mensual', 'anual']

    def test_no_plans_is_an_empty_list(self):
        assert client_for().get(PLANS).data == []

    def test_it_is_read_only(self):
        assert client_for().post(PLANS, {}, format='json').status_code == 405


class TestSubscribe:
    def test_requires_authentication(self):
        make_plan()

        assert client_for().post(SUBSCRIBE, {'plan_code': 'vip-mensual', 'payment_method': 'STRIPE'},
                                 format='json').status_code == 401

    def test_creates_a_pending_purchase_and_points_to_the_checkout(self):
        plan = make_plan()
        user = make_user()
        response = client_for(user).post(SUBSCRIBE, {'plan_code': plan.code, 'payment_method': 'STRIPE'}, format='json')

        assert response.status_code == 201
        payment = response.data['payment']
        assert payment['status'] == 'PENDING'
        assert payment['amount'] == '9.99'
        assert payment['checkout_url'] == f"/pay/mock/{payment['reference']}"
        assert payment['requires_manual_confirmation'] is False
        assert response.data['subscription']['status'] == 'PENDING'
        assert response.data['subscription']['plan']['code'] == 'vip-mensual'

    def test_subscribing_does_not_activate_the_membership(self):
        user = make_user()
        make_plan()

        client_for(user).post(SUBSCRIBE, {'plan_code': 'vip-mensual', 'payment_method': 'STRIPE'}, format='json')

        user.profile.refresh_from_db()
        assert user.profile.membership_status == 'FREE'
        assert user.profile.is_membership_active is False

    def test_a_manual_method_returns_instructions_and_no_checkout(self):
        make_plan()
        response = client_for(make_user()).post(
            SUBSCRIBE, {'plan_code': 'vip-mensual', 'payment_method': 'ZELLE'}, format='json')

        payment = response.data['payment']
        assert response.status_code == 201
        assert payment['checkout_url'] is None
        assert payment['requires_manual_confirmation'] is True
        assert 'Zelle' in payment['instructions']

    def test_the_price_comes_from_the_server_not_from_the_client(self):
        make_plan(price=Decimal('9.99'))
        response = client_for(make_user()).post(
            SUBSCRIBE, {'plan_code': 'vip-mensual', 'payment_method': 'STRIPE', 'amount': '0.01', 'price': '0.01'},
            format='json')

        assert response.data['payment']['amount'] == '9.99'
        assert Payment.objects.get().amount == Decimal('9.99')

    def test_the_purchase_stores_a_snapshot_of_the_plan(self):
        make_plan()
        client_for(make_user()).post(SUBSCRIBE, {'plan_code': 'vip-mensual', 'payment_method': 'STRIPE'}, format='json')

        subscription = Subscription.objects.get()
        assert subscription.duration_days == 30
        assert subscription.recharge_discount_percent == Decimal('5')
        assert subscription.payment.target_id == subscription.pk

    @pytest.mark.parametrize('body, field', [
        ({'payment_method': 'STRIPE'}, 'plan_code'),
        ({'plan_code': 'no-existe', 'payment_method': 'STRIPE'}, 'plan_code'),
        ({'plan_code': 'viejo', 'payment_method': 'STRIPE'}, 'plan_code'),  # inactive
        ({'plan_code': 'vip-mensual'}, 'payment_method'),
        ({'plan_code': 'vip-mensual', 'payment_method': 'BITCOIN'}, 'payment_method'),
    ])
    def test_invalid_requests_are_rejected_and_create_nothing(self, body, field):
        make_plan()
        make_plan('viejo', is_active=False)

        response = client_for(make_user()).post(SUBSCRIBE, body, format='json')

        assert response.status_code == 400
        assert field in response.data
        assert Payment.objects.count() == 0 and Subscription.objects.count() == 0

    def test_error_messages_are_in_spanish(self):
        make_plan()
        response = client_for(make_user()).post(
            SUBSCRIBE, {'plan_code': 'no-existe', 'payment_method': 'BITCOIN'}, format='json')

        assert 'no está disponible' in response.data['plan_code'][0]
        assert 'no válido' in response.data['payment_method'][0]

    def test_every_payment_method_is_accepted(self):
        make_plan()
        user = make_user()
        for method in ['STRIPE', 'PAYPAL', 'WISE', 'MERCADO_PAGO', 'ENZONA', 'ZELLE', 'CASH']:
            response = client_for(user).post(SUBSCRIBE, {'plan_code': 'vip-mensual', 'payment_method': method},
                                             format='json')
            assert response.status_code == 201, method

    def test_each_attempt_is_its_own_pending_payment(self):
        make_plan()
        user = make_user()
        for _ in range(2):
            client_for(user).post(SUBSCRIBE, {'plan_code': 'vip-mensual', 'payment_method': 'STRIPE'}, format='json')

        assert Payment.objects.filter(status=PaymentStatus.PENDING).count() == 2
        assert len({p.external_reference for p in Payment.objects.all()}) == 2

    def test_a_current_vip_can_buy_again_to_extend(self):
        make_plan()
        user = make_user()
        user.profile.is_membership_active = True
        user.profile.save()

        response = client_for(user).post(SUBSCRIBE, {'plan_code': 'vip-mensual', 'payment_method': 'STRIPE'},
                                         format='json')

        assert response.status_code == 201
