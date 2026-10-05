from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from .models import Promotion, RechargePackage
from .services import current_promotions, get_catalog, pick_promotion

pytestmark = pytest.mark.django_db

NOW = timezone.now()


def make_package(code='saldo-10', price='10.00', **extra):
    return RechargePackage.objects.create(
        code=code, name=code, kind=RechargePackage.Kind.BALANCE, price=Decimal(price), **extra,
    )


def make_promo(code='bono', starts=-1, ends=1, package=None, **extra):
    """starts/ends are days from NOW (negative = in the past)."""
    return Promotion.objects.create(
        code=code, title=code, package=package, starts_at=NOW + timedelta(days=starts),
        ends_at=NOW + timedelta(days=ends), **extra,
    )


class TestWhichPromotionsAreCurrent:
    def test_one_inside_its_window_is_current(self):
        promo = make_promo()
        assert current_promotions(NOW) == [promo]

    def test_an_expired_one_is_not(self):
        make_promo(starts=-5, ends=-1)
        assert current_promotions(NOW) == []

    def test_one_that_has_not_started_is_not(self):
        make_promo(starts=1, ends=5)
        assert current_promotions(NOW) == []

    def test_one_switched_off_is_not_even_inside_its_window(self):
        make_promo(is_active=False)
        assert current_promotions(NOW) == []

    def test_the_start_is_included_and_the_end_is_excluded(self):
        promo = make_promo(starts=0, ends=1)
        assert current_promotions(promo.starts_at) == [promo]
        assert current_promotions(promo.ends_at) == []

    def test_without_a_given_time_it_uses_the_real_clock(self):
        promo = Promotion.objects.create(
            code='ahora', title='Ahora', starts_at=timezone.now() - timedelta(minutes=1),
            ends_at=timezone.now() + timedelta(minutes=1),
        )
        assert current_promotions() == [promo]


class TestWhichPromotionShowsForAPackage:
    def test_none_when_there_is_nothing_current(self):
        assert pick_promotion(make_package(), []) is None

    def test_one_for_everything_applies_to_any_package(self):
        promo = make_promo()
        assert pick_promotion(make_package(), [promo]) == promo

    def test_one_for_another_package_does_not_apply(self):
        mine, other = make_package('mine'), make_package('other')
        assert pick_promotion(mine, [make_promo(package=other)]) is None

    def test_one_made_for_the_package_beats_one_for_everything(self):
        package = make_package()
        general = make_promo('general', ends=1)
        specific = make_promo('specific', ends=5, package=package)
        assert pick_promotion(package, [general, specific]) == specific

    def test_between_equals_the_one_ending_first_wins(self):
        package = make_package()
        later = make_promo('later', ends=5, package=package)
        sooner = make_promo('sooner', ends=2, package=package)
        assert pick_promotion(package, [later, sooner]) == sooner


class TestCatalog:
    def test_lists_only_active_packages(self):
        make_package('on')
        make_package('off', is_active=False)
        assert [entry.package.code for entry in get_catalog(NOW)] == ['on']

    def test_attaches_the_current_promotion_to_the_right_packages(self):
        mine, other = make_package('mine', '5.00'), make_package('other', '10.00')
        promo = make_promo(package=mine)
        entries = {entry.package.code: entry.active_promotion for entry in get_catalog(NOW)}
        assert entries == {'mine': promo, 'other': None}

    def test_a_promotion_that_just_ended_disappears_from_the_catalog(self):
        make_package()
        promo = make_promo(starts=-1, ends=1)
        assert get_catalog(NOW)[0].active_promotion == promo
        assert get_catalog(promo.ends_at)[0].active_promotion is None

    def test_follows_the_packages_sort_order(self):
        make_package('b', '10.00')
        make_package('a', '5.00')
        assert [entry.package.code for entry in get_catalog(NOW)] == ['a', 'b']

    def test_does_not_grow_queries_with_the_number_of_packages(self, django_assert_num_queries):
        for index in range(6):
            make_package(f'p{index}', price=str(index + 1))
        make_promo()
        with django_assert_num_queries(2):
            get_catalog(NOW)
