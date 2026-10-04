from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.exchange_rates.models import ExchangeRate
from apps.payments.models import Payment, PaymentStatus
from apps.payments.providers.mock import MockPaymentProvider
from apps.users.models import User

from . import services
from .models import Remittance
from .services import create_remittance, is_valid_tracking_id

pytestmark = pytest.mark.django_db

URL = '/api/remittances/'
CASH = {'delivery_method': 'CASH_DELIVERY', 'recipient_address': 'Calle 23 #456, Vedado, La Habana'}
TRANSFER = {'delivery_method': 'LOCAL_TRANSFER', 'recipient_account': '9225 1234 5678 9012'}


@pytest.fixture(autouse=True)
def usd_rate():
    return ExchangeRate.objects.create(
        currency='USD', base_rate=Decimal('700'), standard_spread_percent=Decimal('5'), vip_spread_percent=Decimal('2'),
    )


@pytest.fixture
def user():
    return make_user()


def make_user(email='ana@example.com', vip_days=None):
    user = User.objects.create_user(username=email, email=email, password='x')
    if vip_days is not None:
        user.profile.is_membership_active = True
        user.profile.membership_expires_at = timezone.now() + timedelta(days=vip_days)
        user.profile.save()
    return user


def client_for(user=None):
    client = APIClient()
    if user:
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return client


def body(**overrides):
    return {
        'amount': '100', 'currency': 'USD', 'recipient_name': 'Rosa Pérez', 'recipient_phone': '+53 5123 4567',
        'payment_method': 'STRIPE', **CASH, **overrides,
    }


def create(user, **overrides):
    return client_for(user).post(URL, body(**overrides), format='json')


class TestCreation:
    def test_requires_authentication(self):
        assert client_for().post(URL, body(), format='json').status_code == 401

    def test_creates_the_remittance_pending_payment_with_a_tracking_id(self, user):
        response = create(user)

        assert response.status_code == 201
        remittance = response.data['remittance']
        assert is_valid_tracking_id(remittance['tracking_id'])
        assert remittance['status'] == 'PENDING_PAYMENT'
        assert remittance['status_display'] == 'Pendiente de pago'
        assert Remittance.objects.get().sender == user

    def test_the_server_computes_and_stores_the_snapshot(self, user):
        data = create(user).data['remittance']

        assert (data['amount_sent'], data['currency'], data['target_currency']) == ('100.00', 'USD', 'CUP')
        assert (data['base_rate_used'], data['spread_percent_used'], data['effective_rate_used']) == (
            '700.000000', '5.00', '665.0000')
        assert data['amount_cup'] == '66500.00'
        assert data['is_vip_rate'] is False

    def test_a_member_gets_the_preferential_rate_stored(self):
        data = create(make_user(vip_days=30)).data['remittance']

        assert (data['spread_percent_used'], data['effective_rate_used'], data['amount_cup']) == (
            '2.00', '686.0000', '68600.00')
        assert data['is_vip_rate'] is True

    def test_it_returns_the_pending_payment_and_where_to_pay(self, user):
        payment = create(user).data['payment']

        assert (payment['purpose'], payment['status'], payment['amount'], payment['currency']) == (
            'REMITTANCE', 'PENDING', '100.00', 'USD')
        assert payment['checkout_url'].startswith('/pay/mock/')

    def test_a_manual_payment_method_returns_instructions_and_no_checkout(self, user):
        payment = create(user, payment_method='ZELLE').data['payment']

        assert payment['checkout_url'] is None
        assert payment['requires_manual_confirmation'] is True
        assert 'Zelle' in payment['instructions']

    @pytest.mark.parametrize('method', ['STRIPE', 'PAYPAL', 'WISE', 'MERCADO_PAGO', 'ENZONA', 'ZELLE', 'CASH'])
    def test_every_payment_method_is_accepted(self, user, method):
        assert create(user, payment_method=method).status_code == 201

    def test_the_payment_is_linked_both_ways(self, user):
        create(user)

        remittance, payment = Remittance.objects.get(), Payment.objects.get()
        assert remittance.payment == payment
        assert payment.target_id == remittance.pk
        assert payment.user == user

    def test_the_response_has_no_internal_ids_and_no_sender_data(self, user):
        text = create(user).content.decode()

        assert 'ana@example.com' not in text
        assert '"id"' not in text and '"sender"' not in text

    def test_recipient_data_is_normalized(self, user):
        data = create(user, recipient_name='  Rosa    María   Pérez ', recipient_phone='51234567').data['remittance']

        assert data['recipient_name'] == 'Rosa María Pérez'
        assert data['recipient_phone'] == '+5351234567'

    def test_each_request_is_its_own_remittance_with_its_own_id(self, user):
        ids = {create(user).data['remittance']['tracking_id'] for _ in range(15)}

        assert len(ids) == 15 and Remittance.objects.count() == 15


