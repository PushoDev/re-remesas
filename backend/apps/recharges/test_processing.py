from decimal import Decimal
from unittest import mock

import pytest
from django.test import Client

from apps.payments.models import Payment, PaymentStatus
from apps.payments.providers.mock import build_signed_event
from apps.payments.services import _HANDLERS, settle_payment
from apps.users.models import User

from .models import RechargeOrder, RechargePackage
from .providers.base import RechargeResult
from .providers.mock import MockRechargeProvider
from .services import create_recharge_order, process_paid_order

pytestmark = pytest.mark.django_db

SUCCESS_PHONE = '+53 5123 4567'
FAIL_PHONE = '+53 5123 4560'
PROCESSING_PHONE = '+53 5123 4561'
RECHARGE = 'apps.recharges.providers.mock.MockRechargeProvider.recharge'


@pytest.fixture
def user():
    return User.objects.create_user(username='ana@example.com', email='ana@example.com', password='x')


@pytest.fixture
def admin():
    return User.objects.create_user(username='admin@example.com', email='admin@example.com', password='x', is_staff=True)


@pytest.fixture
def package():
    return RechargePackage.objects.create(
        code='saldo-10', name='Recarga 10', kind=RechargePackage.Kind.BALANCE, price=Decimal('10.00'),
    )


def new_order(user, package, phone=SUCCESS_PHONE, method='STRIPE'):
    order, _ = create_recharge_order(user, package=package, phone_number=phone, payment_method=method)
    return order


def pay(order, succeeded=True, confirmed_by=None):
    return settle_payment(order.payment_id, succeeded, confirmed_by=confirmed_by)


class TestWhatTheProviderAnswers:
    def test_paid_and_delivered_is_success(self, user, package):
        order = new_order(user, package)
        pay(order)
        order.refresh_from_db()
        assert order.status == RechargeOrder.Status.SUCCESS
        assert order.provider_reference.startswith('RC-')
        assert order.provider_message == 'Recarga entregada.'

    def test_paid_and_refused_is_failed(self, user, package):
        order = new_order(user, package, FAIL_PHONE)
        pay(order)
        order.refresh_from_db()
        assert order.status == RechargeOrder.Status.FAILED
        assert order.provider_reference.startswith('RC-')

    def test_paid_and_accepted_but_not_delivered_stays_processing(self, user, package):
        order = new_order(user, package, PROCESSING_PHONE)
        pay(order)
        order.refresh_from_db()
        assert order.status == RechargeOrder.Status.PROCESSING

    def test_the_payment_stays_paid_even_when_the_top_up_fails(self, user, package):
        order = new_order(user, package, FAIL_PHONE)
        pay(order)
        order.payment.refresh_from_db()
        assert order.payment.status == PaymentStatus.SUCCEEDED  # money taken: refunded by hand

    def test_the_provider_receives_the_normalized_number_the_package_and_the_total(self, user, package):
        order = new_order(user, package)
        with mock.patch(RECHARGE, return_value=RechargeResult('SUCCESS', 'RC-X', 'ok')) as recharge:
            pay(order)
        recharge.assert_called_once_with('+5351234567', 'saldo-10', Decimal('10.00'))


class TestTheProviderIsCalledOnce:
    def test_confirming_the_same_payment_twice_calls_it_once(self, user, package):
        order = new_order(user, package)
        with mock.patch(RECHARGE, wraps=MockRechargeProvider().recharge) as recharge:
            first = pay(order)
            second = pay(order)
        assert first.changed is True and second.changed is False
        assert recharge.call_count == 1

    def test_processing_the_same_order_twice_calls_it_once(self, user, package):
        order = new_order(user, package)
        with mock.patch(RECHARGE, wraps=MockRechargeProvider().recharge) as recharge:
            process_paid_order(order)
            process_paid_order(order)
        assert recharge.call_count == 1

    def test_the_same_signed_webhook_twice_does_not_top_up_twice(self, user, package):
        order = new_order(user, package)
        body, headers = build_signed_event(order.payment.external_reference, succeeded=True)
        client = Client()
        with mock.patch(RECHARGE, wraps=MockRechargeProvider().recharge) as recharge:
            for _ in range(2):
                response = client.post(
                    '/api/payments/webhooks/mock/', data=body, content_type='application/json',
                    HTTP_X_MOCK_SIGNATURE=headers['X-Mock-Signature'],
                )
                assert response.status_code == 200
        assert recharge.call_count == 1
        order.refresh_from_db()
        assert order.status == RechargeOrder.Status.SUCCESS

    def test_an_order_already_processed_is_left_as_it_is(self, user, package):
        order = new_order(user, package, PROCESSING_PHONE)
        pay(order)
        with mock.patch(RECHARGE) as recharge:
            result = process_paid_order(order)
        recharge.assert_not_called()
        assert result.status == RechargeOrder.Status.PROCESSING


