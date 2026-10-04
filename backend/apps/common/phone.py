"""Cuban mobile numbers, shared by remittances (recipient) and recharges.

A Cuban mobile number is +53 followed by 8 digits that start with 5. Input is
accepted in the usual human forms and always normalized to "+53XXXXXXXX".
"""
import re


class InvalidCubanPhone(ValueError):
    """The text is not a valid Cuban mobile number."""


_MOBILE = re.compile(r'^5\d{7}$')


def normalize_cuban_mobile(raw: str) -> str:
    if not isinstance(raw, str):
        raise InvalidCubanPhone('Ingresa un número de teléfono.')
    text = raw.strip()
    if re.search(r'[^\d\s+()\-.]', text):
        raise InvalidCubanPhone('El teléfono solo puede contener números, espacios, + y guiones.')

    digits = re.sub(r'\D', '', text)
    if text.startswith('+') or digits.startswith('53') and len(digits) == 10:
        if not digits.startswith('53'):
            raise InvalidCubanPhone('El número debe llevar el prefijo +53 de Cuba.')
        digits = digits[2:]

    if not _MOBILE.match(digits):
        raise InvalidCubanPhone('Escribe un móvil cubano válido: +53 seguido de 8 dígitos que empiezan por 5.')
    return f'+53{digits}'
