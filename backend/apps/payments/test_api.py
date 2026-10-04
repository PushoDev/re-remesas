import json
from decimal import Decimal

import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.memberships.models import MembershipPlan, Subscription
from apps.users.models import User

from .models import Payment, PaymentStatus
from .providers.mock import SIGNATURE_HEADER, build_signed_event, sign

pytestmark = pytest.mark.django_db

SUBSCRIBE = '/api/memberships/subscribe/'


def webhook_url(provider='mock'):
    return f'/api/payments/webhooks/{provider}/'


def detail_url(payment):
    return f'/api/payments/{payment.reference}/'


def confirm_url(payment):
    return f'/api/payments/mock/{payment.reference}/confirm/'


def make_user(email='ana@example.com'):
    return User.objects.create_user(username=email, email=email, password='x')


def client_for(user=None):
    client = APIClient()
    if user:
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return client


@pytest.fixture
def plan():
    return MembershipPlan.objects.create(
        code='vip-mensual', name='VIP Mensual', period='MONTHLY', price=Decimal('9.99'), duration_days=30,
    )


def buy(user, method='STRIPE'):
    response = client_for(user).post(SUBSCRIBE, {'plan_code': 'vip-mensual', 'payment_method': method}, format='json')
    return Payment.objects.get(reference=response.data['payment']['reference'])


def post_signed(payment, succeeded=True, client=None):
    body, headers = build_signed_event(payment.external_reference, succeeded)
    return (client or APIClient()).generic('POST', webhook_url(), body, content_type='application/json',
                                           HTTP_X_MOCK_SIGNATURE=headers[SIGNATURE_HEADER])


def status_of(user):
    user.profile.refresh_from_db()
    return user.profile.membership_status


class TestWebhook:
    def test_a_signed_webhook_activates_the_membership_without_any_login(self, plan):
        user = make_user()
        payment = buy(user)

        response = post_signed(payment)  # anonymous client: the gateway has no session

        assert response.status_code == 200
        assert response.data == {'status': 'ok', 'processed': True}
        assert status_of(user) == 'VIP'
        payment.refresh_from_db()
        assert payment.status == PaymentStatus.SUCCEEDED

    def test_the_same_webhook_twice_does_not_extend_twice(self, plan):
        user = make_user()
        payment = buy(user)

        first = post_signed(payment)
        expires = user.profile.__class__.objects.get(user=user).membership_expires_at
        second = post_signed(payment)

        assert (first.data['processed'], second.data['processed']) == (True, False)
        assert user.profile.__class__.objects.get(user=user).membership_expires_at == expires

    def test_a_failed_event_does_not_activate(self, plan):
        user = make_user()
        payment = buy(user)

        response = post_signed(payment, succeeded=False)

        assert response.status_code == 200
        assert status_of(user) == 'FREE'
        assert Subscription.objects.get().status == Subscription.Status.FAILED

    def test_a_forged_signature_is_rejected_and_activates_nothing(self, plan):
        user = make_user()
        payment = buy(user)
        body = json.dumps({'external_reference': payment.external_reference, 'status': 'succeeded'}).encode()

        response = APIClient().generic('POST', webhook_url(), body, content_type='application/json',
                                       HTTP_X_MOCK_SIGNATURE='firma-falsa')

        assert response.status_code == 400
        assert status_of(user) == 'FREE'

    def test_a_missing_signature_is_rejected(self, plan):
        payment = buy(make_user())
        body = json.dumps({'external_reference': payment.external_reference, 'status': 'succeeded'}).encode()

        assert APIClient().generic('POST', webhook_url(), body, content_type='application/json').status_code == 400

    def test_a_signature_from_another_body_is_rejected(self, plan):
        user = make_user()
        payment = buy(user)
        other_body, _ = build_signed_event('mock_otro', True)
        real = json.dumps({'external_reference': payment.external_reference, 'status': 'succeeded'}).encode()

        response = APIClient().generic('POST', webhook_url(), real, content_type='application/json',
                                       HTTP_X_MOCK_SIGNATURE=sign(other_body))

        assert response.status_code == 400
        assert status_of(user) == 'FREE'

    def test_an_unknown_reference_is_404(self, plan):
        body, headers = build_signed_event('mock_desconocida', True)

        response = APIClient().generic('POST', webhook_url(), body, content_type='application/json',
                                       HTTP_X_MOCK_SIGNATURE=headers[SIGNATURE_HEADER])

        assert response.status_code == 404

    @pytest.mark.parametrize('provider', ['manual', 'stripe-real', 'nada'])
    def test_providers_without_webhook_or_unknown_are_404(self, provider):
        assert APIClient().post(webhook_url(provider), {}, format='json').status_code == 404

    def test_only_post_is_allowed(self):
        assert APIClient().get(webhook_url()).status_code == 405


