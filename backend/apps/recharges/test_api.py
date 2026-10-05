from datetime import timedelta
from decimal import Decimal
from unittest import mock

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.payments.models import Payment
from apps.payments.providers.mock import build_signed_event
from apps.payments.services import settle_payment
from apps.users.models import User

from .models import Promotion, RechargeOrder, RechargePackage
from .services import create_recharge_order
from .test_orders import make_vip

pytestmark = pytest.mark.django_db

PHONE = '+53 5123 4567'
RECHARGE = 'apps.recharges.providers.mock.MockRechargeProvider.recharge'
URLS = {
    'packages': '/api/recharges/packages/', 'contacts': '/api/recharges/recent-contacts/',
    'quote': '/api/recharges/quote/', 'list': '/api/recharges/', 'admin': '/api/admin/recharges/',
}


def make_user(email='ana@example.com', staff=False):
    return User.objects.create_user(username=email, email=email, password='x', is_staff=staff)


@pytest.fixture
def user():
    return make_user()


@pytest.fixture
def other():
    return make_user('beto@example.com')


@pytest.fixture
def admin():
    return make_user('admin@example.com', staff=True)


@pytest.fixture
def package():
    return RechargePackage.objects.create(
        code='saldo-10', name='Recarga 10', kind=RechargePackage.Kind.BALANCE, price=Decimal('10.00'),
        description='Saldo directo',
    )


