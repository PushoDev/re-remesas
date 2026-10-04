from decimal import Decimal

import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.exchange_rates.models import ExchangeRate
from apps.users.models import User

from .models import Remittance

pytestmark = pytest.mark.django_db

LIST = '/api/remittances/'
BODY = {
    'amount': '100', 'currency': 'USD', 'recipient_name': 'Rosa Pérez', 'recipient_phone': '51234567',
    'delivery_method': 'CASH_DELIVERY', 'recipient_address': 'Calle 23 #456', 'payment_method': 'STRIPE',
}


@pytest.fixture(autouse=True)
def usd_rate():
    return ExchangeRate.objects.create(
        currency='USD', base_rate=Decimal('700'), standard_spread_percent=Decimal('5'), vip_spread_percent=Decimal('2'),
    )


def make_user(email='ana@example.com'):
    return User.objects.create_user(username=email, email=email, password='x')


def client_for(user=None):
    client = APIClient()
    if user:
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return client


def request_remittance(user, **overrides):
    return client_for(user).post(LIST, {**BODY, **overrides}, format='json').data


def tracking_ids(response):
    return [item['tracking_id'] for item in response.data['results']]


@pytest.fixture
def ana():
    return make_user()


class TestAccess:
    def test_everything_requires_authentication(self):
        assert client_for().get(LIST).status_code == 401
        assert client_for().get(f'{LIST}RR-20261004-AAAAA/').status_code == 401

    def test_the_quote_path_is_not_mistaken_for_a_tracking_id(self):
        assert client_for().get(f'{LIST}quote/').status_code == 405  # POST-only, not "remittance quote"


class TestList:
    def test_an_empty_history_is_an_empty_page_not_an_error(self, ana):
        response = client_for(ana).get(LIST)

        assert response.status_code == 200
        assert response.data == {'count': 0, 'next': None, 'previous': None, 'results': []}

    def test_it_lists_only_my_remittances_newest_first(self, ana):
        other = make_user('otro@example.com')
        mine = [request_remittance(ana)['remittance']['tracking_id'] for _ in range(3)]
        request_remittance(other)

        response = client_for(ana).get(LIST)

        assert response.data['count'] == 3
        assert tracking_ids(response) == mine[::-1]

    def test_each_item_carries_what_the_history_screen_needs(self, ana):
        request_remittance(ana)
        item = client_for(ana).get(LIST).data['results'][0]

        assert item['status'] == 'PENDING_PAYMENT'
        assert item['status_display'] == 'Pendiente de pago'
        assert (item['amount_sent'], item['currency'], item['amount_cup']) == ('100.00', 'USD', '66500.00')
        assert item['recipient_name'] == 'Rosa Pérez'
        assert item['payment_method_display'] == 'Stripe'
        assert 'id' not in item and 'sender' not in item

    def test_it_is_paginated(self, ana):
        for _ in range(12):
            request_remittance(ana)

        first = client_for(ana).get(LIST).data
        second = client_for(ana).get(LIST, {'page': 2}).data

        assert (first['count'], len(first['results']), len(second['results'])) == (12, 10, 2)
        assert first['next'] and second['previous']

    def test_the_page_size_can_be_chosen_up_to_a_limit(self, ana):
        for _ in range(3):
            request_remittance(ana)

        assert len(client_for(ana).get(LIST, {'page_size': 2}).data['results']) == 2
        assert client_for(ana).get(LIST, {'page_size': 1000}).status_code == 200  # capped, not an error

    def test_it_filters_by_status(self, ana):
        paid = request_remittance(ana)
        request_remittance(ana)
        client_for(ana).post(f"/api/payments/mock/{paid['payment']['reference']}/confirm/",
                             {'outcome': 'succeeded'}, format='json')

        pending = client_for(ana).get(LIST, {'status': 'PENDING_PAYMENT'})
        done = client_for(ana).get(LIST, {'status': 'PAID'})

        assert (pending.data['count'], done.data['count']) == (1, 1)
        assert tracking_ids(done) == [paid['remittance']['tracking_id']]

    def test_an_unknown_status_is_a_clear_400(self, ana):
        response = client_for(ana).get(LIST, {'status': 'LOST'})

        assert response.status_code == 400
        assert 'Estado no válido' in response.data['status'][0]

    def test_it_searches_by_part_of_the_tracking_id_ignoring_case(self, ana):
        wanted = request_remittance(ana)['remittance']['tracking_id']
        request_remittance(ana)

        found = client_for(ana).get(LIST, {'search': wanted[-5:].lower()})

        assert wanted in tracking_ids(found)
        assert found.data['count'] >= 1

    def test_searching_cannot_reach_other_peoples_remittances(self, ana):
        other = make_user('otro@example.com')
        theirs = request_remittance(other)['remittance']['tracking_id']

        assert client_for(ana).get(LIST, {'search': theirs}).data['count'] == 0

    def test_the_number_of_queries_does_not_grow_with_the_history(self, ana, django_assert_max_num_queries):
        for _ in range(12):
            request_remittance(ana)

        with django_assert_max_num_queries(4):  # user, count, page
            client_for(ana).get(LIST, {'page_size': 12})


