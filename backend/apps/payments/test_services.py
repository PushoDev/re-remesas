import json
from types import SimpleNamespace

import pytest

from apps.users.models import User

from . import services
from .models import Payment, PaymentMethod, PaymentPurpose, PaymentStatus
from .providers.base import InvalidWebhook, WebhookNotSupported
from .providers.mock import SIGNATURE_HEADER, sign
from .services import PaymentNotFound, UnknownProvider, handle_webhook, settle_payment

pytestmark = pytest.mark.django_db


@pytest.fixture
def user():
    return User.objects.create_user(username='ana@example.com', email='ana@example.com', password='x')


@pytest.fixture
def calls():
    """Registers a recording handler for REMITTANCE and restores the registry afterwards."""
    saved = dict(services._HANDLERS)
    recorded = SimpleNamespace(success=[], failure=[])
    services.register_handler(
        PaymentPurpose.REMITTANCE,
        lambda payment: recorded.success.append(payment.pk),
        lambda payment: recorded.failure.append(payment.pk),
    )
    yield recorded
    services._HANDLERS.clear()
    services._HANDLERS.update(saved)


def make_payment(user, **overrides):
    defaults = dict(
        user=user, purpose=PaymentPurpose.REMITTANCE, method=PaymentMethod.STRIPE, provider='MOCK',
        amount='10.00', external_reference='mock_abc',
    )
    return Payment.objects.create(**{**defaults, **overrides})


def webhook(status='succeeded', reference='mock_abc', signed=True):
    body = json.dumps({'external_reference': reference, 'status': status}).encode()
    return body, {SIGNATURE_HEADER: sign(body) if signed else 'firma-falsa'}


class TestSettlePayment:
    def test_success_marks_it_paid_and_runs_the_success_handler_once(self, user, calls):
        payment = make_payment(user)

        result = settle_payment(payment.pk, succeeded=True)

        payment.refresh_from_db()
        assert result.changed is True
        assert payment.status == PaymentStatus.SUCCEEDED
        assert payment.confirmed_at is not None
        assert calls.success == [payment.pk] and calls.failure == []

    def test_failure_marks_it_failed_and_runs_the_failure_handler(self, user, calls):
        payment = make_payment(user)

        settle_payment(payment.pk, succeeded=False)

        payment.refresh_from_db()
        assert payment.status == PaymentStatus.FAILED
        assert calls.failure == [payment.pk] and calls.success == []

    def test_settling_twice_applies_the_effect_only_once(self, user, calls):
        payment = make_payment(user)

        first = settle_payment(payment.pk, True)
        second = settle_payment(payment.pk, True)

        assert (first.changed, second.changed) == (True, False)
        assert calls.success == [payment.pk]

    def test_a_settled_payment_cannot_be_reverted_by_a_late_event(self, user, calls):
        paid = make_payment(user, external_reference='a')
        settle_payment(paid.pk, True)
        settle_payment(paid.pk, False)  # a late "failed" must not undo a success

        failed = make_payment(user, external_reference='b')
        settle_payment(failed.pk, False)
        settle_payment(failed.pk, True)  # nor revive a failure

        paid.refresh_from_db(), failed.refresh_from_db()
        assert (paid.status, failed.status) == (PaymentStatus.SUCCEEDED, PaymentStatus.FAILED)
        assert calls.success == [paid.pk] and calls.failure == [failed.pk]

    def test_a_purpose_without_a_handler_still_settles(self, user):
        payment = make_payment(user, purpose=PaymentPurpose.RECHARGE)

        assert settle_payment(payment.pk, True).payment.status == PaymentStatus.SUCCEEDED

    def test_if_the_handler_fails_everything_rolls_back(self, user):
        saved = dict(services._HANDLERS)

        def boom(payment):
            raise RuntimeError('fallo al aplicar el efecto')

        services.register_handler(PaymentPurpose.REMITTANCE, boom)
        try:
            payment = make_payment(user)
            with pytest.raises(RuntimeError):
                settle_payment(payment.pk, True)

            payment.refresh_from_db()
            assert payment.status == PaymentStatus.PENDING  # can be retried later
            assert payment.confirmed_at is None
        finally:
            services._HANDLERS.clear()
            services._HANDLERS.update(saved)


class TestHandleWebhook:
    def test_a_valid_webhook_settles_the_payment(self, user, calls):
        payment = make_payment(user)
        body, headers = webhook()

        result = handle_webhook('mock', body, headers)

        assert result.changed is True
        assert result.payment.pk == payment.pk
        assert calls.success == [payment.pk]

    def test_the_same_webhook_delivered_twice_applies_once(self, user, calls):
        make_payment(user)
        body, headers = webhook()

        results = [handle_webhook('MOCK', body, headers) for _ in range(3)]

        assert [r.changed for r in results] == [True, False, False]
        assert len(calls.success) == 1

    def test_a_failed_event_marks_the_payment_failed(self, user, calls):
        payment = make_payment(user)
        body, headers = webhook(status='failed')

        handle_webhook('mock', body, headers)

        payment.refresh_from_db()
        assert payment.status == PaymentStatus.FAILED
        assert calls.failure == [payment.pk]

    def test_a_bad_signature_is_rejected_and_changes_nothing(self, user, calls):
        payment = make_payment(user)
        body, headers = webhook(signed=False)

        with pytest.raises(InvalidWebhook):
            handle_webhook('mock', body, headers)

        payment.refresh_from_db()
        assert payment.status == PaymentStatus.PENDING
        assert calls.success == []

    def test_a_reference_we_do_not_know_is_reported(self, user, calls):
        make_payment(user)
        body, headers = webhook(reference='mock_desconocida')

        with pytest.raises(PaymentNotFound):
            handle_webhook('mock', body, headers)

    def test_a_webhook_cannot_settle_a_payment_of_another_provider(self, user, calls):
        make_payment(user, provider='MANUAL', external_reference='mock_abc')
        body, headers = webhook()

        with pytest.raises(PaymentNotFound):
            handle_webhook('mock', body, headers)

    def test_an_unknown_provider(self):
        with pytest.raises(UnknownProvider):
            handle_webhook('paypal-real', b'{}', {})

    def test_manual_providers_have_no_webhook(self):
        with pytest.raises(WebhookNotSupported):
            handle_webhook('manual', b'{}', {})