class TestTheProviderIsNotCalledWithoutAPayment:
    def test_creating_the_order_does_not_call_it(self, user, package):
        with mock.patch(RECHARGE) as recharge:
            new_order(user, package)
        recharge.assert_not_called()

    def test_a_payment_that_failed_does_not_call_it_and_fails_the_order(self, user, package):
        order = new_order(user, package)
        with mock.patch(RECHARGE) as recharge:
            pay(order, succeeded=False)
        recharge.assert_not_called()
        order.refresh_from_db()
        assert order.status == RechargeOrder.Status.FAILED
        assert order.provider_message == 'El pago no se completó.'
        assert order.provider_reference == ''

    def test_a_late_success_after_a_failed_payment_changes_nothing(self, user, package):
        order = new_order(user, package)
        pay(order, succeeded=False)
        with mock.patch(RECHARGE) as recharge:
            result = pay(order, succeeded=True)
        recharge.assert_not_called()
        assert result.changed is False
        order.refresh_from_db()
        assert order.status == RechargeOrder.Status.FAILED


class TestManualPayments:
    def test_an_administrator_confirming_the_payment_sends_the_top_up(self, user, package, admin):
        order = new_order(user, package, method='ZELLE')
        pay(order, confirmed_by=admin)
        order.refresh_from_db()
        assert order.status == RechargeOrder.Status.SUCCESS
        assert order.payment.confirmed_by == admin

    def test_an_order_waiting_for_a_manual_payment_is_not_sent(self, user, package):
        order = new_order(user, package, method='CASH')
        order.refresh_from_db()
        assert order.status == RechargeOrder.Status.PENDING_PAYMENT


class TestWhenTheProviderBreaks:
    def test_an_error_fails_the_order_without_losing_the_payment(self, user, package):
        order = new_order(user, package)
        with mock.patch(RECHARGE, side_effect=RuntimeError('sin conexión')) as recharge:
            result = pay(order)
        assert recharge.call_count == 1
        assert result.changed is True
        order.refresh_from_db()
        assert order.status == RechargeOrder.Status.FAILED
        assert order.provider_message == 'El operador no pudo completar la recarga.'
        assert 'sin conexión' not in order.provider_message  # internals never reach the customer
        order.payment.refresh_from_db()
        assert order.payment.status == PaymentStatus.SUCCEEDED

    def test_it_is_never_retried_after_an_error(self, user, package):
        order = new_order(user, package)
        with mock.patch(RECHARGE, side_effect=RuntimeError('boom')) as recharge:
            pay(order)
            pay(order)
            process_paid_order(order)
        assert recharge.call_count == 1


class TestRegistration:
    def test_the_recharge_handler_is_registered_in_the_payment_layer(self):
        assert 'RECHARGE' in _HANDLERS

    def test_other_purposes_keep_their_own_handlers(self):
        assert {'MEMBERSHIP', 'REMITTANCE', 'RECHARGE'} <= set(_HANDLERS)

    def test_the_order_amounts_are_not_touched_by_processing(self, user, package):
        order = new_order(user, package)
        pay(order)
        order.refresh_from_db()
        assert (order.price_base, order.amount_total) == (Decimal('10.00'), Decimal('10.00'))
        assert Payment.objects.get(pk=order.payment_id).amount == Decimal('10.00')
