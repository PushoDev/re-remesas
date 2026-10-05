from decimal import Decimal

import pytest
from django.core.management import call_command
from rest_framework.test import APIClient

from apps.exchange_rates.models import ExchangeRate
from apps.users.models import User

from .models import MembershipPlan

pytestmark = pytest.mark.django_db


def test_creates_the_monthly_and_annual_plans():
    call_command('seed_demo_plans')

    monthly = MembershipPlan.objects.get(code='vip-mensual')
    annual = MembershipPlan.objects.get(code='vip-anual')
    assert (monthly.price, monthly.duration_days, monthly.period) == (Decimal('9.99'), 30, 'MONTHLY')
    assert (annual.price, annual.duration_days, annual.period) == (Decimal('99.00'), 365, 'ANNUAL')
    assert annual.recharge_discount_percent > monthly.recharge_discount_percent


def test_the_annual_plan_is_cheaper_per_day():
    call_command('seed_demo_plans')
    monthly = MembershipPlan.objects.get(code='vip-mensual')
    annual = MembershipPlan.objects.get(code='vip-anual')

    assert annual.price / annual.duration_days < monthly.price / monthly.duration_days


def test_benefits_mention_the_real_discount_of_each_plan():
    call_command('seed_demo_plans')

    assert any('5 % de descuento' in b for b in MembershipPlan.objects.get(code='vip-mensual').benefits)
    assert any('10 % de descuento' in b for b in MembershipPlan.objects.get(code='vip-anual').benefits)
    for plan in MembershipPlan.objects.all():
        assert any('tipo de cambio' in b for b in plan.benefits)


def test_running_it_twice_does_not_duplicate():
    call_command('seed_demo_plans')
    call_command('seed_demo_plans')

    assert MembershipPlan.objects.count() == 2


def test_it_restores_what_an_admin_changed_and_reactivates():
    call_command('seed_demo_plans')
    plan = MembershipPlan.objects.get(code='vip-mensual')
    plan.price = Decimal('1.00')
    plan.is_active = False
    plan.save()

    call_command('seed_demo_plans')

    plan.refresh_from_db()
    assert plan.price == Decimal('9.99') and plan.is_active is True


def test_the_plans_show_up_in_the_public_api_in_order():
    call_command('seed_demo_plans')

    codes = [p['code'] for p in APIClient().get('/api/memberships/plans/').data]

    assert codes == ['vip-mensual', 'vip-anual']


def test_seed_demo_data_loads_users_rates_and_plans():
    call_command('seed_demo_data')

    assert User.objects.count() == 4
    assert ExchangeRate.objects.count() == 2
    assert MembershipPlan.objects.count() == 2


def test_the_demo_vip_gets_a_real_subscription_so_the_recharge_discount_applies():
    from apps.recharges.models import RechargePackage
    from apps.recharges.services import quote_recharge

    call_command('seed_demo_data')
    vip = User.objects.get(email='vip@rere.test')
    package = RechargePackage.objects.get(code='saldo-10')

    quote = quote_recharge(vip, package, '+53 5123 4567')

    assert (quote.discount_percent, quote.amount_total) == (Decimal('5.00'), Decimal('9.50'))


def test_only_the_active_demo_vip_gets_one_and_running_it_twice_adds_none():
    from .models import Subscription

    call_command('seed_demo_data')
    call_command('seed_demo_data')

    assert Subscription.objects.count() == 1
    assert Subscription.objects.get().user.email == 'vip@rere.test'
