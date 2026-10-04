from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.users.models import User

from .models import ExchangeRate

pytestmark = pytest.mark.django_db

URL = '/api/exchange-rates/'
EXPECTED_KEYS = {
    'currency', 'target_currency', 'base_rate', 'updated_at', 'spread_percent',
    'effective_rate', 'standard_effective_rate', 'is_vip_rate',
}


def make_rate(currency='USD', base='700', standard='5', vip='2', active=True):
    return ExchangeRate.objects.create(
        currency=currency, base_rate=Decimal(base), standard_spread_percent=Decimal(standard),
        vip_spread_percent=Decimal(vip), is_active=active,
    )


def client_for(user=None):
    client = APIClient()
    if user:  # real JWT, so the full authentication path is exercised
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return client


def make_user(email='ana@example.com', vip=None, **extra):
    user = User.objects.create_user(username=email, email=email, password='x', **extra)
    if vip is not None:
        user.profile.is_membership_active = True
        user.profile.membership_expires_at = timezone.now() + timedelta(days=vip)
        user.profile.save()
    return user


class TestAnonymousAndFreeUsers:
    def test_anonymous_sees_the_standard_rate(self):
        make_rate()
        response = client_for().get(URL)

        assert response.status_code == 200
        rate = response.data[0]
        assert rate['effective_rate'] == '665.0000'
        assert rate['standard_effective_rate'] == '665.0000'
        assert rate['spread_percent'] == '5.00'
        assert rate['is_vip_rate'] is False
        assert rate['base_rate'] == '700.000000'

    def test_only_the_documented_fields_are_exposed(self):
        make_rate()

        assert set(client_for().get(URL).data[0]) == EXPECTED_KEYS

    def test_the_vip_margin_is_never_revealed_to_a_non_member(self):
        make_rate(standard='5', vip='2')
        body = client_for(make_user()).get(URL).content.decode()

        assert '686' not in body  # the VIP effective rate
        assert '"2.00"' not in body  # the VIP spread

    def test_a_free_user_gets_the_same_as_anonymous(self):
        make_rate()

        assert client_for(make_user()).get(URL).data == client_for().get(URL).data

    def test_an_admin_who_is_not_a_member_gets_the_standard_rate(self):
        make_rate()
        admin = User.objects.create_superuser(username='a@a.com', email='a@a.com', password='x')

        assert client_for(admin).get(URL).data[0]['is_vip_rate'] is False


class TestMembers:
    def test_an_active_vip_sees_the_preferential_rate(self):
        make_rate(base='700', standard='5', vip='2')
        rate = client_for(make_user(vip=30)).get(URL).data[0]

        assert rate['effective_rate'] == '686.0000'
        assert rate['spread_percent'] == '2.00'
        assert rate['is_vip_rate'] is True
        assert rate['standard_effective_rate'] == '665.0000'  # lets the UI show the saving

    def test_an_expired_vip_gets_the_standard_rate(self):
        make_rate()
        user = make_user(vip=30)
        user.profile.membership_expires_at = timezone.now() - timedelta(days=1)
        user.profile.save()

        rate = client_for(user).get(URL).data[0]
        assert rate['effective_rate'] == '665.0000'
        assert rate['is_vip_rate'] is False


class TestContent:
    def test_only_active_rates_in_a_stable_order(self):
        make_rate('USD')
        make_rate('EUR', base='750')
        make_rate('USD', active=False, base='500')

        assert [r['currency'] for r in client_for().get(URL).data] == ['EUR', 'USD']

    def test_no_rates_configured_is_an_empty_list_not_an_error(self):
        response = client_for().get(URL)

        assert response.status_code == 200
        assert response.data == []

    def test_an_admin_change_is_visible_on_the_next_request(self):
        rate = make_rate(base='700')
        client = client_for()
        assert client.get(URL).data[0]['effective_rate'] == '665.0000'

        rate.base_rate = Decimal('800')
        rate.save()

        assert client.get(URL).data[0]['effective_rate'] == '760.0000'

    def test_the_response_is_never_cached(self):
        assert client_for().get(URL)['Cache-Control'] == 'no-store'

    def test_a_single_query_for_an_anonymous_visitor(self, django_assert_num_queries):
        make_rate()
        make_rate('EUR', base='750')

        with django_assert_num_queries(1):
            client_for().get(URL)


class TestAccess:
    def test_it_is_read_only(self):
        assert client_for().post(URL, {}, format='json').status_code == 405

    def test_an_expired_or_invalid_token_is_a_401_so_the_client_refreshes_it(self):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION='Bearer token-vencido')

        assert client.get(URL).status_code == 401
