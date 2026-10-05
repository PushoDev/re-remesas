from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.users.models import User

from .models import ExchangeRate
from .services import convert

pytestmark = pytest.mark.django_db

LIST = '/api/admin/exchange-rates/'
BODY = {'currency': 'USD', 'base_rate': '700', 'standard_spread_percent': '5', 'vip_spread_percent': '2'}


def detail(pk):
    return f'{LIST}{pk}/'


@pytest.fixture
def anon():
    return APIClient()


@pytest.fixture
def customer():
    user = User.objects.create_user(username='ana@example.com', email='ana@example.com', password='x')
    client = APIClient()
    client.force_authenticate(user)
    return client


@pytest.fixture
def admin():
    user = User.objects.create_superuser(username='admin@example.com', email='admin@example.com', password='x')
    client = APIClient()
    client.force_authenticate(user)
    return client


@pytest.fixture
def rate(admin):
    return ExchangeRate.objects.get(pk=admin.post(LIST, BODY, format='json').data['id'])


class TestPermissions:
    @pytest.mark.parametrize('method, path', [
        ('get', LIST), ('post', LIST), ('get', detail(1)), ('patch', detail(1)),
        ('delete', detail(1)), ('get', detail(1) + 'history/'),
    ])
    def test_anonymous_gets_401(self, anon, method, path):
        assert getattr(anon, method)(path).status_code == 401

    @pytest.mark.parametrize('method, path', [
        ('get', LIST), ('post', LIST), ('get', detail(1)), ('patch', detail(1)),
        ('delete', detail(1)), ('get', detail(1) + 'history/'),
    ])
    def test_a_regular_customer_gets_403(self, customer, method, path):
        assert getattr(customer, method)(path).status_code == 403

    def test_a_customer_cannot_create_or_change_anything(self, customer, admin):
        rate_id = admin.post(LIST, BODY, format='json').data['id']

        assert customer.post(LIST, {**BODY, 'currency': 'EUR'}, format='json').status_code == 403
        assert customer.patch(detail(rate_id), {'base_rate': '1'}, format='json').status_code == 403
        assert customer.delete(detail(rate_id)).status_code == 403
        assert ExchangeRate.objects.get(pk=rate_id).base_rate == Decimal('700')

    def test_admin_can_list(self, admin):
        assert admin.get(LIST).status_code == 200


class TestCreate:
    def test_admin_creates_a_rate(self, admin):
        response = admin.post(LIST, BODY, format='json')

        assert response.status_code == 201
        assert response.data['effective_rate_standard'] == '665.0000'
        assert response.data['effective_rate_vip'] == '686.0000'
        assert response.data['updated_by_email'] == 'admin@example.com'
        assert ExchangeRate.objects.get().history.count() == 1

    def test_invalid_data_is_rejected_in_spanish(self, admin):
        response = admin.post(LIST, {**BODY, 'base_rate': '-1', 'vip_spread_percent': '9'}, format='json')

        assert response.status_code == 400
        assert 'mayor que 0' in response.data['base_rate'][0]
        assert ExchangeRate.objects.count() == 0

    def test_a_second_active_rate_for_the_same_currency_is_rejected(self, admin, rate):
        response = admin.post(LIST, BODY, format='json')

        assert response.status_code == 400
        assert 'Ya existe una tasa activa para USD' in response.data['is_active'][0]


class TestReadAndFilter:
    def test_list_and_detail(self, admin, rate):
        assert admin.get(LIST).data[0]['id'] == rate.pk
        assert admin.get(detail(rate.pk)).data['base_rate'] == '700.000000'

    def test_unknown_id_is_404(self, admin):
        assert admin.get(detail(9999)).status_code == 404

    def test_filters_by_currency_and_by_active(self, admin, rate):
        admin.post(LIST, {**BODY, 'currency': 'EUR', 'base_rate': '750'}, format='json')
        admin.post(LIST, {**BODY, 'is_active': False, 'base_rate': '600'}, format='json')

        assert {r['currency'] for r in admin.get(LIST, {'currency': 'eur'}).data} == {'EUR'}
        assert len(admin.get(LIST, {'is_active': 'true'}).data) == 2
        inactive = admin.get(LIST, {'is_active': 'false'}).data
        assert len(inactive) == 1 and inactive[0]['is_active'] is False


class TestUpdate:
    def test_patch_changes_only_what_is_sent_and_adds_history(self, admin, rate):
        response = admin.patch(detail(rate.pk), {'base_rate': '720'}, format='json')

        assert response.status_code == 200
        assert response.data['base_rate'] == '720.000000'
        assert response.data['standard_spread_percent'] == '5.00'
        assert rate.history.count() == 2

    def test_the_change_applies_to_the_next_quote_immediately(self, admin, rate):
        assert convert(Decimal('10'), 'USD', False).amount_cup == Decimal('6650.00')

        admin.patch(detail(rate.pk), {'base_rate': '800'}, format='json')

        assert convert(Decimal('10'), 'USD', False).amount_cup == Decimal('7600.00')

    def test_updated_at_moves_forward(self, admin, rate):
        before = admin.get(detail(rate.pk)).data['updated_at']

        after = admin.patch(detail(rate.pk), {'standard_spread_percent': '6'}, format='json').data['updated_at']

        assert after > before

    def test_vip_margin_above_the_standard_one_is_rejected(self, admin, rate):
        response = admin.patch(detail(rate.pk), {'vip_spread_percent': '9'}, format='json')

        assert response.status_code == 400
        assert ExchangeRate.objects.get(pk=rate.pk).vip_spread_percent == Decimal('2')

    def test_put_is_not_exposed(self, admin, rate):
        assert admin.put(detail(rate.pk), BODY, format='json').status_code == 405


class TestDeactivate:
    def test_delete_deactivates_and_keeps_the_history(self, admin, rate):
        response = admin.delete(detail(rate.pk))

        assert response.status_code == 204
        rate.refresh_from_db()
        assert rate.is_active is False
        assert [entry.is_active for entry in rate.history.all()] == [False, True]  # newest first

    def test_a_deactivated_currency_can_get_a_new_active_rate(self, admin, rate):
        admin.delete(detail(rate.pk))

        assert admin.post(LIST, {**BODY, 'base_rate': '710'}, format='json').status_code == 201
        assert ExchangeRate.objects.filter(currency='USD').count() == 2

    def test_after_deactivating_there_is_no_active_rate_to_quote(self, admin, rate):
        admin.delete(detail(rate.pk))

        from .services import RateNotAvailable
        with pytest.raises(RateNotAvailable):
            convert(Decimal('10'), 'USD', False)


class TestHistory:
    def test_lists_changes_newest_first_with_author(self, admin, rate):
        admin.patch(detail(rate.pk), {'base_rate': '720'}, format='json')
        admin.patch(detail(rate.pk), {'base_rate': '730'}, format='json')

        response = admin.get(detail(rate.pk) + 'history/')

        assert response.status_code == 200
        assert [e['base_rate'] for e in response.data] == ['730.000000', '720.000000', '700.000000']
        assert response.data[0]['changed_by_email'] == 'admin@example.com'

    def test_unknown_rate_is_404(self, admin):
        assert admin.get(detail(9999) + 'history/').status_code == 404
