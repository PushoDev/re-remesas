from datetime import timedelta
from decimal import Decimal
from itertools import count
from unittest import mock

import pytest
from django.utils import timezone

from apps.common.phone import InvalidCubanPhone
from apps.memberships.models import MembershipPlan, Subscription
from apps.payments.models import Payment, PaymentMethod, PaymentPurpose, PaymentStatus
from apps.users.models import User

from .models import Promotion, RechargeOrder, RechargePackage
from .services import PackageNotAvailable, create_recharge_order, quote_recharge, vip_discount_percent

pytestmark = pytest.mark.django_db

PHONE = '+53 5123 4567'
_ids = count(1)


@pytest.fixture
def user():
    return User.objects.create_user(username='ana@example.com', email='ana@example.com', password='x')


@pytest.fixture
def package():
    return RechargePackage.objects.create(
        code='saldo-10', name='Recarga 10', kind=RechargePackage.Kind.BALANCE, price=Decimal('10.00'),
    )


def give_subscription(user, discount, starts=-1, ends=29, status=Subscription.Status.ACTIVE):
    """A purchase of a plan with `discount` % off recharges; starts/ends are days from now."""
    n = next(_ids)
    now = timezone.now()
    plan = MembershipPlan.objects.create(
        code=f'plan-{n}', name=f'Plan {n}', period=MembershipPlan.Period.MONTHLY, price=Decimal('9.99'),
        duration_days=30, recharge_discount_percent=Decimal(discount),
    )
    payment = Payment.objects.create(
        user=user, purpose=PaymentPurpose.MEMBERSHIP, method=PaymentMethod.CASH, provider='MANUAL',
        amount=plan.price,
    )
    return Subscription.objects.create(
        user=user, plan=plan, payment=payment, status=status, duration_days=30,
        recharge_discount_percent=Decimal(discount), starts_at=now + timedelta(days=starts),
        expires_at=now + timedelta(days=ends),
    )


def make_vip(user, discount='5.00', **kwargs):
    subscription = give_subscription(user, discount, **kwargs)
    user.profile.is_membership_active = True
    user.profile.membership_expires_at = subscription.expires_at
    user.profile.save()
    return subscription


class TestDiscount:
    def test_a_free_customer_pays_the_full_price(self, user, package):
        quote = quote_recharge(user, package, PHONE)
        assert (quote.price_base, quote.discount_percent, quote.discount_amount, quote.amount_total) == (
            Decimal('10.00'), Decimal('0'), Decimal('0.00'), Decimal('10.00'),
        )
        assert quote.is_vip is False

    @pytest.mark.parametrize('percent,total', [('5.00', '9.50'), ('10.00', '9.00')])
    def test_a_vip_gets_the_discount_of_their_plan(self, user, package, percent, total):
        make_vip(user, percent)
        quote = quote_recharge(user, package, PHONE)
        assert quote.discount_percent == Decimal(percent)
        assert quote.amount_total == Decimal(total)
        assert quote.discount_amount == Decimal('10.00') - Decimal(total)
        assert quote.is_vip is True

    def test_a_lapsed_vip_pays_the_full_price(self, user, package):
        make_vip(user, '10.00', starts=-40, ends=-10)
        assert quote_recharge(user, package, PHONE).amount_total == Decimal('10.00')

    def test_a_vip_granted_by_hand_without_a_subscription_gets_no_discount(self, user, package):
        user.profile.is_membership_active = True
        user.profile.save()
        quote = quote_recharge(user, package, PHONE)
        assert quote.is_vip is True
        assert quote.discount_percent == Decimal('0')

    def test_a_subscription_that_never_became_active_gives_nothing(self, user, package):
        make_vip(user, '10.00', status=Subscription.Status.PENDING)
        assert quote_recharge(user, package, PHONE).discount_percent == Decimal('0')

    def test_when_several_run_at_once_the_best_one_applies(self, user, package):
        make_vip(user, '5.00')
        give_subscription(user, '10.00', starts=-2, ends=20)
        assert vip_discount_percent(user) == Decimal('10.00')

    def test_one_that_starts_later_does_not_apply_yet(self, user, package):
        make_vip(user, '5.00')
        give_subscription(user, '10.00', starts=29, ends=59)
        assert vip_discount_percent(user) == Decimal('5.00')

    def test_it_uses_the_percentage_saved_at_purchase_not_the_plans_current_one(self, user, package):
        subscription = make_vip(user, '5.00')
        MembershipPlan.objects.filter(pk=subscription.plan_id).update(recharge_discount_percent=Decimal('50'))
        assert quote_recharge(user, package, PHONE).discount_percent == Decimal('5.00')


