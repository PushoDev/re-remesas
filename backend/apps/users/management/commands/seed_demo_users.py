from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.users.models import User

DEMO_PASSWORD = 'Demo12345'

# (email, first_name, is_staff, membership: None | "active" | "expired")
DEMO_USERS = [
    ('admin@rere.test', 'Admin', True, None),
    ('cliente@rere.test', 'Cliente Gratuito', False, None),
    ('vip@rere.test', 'Cliente VIP', False, 'active'),
    ('vip.vencido@rere.test', 'Cliente VIP Vencido', False, 'expired'),
]


class Command(BaseCommand):
    help = 'Crea (o restablece) usuarios de demostración, uno por rol/estado. Solo para desarrollo.'

    @transaction.atomic
    def handle(self, *args, **options):
        now = timezone.now()
        for email, first_name, is_staff, membership in DEMO_USERS:
            user, created = User.objects.get_or_create(
                email=email,
                defaults={'username': email, 'first_name': first_name},
            )
            user.first_name = first_name
            user.is_staff = is_staff
            user.is_superuser = is_staff
            user.is_active = True
            user.set_password(DEMO_PASSWORD)
            user.save()

            profile = user.profile
            profile.is_membership_active = membership is not None
            profile.membership_expires_at = {
                'active': now + timedelta(days=30),
                'expired': now - timedelta(days=1),
            }.get(membership)
            profile.save()

            self.stdout.write(
                f'{"creado " if created else "restablecido"}  {email:<24} '
                f'{"ADMIN" if is_staff else "CLIENTE":<8} {profile.membership_status}'
            )
        self.stdout.write(self.style.SUCCESS(f'Contraseña de todos: {DEMO_PASSWORD}'))
