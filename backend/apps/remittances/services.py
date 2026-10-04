import re
import secrets

from django.utils import timezone

# Letters and digits without the look-alikes (no 0/O, 1/I): easy to read out loud to support.
ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
SUFFIX_LENGTH = 5
TRACKING_ID_RE = re.compile(rf'^RR-\d{{8}}-[{ALPHABET}]{{{SUFFIX_LENGTH}}}$')
MAX_ATTEMPTS = 10


def generate_tracking_id() -> str:
    """RR-YYYYMMDD-XXXXX, e.g. RR-20261004-7KQ2M. The suffix is random, so the
    ids of other customers cannot be guessed from one's own."""
    day = timezone.now().strftime('%Y%m%d')
    suffix = ''.join(secrets.choice(ALPHABET) for _ in range(SUFFIX_LENGTH))
    return f'RR-{day}-{suffix}'


def normalize_tracking_id(raw: str) -> str:
    """What a customer types ("rr-20261004-7kq2m ") -> the canonical form."""
    return raw.strip().upper()


def is_valid_tracking_id(value: str) -> bool:
    return bool(TRACKING_ID_RE.match(value))
