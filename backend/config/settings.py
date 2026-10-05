"""
Django settings for config project (Re & Re — Remesas & Recargas).
"""

from pathlib import Path
import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, False),
)
environ.Env.read_env(BASE_DIR / '.env')

SECRET_KEY = env('SECRET_KEY', default='django-insecure-dev-only-change-me')
DEBUG = env('DEBUG')

ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=['localhost', '127.0.0.1'])

# nginx (Lerd) terminates TLS and proxies plain HTTP to Django.
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
CSRF_TRUSTED_ORIGINS = env.list('CSRF_TRUSTED_ORIGINS', default=[])


INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'apps.users',
    'apps.memberships',
    'apps.remittances',
    'apps.recharges',
    'apps.payments',
    'apps.exchange_rates',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# Database — Postgres, started via docker-compose (see repo root).
DATABASES = {
    'default': env.db('DATABASE_URL', default='sqlite:///' + str(BASE_DIR / 'db.sqlite3')),
}

AUTH_USER_MODEL = 'users.User'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 8}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
    {'NAME': 'apps.users.validators.LetterAndDigitPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# Django REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
}

from datetime import timedelta  # noqa: E402

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=30),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
}

CORS_ALLOWED_ORIGINS = env.list('CORS_ALLOWED_ORIGINS', default=[])

# The refresh token travels only in an httpOnly cookie (never in a JSON body or
# readable by JS). The cookie is only sent to /api/auth/ and, with SameSite=Lax,
# only between origins of the same site (localhost:5173 -> localhost:8001).
REFRESH_COOKIE_NAME = 'refresh_token'
REFRESH_COOKIE_PATH = '/api/auth/'
REFRESH_COOKIE_SAMESITE = 'Lax'
REFRESH_COOKIE_SECURE = env.bool('AUTH_COOKIE_SECURE', default=not DEBUG)
CORS_ALLOW_CREDENTIALS = True

# Shared secret used to sign/verify the mock gateway's webhooks (HMAC-SHA256).
# The default is for local development only: set a real value in production.
PAYMENT_WEBHOOK_SECRET = env('PAYMENT_WEBHOOK_SECRET', default='dev-only-webhook-secret')

# The simulated checkout (POST /api/payments/mock/<ref>/confirm/) only exists while this is on.
# It defaults to DEBUG, so it is off in production unless explicitly enabled.
PAYMENT_MOCK_ENABLED = env.bool('PAYMENT_MOCK_ENABLED', default=DEBUG)

# Limits for a single remittance, in the currency sent. NOT defined by the specification:
# they are an assumption of this implementation, kept configurable.
REMITTANCE_MIN_AMOUNT = env('REMITTANCE_MIN_AMOUNT', default='1.00')
REMITTANCE_MAX_AMOUNT = env('REMITTANCE_MAX_AMOUNT', default='10000.00')

# Payment proofs uploaded by customers. Private: there is NO public URL for MEDIA_ROOT;
# files are only handed out through authenticated endpoints.
MEDIA_ROOT = BASE_DIR / 'media'
MEDIA_URL = 'media/'
PAYMENT_PROOF_MAX_BYTES = 5 * 1024 * 1024
