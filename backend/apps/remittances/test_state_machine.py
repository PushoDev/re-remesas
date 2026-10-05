from decimal import Decimal

import pytest

from apps.exchange_rates.models import ExchangeRate
from apps.payments.models import PaymentStatus
from apps.payments.services import settle_payment
from apps.users.models import User

from .models import Remittance, RemittanceStatusLog
from .services import (
    TRANSITIONS,
    InvalidTransition,
    NotAManualPayment,
    NoteRequired,
    Source,
    Status,
    cancel_remittance,
    change_status,
    complete_remittance,
    confirm_manual_payment,
    create_remittance,
)

pytestmark = pytest.mark.django_db

ALL = list(Status.values)


@pytest.fixture(autouse=True)
def usd_rate():
    return ExchangeRate.objects.create(
        currency='USD', base_rate=Decimal('700'), standard_spread_percent=Decimal('5'), vip_spread_percent=Decimal('2'),
    )


@pytest.fixture
def customer():
    return User.objects.create_user(username='ana@example.com', email='ana@example.com', password='x')


@pytest.fixture
def admin():
    return User.objects.create_superuser(username='admin@example.com', email='admin@example.com', password='x')


def new_remittance(customer, method='STRIPE'):
    remittance, _ = create_remittance(
        customer, amount=Decimal('100'), currency='USD', recipient_name='Rosa Pérez', recipient_phone='+5351234567',
        delivery_method='CASH_DELIVERY', recipient_address='Calle 1', payment_method=method,
    )
    return remittance


def force_status(remittance, status):
    Remittance.objects.filter(pk=remittance.pk).update(status=status)
    remittance.refresh_from_db()
    return remittance


def trail(remittance):
    return [(e.from_status, e.to_status, e.source) for e in remittance.status_log.all()]


class TestTheTransitionTable:
    def test_the_machine_is_exactly_the_one_in_the_specification(self):
        assert TRANSITIONS == {
            'PENDING_PAYMENT': {'PAID', 'CANCELLED'},
            'PAID': {'COMPLETED', 'CANCELLED'},
            'COMPLETED': set(),
            'CANCELLED': set(),
        }

    @pytest.mark.parametrize('current', ALL)
    @pytest.mark.parametrize('wanted', ALL)
    def test_every_pair_is_allowed_or_refused_as_the_table_says(self, customer, current, wanted):
        remittance = force_status(new_remittance(customer), current)
        note = 'motivo' if wanted == 'CANCELLED' else ''

        if wanted in TRANSITIONS[current]:
            assert change_status(remittance, wanted, note=note).status == wanted
        else:
            with pytest.raises(InvalidTransition):
                change_status(remittance, wanted, note=note)
            remittance.refresh_from_db()
            assert remittance.status == current

    @pytest.mark.parametrize('final', ['COMPLETED', 'CANCELLED'])
    def test_final_states_have_no_way_out(self, customer, final):
        remittance = force_status(new_remittance(customer), final)

        for wanted in ALL:
            with pytest.raises(InvalidTransition):
                change_status(remittance, wanted, note='x')

    def test_an_unknown_status_is_refused(self, customer):
        with pytest.raises(InvalidTransition, match='no válido'):
            change_status(new_remittance(customer), 'LOST', note='x')

    def test_the_error_names_both_states_in_spanish(self, customer):
        remittance = force_status(new_remittance(customer), 'COMPLETED')

        with pytest.raises(InvalidTransition, match='Completado.*Pagado'):
            change_status(remittance, 'PAID')


class TestChangeStatusRecordsEverything:
    def test_creation_is_the_first_entry_of_the_trail(self, customer):
        remittance = new_remittance(customer)

        entry = remittance.status_log.get()
        assert (entry.from_status, entry.to_status, entry.source, entry.changed_by) == (
            '', 'PENDING_PAYMENT', Source.CUSTOMER, customer)

    def test_each_change_leaves_who_what_and_why(self, customer, admin):
        remittance = force_status(new_remittance(customer), 'PAID')

        change_status(remittance, 'COMPLETED', user=admin, note='  Entregado a la hermana  ', source=Source.ADMIN)

        entry = remittance.status_log.last()
        assert (entry.from_status, entry.to_status, entry.changed_by, entry.note, entry.source) == (
            'PAID', 'COMPLETED', admin, 'Entregado a la hermana', 'ADMIN')

    def test_the_updated_at_moves(self, customer):
        remittance = new_remittance(customer)
        before = remittance.updated_at

        changed = change_status(remittance, 'CANCELLED', note='x')

        assert changed.updated_at > before

    def test_a_refused_change_writes_nothing(self, customer):
        remittance = new_remittance(customer)

        with pytest.raises(InvalidTransition):
            change_status(remittance, 'COMPLETED')

        assert remittance.status_log.count() == 1  # only the creation


