from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.users.models import User

from .models import ExchangeRate, ExchangeRateHistory
from .services import (
    RateNotAvailable,
    convert,
    effective_rate,
    get_active_rate,
    save_exchange_rate,
    user_gets_vip_rate,
)

pytestmark = pytest.mark.django_db


def make_rate(currency='USD', base='700', standard='5', vip='2', active=True):
    return ExchangeRate.objects.create(
        currency=currency,
        base_rate=Decimal(base),
        standard_spread_percent=Decimal(standard),
        vip_spread_percent=Decimal(vip),
        is_active=active,
    )


def make_user(email='ana@example.com'):
    return User.objects.create_user(username=email, email=email, password='Tr3sPatos88x')


class TestFormula:
    def test_standard_rate_applies_the_standard_spread(self):
        rate = make_rate(base='700', standard='5')

        assert effective_rate(rate, is_vip=False) == Decimal('665.0000')

    def test_vip_rate_applies_the_lower_vip_spread(self):
        rate = make_rate(base='700', standard='5', vip='2')

        assert effective_rate(rate, is_vip=True) == Decimal('686.0000')

    def test_vip_always_gets_at_least_as_much_as_standard(self):
        rate = make_rate(base='700.123456', standard='7.5', vip='3.25')

        assert effective_rate(rate, True) >= effective_rate(rate, False)

    def test_zero_spread_gives_the_base_rate(self):
        rate = make_rate(base='700', standard='0', vip='0')

        assert effective_rate(rate, False) == Decimal('700.0000')

    def test_everything_is_decimal_never_float(self):
        make_rate()
        quote = convert(Decimal('10.00'), 'USD', is_vip=False)

        for value in (quote.base_rate, quote.spread_percent, quote.effective_rate, quote.amount_cup):
            assert isinstance(value, Decimal)

    def test_convert_standard(self):
        make_rate(base='700', standard='5', vip='2')
        quote = convert(Decimal('10.00'), 'USD', is_vip=False)

        assert quote.effective_rate == Decimal('665.0000')
        assert quote.amount_cup == Decimal('6650.00')
        assert quote.spread_percent == Decimal('5.00')
        assert quote.is_vip_rate is False

    def test_convert_vip(self):
        make_rate(base='700', standard='5', vip='2')
        quote = convert(Decimal('10.00'), 'USD', is_vip=True)

        assert quote.effective_rate == Decimal('686.0000')
        assert quote.amount_cup == Decimal('6860.00')
        assert quote.is_vip_rate is True

    @pytest.mark.parametrize('amount', [Decimal('0'), Decimal('-5'), 10, 10.5, '10'])
    def test_convert_rejects_invalid_amounts(self, amount):
        make_rate()

        with pytest.raises(ValueError):
            convert(amount, 'USD', is_vip=False)


class TestRounding:
    def test_effective_rate_rounds_half_up_to_4_decimals(self):
        # 1.000050 -> 1.0001 with half-up (banker's rounding would give 1.0000)
        rate = make_rate(base='1.000050', standard='0', vip='0')

        assert effective_rate(rate, False) == Decimal('1.0001')

    def test_cup_amount_rounds_down_to_2_decimals(self):
        # 0.03 * 665.5555 = 19.966665 -> 19.96 (half-up would promise 19.97)
        make_rate(base='665.5555', standard='0', vip='0')

        assert convert(Decimal('0.03'), 'USD', False).amount_cup == Decimal('19.96')

    def test_the_cup_amount_is_the_shown_rate_times_the_amount(self):
        make_rate(base='700.123456', standard='3.33', vip='1')
        quote = convert(Decimal('37.45'), 'USD', False)

        assert quote.amount_cup <= quote.amount * quote.effective_rate
        assert quote.amount * quote.effective_rate - quote.amount_cup < Decimal('0.01')


