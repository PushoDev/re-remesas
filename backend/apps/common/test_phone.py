import pytest

from .phone import InvalidCubanPhone, normalize_cuban_mobile


@pytest.mark.parametrize('raw', [
    '+53 5123 4567',
    '+5351234567',
    '5351234567',
    '53-51234567',
    '(+53) 51234567',
    '51234567',
    '  5123 4567  ',
    '5123-4567',
    '+53.5123.4567',
])
def test_accepts_the_usual_ways_of_writing_a_cuban_mobile(raw):
    assert normalize_cuban_mobile(raw) == '+5351234567'


@pytest.mark.parametrize('raw', [
    '',
    '   ',
    '5123456',          # 7 digits
    '512345678',        # 9 digits
    '41234567',         # does not start with 5 (not a mobile)
    '71234567',
    '+54 51234567',     # another country
    '+1 5123 4567',
    '5311111111',       # 53 prefix but the number itself is not a mobile
    'abcdefgh',
    '5123 45a7',
    '+53',
])
def test_rejects_anything_else(raw):
    with pytest.raises(InvalidCubanPhone):
        normalize_cuban_mobile(raw)


def test_rejects_non_strings():
    with pytest.raises(InvalidCubanPhone):
        normalize_cuban_mobile(None)  # type: ignore[arg-type]
    with pytest.raises(InvalidCubanPhone):
        normalize_cuban_mobile(51234567)  # type: ignore[arg-type]


def test_the_error_is_a_value_error_with_a_spanish_message():
    with pytest.raises(ValueError, match='móvil cubano'):
        normalize_cuban_mobile('123')


def test_normalizing_twice_changes_nothing():
    once = normalize_cuban_mobile('5123 4567')

    assert normalize_cuban_mobile(once) == once
