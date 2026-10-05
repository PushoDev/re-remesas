import pytest
from django.test import Client
from django.urls import reverse

from .models import Profile, User

pytestmark = pytest.mark.django_db

PASSWORD = 'Tr3sPatos88x'


@pytest.fixture
def admin_client():
    admin = User.objects.create_superuser(
        username='admin@example.com', email='admin@example.com', password=PASSWORD,
    )
    client = Client()
    client.force_login(admin)
    return client


@pytest.fixture
def customer():
    return User.objects.create_user(
        username='ana@example.com', email='ana@example.com', password=PASSWORD,
    )


class TestAdminAccess:
    def test_admin_login_works_with_email(self):
        User.objects.create_superuser(
            username='admin@example.com', email='admin@example.com', password=PASSWORD,
        )
        # The real login form carries a hidden `next` field pointing to the admin.
        response = Client().post(reverse('admin:login'), {
            'username': 'admin@example.com',
            'password': PASSWORD,
            'next': reverse('admin:index'),
        })

        assert response.status_code == 302
        assert response.url == reverse('admin:index')

    def test_regular_customer_cannot_enter_admin(self, customer):
        response = Client().post(
            reverse('admin:login'), {'username': 'ana@example.com', 'password': PASSWORD},
        )

        assert response.status_code == 200  # login form again, with an error
        assert Client().get(reverse('admin:users_user_changelist')).status_code == 302


class TestAdminPages:
    def test_changelist_shows_users_with_membership(self, admin_client, customer):
        response = admin_client.get(reverse('admin:users_user_changelist'))

        assert response.status_code == 200
        assert b'ana@example.com' in response.content

    def test_changelist_search_by_email(self, admin_client, customer):
        response = admin_client.get(reverse('admin:users_user_changelist'), {'q': 'ana@'})

        assert b'ana@example.com' in response.content

    def test_change_page_shows_profile_inline(self, admin_client, customer):
        response = admin_client.get(reverse('admin:users_user_change', args=[customer.pk]))

        assert response.status_code == 200
        assert b'is_membership_active' in response.content

    def test_add_page_has_no_profile_inline(self, admin_client):
        response = admin_client.get(reverse('admin:users_user_add'))

        assert response.status_code == 200
        assert b'is_membership_active' not in response.content


class TestAdminCreateAndEdit:
    def test_create_user_sets_username_and_a_single_free_profile(self, admin_client):
        response = admin_client.post(reverse('admin:users_user_add'), {
            'email': 'Nuevo@Example.com',
            'usable_password': 'true',
            'password1': PASSWORD,
            'password2': PASSWORD,
        })

        assert response.status_code == 302, getattr(response, 'context', None) and response.context['errors']
        user = User.objects.get(email='nuevo@example.com')
        assert user.username == 'nuevo@example.com'
        assert user.check_password(PASSWORD)
        assert Profile.objects.filter(user=user).count() == 1
        assert user.profile.membership_status == Profile.FREE

    def test_activate_membership_from_the_inline(self, admin_client, customer):
        profile = customer.profile
        response = admin_client.post(reverse('admin:users_user_change', args=[customer.pk]), {
            'email': customer.email,
            'first_name': 'Ana',
            'last_name': '',
            'is_active': 'on',
            'profile-TOTAL_FORMS': '1',
            'profile-INITIAL_FORMS': '1',
            'profile-MIN_NUM_FORMS': '0',
            'profile-MAX_NUM_FORMS': '1',
            'profile-0-id': profile.pk,
            'profile-0-user': customer.pk,
            'profile-0-is_membership_active': 'on',
            'profile-0-membership_expires_at_0': '2099-01-01',
            'profile-0-membership_expires_at_1': '00:00:00',
        })

        assert response.status_code == 302, getattr(response, 'context', None) and response.context['errors']
        customer.refresh_from_db()
        assert customer.first_name == 'Ana'
        assert customer.profile.membership_status == Profile.VIP
