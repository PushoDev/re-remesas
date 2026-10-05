from decimal import Decimal

import pytest
from django.core.management import call_command

from .models import Promotion, RechargePackage
from .services import get_catalog

pytestmark = pytest.mark.django_db


def test_creates_one_package_of_each_kind_marked_as_demo():
    call_command('seed_demo_recharges')
    kinds = set(RechargePackage.objects.values_list('kind', flat=True))
    assert kinds == {'BALANCE', 'DATA', 'VOICE', 'COMBO'}
    assert RechargePackage.objects.filter(is_demo=False).count() == 0
    assert all(package.price > 0 for package in RechargePackage.objects.all())


def test_exactly_one_promotion_is_current_and_it_shows_in_the_catalog():
    call_command('seed_demo_recharges')
    current = {entry.package.code: entry.active_promotion.code for entry in get_catalog() if entry.active_promotion}
    assert current == {'saldo-10': 'bono-saldo-demo'}


def test_the_expired_promotion_exists_but_is_not_shown():
    call_command('seed_demo_recharges')
    assert Promotion.objects.filter(code='bono-vencido-demo').exists()
    assert 'bono-vencido-demo' not in {e.active_promotion.code for e in get_catalog() if e.active_promotion}


def test_running_it_twice_does_not_duplicate():
    call_command('seed_demo_recharges')
    call_command('seed_demo_recharges')
    assert RechargePackage.objects.count() == 6 and Promotion.objects.count() == 2


def test_it_restores_what_was_changed_and_reactivates():
    call_command('seed_demo_recharges')
    RechargePackage.objects.filter(code='saldo-5').update(price=Decimal('99.00'), is_active=False)
    Promotion.objects.filter(code='bono-saldo-demo').update(is_active=False)
    call_command('seed_demo_recharges')
    package = RechargePackage.objects.get(code='saldo-5')
    assert (package.price, package.is_active) == (Decimal('5.00'), True)
    assert Promotion.objects.get(code='bono-saldo-demo').is_active is True


def test_it_never_touches_existing_orders_or_other_packages():
    extra = RechargePackage.objects.create(code='mio', name='Mío', kind='BALANCE', price=Decimal('3'))
    call_command('seed_demo_recharges')
    extra.refresh_from_db()
    assert (extra.name, extra.is_demo) == ('Mío', False)


def test_the_master_command_loads_the_recharges_too():
    call_command('seed_demo_data')
    assert RechargePackage.objects.count() == 6