class TestCancellationNeedsAReason:
    @pytest.mark.parametrize('note', ['', '   ', '\n'])
    def test_an_administrator_must_give_a_reason(self, customer, admin, note):
        remittance = new_remittance(customer)

        with pytest.raises(NoteRequired):
            cancel_remittance(remittance, admin, note)

        remittance.refresh_from_db()
        assert remittance.status == 'PENDING_PAYMENT' and remittance.status_log.count() == 1

    def test_an_automatic_cancellation_does_not_need_one(self, customer):
        assert change_status(new_remittance(customer), 'CANCELLED', source=Source.PAYMENT).status == 'CANCELLED'


class TestWhenThePaymentIsSettled:
    def test_a_confirmed_gateway_payment_marks_it_paid_and_says_why(self, customer):
        remittance = new_remittance(customer)

        settle_payment(remittance.payment_id, True)

        remittance.refresh_from_db()
        entry = remittance.status_log.last()
        assert remittance.status == 'PAID'
        assert (entry.source, entry.changed_by, entry.note) == ('PAYMENT', None, 'Pago confirmado.')

    def test_a_failed_payment_cancels_it_and_says_why(self, customer):
        remittance = new_remittance(customer)

        settle_payment(remittance.payment_id, False)

        remittance.refresh_from_db()
        assert remittance.status == 'CANCELLED'
        assert remittance.status_log.last().note == 'El pago no se completó.'

    def test_a_repeated_confirmation_adds_no_second_entry(self, customer):
        remittance = new_remittance(customer)

        for _ in range(3):
            settle_payment(remittance.payment_id, True)

        assert trail(remittance) == [('', 'PENDING_PAYMENT', 'CUSTOMER'), ('PENDING_PAYMENT', 'PAID', 'PAYMENT')]

    def test_money_arriving_for_a_cancelled_remittance_is_flagged_not_hidden(self, customer):
        remittance = force_status(new_remittance(customer), 'CANCELLED')

        settle_payment(remittance.payment_id, True)

        remittance.refresh_from_db()
        entry = remittance.status_log.last()
        assert remittance.status == 'CANCELLED'  # the state does not move...
        assert (entry.from_status, entry.to_status) == ('CANCELLED', 'CANCELLED')
        assert 'reembolso manual' in entry.note  # ...but a person is told to look


class TestConfirmingAManualPayment:
    def test_the_administrator_verifies_and_it_becomes_paid(self, customer, admin):
        remittance = new_remittance(customer, method='ZELLE')

        confirmed = confirm_manual_payment(remittance, admin)

        assert confirmed.status == 'PAID'
        assert confirmed.payment.status == PaymentStatus.SUCCEEDED
        assert confirmed.payment.confirmed_by == admin
        entry = confirmed.status_log.last()
        assert (entry.source, entry.changed_by, entry.note) == ('PAYMENT', admin, 'Pago verificado por un administrador.')

    @pytest.mark.parametrize('method', ['WISE', 'ZELLE', 'CASH'])
    def test_every_manual_method_can_be_confirmed(self, customer, admin, method):
        assert confirm_manual_payment(new_remittance(customer, method), admin).status == 'PAID'

    @pytest.mark.parametrize('method', ['STRIPE', 'PAYPAL', 'MERCADO_PAGO', 'ENZONA'])
    def test_a_gateway_payment_cannot_be_marked_paid_by_hand(self, customer, admin, method):
        remittance = new_remittance(customer, method)

        with pytest.raises(NotAManualPayment):
            confirm_manual_payment(remittance, admin)

        remittance.refresh_from_db()
        assert remittance.status == 'PENDING_PAYMENT'
        assert remittance.payment.status == PaymentStatus.PENDING

    def test_confirming_twice_is_refused_the_second_time(self, customer, admin):
        remittance = new_remittance(customer, 'ZELLE')
        confirm_manual_payment(remittance, admin)

        with pytest.raises(InvalidTransition):
            confirm_manual_payment(remittance, admin)

        assert remittance.status_log.filter(to_status='PAID').count() == 1

    @pytest.mark.parametrize('status', ['PAID', 'COMPLETED', 'CANCELLED'])
    def test_only_a_pending_remittance_can_be_confirmed(self, customer, admin, status):
        remittance = force_status(new_remittance(customer, 'ZELLE'), status)

        with pytest.raises(InvalidTransition):
            confirm_manual_payment(remittance, admin)