class TestMoney:
    def test_rounds_half_up_to_cents(self, user):
        make_vip(user, '5.00')
        package = RechargePackage.objects.create(
            code='odd', name='Odd', kind=RechargePackage.Kind.DATA, price=Decimal('9.99'),
        )
        quote = quote_recharge(user, package, PHONE)
        assert quote.discount_amount == Decimal('0.50')  # 0.4995 rounds up
        assert quote.amount_total == Decimal('9.49')

    def test_amounts_are_decimals_with_two_places(self, user, package):
        make_vip(user, '7.50')
        quote = quote_recharge(user, package, PHONE)
        for value in (quote.price_base, quote.discount_amount, quote.amount_total):
            assert isinstance(value, Decimal)
            assert value == value.quantize(Decimal('0.01'))
        assert quote.amount_total == Decimal('9.25')  # 0.75 off

    def test_the_total_is_never_above_the_base_price_nor_below_a_cent(self, user):
        make_vip(user, '99.99')
        package = RechargePackage.objects.create(
            code='tiny', name='Tiny', kind=RechargePackage.Kind.BALANCE, price=Decimal('0.01'),
        )
        quote = quote_recharge(user, package, PHONE)
        assert Decimal('0.01') <= quote.amount_total <= quote.price_base


class TestQuoteValidation:
    @pytest.mark.parametrize('raw', ['', '5123', '+34 612345678', '+53 2123 4567', 'hola'])
    def test_a_bad_phone_is_refused(self, user, package, raw):
        with pytest.raises(InvalidCubanPhone):
            quote_recharge(user, package, raw)

    @pytest.mark.parametrize('raw', ['+53 5123 4567', '5351234567', '53-51234567', '+5351234567'])
    def test_the_phone_comes_back_normalized(self, user, package, raw):
        assert quote_recharge(user, package, raw).phone_number == '+5351234567'

    def test_an_inactive_package_cannot_be_quoted(self, user, package):
        package.is_active = False
        with pytest.raises(PackageNotAvailable):
            quote_recharge(user, package, PHONE)


class TestPromotionIsOnlyInformation:
    def test_the_current_promotion_is_reported_but_the_price_does_not_move(self, user, package):
        now = timezone.now()
        promo = Promotion.objects.create(
            code='bono', title='Bono', starts_at=now - timedelta(days=1), ends_at=now + timedelta(days=1),
        )
        quote = quote_recharge(user, package, PHONE)
        assert quote.active_promotion == promo
        assert quote.amount_total == Decimal('10.00')

    def test_no_promotion_when_there_is_none_current(self, user, package):
        assert quote_recharge(user, package, PHONE).active_promotion is None