class TestMockCheckout:
    def test_the_owner_pays_and_becomes_vip(self, plan):
        user = make_user()
        payment = buy(user)

        response = client_for(user).post(confirm_url(payment), {'outcome': 'succeeded'}, format='json')

        assert response.status_code == 200
        assert response.data['status'] == 'SUCCEEDED'
        assert response.data['checkout_url'] is None
        assert status_of(user) == 'VIP'

    def test_the_owner_can_make_it_fail(self, plan):
        user = make_user()
        payment = buy(user)

        response = client_for(user).post(confirm_url(payment), {'outcome': 'failed'}, format='json')

        assert response.data['status'] == 'FAILED'
        assert status_of(user) == 'FREE'

    def test_confirming_twice_does_not_extend_twice(self, plan):
        user = make_user()
        payment = buy(user)
        client = client_for(user)

        client.post(confirm_url(payment), {'outcome': 'succeeded'}, format='json')
        user.profile.refresh_from_db()
        expires = user.profile.membership_expires_at
        client.post(confirm_url(payment), {'outcome': 'succeeded'}, format='json')

        user.profile.refresh_from_db()
        assert user.profile.membership_expires_at == expires

    def test_someone_else_cannot_pay_it(self, plan):
        owner, other = make_user(), make_user('otro@example.com')
        payment = buy(owner)

        response = client_for(other).post(confirm_url(payment), {'outcome': 'succeeded'}, format='json')

        assert response.status_code == 404
        assert status_of(owner) == 'FREE'

    def test_requires_authentication(self, plan):
        payment = buy(make_user())

        assert APIClient().post(confirm_url(payment), {'outcome': 'succeeded'}, format='json').status_code == 401

    def test_it_does_not_exist_when_the_simulation_is_disabled(self, plan, settings):
        user = make_user()
        payment = buy(user)
        settings.PAYMENT_MOCK_ENABLED = False

        response = client_for(user).post(confirm_url(payment), {'outcome': 'succeeded'}, format='json')

        assert response.status_code == 404
        assert status_of(user) == 'FREE'

    def test_manual_payments_cannot_be_confirmed_through_the_mock(self, plan):
        user = make_user()
        payment = buy(user, method='ZELLE')

        response = client_for(user).post(confirm_url(payment), {'outcome': 'succeeded'}, format='json')

        assert response.status_code == 404
        assert status_of(user) == 'FREE'

    @pytest.mark.parametrize('body', [{}, {'outcome': 'paid'}, {'outcome': ''}])
    def test_an_invalid_outcome_is_400(self, plan, body):
        user = make_user()
        payment = buy(user)

        assert client_for(user).post(confirm_url(payment), body, format='json').status_code == 400


class TestPaymentStatus:
    def test_the_owner_sees_the_state_and_where_to_pay(self, plan):
        user = make_user()
        payment = buy(user)

        response = client_for(user).get(detail_url(payment))

        assert response.status_code == 200
        assert response.data['status'] == 'PENDING'
        assert response.data['checkout_url'] == f'/pay/mock/{payment.reference}'
        assert 'external_reference' not in response.data

    def test_once_paid_the_checkout_url_disappears(self, plan):
        user = make_user()
        payment = buy(user)
        post_signed(payment)

        data = client_for(user).get(detail_url(payment)).data

        assert data['status'] == 'SUCCEEDED'
        assert data['checkout_url'] is None

    def test_other_users_get_404_and_anonymous_get_401(self, plan):
        payment = buy(make_user())

        assert client_for(make_user('otro@example.com')).get(detail_url(payment)).status_code == 404
        assert APIClient().get(detail_url(payment)).status_code == 401


class TestWholeJourney:
    def test_a_new_free_user_buys_a_plan_and_becomes_vip_everywhere(self, plan):
        from apps.exchange_rates.models import ExchangeRate

        ExchangeRate.objects.create(currency='USD', base_rate=Decimal('700'),
                                    standard_spread_percent=Decimal('5'), vip_spread_percent=Decimal('2'))
        user = make_user()
        client = client_for(user)
        assert client.get('/api/users/me/').data['profile']['membership_status'] == 'FREE'
        assert client.get('/api/exchange-rates/').data[0]['effective_rate'] == '665.0000'

        payment = buy(user)
        assert client.get('/api/users/me/').data['profile']['membership_status'] == 'FREE'  # paying is pending

        client.post(confirm_url(payment), {'outcome': 'succeeded'}, format='json')

        me = client.get('/api/users/me/').data
        assert me['profile']['membership_status'] == 'VIP'
        assert me['profile']['membership_expires_at']
        rate = client.get('/api/exchange-rates/').data[0]
        assert rate['effective_rate'] == '686.0000' and rate['is_vip_rate'] is True
