from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.exchange_rates.models import ExchangeRate
from apps.payments.models import Payment
from apps.users.models import User

from .models import Remittance

pytestmark = pytest.mark.django_db

URL = '/api/remittances/quote/'
EXPECTED_KEYS = {
    'currency', 'target_currency', 'amount', 'base_rate', 'spread_percent', 'effective_rate',
    'amount_cup', 'is_vip_rate', 'standard_effective_rate', 'saving_cup',
}


@pytest.fixture(autouse=True)
def usd_rate():
    return ExchangeRate.objects.create(
        currency='USD', base_rate=Decimal('700'), standard_spread_percent=Decimal('5'), vip_spread_percent=Decimal('2'),
    )


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


def quote(client=None, **body):
    return (client or client_for()).post(URL, {'amount': '100', 'currency': 'USD', **body}, format='json')


class TestStandardCustomer:
    def test_an_anonymous_visitor_gets_the_standard_rate(self):
        response = quote()

        assert response.status_code == 200
        assert response.data == {
            'currency': 'USD', 'target_currency': 'CUP', 'amount': '100.00', 'base_rate': '700.000000',
            'spread_percent': '5.00', 'effective_rate': '665.0000', 'amount_cup': '66500.00',
            'is_vip_rate': False, 'standard_effective_rate': None, 'saving_cup': None,
        }

    def test_a_free_user_gets_exactly_the_same_as_an_anonymous_visitor(self):
        assert quote(client_for(make_user())).data == quote().data

    def test_nothing_about_the_vip_rate_leaks_to_a_standard_customer(self):
        body = quote(client_for(make_user())).content.decode()

        assert '686' not in body and '68600' not in body and '"2.00"' not in body

    def test_an_expired_vip_is_a_standard_customer(self):
        user = make_user(vip_days=30)
        user.profile.membership_expires_at = timezone.now() - timedelta(days=1)
        user.profile.save()

        assert quote(client_for(user)).data['is_vip_rate'] is False

    def test_the_response_has_exactly_the_documented_fields_and_is_not_cached(self):
        response = quote()

        assert set(response.data) == EXPECTED_KEYS
        assert response['Cache-Control'] == 'no-store'


class TestMember:
    def test_a_member_gets_the_preferential_rate_automatically(self):
        data = quote(client_for(make_user(vip_days=30))).data

        assert data['is_vip_rate'] is True
        assert data['spread_percent'] == '2.00'
        assert data['effective_rate'] == '686.0000'
        assert data['amount_cup'] == '68600.00'

    def test_a_member_sees_how_much_they_save(self):
        data = quote(client_for(make_user(vip_days=30))).data

        assert data['standard_effective_rate'] == '665.0000'
        assert data['saving_cup'] == '2100.00'  # 68600 - 66500

    def test_buying_vip_changes_the_next_quote(self):
        user = make_user()
        client = client_for(user)
        assert quote(client).data['effective_rate'] == '665.0000'

        user.profile.is_membership_active = True
        user.profile.membership_expires_at = timezone.now() + timedelta(days=30)
        user.profile.save()

        assert quote(client).data['effective_rate'] == '686.0000'


class TestExactMoney:
    def test_decimals_and_rounding_follow_the_documented_rules(self, usd_rate):
        usd_rate.base_rate = Decimal('700.123456')
        usd_rate.standard_spread_percent = Decimal('3.33')
        usd_rate.save()

        data = quote(amount='37.45').data

        assert data['effective_rate'] == '676.8093'
        assert data['amount_cup'] == '25346.50'  # exact 25346.508285, rounded DOWN

    def test_the_amount_can_be_a_json_number_or_a_string(self):
        assert quote(amount=100).data['amount_cup'] == quote(amount='100').data['amount_cup'] == '66500.00'
        assert quote(amount=37.5).data['amount'] == '37.50'

    def test_a_change_of_rate_by_the_admin_applies_to_the_next_quote(self, usd_rate):
        assert quote().data['amount_cup'] == '66500.00'

        usd_rate.base_rate = Decimal('800')
        usd_rate.save()

        assert quote().data['amount_cup'] == '76000.00'

    def test_euro_uses_its_own_rate(self):
        ExchangeRate.objects.create(currency='EUR', base_rate=Decimal('760'), standard_spread_percent=Decimal('5'),
                                    vip_spread_percent=Decimal('2'))

        data = quote(currency='EUR').data

        assert (data['currency'], data['effective_rate'], data['amount_cup']) == ('EUR', '722.0000', '72200.00')


class TestValidation:
    @pytest.mark.parametrize('body, field, fragment', [
        ({'amount': None}, 'amount', 'Ingresa el monto'),
        ({'amount': ''}, 'amount', 'monto válido'),
        ({'amount': 'abc'}, 'amount', 'monto válido'),
        ({'amount': '0'}, 'amount', 'mínimo'),
        ({'amount': '-5'}, 'amount', 'mínimo'),
        ({'amount': '0.99'}, 'amount', 'mínimo'),
        ({'amount': '10000.01'}, 'amount', 'máximo'),
        ({'amount': '10.123'}, 'amount', '2 decimales'),
        ({'amount': '1e3'}, 'amount', 'monto válido'),
        ({'amount': '+5'}, 'amount', 'monto válido'),
        ({'amount': 'NaN'}, 'amount', 'monto válido'),
        ({'amount': 'Infinity'}, 'amount', 'monto válido'),
        ({'amount': '0x10'}, 'amount', 'monto válido'),
        ({'amount': '10,50'}, 'amount', 'monto válido'),
        ({'currency': 'MXN'}, 'currency', 'USD o EUR'),
        ({'currency': ''}, 'currency', 'USD o EUR'),
    ])
    def test_invalid_input_is_rejected_in_spanish(self, body, field, fragment):
        response = quote(**body)

        assert response.status_code == 400
        assert fragment in response.data[field][0]

    def test_missing_fields(self):
        response = client_for().post(URL, {}, format='json')

        assert response.status_code == 400
        assert set(response.data) == {'amount', 'currency'}

    def test_the_limits_are_inclusive(self):
        assert quote(amount='1.00').status_code == 200
        assert quote(amount='10000.00').status_code == 200

    def test_the_limits_are_configurable(self, settings):
        settings.REMITTANCE_MIN_AMOUNT = '20'
        settings.REMITTANCE_MAX_AMOUNT = '500'

        assert quote(amount='19.99').status_code == 400
        assert quote(amount='20').status_code == 200
        assert quote(amount='500.01').status_code == 400

    def test_no_active_rate_for_the_currency_is_a_clear_field_error(self):
        response = quote(currency='EUR')  # only USD is configured here

        assert response.status_code == 400
        assert 'No hay una tasa de cambio disponible para EUR' in response.data['currency'][0]

    def test_a_deactivated_rate_cannot_be_quoted(self, usd_rate):
        usd_rate.is_active = False
        usd_rate.save()

        assert quote().status_code == 400


class TestAccess:
    def test_it_is_post_only(self):
        assert client_for().get(URL).status_code == 405

    def test_an_expired_token_is_a_401_so_the_client_refreshes_it(self):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION='Bearer token-vencido')

        assert quote(client).status_code == 401

    def test_quoting_stores_nothing(self):
        quote()
        quote(client_for(make_user(vip_days=30)))

        assert Remittance.objects.count() == 0 and Payment.objects.count() == 0