class TestDetail:
    def test_the_owner_sees_the_remittance_and_its_payment(self, ana):
        created = request_remittance(ana)
        tracking_id = created['remittance']['tracking_id']

        response = client_for(ana).get(f'{LIST}{tracking_id}/')

        assert response.status_code == 200
        assert response.data['tracking_id'] == tracking_id
        assert response.data['effective_rate_used'] == '665.0000'
        assert response.data['payment']['status'] == 'PENDING'
        assert response.data['payment']['checkout_url'] == created['payment']['checkout_url']

    def test_the_tracking_id_works_in_lowercase_and_with_spaces_around(self, ana):
        tracking_id = request_remittance(ana)['remittance']['tracking_id']

        assert client_for(ana).get(f'{LIST}{tracking_id.lower()}/').status_code == 200

    def test_after_paying_the_state_and_payment_are_updated(self, ana):
        created = request_remittance(ana)
        client_for(ana).post(f"/api/payments/mock/{created['payment']['reference']}/confirm/",
                             {'outcome': 'succeeded'}, format='json')

        data = client_for(ana).get(f"{LIST}{created['remittance']['tracking_id']}/").data

        assert (data['status'], data['payment']['status'], data['payment']['checkout_url']) == (
            'PAID', 'SUCCEEDED', None)

    def test_a_remittance_of_someone_else_is_a_404(self, ana):
        theirs = request_remittance(make_user('otro@example.com'))['remittance']['tracking_id']

        assert client_for(ana).get(f'{LIST}{theirs}/').status_code == 404

    def test_an_administrator_does_not_get_others_remittances_here_either(self, ana):
        admin = User.objects.create_superuser(username='a@a.com', email='a@a.com', password='x')
        tracking_id = request_remittance(ana)['remittance']['tracking_id']

        assert client_for(admin).get(f'{LIST}{tracking_id}/').status_code == 404

    @pytest.mark.parametrize('tracking_id', ['RR-20261004-ZZZZZ', 'nada', '1', 'RR-', '../../admin'])
    def test_unknown_or_malformed_ids_are_a_404(self, ana, tracking_id):
        assert client_for(ana).get(f'{LIST}{tracking_id}/').status_code in (404,)

    def test_not_found_and_not_yours_look_identical(self, ana):
        theirs = request_remittance(make_user('otro@example.com'))['remittance']['tracking_id']

        mine_missing = client_for(ana).get(f'{LIST}RR-20261004-ZZZZZ/')
        not_mine = client_for(ana).get(f'{LIST}{theirs}/')

        assert mine_missing.status_code == not_mine.status_code == 404
        assert mine_missing.data == not_mine.data

    def test_a_detail_cannot_be_modified_or_deleted(self, ana):
        tracking_id = request_remittance(ana)['remittance']['tracking_id']
        client = client_for(ana)

        for method in (client.put, client.patch, client.delete):
            assert method(f'{LIST}{tracking_id}/').status_code == 405
        assert Remittance.objects.get().status == 'PENDING_PAYMENT'
