from decimal import Decimal

import pytest
from django.core.management import call_command

from apps.users.models import User

from .models import ExchangeRate
from .services import convert

pytestmark = pytest.mark.django_db


def test_creates_usd_and_eur_active_rates():
    call_command('seed_demo_rates')

    usd = ExchangeRate.objects.get(currency='USD', is_active=True)
    assert (usd.base_rate, usd.standard_spread_percent, usd.vip_spread_percent) == (
        Decimal('700'), Decimal('5'), Decimal('2'))
    assert ExchangeRate.objects.get(currency='EUR', is_active=True)


def test_rates_are_usable_by_the_calculation_service():
    call_command('seed_demo_rates')

    assert convert(Decimal('10'), 'USD', False).amount_cup == Decimal('6650.00')
    assert convert(Decimal('10'), 'USD', True).amount_cup == Decimal('6860.00')


def test_running_it_twice_changes_nothing():
    call_command('seed_demo_rates')
    call_command('seed_demo_rates')

    assert ExchangeRate.objects.count() == 2
    assert all(rate.history.count() == 1 for rate in ExchangeRate.objects.all())


def test_it_restores_values_an_admin_changed_and_records_it():
    call_command('seed_demo_rates')
    usd = ExchangeRate.objects.get(currency='USD')
    usd.base_rate = Decimal('999')
    usd.save()

    call_command('seed_demo_rates')

    usd.refresh_from_db()
    assert usd.base_rate == Decimal('700')
    assert usd.history.count() == 2


def test_the_demo_admin_is_credited_when_it_exists():
    admin = User.objects.create_superuser(username='admin@rere.test', email='admin@rere.test', password='x')

    call_command('seed_demo_rates')

    assert ExchangeRate.objects.get(currency='USD').updated_by == admin


def test_it_works_without_any_user():
    call_command('seed_demo_rates')

    assert ExchangeRate.objects.get(currency='USD').updated_by is None


def test_seed_demo_data_loads_users_and_rates():
    call_command('seed_demo_data')

    assert User.objects.count() == 4
    assert ExchangeRate.objects.count() == 2
    assert ExchangeRate.objects.get(currency='USD').updated_by.email == 'admin@rere.test'