class TestActiveRate:
    def test_returns_the_active_rate_of_the_currency(self):
        usd = make_rate('USD', base='700')
        make_rate('EUR', base='750')

        assert get_active_rate('USD') == usd

    def test_no_rate_configured_raises_a_clear_error(self):
        with pytest.raises(RateNotAvailable, match='EUR'):
            get_active_rate('EUR')

    def test_inactive_rate_is_ignored(self):
        make_rate('USD', active=False)

        with pytest.raises(RateNotAvailable):
            convert(Decimal('10'), 'USD', False)

    def test_changing_the_rate_applies_to_the_next_quote(self):
        rate = make_rate(base='700', standard='5')
        assert convert(Decimal('10'), 'USD', False).amount_cup == Decimal('6650.00')

        rate.base_rate = Decimal('800')
        rate.save()

        assert convert(Decimal('10'), 'USD', False).amount_cup == Decimal('7600.00')


class TestConstraints:
    def test_only_one_active_rate_per_currency(self):
        make_rate('USD')

        with pytest.raises(IntegrityError), transaction.atomic():
            make_rate('USD')

    def test_an_inactive_rate_can_coexist_with_the_active_one(self):
        make_rate('USD')
        make_rate('USD', active=False)

        assert ExchangeRate.objects.filter(currency='USD').count() == 2

    @pytest.mark.parametrize('fields', [
        {'base': '0'},
        {'base': '-1'},
        {'standard': '100', 'vip': '0'},
        {'standard': '-1', 'vip': '0'},
        {'standard': '5', 'vip': '6'},  # VIP margin above the standard one
    ])
    def test_database_rejects_invalid_values(self, fields):
        with pytest.raises(IntegrityError), transaction.atomic():
            make_rate(**fields)


class TestSaveWithHistory:
    def test_create_records_who_and_what(self):
        admin = make_user('admin@example.com')
        rate = ExchangeRate(currency='USD', base_rate=Decimal('700'), standard_spread_percent=Decimal('5'),
                            vip_spread_percent=Decimal('2'))

        save_exchange_rate(rate, admin)

        assert rate.updated_by == admin
        entry = rate.history.get()
        assert (entry.base_rate, entry.standard_spread_percent, entry.vip_spread_percent) == (
            Decimal('700'), Decimal('5'), Decimal('2'))
        assert entry.changed_by == admin

    def test_each_update_adds_a_history_entry_keeping_the_previous_values(self):
        admin = make_user('admin@example.com')
        rate = ExchangeRate(currency='USD', base_rate=Decimal('700'), standard_spread_percent=Decimal('5'),
                            vip_spread_percent=Decimal('2'))
        save_exchange_rate(rate, admin)

        rate.base_rate = Decimal('720')
        save_exchange_rate(rate, admin)

        assert [e.base_rate for e in rate.history.all()] == [Decimal('720'), Decimal('700')]  # newest first

    def test_invalid_values_are_rejected_and_leave_no_history(self):
        admin = make_user('admin@example.com')
        rate = ExchangeRate(currency='USD', base_rate=Decimal('700'), standard_spread_percent=Decimal('5'),
                            vip_spread_percent=Decimal('9'))

        with pytest.raises(ValidationError):
            save_exchange_rate(rate, admin)

        assert ExchangeRate.objects.count() == 0
        assert ExchangeRateHistory.objects.count() == 0

    def test_a_second_active_rate_for_the_same_currency_is_rejected_cleanly(self):
        admin = make_user('admin@example.com')
        make_rate('USD')
        duplicate = ExchangeRate(currency='USD', base_rate=Decimal('710'), standard_spread_percent=Decimal('5'),
                                 vip_spread_percent=Decimal('2'))

        with pytest.raises(ValidationError):
            save_exchange_rate(duplicate, admin)


class TestWhoGetsTheVipRate:
    def test_anonymous_does_not(self):
        assert user_gets_vip_rate(AnonymousUser()) is False
        assert user_gets_vip_rate(None) is False

    def test_free_user_does_not(self):
        assert user_gets_vip_rate(make_user()) is False

    def test_active_vip_does(self):
        user = make_user()
        user.profile.is_membership_active = True
        user.profile.membership_expires_at = timezone.now() + timedelta(days=30)
        user.profile.save()

        assert user_gets_vip_rate(user) is True

    def test_expired_vip_does_not_even_with_the_flag_on(self):
        user = make_user()
        user.profile.is_membership_active = True
        user.profile.membership_expires_at = timezone.now() - timedelta(days=1)
        user.profile.save()

        assert user_gets_vip_rate(user) is False
