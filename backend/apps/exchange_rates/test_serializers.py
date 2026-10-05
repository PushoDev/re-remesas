from decimal import Decimal
from types import SimpleNamespace

import pytest

from apps.users.models import User

from .models import ExchangeRate
from .serializers import ExchangeRateHistorySerializer, ExchangeRateSerializer

pytestmark = pytest.mark.django_db

VALID = {
    'currency': 'USD',
    'base_rate': '700',
    'standard_spread_percent': '5',
    'vip_spread_percent': '2',
}


@pytest.fixture
def admin():
    return User.objects.create_superuser(username='admin@example.com', email='admin@example.com', password='x')


@pytest.fixture
def ctx(admin):
    return {'request': SimpleNamespace(user=admin)}


def create(ctx, **overrides):
    serializer = ExchangeRateSerializer(data={**VALID, **overrides}, context=ctx)
    serializer.is_valid(raise_exception=True)
    return serializer.save()


def errors(ctx, instance=None, partial=False, **data):
    payload = data if partial else {**VALID, **data}
    serializer = ExchangeRateSerializer(instance, data=payload, partial=partial, context=ctx)
    assert not serializer.is_valid(), 'expected validation errors'
    return serializer.errors


class TestCreate:
    def test_valid_data_creates_the_rate_the_history_and_the_author(self, ctx, admin):
        rate = create(ctx)

        assert rate.base_rate == Decimal('700')
        assert rate.updated_by == admin
        assert rate.history.count() == 1

    def test_output_has_string_decimals_and_the_effective_rates(self, ctx):
        data = ExchangeRateSerializer(create(ctx)).data

        assert data['base_rate'] == '700.000000'
        assert data['standard_spread_percent'] == '5.00'
        assert data['effective_rate_standard'] == '665.0000'
        assert data['effective_rate_vip'] == '686.0000'
        assert data['target_currency'] == 'CUP'
        assert data['updated_by_email'] == 'admin@example.com'

    def test_target_currency_cannot_be_set_by_the_client(self, ctx):
        assert create(ctx, target_currency='USD').target_currency == 'CUP'

    def test_decimals_are_accepted_as_numbers_or_strings(self, ctx):
        assert create(ctx, base_rate=700.5).base_rate == Decimal('700.500000')


class TestValidationMessages:
    @pytest.mark.parametrize('value, message', [
        ('0', 'mayor que 0'),
        ('-5', 'mayor que 0'),
        ('abc', 'número válido'),
        ('700.1234567', 'decimales'),
    ])
    def test_base_rate(self, ctx, value, message):
        assert message in errors(ctx, base_rate=value)['base_rate'][0]

    @pytest.mark.parametrize('value, message', [
        ('-1', 'negativo'),
        ('100', 'menor que 100'),
        ('5.123', 'decimales'),
        ('x', 'número válido'),
    ])
    def test_standard_spread(self, ctx, value, message):
        assert message in errors(ctx, standard_spread_percent=value)['standard_spread_percent'][0]

    def test_vip_spread_cannot_exceed_the_standard_one(self, ctx):
        problem = errors(ctx, standard_spread_percent='5', vip_spread_percent='6')

        assert 'VIP no puede ser mayor' in problem['vip_spread_percent'][0]

    def test_vip_spread_equal_to_standard_is_allowed(self, ctx):
        assert create(ctx, standard_spread_percent='4', vip_spread_percent='4')

    def test_unknown_currency(self, ctx):
        assert 'USD o EUR' in errors(ctx, currency='MXN')['currency'][0]

    def test_required_fields(self, ctx):
        serializer = ExchangeRateSerializer(data={}, context=ctx)

        assert not serializer.is_valid()
        assert set(serializer.errors) == {'currency', 'base_rate', 'standard_spread_percent', 'vip_spread_percent'}

    def test_a_second_active_rate_for_the_same_currency_is_rejected(self, ctx):
        create(ctx)

        assert 'Ya existe una tasa activa para USD' in errors(ctx)['is_active'][0]

    def test_another_currency_or_an_inactive_duplicate_is_fine(self, ctx):
        create(ctx)

        assert create(ctx, currency='EUR')
        assert create(ctx, is_active=False)


class TestUpdate:
    def test_partial_update_keeps_other_fields_and_adds_history(self, ctx):
        rate = create(ctx)
        serializer = ExchangeRateSerializer(rate, data={'base_rate': '720'}, partial=True, context=ctx)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        rate.refresh_from_db()
        assert rate.base_rate == Decimal('720')
        assert rate.standard_spread_percent == Decimal('5')
        assert rate.history.count() == 2

    def test_updating_an_active_rate_does_not_clash_with_itself(self, ctx):
        rate = create(ctx)
        serializer = ExchangeRateSerializer(rate, data={'standard_spread_percent': '6'}, partial=True, context=ctx)

        assert serializer.is_valid(), serializer.errors

    def test_partial_update_is_checked_against_the_stored_values(self, ctx):
        rate = create(ctx)  # standard 5, vip 2
        problem = errors(ctx, rate, partial=True, vip_spread_percent='9')

        assert 'VIP no puede ser mayor' in problem['vip_spread_percent'][0]

    def test_lowering_the_standard_spread_below_the_stored_vip_one_is_rejected(self, ctx):
        rate = create(ctx)  # vip 2
        problem = errors(ctx, rate, partial=True, standard_spread_percent='1')

        assert 'vip_spread_percent' in problem

    def test_the_currency_of_an_existing_rate_cannot_change(self, ctx):
        rate = create(ctx)
        problem = errors(ctx, rate, partial=True, currency='EUR')

        assert 'No se puede cambiar la moneda' in problem['currency'][0]

    def test_deactivating_frees_the_currency_for_a_new_active_rate(self, ctx):
        rate = create(ctx)
        serializer = ExchangeRateSerializer(rate, data={'is_active': False}, partial=True, context=ctx)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        assert create(ctx, base_rate='710')
        assert ExchangeRate.objects.filter(currency='USD', is_active=True).count() == 1


class TestHistorySerializer:
    def test_exposes_the_snapshot_and_who_made_it(self, ctx):
        rate = create(ctx)
        entry = ExchangeRateHistorySerializer(rate.history.get()).data

        assert entry['base_rate'] == '700.000000'
        assert entry['changed_by_email'] == 'admin@example.com'
        assert set(entry) == {
            'id', 'base_rate', 'standard_spread_percent', 'vip_spread_percent',
            'is_active', 'changed_by_email', 'changed_at',
        }
