from datetime import timedelta

import pytest
from django.contrib.auth import authenticate
from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import Profile, User

pytestmark = pytest.mark.django_db


def make_user(email='ana@example.com', password='Clave1234'):
    return User.objects.create_user(username=email, email=email, password=password)


class TestUser:
    def test_email_is_login_identifier(self):
        assert User.USERNAME_FIELD == 'email'
        make_user()
        assert authenticate(email='ana@example.com', password='Clave1234') is not None

    def test_email_is_normalized_to_lowercase(self):
        user = make_user('Ana@Example.COM')
        assert user.email == 'ana@example.com'

    def test_duplicate_email_is_rejected_ignoring_case(self):
        make_user('ana@example.com')
        with pytest.raises(IntegrityError), transaction.atomic():
            make_user('ANA@example.com')


class TestProfile:
    def test_profile_is_created_with_user_as_free(self):
        user = make_user()
        assert Profile.objects.filter(user=user).count() == 1
        assert user.profile.is_membership_active is False
        assert user.profile.membership_status == Profile.FREE

    def test_superuser_also_gets_profile(self):
        admin = User.objects.create_superuser(
            username='admin@example.com', email='admin@example.com', password='Admin1234',
        )
        assert admin.profile.membership_status == Profile.FREE

    def test_vip_when_active_with_future_expiration(self):
        profile = make_user().profile
        profile.is_membership_active = True
        profile.membership_expires_at = timezone.now() + timedelta(days=30)
        assert profile.membership_status == Profile.VIP

    def test_vip_when_active_without_expiration(self):
        profile = make_user().profile
        profile.is_membership_active = True
        assert profile.membership_status == Profile.VIP

    def test_free_when_expired_even_if_flag_is_true(self):
        profile = make_user().profile
        profile.is_membership_active = True
        profile.membership_expires_at = timezone.now() - timedelta(seconds=1)
        assert profile.membership_status == Profile.FREE

    def test_free_when_flag_is_false_even_with_future_expiration(self):
        profile = make_user().profile
        profile.is_membership_active = False
        profile.membership_expires_at = timezone.now() + timedelta(days=30)
        assert profile.membership_status == Profile.FREE


class TestSeedDemoUsers:
    def test_seed_creates_one_user_per_role_and_is_idempotent(self):
        from django.core.management import call_command

        call_command('seed_demo_users')
        call_command('seed_demo_users')  # running twice must not duplicate

        assert User.objects.count() == 4
        admin = User.objects.get(email='admin@rere.test')
        assert admin.is_staff and admin.check_password('Demo12345')
        assert User.objects.get(email='cliente@rere.test').profile.membership_status == Profile.FREE
        assert User.objects.get(email='vip@rere.test').profile.membership_status == Profile.VIP
        assert User.objects.get(email='vip.vencido@rere.test').profile.membership_status == Profile.FREE


class TestPasswordRules:
    """HU-AUTH-01: mínimo 8 caracteres, con letras y números."""

    @staticmethod
    def codes(password):
        from django.contrib.auth.password_validation import validate_password
        from django.core.exceptions import ValidationError

        try:
            validate_password(password)
        except ValidationError as exc:
            return {error.code for error in exc.error_list}
        return set()

    def test_valid_password_is_accepted(self):
        assert self.codes('Tr3sPatos88x') == set()

    def test_only_letters_is_rejected(self):
        assert 'password_no_digit' in self.codes('SoloLetrasAqui')

    def test_only_digits_is_rejected(self):
        assert 'password_no_letter' in self.codes('48273650192')

    def test_shorter_than_8_is_rejected(self):
        assert 'password_too_short' in self.codes('Ab1xyz')

    def test_common_password_is_rejected(self):
        assert 'password_too_common' in self.codes('password123')

    def test_unicode_letters_count_as_letters(self):
        assert self.codes('Contraseña2026') == set()

    def test_error_messages_are_in_spanish(self):
        from django.core.exceptions import ValidationError
        from apps.users.validators import LetterAndDigitPasswordValidator

        with pytest.raises(ValidationError) as exc:
            LetterAndDigitPasswordValidator().validate('!!!!!!!!')
        messages = ' '.join(exc.value.messages)
        assert 'letra' in messages and 'número' in messages
