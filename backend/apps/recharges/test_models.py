from datetime import timedelta
from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.payments.models import Payment, PaymentMethod, PaymentPurpose
from apps.users.models import User

from .models import Promotion, RechargeOrder, RechargePackage

pytestmark = pytest.mark.django_db


@pytest.fixture
def user():
    return User.objects.create_user(username='ana@example.com', email='ana@example.com', password='x')


@pytest.fixture
def package():
    return RechargePackage.objects.create(
        code='saldo-10', name='Recarga 10 USD', kind=RechargePackage.Kind.BALANCE, price=Decimal('10.00'),
    )


def make_order(user, package, **overrides):
    payment = Payment.objects.create(
        user=user, purpose=PaymentPurpose.RECHARGE, method=PaymentMethod.CASH, provider='MANUAL',
        amount=Decimal('10.00'),
    )
    values = {
        'user': user, 'phone_number': '+5351234567', 'package': package, 'payment': payment,
        'price_base': Decimal('10.00'), 'amount_total': Decimal('10.00'),
    }
    values.update(overrides)
    return RechargeOrder.objects.create(**values)


def fails_to_save(build):
    """True when the database refuses it (the constraint, not just Python, protects the data)."""
    try:
        with transaction.atomic():
            build()
    except IntegrityError:
        return True
    return False


class TestRechargePackage:
    def test_code_is_unique(self, package):
        assert fails_to_save(lambda: RechargePackage.objects.create(
            code='saldo-10', name='Otro', kind=RechargePackage.Kind.DATA, price=Decimal('5'),
        ))

    @pytest.mark.parametrize('price', ['0', '-1'])
    def test_price_must_be_positive(self, price):
        assert fails_to_save(lambda: RechargePackage.objects.create(
            code='x', name='X', kind=RechargePackage.Kind.DATA, price=Decimal(price),
        ))

    def test_defaults_to_active_usd_and_not_demo(self, package):
        package.refresh_from_db()
        assert (package.is_active, package.currency, package.is_demo) == (True, 'USD', False)

    def test_is_listed_cheapest_first_within_the_same_sort_order(self, package):
        RechargePackage.objects.create(code='saldo-5', name='5', kind=RechargePackage.Kind.BALANCE, price=Decimal('5'))
        assert [p.code for p in RechargePackage.objects.all()] == ['saldo-5', 'saldo-10']


class TestPromotion:
    def test_must_end_after_it_starts(self, package):
        now = timezone.now()
        assert fails_to_save(lambda: Promotion.objects.create(code='p', title='P', starts_at=now, ends_at=now))
        assert fails_to_save(lambda: Promotion.objects.create(
            code='p2', title='P', starts_at=now, ends_at=now - timedelta(days=1),
        ))

    def test_can_apply_to_every_package_or_to_one(self, package):
        now = timezone.now()
        everything = Promotion.objects.create(code='all', title='Todo', starts_at=now, ends_at=now + timedelta(days=1))
        one = Promotion.objects.create(
            code='one', title='Uno', package=package, starts_at=now, ends_at=now + timedelta(days=1),
        )
        assert everything.package is None
        assert one.package == package

    def test_deleting_a_package_removes_its_own_promotions(self, package):
        now = timezone.now()
        Promotion.objects.create(code='one', title='Uno', package=package, starts_at=now, ends_at=now + timedelta(days=1))
        package.delete()
        assert not Promotion.objects.filter(code='one').exists()


class TestRechargeOrder:
    def test_starts_pending_payment_with_a_hard_to_guess_reference(self, user, package):
        first = make_order(user, package)
        second = make_order(user, package)
        assert first.status == RechargeOrder.Status.PENDING_PAYMENT
        assert first.reference != second.reference
        assert len(str(first.reference)) == 36

    def test_keeps_exact_decimal_amounts(self, user, package):
        order = make_order(
            user, package, price_base=Decimal('9.99'), discount_percent_applied=Decimal('5.00'),
            amount_total=Decimal('9.49'),
        )
        order.refresh_from_db()
        assert (order.price_base, order.discount_percent_applied, order.amount_total) == (
            Decimal('9.99'), Decimal('5.00'), Decimal('9.49'),
        )

    def test_total_cannot_be_above_the_base_price(self, user, package):
        assert fails_to_save(lambda: make_order(user, package, amount_total=Decimal('10.01')))

    @pytest.mark.parametrize('field,value', [
        ('price_base', '0'), ('amount_total', '0'), ('discount_percent_applied', '-1'),
        ('discount_percent_applied', '100'),
    ])
    def test_rejects_impossible_amounts(self, user, package, field, value):
        assert fails_to_save(lambda: make_order(user, package, **{field: Decimal(value)}))

    def test_a_payment_pays_for_a_single_order(self, user, package):
        order = make_order(user, package)
        assert fails_to_save(lambda: RechargeOrder.objects.create(
            user=user, phone_number='+5351234567', package=package, payment=order.payment,
            price_base=Decimal('10'), amount_total=Decimal('10'),
        ))

    def test_the_package_cannot_be_deleted_while_orders_use_it(self, user, package):
        make_order(user, package)
        with pytest.raises(Exception) as error:
            package.delete()
        assert 'protected' in str(error.value).lower()

    def test_the_promotion_is_kept_as_a_snapshot(self, user, package):
        order = make_order(user, package, promotion_snapshot={'code': 'bono', 'title': 'Bono 50 %'})
        order.refresh_from_db()
        assert order.promotion_snapshot == {'code': 'bono', 'title': 'Bono 50 %'}
