import json
from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction

from apps.users.models import User

from .models import Payment, PaymentMethod, PaymentPurpose, PaymentStatus
from .providers.base import InvalidWebhook, WebhookNotSupported
from .providers.manual import ManualPaymentProvider
from .providers.mock import SIGNATURE_HEADER, MockPaymentProvider, sign
from .providers.registry import METHOD_TO_PROVIDER, get_provider, provider_for_method

pytestmark = pytest.mark.django_db


def make_payment(method=PaymentMethod.STRIPE, **overrides):
    user = overrides.pop('user', None) or User.objects.get_or_create(
        email='ana@example.com', defaults={'username': 'ana@example.com'},
    )[0]
    defaults = dict(
        user=user, purpose=PaymentPurpose.MEMBERSHIP, method=method, provider='MOCK', amount=Decimal('9.99'),
    )
    return Payment.objects.create(**{**defaults, **overrides})


class TestPaymentModel:
    def test_defaults(self):
        payment = make_payment()

        assert payment.status == PaymentStatus.PENDING
        assert payment.currency == 'USD'
        assert payment.confirmed_at is None
        assert payment.reference

    def test_each_payment_gets_its_own_public_reference(self):
        assert make_payment().reference != make_payment().reference

    @pytest.mark.parametrize('amount', ['0', '-1'])
    def test_amount_must_be_positive(self, amount):
        with pytest.raises(IntegrityError), transaction.atomic():
            make_payment(amount=Decimal(amount))

    def test_the_same_external_reference_cannot_repeat_within_a_provider(self):
        make_payment(external_reference='ext_1')

        with pytest.raises(IntegrityError), transaction.atomic():
            make_payment(external_reference='ext_1')

    def test_empty_external_references_do_not_clash(self):
        make_payment(external_reference='')
        make_payment(external_reference='')

        assert Payment.objects.count() == 2

    def test_the_same_external_reference_is_fine_across_providers(self):
        make_payment(external_reference='ext_1', provider='MOCK')
        make_payment(external_reference='ext_1', provider='STRIPE')

        assert Payment.objects.count() == 2


class TestMockProvider:
    provider = MockPaymentProvider()

    def body(self, **data):
        return json.dumps({'external_reference': 'mock_abc', 'status': 'succeeded', **data}).encode()

    def test_create_payment_returns_a_checkout_url_and_a_fresh_reference(self):
        payment = make_payment()
        first = self.provider.create_payment(payment)
        second = self.provider.create_payment(payment)

        assert first.redirect_url == f'/pay/mock/{payment.reference}'
        assert first.external_reference.startswith('mock_')
        assert first.external_reference != second.external_reference
        assert first.requires_manual_confirmation is False

    def test_a_signed_webhook_is_accepted(self):
        body = self.body()
        event = self.provider.parse_webhook(body, {SIGNATURE_HEADER: sign(body)})

        assert event.succeeded is True
        assert event.external_reference == 'mock_abc'

    def test_a_signed_failure_is_reported_as_not_succeeded(self):
        body = self.body(status='failed')

        assert self.provider.parse_webhook(body, {SIGNATURE_HEADER: sign(body)}).succeeded is False

    @pytest.mark.parametrize('headers', [{}, {SIGNATURE_HEADER: ''}, {SIGNATURE_HEADER: 'firma-falsa'}])
    def test_a_missing_or_wrong_signature_is_rejected(self, headers):
        with pytest.raises(InvalidWebhook):
            self.provider.parse_webhook(self.body(), headers)

    def test_a_tampered_body_is_rejected(self):
        original = self.body()
        tampered = self.body(external_reference='mock_otro')

        with pytest.raises(InvalidWebhook):
            self.provider.parse_webhook(tampered, {SIGNATURE_HEADER: sign(original)})

    def test_the_signature_depends_on_the_secret(self, settings):
        body = self.body()
        signature = sign(body)  # signed with the current secret
        settings.PAYMENT_WEBHOOK_SECRET = 'otro-secreto'

        with pytest.raises(InvalidWebhook):
            self.provider.parse_webhook(body, {SIGNATURE_HEADER: signature})

    @pytest.mark.parametrize('raw', [b'no es json', b'{}', b'[]', b'{"status": "succeeded"}'])
    def test_a_signed_but_malformed_body_is_rejected(self, raw):
        with pytest.raises(InvalidWebhook):
            self.provider.parse_webhook(raw, {SIGNATURE_HEADER: sign(raw)})


class TestManualProvider:
    provider = ManualPaymentProvider()

    @pytest.mark.parametrize('method, word', [
        (PaymentMethod.ZELLE, 'Zelle'),
        (PaymentMethod.WISE, 'Wise'),
        (PaymentMethod.CASH, 'efectivo'),
    ])
    def test_gives_instructions_and_waits_for_an_administrator(self, method, word):
        session = self.provider.create_payment(make_payment(method=method, provider='MANUAL'))

        assert word in session.instructions
        assert 'administrador' in session.instructions
        assert session.requires_manual_confirmation is True
        assert session.redirect_url is None

    def test_it_has_no_webhook(self):
        with pytest.raises(WebhookNotSupported):
            self.provider.parse_webhook(b'{}', {})


class TestRegistry:
    def test_every_payment_method_has_a_provider(self):
        assert set(METHOD_TO_PROVIDER) == set(PaymentMethod.values)
        for method in PaymentMethod.values:
            assert provider_for_method(method).code in {'MOCK', 'MANUAL'}

    @pytest.mark.parametrize('method', ['STRIPE', 'PAYPAL', 'MERCADO_PAGO', 'ENZONA'])
    def test_online_gateways_without_credentials_use_the_mock(self, method):
        assert provider_for_method(method).code == 'MOCK'

    @pytest.mark.parametrize('method', ['WISE', 'ZELLE', 'CASH'])
    def test_off_app_methods_are_settled_manually(self, method):
        assert provider_for_method(method).code == 'MANUAL'

    def test_lookup_by_code(self):
        assert get_provider('MOCK').code == 'MOCK'
        assert get_provider('MANUAL').code == 'MANUAL'
