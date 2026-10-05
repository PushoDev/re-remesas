import pytest
from django.conf import settings as django_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User

pytestmark = pytest.mark.django_db

LOGIN = '/api/auth/login/'
REFRESH = '/api/auth/refresh/'
LOGOUT = '/api/auth/logout/'
ME = '/api/users/me/'
PASSWORD = 'Tr3sPatos88x'
COOKIE = 'refresh_token'


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def user():
    return User.objects.create_user(
        username='ana@example.com', email='ana@example.com', password=PASSWORD,
    )


def login(client):
    return client.post(LOGIN, {'email': 'ana@example.com', 'password': PASSWORD}, format='json')


class TestRefreshCookieAttributes:
    def test_cookie_is_httponly_scoped_and_samesite(self, client, user):
        morsel = login(client).cookies[COOKIE]

        assert morsel['httponly'] is True
        assert morsel['path'] == '/api/auth/'
        assert morsel['samesite'] == 'Lax'
        assert int(morsel['max-age']) == 7 * 24 * 3600
        assert bool(morsel['secure']) is django_settings.REFRESH_COOKIE_SECURE

    def test_secure_flag_follows_setting(self, client, user, settings):
        settings.REFRESH_COOKIE_SECURE = True

        assert login(client).cookies[COOKIE]['secure'] is True

    def test_refresh_token_is_not_readable_from_any_body(self, client, user):
        assert COOKIE not in login(client).content.decode()
        client.cookies.pop(COOKIE, None)


class TestRefreshEndpoint:
    def test_without_cookie_is_401(self, client):
        assert client.post(REFRESH).status_code == 401

    def test_refresh_token_in_body_is_ignored(self, client, user):
        token = str(RefreshToken.for_user(user))

        assert client.post(REFRESH, {'refresh': token}, format='json').status_code == 401

    def test_rotates_the_cookie_and_returns_a_working_access(self, client, user):
        first = login(client).cookies[COOKIE].value
        response = client.post(REFRESH)

        assert response.status_code == 200
        assert 'refresh' not in response.data
        assert response.cookies[COOKIE].value != first
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
        assert client.get(ME).status_code == 200

    def test_invalid_cookie_is_cleared(self, client):
        client.cookies[COOKIE] = 'basura'
        response = client.post(REFRESH)

        assert response.status_code == 401
        assert response.cookies[COOKIE].value == ''

    def test_rotated_token_cannot_be_replayed(self, client, user):
        old = login(client).cookies[COOKIE].value
        client.post(REFRESH)  # rotates: the old token is blacklisted
        client.cookies[COOKIE] = old

        assert client.post(REFRESH).status_code == 401

    def test_deactivated_user_cannot_refresh(self, client, user):
        login(client)
        user.is_active = False
        user.save()
        response = client.post(REFRESH)

        assert response.status_code == 401
        assert response.cookies[COOKIE].value == ''


class TestLogout:
    def test_logout_clears_cookie_and_invalidates_the_token(self, client, user):
        token = login(client).cookies[COOKIE].value
        response = client.post(LOGOUT)

        assert response.status_code == 204
        assert response.cookies[COOKIE].value == ''
        client.cookies[COOKIE] = token  # a copied token no longer works
        assert client.post(REFRESH).status_code == 401

    def test_logout_without_session_is_idempotent(self, client):
        assert client.post(LOGOUT).status_code == 204

    def test_logout_with_garbage_cookie_is_ok(self, client):
        client.cookies[COOKIE] = 'basura'

        assert client.post(LOGOUT).status_code == 204


class TestCors:
    def test_credentials_are_allowed_for_the_frontend_origin(self, client, settings):
        settings.CORS_ALLOWED_ORIGINS = ['http://localhost:5173']
        response = client.options(
            REFRESH,
            HTTP_ORIGIN='http://localhost:5173',
            HTTP_ACCESS_CONTROL_REQUEST_METHOD='POST',
        )

        assert response['Access-Control-Allow-Origin'] == 'http://localhost:5173'
        assert response['Access-Control-Allow-Credentials'] == 'true'

    def test_unknown_origin_gets_no_cors_headers(self, client, settings):
        settings.CORS_ALLOWED_ORIGINS = ['http://localhost:5173']
        response = client.options(
            REFRESH,
            HTTP_ORIGIN='http://sitio-malo.example',
            HTTP_ACCESS_CONTROL_REQUEST_METHOD='POST',
        )

        assert 'Access-Control-Allow-Origin' not in response
