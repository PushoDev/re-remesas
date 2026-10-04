import re
from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError

from apps.payments.models import Payment, PaymentMethod, PaymentPurpose
from apps.users.models import User

from .models import Remittance
from .services import ALPHABET, generate_tracking_id, is_valid_tracking_id, normalize_tracking_id

pytestmark = pytest.mark.django_db


def make_remittance(tracking_id=None, **overrides):
    user = overrides.pop('sender', None) or User.objects.get_or_create(
        email='ana@example.com', defaults={'username': 'ana@example.com'})[0]
    payment = Payment.objects.create(
        user=user, purpose=PaymentPurpose.REMITTANCE, method=PaymentMethod.STRIPE, provider='MOCK',
        amount=Decimal('100.00'), external_reference=f'mock_{Payment.objects.count()}',
    )
    defaults = dict(
        tracking_id=tracking_id or generate_tracking_id(), sender=user, amount_sent=Decimal('100.00'), currency='USD',
        base_rate_used=Decimal('700'), spread_percent_used=Decimal('5'), effective_rate_used=Decimal('665.0000'),
        amount_cup=Decimal('66500.00'), recipient_name='Rosa Pérez', recipient_phone='+5351234567',
        delivery_method='CASH_DELIVERY', recipient_address='Calle 23 #456, La Habana',
        payment_method=PaymentMethod.STRIPE, payment=payment,
    )
    return Remittance.objects.create(**{**defaults, **overrides})


class TestTrackingId:
    def test_format_is_rr_date_and_five_characters(self):
        tracking_id = generate_tracking_id()

        assert re.fullmatch(r'RR-\d{8}-[A-Z2-9]{5}', tracking_id)
        assert is_valid_tracking_id(tracking_id)

    def test_it_carries_todays_date(self, monkeypatch):
        from datetime import datetime, timezone
        monkeypatch.setattr('django.utils.timezone.now', lambda: datetime(2026, 10, 4, 12, 0, tzinfo=timezone.utc))

        assert generate_tracking_id().startswith('RR-20261004-')

    def test_the_suffix_never_uses_look_alike_characters(self):
        for char in 'O0I1':
            assert char not in ALPHABET
        suffixes = ''.join(generate_tracking_id()[-5:] for _ in range(300))

        assert set(suffixes) <= set(ALPHABET)

    def test_ids_are_random_enough_not_to_repeat_in_practice(self):
        ids = {generate_tracking_id() for _ in range(200)}

        assert len(ids) >= 198  # 200 draws over 33 million possibilities

    def test_the_alphabet_has_32_characters_which_gives_33_million_ids_per_day(self):
        assert len(ALPHABET) == 32 and len(set(ALPHABET)) == 32

    @pytest.mark.parametrize('bad', [
        '', 'RR-20261004-7KQ2', 'RR-20261004-7KQ2MX', 'RR-2026104-7KQ2M', 'XX-20261004-7KQ2M',
        'RR-20261004-7KQ0M', 'RR-20261004-7kq2m', 'RR-20261004-7KQ2M ',
    ])
    def test_invalid_formats(self, bad):
        assert is_valid_tracking_id(bad) is False

    def test_what_a_customer_types_is_normalized(self):
        assert normalize_tracking_id('  rr-20261004-7kq2m ') == 'RR-20261004-7KQ2M'
        assert is_valid_tracking_id(normalize_tracking_id('rr-20261004-7kq2m'))

    def test_generating_an_id_does_not_touch_the_database(self, django_assert_num_queries):
        with django_assert_num_queries(0):  # uniqueness is the database's job, not the generator's
            generate_tracking_id()


class TestRemittanceModel:
    def test_defaults_and_string(self):
        remittance = make_remittance('RR-20261004-AAAAA')

        assert remittance.status == Remittance.Status.PENDING_PAYMENT
        assert remittance.is_vip_rate is False
        assert str(remittance) == 'RR-20261004-AAAAA 100.00 USD [PENDING_PAYMENT]'

    def test_the_tracking_id_is_unique(self):
        make_remittance('RR-20261004-AAAAA')

        with pytest.raises(IntegrityError), transaction.atomic():
            make_remittance('RR-20261004-AAAAA')

    def test_each_remittance_has_its_own_payment(self):
        remittance = make_remittance()

        with pytest.raises(IntegrityError), transaction.atomic():
            make_remittance(payment=remittance.payment)

    @pytest.mark.parametrize('overrides', [
        {'amount_sent': Decimal('0')},
        {'amount_sent': Decimal('-5')},
        {'effective_rate_used': Decimal('0')},
        {'amount_cup': Decimal('0')},
    ])
    def test_amounts_must_be_positive(self, overrides):
        with pytest.raises(IntegrityError), transaction.atomic():
            make_remittance(**overrides)

    def test_cash_delivery_needs_an_address(self):
        with pytest.raises(IntegrityError), transaction.atomic():
            make_remittance(delivery_method='CASH_DELIVERY', recipient_address='')

    def test_a_local_transfer_needs_an_account_but_not_an_address(self):
        remittance = make_remittance(delivery_method='LOCAL_TRANSFER', recipient_address='',
                                     recipient_account='9225 1234 5678 9012')

        assert remittance.recipient_address == ''

    def test_a_local_transfer_without_an_account_is_rejected(self):
        with pytest.raises(IntegrityError), transaction.atomic():
            make_remittance(delivery_method='LOCAL_TRANSFER', recipient_address='Calle 1', recipient_account='')

    def test_the_sender_and_payment_cannot_be_deleted_while_the_remittance_exists(self):
        remittance = make_remittance()

        with pytest.raises(ProtectedError):
            remittance.sender.delete()
        with pytest.raises(ProtectedError):
            remittance.payment.delete()

    def test_the_snapshot_keeps_its_exact_decimals(self):
        remittance = make_remittance(
            base_rate_used=Decimal('700.123456'), effective_rate_used=Decimal('676.8093'),
            amount_sent=Decimal('37.45'), amount_cup=Decimal('25346.50'),
        )
        remittance.refresh_from_db()

        assert (remittance.base_rate_used, remittance.effective_rate_used, remittance.amount_cup) == (
            Decimal('700.123456'), Decimal('676.8093'), Decimal('25346.50'))

    def test_newest_first(self):
        first, second = make_remittance(), make_remittance()

        assert list(Remittance.objects.all()) == [second, first]