class TestTheClientCannotDecideTheMoney:
    def test_rates_amounts_status_and_ids_sent_by_the_client_are_ignored(self, user):
        other = make_user('otro@example.com')
        response = create(
            user, amount_cup='999999.00', effective_rate_used='9999', base_rate_used='9999', spread_percent_used='0',
            effective_rate='9999', is_vip_rate=True, status='COMPLETED', tracking_id='RR-20200101-AAAAA',
            sender=other.pk, sender_id=other.pk, payment=1,
        )

        remittance = Remittance.objects.get()
        assert response.status_code == 201
        assert remittance.amount_cup == Decimal('66500.00')
        assert remittance.effective_rate_used == Decimal('665.0000')
        assert remittance.spread_percent_used == Decimal('5.00')
        assert remittance.is_vip_rate is False
        assert remittance.status == 'PENDING_PAYMENT'
        assert remittance.tracking_id != 'RR-20200101-AAAAA'
        assert remittance.sender == user

    def test_a_free_user_cannot_claim_the_vip_rate(self, user):
        data = create(user, is_vip_rate=True, vip=True, spread_percent='2').data['remittance']

        assert data['effective_rate_used'] == '665.0000'

    def test_the_payment_amount_is_the_amount_sent_not_something_the_client_sets(self, user):
        create(user, payment_amount='0.01', price='0.01')

        assert Payment.objects.get().amount == Decimal('100.00')

    def test_a_later_rate_change_does_not_alter_an_existing_remittance(self, user, usd_rate):
        create(user)
        usd_rate.base_rate = Decimal('900')
        usd_rate.save()
        remittance = Remittance.objects.get()

        assert remittance.base_rate_used == Decimal('700.000000')
        assert remittance.amount_cup == Decimal('66500.00')

    def test_deactivating_the_rate_afterwards_does_not_touch_it_either(self, user, usd_rate):
        create(user)
        usd_rate.is_active = False
        usd_rate.save()

        assert Remittance.objects.get().amount_cup == Decimal('66500.00')

    def test_the_payment_stays_with_the_user_who_requested_it(self, user):
        create(user)

        assert Payment.objects.get().user == user


class TestRecipientAndDelivery:
    def test_cash_delivery_needs_an_address(self, user):
        response = create(user, delivery_method='CASH_DELIVERY', recipient_address='')

        assert response.status_code == 400
        assert 'dirección' in response.data['recipient_address'][0]
        assert Remittance.objects.count() == 0 and Payment.objects.count() == 0

    def test_a_local_transfer_needs_an_account(self, user):
        response = create(user, delivery_method='LOCAL_TRANSFER', recipient_address='', recipient_account='')

        assert response.status_code == 400
        assert 'cuenta' in response.data['recipient_account'][0]

    def test_a_local_transfer_is_created_with_a_normalized_account(self, user):
        data = create(user, **TRANSFER, recipient_address='').data['remittance']

        assert data['recipient_account'] == '9225123456789012'
        assert data['recipient_address'] == ''

    @pytest.mark.parametrize('account', ['123', '9225-1234-ABCD-9012', '1' * 21])
    def test_an_account_with_a_wrong_format_is_rejected(self, user, account):
        response = create(user, delivery_method='LOCAL_TRANSFER', recipient_account=account)

        assert response.status_code == 400
        assert '12 y 20 dígitos' in response.data['recipient_account'][0]

    def test_data_that_the_delivery_method_does_not_use_is_not_kept(self, user):
        cash = create(user, recipient_account='9225123456789012').data['remittance']
        transfer = create(user, **TRANSFER, recipient_address='Calle 1').data['remittance']

        assert cash['recipient_account'] == '' and cash['recipient_address']
        assert transfer['recipient_address'] == '' and transfer['recipient_account']

    @pytest.mark.parametrize('phone', ['', '123', '41234567', '+54 51234567', 'abc', '5123 456'])
    def test_an_invalid_cuban_phone_is_rejected(self, user, phone):
        response = create(user, recipient_phone=phone)

        assert response.status_code == 400
        assert 'recipient_phone' in response.data

    @pytest.mark.parametrize('name', ['', '   ', 'A', 'x' * 121])
    def test_an_invalid_name_is_rejected(self, user, name):
        response = create(user, recipient_name=name)

        assert response.status_code == 400
        assert 'recipient_name' in response.data

    def test_unknown_delivery_or_payment_methods_are_rejected(self, user):
        assert 'delivery_method' in create(user, delivery_method='DRONE').data
        assert 'payment_method' in create(user, payment_method='BITCOIN').data

    def test_errors_are_in_spanish_and_nothing_is_created(self, user):
        response = create(user, recipient_name='', recipient_phone='1', payment_method='X')

        assert response.status_code == 400
        assert set(response.data) == {'recipient_name', 'recipient_phone', 'payment_method'}
        assert Remittance.objects.count() == 0 and Payment.objects.count() == 0


