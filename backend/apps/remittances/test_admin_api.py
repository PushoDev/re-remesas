from decimal import Decimal

import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.exchange_rates.models import ExchangeRate
from apps.payments.models import PaymentStatus
from apps.users.models import User

from .models import Remittance
from .services import create_remittance

pytestmark = pytest.mark.django_db

LIST = '/api/admin/remittances/'


def detail(remittance):
    return f'{LIST}{remittance.tracking_id}/'


def status_url(remittance):
    return f'{LIST}{remittance.tracking_id}/status/'


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
    return client_for(User.objects.create_user(username='admin@example.com', email='admin@example.com',
                                               password='x', is_staff=True))


@pytest.fixture
def customer():
    return make_user()


def new_remittance(user, method='STRIPE', amount='100', name='Rosa Pérez', phone='+5351234567'):
    remittance, _ = create_remittance(
        user, amount=Decimal(amount), currency='USD', recipient_name=name, recipient_phone=phone,
        delivery_method='CASH_DELIVERY', recipient_address='Calle 1', payment_method=method,
    )
    return remittance


class TestPermissions:
    @pytest.mark.parametrize('method, path', [
        ('get', LIST), ('get', f'{LIST}RR-20261004-AAAAA/'), ('patch', f'{LIST}RR-20261004-AAAAA/status/'),
    ])
    def test_anonymous_gets_401(self, method, path):
        assert getattr(client_for(), method)(path).status_code == 401

    def test_a_customer_gets_403_everywhere(self, customer):
        remittance = new_remittance(customer)
        client = client_for(customer)

        assert client.get(LIST).status_code == 403
        assert client.get(detail(remittance)).status_code == 403
        assert client.patch(status_url(remittance), {'status': 'CANCELLED', 'note': 'x'}, format='json').status_code == 403
        assert Remittance.objects.get().status == 'PENDING_PAYMENT'

    def test_staff_who_is_not_superuser_can_work(self, admin, customer):
        new_remittance(customer)

        assert admin.get(LIST).status_code == 200

    def test_the_inbox_is_read_only(self, admin, customer):
        remittance = new_remittance(customer)

        assert admin.post(LIST, {}, format='json').status_code == 405
        assert admin.put(detail(remittance), {}, format='json').status_code == 405
        assert admin.delete(detail(remittance)).status_code == 405


class TestInbox:
    def test_it_lists_everyones_remittances_newest_first(self, admin, customer):
        other = make_user('otro@example.com')
        first, second = new_remittance(customer), new_remittance(other)

        data = admin.get(LIST).data

        assert data['count'] == 2
        assert [r['tracking_id'] for r in data['results']] == [second.tracking_id, first.tracking_id]

    def test_each_row_has_what_the_inbox_needs(self, admin, customer):
        new_remittance(customer, method='ZELLE')
        row = admin.get(LIST).data['results'][0]

        assert row['sender_email'] == 'ana@example.com'
        assert (row['status'], row['status_display']) == ('PENDING_PAYMENT', 'Pendiente de pago')
        assert (row['payment_provider'], row['payment_status'], row['payment_method']) == ('MANUAL', 'PENDING', 'ZELLE')
        assert (row['amount_sent'], row['currency'], row['amount_cup']) == ('100.00', 'USD', '66500.00')
        assert row['has_proof'] is False
        assert 'id' not in row

    def test_an_empty_inbox_is_a_normal_page(self, admin):
        assert admin.get(LIST).data == {'count': 0, 'next': None, 'previous': None, 'results': []}

    def test_it_is_paginated(self, admin, customer):
        for _ in range(12):
            new_remittance(customer)

        first, second = admin.get(LIST).data, admin.get(LIST, {'page': 2}).data

        assert (first['count'], len(first['results']), len(second['results'])) == (12, 10, 2)

    @pytest.mark.parametrize('status', ['PENDING_PAYMENT', 'PAID', 'COMPLETED', 'CANCELLED'])
    def test_it_filters_by_each_of_the_four_states(self, admin, customer, status):
        for state in ['PENDING_PAYMENT', 'PAID', 'COMPLETED', 'CANCELLED']:
            Remittance.objects.filter(pk=new_remittance(customer).pk).update(status=state)

        data = admin.get(LIST, {'status': status}).data

        assert data['count'] == 1
        assert data['results'][0]['status'] == status

    def test_an_unknown_status_is_a_400(self, admin):
        response = admin.get(LIST, {'status': 'LOST'})

        assert response.status_code == 400 and 'Estado no válido' in response.data['status'][0]

    def test_it_searches_by_tracking_id_ignoring_case_and_partial(self, admin, customer):
        wanted = new_remittance(customer)
        new_remittance(customer)

        found = admin.get(LIST, {'search': wanted.tracking_id[-5:].lower()}).data

        assert wanted.tracking_id in [r['tracking_id'] for r in found['results']]

    def test_it_searches_by_sender_email_recipient_name_and_phone(self, admin):
        ana, luis = make_user('ana@example.com'), make_user('luis@example.com')
        new_remittance(ana, name='Rosa Pérez', phone='+5351111111')
        target = new_remittance(luis, name='Marta Gómez', phone='+5352222222')

        for term in ('luis@', 'marta', '5222222'):
            data = admin.get(LIST, {'search': term}).data
            assert [r['tracking_id'] for r in data['results']] == [target.tracking_id], term

    def test_filter_and_search_combine(self, admin, customer):
        paid = new_remittance(customer, name='Rosa Pérez')
        Remittance.objects.filter(pk=paid.pk).update(status='PAID')
        new_remittance(customer, name='Rosa Pérez')

        data = admin.get(LIST, {'status': 'PAID', 'search': 'rosa'}).data

        assert [r['tracking_id'] for r in data['results']] == [paid.tracking_id]

    def test_it_orders_by_amount(self, admin, customer):
        for amount in ('50', '300', '120'):
            new_remittance(customer, amount=amount)

        descending = [r['amount_sent'] for r in admin.get(LIST, {'ordering': '-amount_sent'}).data['results']]
        ascending = [r['amount_cup'] for r in admin.get(LIST, {'ordering': 'amount_cup'}).data['results']]

        assert descending == ['300.00', '120.00', '50.00']
        assert ascending == ['33250.00', '79800.00', '199500.00']

    def test_an_unknown_ordering_is_a_400(self, admin):
        assert admin.get(LIST, {'ordering': 'sender__password'}).status_code == 400

    def test_the_number_of_queries_does_not_grow_with_the_inbox(self, admin, customer, django_assert_max_num_queries):
        for _ in range(12):
            new_remittance(customer)

        with django_assert_max_num_queries(4):  # user, count, page
            admin.get(LIST, {'page_size': 12})


