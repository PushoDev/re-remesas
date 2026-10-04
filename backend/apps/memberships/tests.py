from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError

from apps.payments.models import Payment, PaymentMethod, PaymentPurpose
from apps.users.models import User

from .models import MembershipPlan, Subscription

pytestmark = pytest.mark.django_db


def make_plan(code='vip-mensual', **overrides):
    defaults = dict(
        code=code, name='VIP Mensual', period=MembershipPlan.Period.MONTHLY,
        price=Decimal('9.99'), duration_days=30, recharge_discount_percent=Decimal('5'),
    )
    return MembershipPlan.objects.create(**{**defaults, **overrides})


def make_subscription(plan=None):
    user = User.objects.create_user(username='ana@example.com', email='ana@example.com', password='x')
    plan = plan or make_plan()
    payment = Payment.objects.create(
        user=user, purpose=PaymentPurpose.MEMBERSHIP, method=PaymentMethod.STRIPE, provider='MOCK', amount=plan.price,
    )
    return Subscription.objects.create(
        user=user, plan=plan, payment=payment, duration_days=plan.duration_days,
        recharge_discount_percent=plan.recharge_discount_percent,
    )


class TestPlan:
    def test_defaults(self):
        plan = make_plan()

        assert plan.is_active is True
        assert plan.currency == 'USD'
        assert plan.benefits == []

    def test_benefits_are_a_list_of_texts(self):
        plan = make_plan(benefits=['Mejor tasa de cambio', 'Descuento en recargas'])
        plan.refresh_from_db()

        assert plan.benefits == ['Mejor tasa de cambio', 'Descuento en recargas']

    def test_code_is_unique(self):
        make_plan()

        with pytest.raises(IntegrityError), transaction.atomic():
            make_plan()

    @pytest.mark.parametrize('overrides', [
        {'price': Decimal('0')},
        {'price': Decimal('-1')},
        {'duration_days': 0},
        {'recharge_discount_percent': Decimal('-1')},
        {'recharge_discount_percent': Decimal('100')},
    ])
    def test_database_rejects_invalid_values(self, overrides):
        with pytest.raises(IntegrityError), transaction.atomic():
            make_plan(**overrides)

    def test_plans_are_listed_by_sort_order_then_price(self):
        make_plan('b', sort_order=2, price=Decimal('5'))
        make_plan('a', sort_order=1, price=Decimal('99'))
        make_plan('c', sort_order=1, price=Decimal('10'))

        assert [p.code for p in MembershipPlan.objects.all()] == ['c', 'a', 'b']


class TestSubscription:
    def test_it_starts_pending_and_snapshots_the_plan(self):
        subscription = make_subscription()

        assert subscription.status == Subscription.Status.PENDING
        assert subscription.duration_days == 30
        assert subscription.recharge_discount_percent == Decimal('5')
        assert subscription.starts_at is None and subscription.expires_at is None

    def test_editing_the_plan_later_does_not_change_a_past_purchase(self):
        subscription = make_subscription()
        subscription.plan.duration_days = 365
        subscription.plan.save()
        subscription.refresh_from_db()

        assert subscription.duration_days == 30

    def test_a_payment_belongs_to_at_most_one_subscription(self):
        subscription = make_subscription()

        with pytest.raises(IntegrityError), transaction.atomic():
            Subscription.objects.create(
                user=subscription.user, plan=subscription.plan, payment=subscription.payment, duration_days=30,
            )

    def test_a_plan_with_purchases_cannot_be_deleted(self):
        subscription = make_subscription()

        with pytest.raises(ProtectedError):
            subscription.plan.delete()
