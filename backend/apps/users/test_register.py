import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from .models import Profile, User

pytestmark = pytest.mark.django_db

URL = '/api/auth/register/'
VALID = {'email': 'ana@example.com', 'password': 'Tr3sPatos88x'}


@pytest.fixture
def client():
    return APIClient()


class TestRegisterSuccess:
    def test_creates_user_and_free_profile(self, client):
        response = client.post(URL, VALID, format='json')

        assert response.status_code == 201
        user = User.objects.get(email='ana@example.com')
        assert user.username == 'ana@example.com'
        assert user.profile.membership_status == Profile.FREE
        body = response.data
        assert body['user']['email'] == 'ana@example.com'
        assert body['user']['is_staff'] is False
        assert body['user']['profile']['membership_status'] == 'FREE'

    def test_returns_valid_jwt_tokens(self, client):
        response = client.post(URL, VALID, format='json')

        user = User.objects.get(email='ana@example.com')
        assert AccessToken(response.data['access'])['user_id'] == str(user.pk)
        assert response.data['refresh']

    def test_password_is_hashed_and_never_returned(self, client):
        response = client.post(URL, VALID, format='json')

        user = User.objects.get(email='ana@example.com')
        assert user.password != VALID['password']
        assert user.check_password(VALID['password'])
        assert 'password' not in response.data['user']
        assert 'password' not in response.data

    def test_email_is_normalized_to_lowercase(self, client):
        response = client.post(URL, {**VALID, 'email': '  Ana@Example.COM '}, format='json')

        assert response.status_code == 201
        assert response.data['user']['email'] == 'ana@example.com'

    def test_optional_names_are_saved(self, client):
        data = {**VALID, 'first_name': 'Ana', 'last_name': 'Pérez'}
        response = client.post(URL, data, format='json')

        assert response.status_code == 201
        assert response.data['user']['first_name'] == 'Ana'

    def test_cannot_self_assign_admin_role(self, client):
        data = {**VALID, 'is_staff': True, 'is_superuser': True}
        client.post(URL, data, format='json')

        user = User.objects.get(email='ana@example.com')
        assert user.is_staff is False and user.is_superuser is False

    def test_invalid_authorization_header_does_not_block_registration(self, client):
        client.credentials(HTTP_AUTHORIZATION='Bearer token-vencido-o-basura')
        response = client.post(URL, VALID, format='json')

        assert response.status_code == 201


class TestRegisterDuplicateEmail:
    def test_duplicate_email_is_rejected(self, client):
        client.post(URL, VALID, format='json')
        response = client.post(URL, VALID, format='json')

        assert response.status_code == 400
        assert 'email' in response.data
        assert User.objects.count() == 1

    def test_duplicate_email_ignores_case(self, client):
        client.post(URL, VALID, format='json')
        response = client.post(URL, {**VALID, 'email': 'ANA@Example.com'}, format='json')

        assert response.status_code == 400
        assert 'email' in response.data
        assert User.objects.count() == 1


class TestRegisterPasswordRules:
    @pytest.mark.parametrize('password', [
        'Ab1xyz',          # menos de 8
        'SoloLetrasAqui',  # sin números
        '48273650192',     # sin letras
        'password123',     # contraseña común
    ])
    def test_weak_passwords_are_rejected(self, client, password):
        response = client.post(URL, {**VALID, 'password': password}, format='json')

        assert response.status_code == 400
        assert 'password' in response.data
        assert User.objects.count() == 0

    def test_password_similar_to_email_is_rejected(self, client):
        data = {'email': 'carlosperez@example.com', 'password': 'carlosperez1'}
        response = client.post(URL, data, format='json')

        assert response.status_code == 400
        assert 'password' in response.data


class TestRegisterValidation:
    def test_missing_fields(self, client):
        response = client.post(URL, {}, format='json')

        assert response.status_code == 400
        assert 'email' in response.data and 'password' in response.data

    def test_invalid_email_format(self, client):
        response = client.post(URL, {**VALID, 'email': 'no-es-un-correo'}, format='json')

        assert response.status_code == 400
        assert 'email' in response.data

    def test_get_is_not_allowed(self, client):
        assert client.get(URL).status_code == 405