class TestDetail:
    def test_it_shows_everything_needed_to_decide(self, admin, customer):
        remittance = new_remittance(customer, method='ZELLE')
        data = admin.get(detail(remittance)).data

        assert data['tracking_id'] == remittance.tracking_id
        assert data['sender'] == {
            'email': 'ana@example.com', 'first_name': '', 'last_name': '', 'membership_status': 'FREE'}
        assert (data['recipient_name'], data['recipient_phone'], data['recipient_address']) == (
            'Rosa Pérez', '+5351234567', 'Calle 1')
        assert (data['effective_rate_used'], data['amount_cup']) == ('665.0000', '66500.00')
        assert (data['payment']['provider'], data['payment']['status'], data['payment']['method']) == (
            'MANUAL', 'PENDING', 'ZELLE')
        assert data['payment']['confirmed_by_email'] is None
        assert data['payment_reference'] == '' and data['has_proof_file'] is False
        assert 'id' not in data

    def test_the_history_is_included_oldest_first_with_who_and_why(self, admin, customer):
        remittance = new_remittance(customer, method='ZELLE')
        admin.patch(status_url(remittance), {'status': 'PAID'}, format='json')

        log = admin.get(detail(remittance)).data['status_log']

        assert [(e['from_status'], e['to_status'], e['source']) for e in log] == [
            ('', 'PENDING_PAYMENT', 'CUSTOMER'), ('PENDING_PAYMENT', 'PAID', 'PAYMENT')]
        assert log[0]['changed_by_email'] == 'ana@example.com'
        assert log[1]['changed_by_email'] == 'admin@example.com'
        assert log[1]['source_display'] == 'Pago'

    def test_the_sender_membership_is_visible(self, admin):
        from datetime import timedelta
        from django.utils import timezone
        vip = make_user('vip@example.com')
        vip.profile.is_membership_active = True
        vip.profile.membership_expires_at = timezone.now() + timedelta(days=30)
        vip.profile.save()
        remittance = new_remittance(vip)

        data = admin.get(detail(remittance)).data

        assert data['sender']['membership_status'] == 'VIP' and data['is_vip_rate'] is True

    @pytest.mark.parametrize('method, status, expected', [
        ('ZELLE', 'PENDING_PAYMENT', ['confirm_payment', 'cancel']),
        ('STRIPE', 'PENDING_PAYMENT', ['cancel']),
        ('ZELLE', 'PAID', ['complete', 'cancel']),
        ('STRIPE', 'PAID', ['complete', 'cancel']),
        ('ZELLE', 'COMPLETED', []),
        ('ZELLE', 'CANCELLED', []),
    ])
    def test_it_says_which_actions_are_possible_now(self, admin, customer, method, status, expected):
        remittance = new_remittance(customer, method=method)
        Remittance.objects.filter(pk=remittance.pk).update(status=status)

        assert admin.get(detail(remittance)).data['allowed_actions'] == expected

    def test_the_id_works_in_lowercase(self, admin, customer):
        remittance = new_remittance(customer)

        assert admin.get(f'{LIST}{remittance.tracking_id.lower()}/').status_code == 200

    def test_unknown_id_is_404(self, admin):
        assert admin.get(f'{LIST}RR-20261004-ZZZZZ/').status_code == 404