class TestCompleting:
    def test_a_paid_remittance_is_completed_with_an_optional_note(self, customer, admin):
        remittance = confirm_manual_payment(new_remittance(customer, 'ZELLE'), admin)

        done = complete_remittance(remittance, admin, 'Entregado en mano')

        assert done.status == 'COMPLETED'
        assert done.status_log.last().note == 'Entregado en mano'

    def test_an_unpaid_remittance_cannot_be_completed(self, customer, admin):
        with pytest.raises(InvalidTransition, match='Pendiente de pago.*Completado'):
            complete_remittance(new_remittance(customer), admin)

    @pytest.mark.parametrize('status', ['COMPLETED', 'CANCELLED'])
    def test_it_cannot_be_completed_twice_or_after_cancelling(self, customer, admin, status):
        remittance = force_status(new_remittance(customer), status)

        with pytest.raises(InvalidTransition):
            complete_remittance(remittance, admin)


class TestCancelling:
    def test_a_pending_remittance_is_cancelled_and_its_payment_closed(self, customer, admin):
        remittance = new_remittance(customer)

        cancelled = cancel_remittance(remittance, admin, 'El cliente lo pidió')

        assert cancelled.status == 'CANCELLED'
        assert cancelled.payment.status == PaymentStatus.FAILED
        assert [e.note for e in cancelled.status_log.all()][-1] == 'El cliente lo pidió'

    def test_a_late_payment_cannot_revive_a_cancelled_remittance(self, customer, admin):
        remittance = new_remittance(customer)
        cancel_remittance(remittance, admin, 'Duplicada')

        late = settle_payment(remittance.payment_id, True)  # the gateway confirms afterwards

        remittance.refresh_from_db()
        assert late.changed is False
        assert remittance.status == 'CANCELLED'
        assert remittance.payment.status == PaymentStatus.FAILED

    def test_cancelling_leaves_one_cancellation_entry_not_two(self, customer, admin):
        remittance = new_remittance(customer)

        cancel_remittance(remittance, admin, 'Duplicada')

        assert trail(remittance) == [('', 'PENDING_PAYMENT', 'CUSTOMER'), ('PENDING_PAYMENT', 'CANCELLED', 'ADMIN')]

    def test_a_paid_remittance_can_be_cancelled_and_the_refund_is_manual(self, customer, admin):
        remittance = confirm_manual_payment(new_remittance(customer, 'ZELLE'), admin)

        cancelled = cancel_remittance(remittance, admin, 'Datos del destinatario falsos')

        assert cancelled.status == 'CANCELLED'
        assert cancelled.payment.status == PaymentStatus.SUCCEEDED  # the money was received; refund by hand

    @pytest.mark.parametrize('status', ['COMPLETED', 'CANCELLED'])
    def test_a_finished_remittance_cannot_be_cancelled(self, customer, admin, status):
        remittance = force_status(new_remittance(customer), status)

        with pytest.raises(InvalidTransition):
            cancel_remittance(remittance, admin, 'x')


class TestWholeJourneys:
    def test_manual_payment_from_request_to_delivery(self, customer, admin):
        remittance = new_remittance(customer, 'ZELLE')
        remittance = confirm_manual_payment(remittance, admin)
        complete_remittance(remittance, admin, 'Entregado')

        assert trail(remittance) == [
            ('', 'PENDING_PAYMENT', 'CUSTOMER'),
            ('PENDING_PAYMENT', 'PAID', 'PAYMENT'),
            ('PAID', 'COMPLETED', 'ADMIN'),
        ]
        assert remittance.status_log.count() == 3

    def test_gateway_payment_from_request_to_delivery(self, customer, admin):
        remittance = new_remittance(customer, 'STRIPE')
        settle_payment(remittance.payment_id, True)
        remittance.refresh_from_db()
        complete_remittance(remittance, admin)

        remittance.refresh_from_db()
        assert remittance.status == 'COMPLETED'
        assert [e.changed_by for e in remittance.status_log.all()] == [customer, None, admin]

    def test_the_trail_is_chronological(self, customer, admin):
        remittance = confirm_manual_payment(new_remittance(customer, 'CASH'), admin)
        complete_remittance(remittance, admin)

        dates = [e.changed_at for e in remittance.status_log.all()]

        assert dates == sorted(dates)