class TestAmountAndRate:
    @pytest.mark.parametrize('amount, fragment', [
        ('0', 'mínimo'), ('0.99', 'mínimo'), ('10000.01', 'máximo'), ('10.123', '2 decimales'), ('1e3', 'válido'),
    ])
    def test_invalid_amounts(self, user, amount, fragment):
        response = create(user, amount=amount)

        assert response.status_code == 400
        assert fragment in response.data['amount'][0]
        assert Remittance.objects.count() == 0

    def test_the_limits_are_inclusive(self, user):
        assert create(user, amount='1.00').status_code == 201
        assert create(user, amount='10000.00').status_code == 201

    def test_no_active_rate_means_no_remittance(self, user, usd_rate):
        usd_rate.is_active = False
        usd_rate.save()

        response = create(user)

        assert response.status_code == 400
        assert 'No hay una tasa de cambio disponible para USD' in response.data['currency'][0]
        assert Remittance.objects.count() == 0 and Payment.objects.count() == 0

    def test_cup_is_rounded_down_and_the_figure_is_stored_exactly(self, user, usd_rate):
        usd_rate.base_rate = Decimal('700.123456')
        usd_rate.standard_spread_percent = Decimal('3.33')
        usd_rate.save()

        data = create(user, amount='37.45').data['remittance']

        assert (data['effective_rate_used'], data['amount_cup']) == ('676.8093', '25346.50')


class TestAllOrNothing:
    def test_if_the_provider_fails_nothing_is_left_behind(self, user, monkeypatch):
        def boom(self, payment):
            raise RuntimeError('pasarela caída')

        monkeypatch.setattr(MockPaymentProvider, 'create_payment', boom)

        with pytest.raises(RuntimeError):
            create_remittance(user, amount=Decimal('100'), currency='USD', recipient_name='Rosa',
                              recipient_phone='+5351234567', delivery_method='CASH_DELIVERY',
                              recipient_address='Calle 1', payment_method='STRIPE')

        assert Remittance.objects.count() == 0 and Payment.objects.count() == 0

    def test_a_tracking_id_clash_is_retried(self, user, monkeypatch):
        first = create(user).data['remittance']['tracking_id']
        ids = iter([first, first, 'RR-20261004-NEWID']) 
        monkeypatch.setattr(services, 'generate_tracking_id', lambda: next(ids))

        response = create(user)

        assert response.status_code == 201
        assert response.data['remittance']['tracking_id'] == 'RR-20261004-NEWID'
        assert Remittance.objects.count() == 2 and Payment.objects.count() == 2

    def test_it_gives_up_cleanly_if_it_can_never_find_a_free_id(self, user, monkeypatch):
        taken = create(user).data['remittance']['tracking_id']
        monkeypatch.setattr(services, 'generate_tracking_id', lambda: taken)

        with pytest.raises(RuntimeError):
            create_remittance(user, amount=Decimal('50'), currency='USD', recipient_name='Rosa',
                              recipient_phone='+5351234567', delivery_method='CASH_DELIVERY',
                              recipient_address='Calle 1', payment_method='STRIPE')

        assert Remittance.objects.count() == 1 and Payment.objects.count() == 1  # the failed attempt left nothing


class TestWhenThePaymentIsSettled:
    def settle(self, user, remittance_data, outcome):
        reference = remittance_data['payment']['reference']
        return client_for(user).post(f'/api/payments/mock/{reference}/confirm/', {'outcome': outcome}, format='json')

    def test_a_confirmed_payment_marks_the_remittance_paid(self, user):
        data = create(user).data

        response = self.settle(user, data, 'succeeded')

        assert response.status_code == 200
        assert Remittance.objects.get().status == Remittance.Status.PAID

    def test_a_failed_payment_cancels_the_request(self, user):
        data = create(user).data

        self.settle(user, data, 'failed')

        assert Remittance.objects.get().status == Remittance.Status.CANCELLED
        assert Payment.objects.get().status == PaymentStatus.FAILED

    def test_confirming_twice_changes_nothing_more(self, user):
        data = create(user).data
        self.settle(user, data, 'succeeded')
        self.settle(user, data, 'failed')  # a late contradictory event

        assert Remittance.objects.get().status == Remittance.Status.PAID

    def test_an_unpaid_remittance_stays_pending(self, user):
        create(user)

        assert Remittance.objects.get().status == Remittance.Status.PENDING_PAYMENT
