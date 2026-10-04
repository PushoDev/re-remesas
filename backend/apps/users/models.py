from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    """Custom user: the email is unique and is the login identifier.

    `username` is kept (AbstractUser requires it) and is filled with the
    email at registration time.
    """

    email = models.EmailField(unique=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    def save(self, *args, **kwargs):
        # Emails are case-insensitive: store them normalized so "A@x.com"
        # and "a@x.com" can never be two different accounts.
        if self.email:
            self.email = self.email.strip().lower()
        super().save(*args, **kwargs)


class Profile(models.Model):
    """Membership state of a user (Free or VIP).

    HU-AUTH-01 only reads this state; HU-MEM-01 is the one that activates and
    extends it after a confirmed payment.
    """

    FREE = 'FREE'
    VIP = 'VIP'

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='profile',
    )
    is_membership_active = models.BooleanField(default=False)
    membership_expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Profile({self.user.email}, {self.membership_status})'

    @property
    def membership_status(self):
        """VIP only while the membership is active and not expired."""
        if not self.is_membership_active:
            return self.FREE
        if self.membership_expires_at and self.membership_expires_at <= timezone.now():
            return self.FREE
        return self.VIP