def logged(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def order_for(user, package, phone=PHONE, method='STRIPE'):
    return create_recharge_order(user, package=package, phone_number=phone, payment_method=method)[0]


def body(package, **extra):
    return {'phone_number': PHONE, 'package_code': package.code, **extra}


class TestWhoCanCall:
    @pytest.mark.parametrize('name', ['packages', 'contacts', 'list', 'admin'])
    def test_anonymous_visitors_get_401_on_reads(self, name):
        assert APIClient().get(URLS[name]).status_code == 401

    @pytest.mark.parametrize('name', ['quote', 'list'])
    def test_anonymous_visitors_get_401_on_writes(self, name):
        assert APIClient().post(URLS[name], {}, format='json').status_code == 401

    def test_a_customer_cannot_use_the_admin_list(self, user):
        assert logged(user).get(URLS['admin']).status_code == 403

    def test_an_administrator_can(self, admin):
        assert logged(admin).get(URLS['admin']).status_code == 200


class TestCatalog:
    def test_lists_only_active_packages_with_their_data(self, user, package):
        RechargePackage.objects.create(code='off', name='Off', kind='DATA', price=Decimal('5'), is_active=False)
        response = logged(user).get(URLS['packages'])
        assert response.status_code == 200
        assert response.json() == [{
            'code': 'saldo-10', 'name': 'Recarga 10', 'kind': 'BALANCE', 'kind_display': 'Saldo', 'price': '10.00',
            'currency': 'USD', 'description': 'Saldo directo', 'active_promotion': None,
        }]
        assert response['Cache-Control'] == 'no-store'

    def test_the_current_promotion_is_injected_by_the_server(self, user, package):
        now = timezone.now()
        Promotion.objects.create(
            code='bono', title='Bono 50 %', description='Doble saldo', starts_at=now - timedelta(days=1),
            ends_at=now + timedelta(days=1),
        )
        promo = logged(user).get(URLS['packages']).json()[0]['active_promotion']
        assert (promo['code'], promo['title'], promo['description']) == ('bono', 'Bono 50 %', 'Doble saldo')
        assert 'ends_at' in promo

    @pytest.mark.parametrize('starts,ends', [(-5, -1), (1, 5)])
    def test_an_expired_or_future_promotion_is_not_shown(self, user, package, starts, ends):
        now = timezone.now()
        Promotion.objects.create(
            code='x', title='X', starts_at=now + timedelta(days=starts), ends_at=now + timedelta(days=ends),
        )
        assert logged(user).get(URLS['packages']).json()[0]['active_promotion'] is None


class TestRecentContacts:
    def test_unique_numbers_newest_first(self, user, package):
        order_for(user, package, '+53 5000 0001')
        order_for(user, package, '+53 5000 0002')
        order_for(user, package, '+53 5000 0001')
        numbers = [row['phone_number'] for row in logged(user).get(URLS['contacts']).json()]
        assert numbers == ['+5350000001', '+5350000002']

    def test_only_the_callers_own_numbers(self, user, other, package):
        order_for(other, package, '+53 5999 9999')
        assert logged(user).get(URLS['contacts']).json() == []

    def test_at_most_eight(self, user, package):
        for index in range(10):
            order_for(user, package, f'+53 5000 00{index:02d}')
        assert len(logged(user).get(URLS['contacts']).json()) == 8


class TestQuote:
    def test_a_free_customer_sees_the_full_price(self, user, package):
        response = logged(user).post(URLS['quote'], body(package), format='json')
        assert response.status_code == 200
        data = response.json()
        assert data['phone_number'] == '+5351234567'
        assert (data['price_base'], data['discount_percent'], data['amount_total']) == ('10.00', '0.00', '10.00')
        assert data['is_vip'] is False and data['active_promotion'] is None
        assert data['package']['code'] == 'saldo-10'
        assert response['Cache-Control'] == 'no-store'

    def test_a_vip_sees_the_discount(self, user, package):
        make_vip(user, '10.00')
        data = logged(user).post(URLS['quote'], body(package), format='json').json()
        assert (data['discount_percent'], data['discount_amount'], data['amount_total']) == ('10.00', '1.00', '9.00')
        assert data['is_vip'] is True

    def test_the_client_cannot_set_the_price(self, user, package):
        data = logged(user).post(
            URLS['quote'], body(package, amount_total='0.01', price='0.01', discount_percent='99'), format='json',
        ).json()
        assert data['amount_total'] == '10.00'

    @pytest.mark.parametrize('phone', ['', '5123', '+34 612345678', '+53 2123 4567', 'hola'])
    def test_a_bad_phone_is_a_400_on_that_field(self, user, package, phone):
        response = logged(user).post(URLS['quote'], body(package, phone_number=phone), format='json')
        assert response.status_code == 400
        assert 'phone_number' in response.json()

    def test_an_unknown_package_is_a_400_on_that_field(self, user, package):
        response = logged(user).post(URLS['quote'], body(package, package_code='nope'), format='json')
        assert response.status_code == 400
        assert response.json()['package_code'] == ['Paquete no válido.']

    def test_an_inactive_package_is_a_400(self, user, package):
        package.is_active = False
        package.save()
        response = logged(user).post(URLS['quote'], body(package), format='json')
        assert response.json()['package_code'] == ['Este paquete no está disponible.']

    def test_missing_fields_are_reported_in_spanish(self, user):
        response = logged(user).post(URLS['quote'], {}, format='json')
        assert response.json() == {'phone_number': ['Ingresa el teléfono.'], 'package_code': ['Elige un paquete.']}

    def test_quoting_creates_nothing(self, user, package):
        logged(user).post(URLS['quote'], body(package), format='json')
        assert RechargeOrder.objects.count() == 0 and Payment.objects.count() == 0


class TestCreate:
    def test_creates_the_order_and_tells_where_to_pay(self, user, package):
        response = logged(user).post(URLS['list'], body(package, payment_method='STRIPE'), format='json')
        assert response.status_code == 201
        data = response.json()
        order = RechargeOrder.objects.get()
        assert order.user == user
        assert data['order']['reference'] == str(order.reference)
        assert data['order']['status'] == 'PENDING_PAYMENT'
        assert data['order']['phone_number'] == '+5351234567'
        assert data['order']['amount_total'] == '10.00'
        assert data['payment']['checkout_url'] == f'/pay/mock/{order.payment.reference}'
        assert 'external_reference' not in data['payment']

    def test_a_manual_method_comes_with_instructions(self, user, package):
        data = logged(user).post(URLS['list'], body(package, payment_method='ZELLE'), format='json').json()
        assert data['payment']['requires_manual_confirmation'] is True
        assert 'Zelle' in data['payment']['instructions']
        assert data['payment']['checkout_url'] is None

    def test_the_vip_discount_is_charged(self, user, package):
        make_vip(user, '5.00')
        data = logged(user).post(URLS['list'], body(package, payment_method='CASH'), format='json').json()
        assert (data['order']['amount_total'], data['payment']['amount']) == ('9.50', '9.50')

    def test_the_client_cannot_choose_price_status_or_owner(self, user, other, package):
        payload = body(package, payment_method='CASH', amount_total='0.01', status='SUCCESS', user=other.pk)
        response = logged(user).post(URLS['list'], payload, format='json')
        order = RechargeOrder.objects.get()
        assert response.status_code == 201
        assert (order.amount_total, order.status, order.user) == (Decimal('10.00'), 'PENDING_PAYMENT', user)

    def test_it_does_not_call_the_provider(self, user, package):
        with mock.patch(RECHARGE) as recharge:
            logged(user).post(URLS['list'], body(package, payment_method='STRIPE'), format='json')
        recharge.assert_not_called()

    @pytest.mark.parametrize('extra,field', [
        ({'payment_method': 'BITCOIN'}, 'payment_method'),
        ({}, 'payment_method'),
        ({'payment_method': 'CASH', 'phone_number': '+53 2123 4567'}, 'phone_number'),
        ({'payment_method': 'CASH', 'package_code': 'nope'}, 'package_code'),
    ])
    def test_invalid_input_is_a_400_and_leaves_nothing_behind(self, user, package, extra, field):
        response = logged(user).post(URLS['list'], body(package, **extra), format='json')
        assert response.status_code == 400
        assert field in response.json()
        assert RechargeOrder.objects.count() == 0 and Payment.objects.count() == 0


class TestOwnOrders:
    def test_lists_only_mine_newest_first(self, user, other, package):
        first = order_for(user, package)
        second = order_for(user, package)
        order_for(other, package)
        data = logged(user).get(URLS['list']).json()
        assert data['count'] == 2
        assert [row['reference'] for row in data['results']] == [str(second.reference), str(first.reference)]

    def test_filters_by_status_and_rejects_a_bad_one(self, user, package):
        paid = order_for(user, package)
        order_for(user, package)
        settle_payment(paid.payment_id, True)
        client = logged(user)
        assert client.get(URLS['list'], {'status': 'SUCCESS'}).json()['count'] == 1
        assert client.get(URLS['list'], {'status': 'PENDING_PAYMENT'}).json()['count'] == 1
        assert client.get(URLS['list'], {'status': 'NOPE'}).status_code == 400

    def test_the_owner_sees_the_detail_with_the_payment(self, user, package):
        order = order_for(user, package)
        data = logged(user).get(f'/api/recharges/{order.reference}/').json()
        assert data['reference'] == str(order.reference)
        assert data['package']['name'] == 'Recarga 10'
        assert data['payment']['status'] == 'PENDING'

    def test_someone_elses_order_is_a_404(self, user, other, package):
        order = order_for(other, package)
        assert logged(user).get(f'/api/recharges/{order.reference}/').status_code == 404

    @pytest.mark.parametrize('reference', ['00000000-0000-0000-0000-000000000000', 'not-a-uuid', '1'])
    def test_an_unknown_order_is_a_404(self, user, reference):
        assert logged(user).get(f'/api/recharges/{reference}/').status_code == 404


class TestFromPurchaseToTopUp:
    def test_paying_online_ends_in_an_order_the_customer_can_see_as_successful(self, user, package):
        client = logged(user)
        created = client.post(URLS['list'], body(package, payment_method='STRIPE'), format='json').json()
        order = RechargeOrder.objects.get()
        payload, headers = build_signed_event(order.payment.external_reference, succeeded=True)
        response = APIClient().post(
            '/api/payments/webhooks/mock/', data=payload, content_type='application/json',
            HTTP_X_MOCK_SIGNATURE=headers['X-Mock-Signature'],
        )
        assert response.status_code == 200
        detail = client.get(f"/api/recharges/{created['order']['reference']}/").json()
        assert detail['status'] == 'SUCCESS'
        assert detail['status_display'] == 'Exitosa'
        assert detail['provider_reference'].startswith('RC-')
        assert detail['payment']['status'] == 'SUCCEEDED'

    @pytest.mark.parametrize('phone,expected', [
        ('+53 5123 4560', 'FAILED'), ('+53 5123 4561', 'PROCESSING'), ('+53 5123 4562', 'SUCCESS'),
    ])
    def test_the_three_provider_paths_reach_the_customer(self, user, package, phone, expected):
        order = order_for(user, package, phone)
        settle_payment(order.payment_id, True)
        assert logged(user).get(f'/api/recharges/{order.reference}/').json()['status'] == expected


class TestAdminList:
    def test_sees_everyones_orders_with_the_customer(self, user, other, admin, package):
        order_for(user, package)
        order_for(other, package)
        data = logged(admin).get(URLS['admin']).json()
        assert data['count'] == 2
        assert {row['user_email'] for row in data['results']} == {'ana@example.com', 'beto@example.com'}
        row = data['results'][0]
        assert {'reference', 'phone_number', 'package', 'amount_total', 'status', 'provider_reference',
                'provider_message', 'payment_method', 'payment_status', 'needs_refund'} <= set(row)

    def test_filters_by_status(self, user, admin, package):
        paid = order_for(user, package)
        order_for(user, package)
        settle_payment(paid.payment_id, True)
        client = logged(admin)
        assert client.get(URLS['admin'], {'status': 'SUCCESS'}).json()['count'] == 1
        assert client.get(URLS['admin'], {'status': 'NOPE'}).status_code == 400

    def test_searches_by_phone_email_and_both_references(self, user, other, admin, package):
        mine = order_for(user, package, '+53 5111 1111')
        order_for(other, package, '+53 5222 2222')
        settle_payment(mine.payment_id, True)
        mine.refresh_from_db()
        client = logged(admin)
        for term in ('5111111', 'ana@', mine.provider_reference, str(mine.reference)[:8]):
            data = client.get(URLS['admin'], {'search': term}).json()
            assert [row['reference'] for row in data['results']] == [str(mine.reference)], term

    def test_marks_what_must_be_refunded(self, user, admin, package):
        refused = order_for(user, package, '+53 5123 4560')
        delivered = order_for(user, package, '+53 5123 4562')
        unpaid = order_for(user, package, '+53 5123 4563')
        settle_payment(refused.payment_id, True)
        settle_payment(delivered.payment_id, True)
        rows = {row['reference']: row for row in logged(admin).get(URLS['admin']).json()['results']}
        assert rows[str(refused.reference)]['needs_refund'] is True
        assert rows[str(delivered.reference)]['needs_refund'] is False
        assert rows[str(unpaid.reference)]['needs_refund'] is False

    def test_a_failed_payment_needs_no_refund(self, user, admin, package):
        order = order_for(user, package)
        settle_payment(order.payment_id, False)
        row = logged(admin).get(URLS['admin']).json()['results'][0]
        assert (row['status'], row['payment_status'], row['needs_refund']) == ('FAILED', 'FAILED', False)