class TestCreateOrder:
    def test_creates_the_order_and_its_pending_payment(self, user, package):
        order, session = create_recharge_order(user, package=package, phone_number=PHONE, payment_method='CASH')
        payment = order.payment
        assert order.status == RechargeOrder.Status.PENDING_PAYMENT
        assert order.phone_number == '+5351234567'
        assert (order.price_base, order.discount_percent_applied, order.amount_total) == (
            Decimal('10.00'), Decimal('0'), Decimal('10.00'),
        )
        assert payment.status == PaymentStatus.PENDING
        assert payment.purpose == PaymentPurpose.RECHARGE
        assert payment.target_id == order.pk
        assert payment.user == user
        assert (payment.amount, payment.currency) == (Decimal('10.00'), 'USD')
        assert session.requires_manual_confirmation is True

    def test_the_payment_is_for_the_discounted_total(self, user, package):
        make_vip(user, '10.00')
        order, _ = create_recharge_order(user, package=package, phone_number=PHONE, payment_method='CASH')
        assert order.amount_total == Decimal('9.00')
        assert order.payment.amount == Decimal('9.00')
        assert order.discount_percent_applied == Decimal('10.00')

    def test_an_online_method_gets_a_gateway_session(self, user, package):
        order, session = create_recharge_order(user, package=package, phone_number=PHONE, payment_method='STRIPE')
        assert order.payment.provider == 'MOCK'
        assert session.redirect_url == f'/pay/mock/{order.payment.reference}'
        assert order.payment.external_reference == session.external_reference != ''

    def test_a_manual_method_keeps_its_instructions(self, user, package):
        order, _ = create_recharge_order(user, package=package, phone_number=PHONE, payment_method='ZELLE')
        assert order.payment.provider == 'MANUAL'
        assert 'Zelle' in order.payment.instructions

    def test_the_provider_is_not_called_when_the_order_is_created(self, user, package):
        with mock.patch('apps.recharges.providers.mock.MockRechargeProvider.recharge') as recharge:
            create_recharge_order(user, package=package, phone_number=PHONE, payment_method='STRIPE')
        recharge.assert_not_called()

    def test_the_current_promotion_is_saved_with_the_order(self, user, package):
        now = timezone.now()
        Promotion.objects.create(
            code='bono', title='Bono 50 %', description='Doble saldo', starts_at=now - timedelta(days=1),
            ends_at=now + timedelta(days=1),
        )
        order, _ = create_recharge_order(user, package=package, phone_number=PHONE, payment_method='CASH')
        assert order.promotion_snapshot['code'] == 'bono'
        assert order.promotion_snapshot['title'] == 'Bono 50 %'
        assert order.amount_total == Decimal('10.00')

    def test_there_is_no_promotion_snapshot_when_none_applies(self, user, package):
        order, _ = create_recharge_order(user, package=package, phone_number=PHONE, payment_method='CASH')
        assert order.promotion_snapshot is None

    def test_a_later_price_change_does_not_alter_an_existing_order(self, user, package):
        order, _ = create_recharge_order(user, package=package, phone_number=PHONE, payment_method='CASH')
        RechargePackage.objects.filter(pk=package.pk).update(price=Decimal('99.00'))
        order.refresh_from_db()
        assert order.amount_total == Decimal('10.00')
        assert order.payment.amount == Decimal('10.00')

    def test_two_orders_get_different_references(self, user, package):
        first, _ = create_recharge_order(user, package=package, phone_number=PHONE, payment_method='CASH')
        second, _ = create_recharge_order(user, package=package, phone_number=PHONE, payment_method='CASH')
        assert first.reference != second.reference


class TestCreateOrderIsAllOrNothing:
    @pytest.mark.parametrize('phone', ['', '+53 2123 4567', 'x'])
    def test_a_bad_phone_leaves_nothing_behind(self, user, package, phone):
        with pytest.raises(InvalidCubanPhone):
            create_recharge_order(user, package=package, phone_number=phone, payment_method='CASH')
        assert Payment.objects.count() == 0 and RechargeOrder.objects.count() == 0

    def test_an_inactive_package_leaves_nothing_behind(self, user, package):
        package.is_active = False
        with pytest.raises(PackageNotAvailable):
            create_recharge_order(user, package=package, phone_number=PHONE, payment_method='CASH')
        assert Payment.objects.count() == 0 and RechargeOrder.objects.count() == 0

    def test_if_the_order_cannot_be_saved_the_payment_is_rolled_back(self, user, package):
        with mock.patch.object(RechargeOrder.objects, 'create', side_effect=RuntimeError('boom')):
            with pytest.raises(RuntimeError):
                create_recharge_order(user, package=package, phone_number=PHONE, payment_method='CASH')
        assert Payment.objects.count() == 0 and RechargeOrder.objects.count() == 0
