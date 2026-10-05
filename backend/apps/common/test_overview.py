from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.exchange_rates.models import ExchangeRate
from apps.remittances.models import Remittance
from apps.remittances.services import create_remittance
from apps.users.models import User

pytestmark = pytest.mark.django_db

URL = '/api/admin/overview/'


@pytest.fixture(autouse=True)
def usd_rate():
    return ExchangeRate.objects.create(
        currency='USD', base_rate=Decimal('700'), standard_spread_percent=Decimal('5'), vip_spread_percent=Decimal('2'),
    )


def make_user(email='ana@example.com', **extra):
    return User.objects.create_user(username=email, email=email, password='x', **extra)


def client_for(user=None):
    client = APIClient()
    if user:
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return client


@pytest.fixture
def admin():
    return client_for(make_user('admin@example.com', is_staff=True))


def remittance(user, status='PENDING_PAYMENT', method='STRIPE', reference=''):
    created, _ = create_remittance(
        user, amount=Decimal('100'), currency='USD', recipient_name='Rosa', recipient_phone='+5351234567',
        delivery_method='CASH_DELIVERY', recipient_address='Calle 1', payment_method=method,
    )
    Remittance.objects.filter(pk=created.pk).update(status=status, payment_reference=reference)
    return created


def make_vip(user, expires_in_days=30, active=True):
    user.profile.is_membership_active = active
    user.profile.membership_expires_at = None if expires_in_days is None else timezone.now() + timedelta(days=expires_in_days)
    user.profile.save()


class TestAccess:
    def test_anonymous_gets_401(self):
        assert client_for().get(URL).status_code == 401

    def test_a_customer_gets_403(self):
        assert client_for(make_user()).get(URL).status_code == 403

    def test_staff_gets_200_and_it_is_never_cached(self, admin):
        response = admin.get(URL)

        assert response.status_code == 200
        assert response['Cache-Control'] == 'no-store'

    def test_it_is_read_only(self, admin):
        assert admin.post(URL, {}, format='json').status_code == 405


class TestCounters:
    def test_an_empty_system_is_all_zeros(self, admin):
        data = admin.get(URL).data

        assert data['remittances'] == {
            'total': 0, 'pending_payment': 0, 'paid': 0, 'completed': 0, 'cancelled': 0, 'needs_review': 0}
        assert data['recharge_orders'] == {'total': 0}
        assert data['memberships'] == {'active_vip': 0}
        assert data['generated_at']

    def test_remittances_are_counted_by_state_across_all_customers(self, admin):
        ana, luis = make_user('ana@example.com'), make_user('luis@example.com')
        remittance(ana, 'PENDING_PAYMENT'), remittance(luis, 'PENDING_PAYMENT'), remittance(ana, 'PENDING_PAYMENT')
        remittance(ana, 'PAID'), remittance(luis, 'PAID')
        remittance(luis, 'COMPLETED')
        remittance(ana, 'CANCELLED'), remittance(luis, 'CANCELLED')

        counts = admin.get(URL).data['remittances']

        assert counts == {
            'total': 8, 'pending_payment': 3, 'paid': 2, 'completed': 1, 'cancelled': 2, 'needs_review': 0}

    def test_the_four_states_always_add_up_to_the_total(self, admin):
        user = make_user()
        for status in ['PENDING_PAYMENT', 'PAID', 'PAID', 'COMPLETED', 'CANCELLED', 'CANCELLED', 'CANCELLED']:
            remittance(user, status)

        counts = admin.get(URL).data['remittances']

        assert counts['pending_payment'] + counts['paid'] + counts['completed'] + counts['cancelled'] == counts['total']

    def test_needs_review_counts_manual_payments_with_a_reference_still_pending(self, admin):
        user = make_user()
        remittance(user, method='ZELLE', reference='ZEL-123')        # waiting for the admin: counts
        remittance(user, method='ZELLE', reference='')               # no proof sent yet: does not
        remittance(user, method='STRIPE', reference='irrelevant')    # gateway payment: nobody reviews it
        remittance(user, status='PAID', method='ZELLE', reference='ZEL-456')  # already decided: does not
        remittance(user, method='CASH', reference='RECIBO-9')        # counts

        assert admin.get(URL).data['remittances']['needs_review'] == 2

    def test_active_vip_excludes_expired_and_switched_off(self, admin):
        active, expired, off, open_ended = (make_user(f'u{i}@example.com') for i in range(4))
        make_vip(active, 30)
        make_vip(expired, -1)
        make_vip(off, 30, active=False)
        make_vip(open_ended, None)  # VIP granted without an end date
        make_user('free@example.com')

        assert admin.get(URL).data['memberships']['active_vip'] == 2

    def test_a_new_state_change_shows_in_the_next_reading(self, admin):
        user = make_user()
        created = remittance(user)
        assert admin.get(URL).data['remittances']['paid'] == 0

        Remittance.objects.filter(pk=created.pk).update(status='PAID')

        data = admin.get(URL).data['remittances']
        assert (data['pending_payment'], data['paid']) == (0, 1)

    def test_it_stays_cheap_however_much_data_there_is(self, admin, django_assert_max_num_queries):
        user = make_user()
        for _ in range(10):
            remittance(user)

        with django_assert_max_num_queries(5):  # user, remittances, vip (+ recharges when it exists)
            admin.get(URL)
