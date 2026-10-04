from datetime import timedelta

import pytest
from django.core.management import call_command
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from .models import User

pytestmark = pytest.mark.django_db

LOGIN = '/api/auth/login/'
REFRESH = '/api/auth/refresh/'
ME = '/api/users/me/'
PASSWORD = 'Tr3sPatos88x'


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def user():
    return User.objects.create_user(
        username='ana@example.com', email='ana@example.com', password=PASSWORD,
    )


def login(client, email='ana@example.com', password=PASSWORD):
    return client.post(LOGIN, {'email': email, 'password': password}, format='json')


def auth(client, access):
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')


class TestLogin:
    def test_login_returns_tokens(self, client, user):
        response = login(client)

        assert response.status_code == 200
        assert response.data['access'] and response.data['refresh']

    def test_login_normalizes_email(self, client, user):
        assert login(client, email='  ANA@Example.COM ').status_code == 200

    def test_wrong_password_is_rejected(self, client, user):
        assert login(client, password='OtraClave123').status_code == 401

    def test_unknown_email_is_rejected(self, client, user):
        assert login(client, email='nadie@example.com').status_code == 401

    def test_inactive_user_cannot_login(self, client, user):
        user.is_active = False
        user.save()

        assert login(client).status_code == 401

    def test_missing_fields(self, client):
        response = client.post(LOGIN, {}, format='json')

        assert response.status_code == 400
        assert 'email' in response.data and 'password' in response.data

    def test_login_with_invalid_authorization_header_still_works(self, client, user):
        client.credentials(HTTP_AUTHORIZATION='Bearer basura')

        assert login(client).status_code == 200


class TestRefresh:
    def test_valid_refresh_returns_new_access(self, client, user):
        refresh = login(client).data['refresh']
        response = client.post(REFRESH, {'refresh': refresh}, format='json')

        assert response.status_code == 200
        assert response.data['access']

    def test_invalid_refresh_is_rejected(self, client):
        response = client.post(REFRESH, {'refresh': 'no-es-un-token'}, format='json')

        assert response.status_code == 401

    def test_access_token_cannot_be_used_as_refresh(self, client, user):
        access = login(client).data['access']
        response = client.post(REFRESH, {'refresh': access}, format='json')

        assert response.status_code == 401


class TestMe:
    def test_requires_authentication(self, client):
        assert client.get(ME).status_code == 401

    def test_invalid_token_is_rejected(self, client):
        auth(client, 'token-invalido')

        assert client.get(ME).status_code == 401

    def test_expired_token_is_rejected(self, client, user):
        token = AccessToken.for_user(user)
        token.set_exp(lifetime=-timedelta(seconds=1))
        auth(client, str(token))

        assert client.get(ME).status_code == 401

    def test_refresh_token_cannot_authenticate(self, client, user):
        auth(client, str(RefreshToken.for_user(user)))

        assert client.get(ME).status_code == 401

    def test_deactivated_user_with_valid_token_is_rejected(self, client, user):
        access = login(client).data['access']
        user.is_active = False
        user.save()
        auth(client, access)

        assert client.get(ME).status_code == 401

    def test_returns_user_with_free_membership(self, client, user):
        auth(client, login(client).data['access'])
        response = client.get(ME)

        assert response.status_code == 200
        assert response.data['email'] == 'ana@example.com'
        assert response.data['is_staff'] is False
        assert response.data['profile']['membership_status'] == 'FREE'
        assert 'password' not in response.data

    def test_is_read_only(self, client, user):
        auth(client, login(client).data['access'])

        assert client.patch(ME, {'is_staff': True}, format='json').status_code == 405
        assert client.post(ME, {}, format='json').status_code == 405
        user.refresh_from_db()
        assert user.is_staff is False

    def test_register_then_me_works_with_the_returned_token(self, client):
        response = client.post(
            '/api/auth/register/', {'email': 'nuevo@example.com', 'password': PASSWORD},
            format='json',
        )
        auth(client, response.data['access'])

        assert client.get(ME).data['email'] == 'nuevo@example.com'


class TestDemoRoles:
    """Login by role with the seeded demo users."""

    @pytest.fixture(autouse=True)
    def seed(self):
        call_command('seed_demo_users')

    def me(self, client, email):
        response = login(client, email=email, password='Demo12345')
        assert response.status_code == 200
        auth(client, response.data['access'])
        return client.get(ME).data

    def test_admin(self, client):
        data = self.me(client, 'admin@rere.test')
        assert data['is_staff'] is True
        assert data['profile']['membership_status'] == 'FREE'

    def test_free_client(self, client):
        data = self.me(client, 'cliente@rere.test')
        assert data['is_staff'] is False
        assert data['profile']['membership_status'] == 'FREE'

    def test_vip_client(self, client):
        data = self.me(client, 'vip@rere.test')
        assert data['is_staff'] is False
        assert data['profile']['membership_status'] == 'VIP'
        assert data['profile']['membership_expires_at']

    def test_expired_vip_client_is_free(self, client):
        data = self.me(client, 'vip.vencido@rere.test')
        assert data['profile']['is_membership_active'] is True
        assert data['profile']['membership_status'] == 'FREE'
