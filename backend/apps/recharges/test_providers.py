from decimal import Decimal

import pytest

from .providers import registry
from .providers.base import ProviderOutcome, RechargeResult
from .providers.mock import MockRechargeProvider


@pytest.fixture
def provider():
    return MockRechargeProvider()


def call(provider, phone='+5351234567'):
    return provider.recharge(phone, 'saldo-10', Decimal('10.00'))


class TestMockOutcomes:
    @pytest.mark.parametrize('last_digit', '23456789')
    def test_most_numbers_succeed(self, provider, last_digit):
        assert call(provider, f'+535123456{last_digit}').status == ProviderOutcome.SUCCESS

    def test_a_number_ending_in_zero_fails(self, provider):
        assert call(provider, '+5351234560').status == ProviderOutcome.FAILED

    def test_a_number_ending_in_one_stays_processing(self, provider):
        assert call(provider, '+5351234561').status == ProviderOutcome.PROCESSING

    def test_the_same_number_always_gets_the_same_outcome(self, provider):
        assert {call(provider, '+5351234561').status for _ in range(5)} == {ProviderOutcome.PROCESSING}


class TestMockAnswer:
    @pytest.mark.parametrize('phone', ['+5351234567', '+5351234560', '+5351234561'])
    def test_always_gives_a_reference_and_a_message_in_spanish(self, provider, phone):
        result = call(provider, phone)
        assert isinstance(result, RechargeResult)
        assert result.provider_reference.startswith('RC-') and len(result.provider_reference) == 15
        assert result.message

    def test_each_call_gets_its_own_reference(self, provider):
        assert call(provider).provider_reference != call(provider).provider_reference

    @pytest.mark.parametrize('phone', ['+5351234567', '+5351234560', '+5351234561'])
    def test_the_customer_is_never_told_it_is_simulated(self, provider, phone):
        text = (call(provider, phone).message + call(provider, phone).provider_reference).lower()
        assert not any(word in text for word in ('mock', 'simul', 'demo', 'prueba', 'fake'))

    @pytest.mark.parametrize('phone', ['', '+53abc', '+5351234abc'])
    def test_refuses_something_that_is_not_a_number(self, provider, phone):
        with pytest.raises(ValueError):
            call(provider, phone)


class TestRegistry:
    def test_the_active_provider_is_the_simulated_one(self):
        assert isinstance(registry.get_provider(), MockRechargeProvider)

    def test_can_be_asked_for_by_code(self):
        assert registry.get_provider('MOCK').code == 'MOCK'

    def test_an_unknown_code_fails_loudly(self):
        with pytest.raises(KeyError):
            registry.get_provider('NOPE')
