import uuid
from datetime import datetime, timedelta, timezone as dt_timezone
from decimal import Decimal

import pytest

from apps.exchange_rates.services import user_gets_vip_rate
from apps.payments.models import Payment, PaymentMethod, PaymentPurpose, PaymentStatus
from apps.payments.services import settle_payment
from apps.users.models import User

from .models import MembershipPlan, Subscription
from .services import activate_membership

pytestmark = pytest.mark.django_db

NOW = datetime(2026, 10, 4, 12, 0, tzinfo=dt_timezone.utc)
DAY = timedelta(days=1)


@pytest.fixture(autouse=True)
def frozen_now(monkeypatch):
    monkeypatch.setattr('django.utils.timezone.now', lambda: NOW)


@pytest.fixture
def user():
    return User.objects.create_user(username='ana@example.com', email='ana@example.com', password='x')


@pytest.fixture
def plan():
    return MembershipPlan.objects.create(
        code='vip-mensual', name='VIP Mensual', period='MONTHLY', price=Decimal('9.99'), duration_days=30,
        recharge_discount_percent=Decimal('5'),
    )


def purchase(user, plan):
    payment = Payment.objects.create(
        user=user, purpose=PaymentPurpose.MEMBERSHIP, method=PaymentMethod.STRIPE, provider='MOCK',
        amount=plan.price, external_reference=f'mock_{uuid.uuid4().hex}',
    )
    return Subscription.objects.create(
        user=user, plan=plan, payment=payment, duration_days=plan.duration_days,
        recharge_discount_percent=plan.recharge_discount_percent,
    )


def make_vip(user, expires_at):
    user.profile.is_membership_active = True
    user.profile.membership_expires_at = expires_at
    user.profile.save()


def profile_of(user):
    user.profile.refresh_from_db()
    return user.profile


class TestActivation:
    def test_a_free_user_becomes_vip_for_the_plan_duration(self, user, plan):
        subscription = purchase(user, plan)

        activate_membership(subscription.payment)

        profile = profile_of(user)
        assert profile.is_membership_active is True
        assert profile.membership_expires_at == NOW + 30 * DAY
        assert profile.membership_status == 'VIP'

    def test_the_subscription_records_the_period_it_covers(self, user, plan):
        subscription = purchase(user, plan)

        activate_membership(subscription.payment)

        subscription.refresh_from_db()
        assert subscription.status == Subscription.Status.ACTIVE
        assert subscription.starts_at == NOW
        assert subscription.expires_at == NOW + 30 * DAY

    def test_a_current_vip_gets_the_new_period_added_after_the_expiration(self, user, plan):
        make_vip(user, NOW + 10 * DAY)

        activate_membership(purchase(user, plan).payment)

        assert profile_of(user).membership_expires_at == NOW + 40 * DAY  # 10 left + 30 bought

    def test_the_extension_period_starts_where_the_old_one_ends(self, user, plan):
        make_vip(user, NOW + 10 * DAY)
        subscription = purchase(user, plan)

        activate_membership(subscription.payment)

        subscription.refresh_from_db()
        assert subscription.starts_at == NOW + 10 * DAY
        assert subscription.expires_at == NOW + 40 * DAY

    def test_a_lapsed_vip_starts_from_now_not_from_the_past(self, user, plan):
        make_vip(user, NOW - 20 * DAY)

        activate_membership(purchase(user, plan).payment)

        assert profile_of(user).membership_expires_at == NOW + 30 * DAY

    def test_a_user_with_the_flag_off_starts_from_now(self, user, plan):
        user.profile.membership_expires_at = NOW + 100 * DAY  # stale date, flag still off
        user.profile.save()

        activate_membership(purchase(user, plan).payment)

        assert profile_of(user).membership_expires_at == NOW + 30 * DAY

    def test_an_open_ended_vip_granted_by_an_admin_is_never_shortened(self, user, plan):
        make_vip(user, None)
        subscription = purchase(user, plan)

        activate_membership(subscription.payment)

        assert profile_of(user).membership_expires_at is None
        assert profile_of(user).membership_status == 'VIP'
        subscription.refresh_from_db()
        assert subscription.status == Subscription.Status.ACTIVE

    def test_two_purchases_stack(self, user, plan):
        activate_membership(purchase(user, plan).payment)
        activate_membership(purchase(user, plan).payment)

        assert profile_of(user).membership_expires_at == NOW + 60 * DAY

    def test_the_duration_is_the_one_snapshotted_at_purchase(self, user, plan):
        subscription = purchase(user, plan)
        plan.duration_days = 365  # the admin edits the plan afterwards
        plan.save()

        activate_membership(subscription.payment)

        assert profile_of(user).membership_expires_at == NOW + 30 * DAY

    def test_the_annual_plan_adds_a_year(self, user):
        annual = MembershipPlan.objects.create(
            code='vip-anual', name='VIP Anual', period='ANNUAL', price=Decimal('99'), duration_days=365,
        )

        activate_membership(purchase(user, annual).payment)

        assert profile_of(user).membership_expires_at == NOW + 365 * DAY


class TestThroughPaymentSettlement:
    """The real path: a confirmed payment triggers the activation."""

    def test_a_confirmed_payment_activates_the_membership(self, user, plan):
        subscription = purchase(user, plan)

        settle_payment(subscription.payment_id, succeeded=True)

        assert profile_of(user).membership_status == 'VIP'
        subscription.refresh_from_db()
        assert subscription.status == Subscription.Status.ACTIVE

    def test_a_repeated_confirmation_does_not_extend_twice(self, user, plan):
        subscription = purchase(user, plan)

        for _ in range(3):
            settle_payment(subscription.payment_id, succeeded=True)

        assert profile_of(user).membership_expires_at == NOW + 30 * DAY  # not 90

    def test_a_failed_payment_leaves_the_profile_untouched(self, user, plan):
        subscription = purchase(user, plan)

        settle_payment(subscription.payment_id, succeeded=False)

        assert profile_of(user).membership_status == 'FREE'
        subscription.refresh_from_db()
        assert subscription.status == Subscription.Status.FAILED
        assert subscription.payment.status == PaymentStatus.FAILED

    def test_a_pending_payment_does_not_activate_anything(self, user, plan):
        purchase(user, plan)  # created but never confirmed

        assert profile_of(user).membership_status == 'FREE'

    def test_after_activation_the_user_gets_the_vip_exchange_rate(self, user, plan):
        assert user_gets_vip_rate(user) is False

        settle_payment(purchase(user, plan).payment_id, succeeded=True)
        user.refresh_from_db()

        assert user_gets_vip_rate(user) is True