class TestChangingTheStatus:
    def patch(self, admin, remittance, status, note=''):
        return admin.patch(status_url(remittance), {'status': status, 'note': note}, format='json')

    def test_confirming_a_manual_payment_marks_it_paid(self, admin, customer):
        remittance = new_remittance(customer, method='ZELLE')

        response = self.patch(admin, remittance, 'PAID')

        assert response.status_code == 200
        assert response.data['status'] == 'PAID'
        assert response.data['payment']['status'] == 'SUCCEEDED'
        assert response.data['payment']['confirmed_by_email'] == 'admin@example.com'
        assert response.data['allowed_actions'] == ['complete', 'cancel']

    def test_a_gateway_payment_cannot_be_marked_paid_by_hand(self, admin, customer):
        remittance = new_remittance(customer, method='STRIPE')

        response = self.patch(admin, remittance, 'PAID')

        assert response.status_code == 400
        assert 'pasarela' in response.data['status'][0]
        assert Remittance.objects.get().status == 'PENDING_PAYMENT'

    def test_completing_a_paid_remittance(self, admin, customer):
        remittance = new_remittance(customer, method='ZELLE')
        self.patch(admin, remittance, 'PAID')

        response = self.patch(admin, remittance, 'COMPLETED', 'Entregado a la hermana')

        assert response.status_code == 200 and response.data['status'] == 'COMPLETED'
        assert response.data['status_log'][-1]['note'] == 'Entregado a la hermana'
        assert response.data['allowed_actions'] == []

    def test_an_unpaid_remittance_cannot_be_completed(self, admin, customer):
        remittance = new_remittance(customer)

        response = self.patch(admin, remittance, 'COMPLETED')

        assert response.status_code == 400
        assert 'Pendiente de pago' in response.data['status'][0] and 'Completado' in response.data['status'][0]

    def test_cancelling_needs_a_reason(self, admin, customer):
        remittance = new_remittance(customer)

        for note in ('', '   '):
            response = self.patch(admin, remittance, 'CANCELLED', note)
            assert response.status_code == 400 and 'motivo' in response.data['note'][0]

        assert Remittance.objects.get().status == 'PENDING_PAYMENT'

    def test_cancelling_with_a_reason_closes_the_payment(self, admin, customer):
        remittance = new_remittance(customer)

        response = self.patch(admin, remittance, 'CANCELLED', 'Datos incorrectos')

        assert response.status_code == 200
        assert response.data['status'] == 'CANCELLED'
        assert response.data['payment']['status'] == PaymentStatus.FAILED
        assert response.data['status_log'][-1]['note'] == 'Datos incorrectos'

    def test_repeating_an_action_is_refused(self, admin, customer):
        remittance = new_remittance(customer, method='ZELLE')
        self.patch(admin, remittance, 'PAID')

        assert self.patch(admin, remittance, 'PAID').status_code == 400
        remittance.refresh_from_db()
        assert remittance.status_log.filter(to_status='PAID').count() == 1

    def test_a_finished_remittance_cannot_be_touched(self, admin, customer):
        remittance = new_remittance(customer)
        self.patch(admin, remittance, 'CANCELLED', 'x')

        for target in ('PAID', 'COMPLETED', 'CANCELLED'):
            assert self.patch(admin, remittance, target, 'x').status_code == 400

    @pytest.mark.parametrize('body', [{}, {'status': 'LOST'}, {'status': 'PENDING_PAYMENT'}, {'status': ''}])
    def test_invalid_targets_are_a_400(self, admin, customer, body):
        remittance = new_remittance(customer)

        response = admin.patch(status_url(remittance), body, format='json')

        assert response.status_code == 400 and 'status' in response.data

    def test_the_note_has_a_length_limit(self, admin, customer):
        remittance = new_remittance(customer)

        response = self.patch(admin, remittance, 'CANCELLED', 'x' * 501)

        assert response.status_code == 400 and 'note' in response.data

    def test_the_customer_sees_the_new_state_on_their_own_side(self, admin, customer):
        remittance = new_remittance(customer, method='ZELLE')
        self.patch(admin, remittance, 'PAID')
        self.patch(admin, remittance, 'COMPLETED', 'Entregado')

        mine = client_for(customer).get(f'/api/remittances/{remittance.tracking_id}/').data

        assert (mine['status'], mine['status_display']) == ('COMPLETED', 'Completado')

    def test_an_unknown_remittance_is_404(self, admin):
        assert admin.patch(f'{LIST}RR-20261004-ZZZZZ/status/', {'status': 'COMPLETED'}, format='json').status_code == 404
