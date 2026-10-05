from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Profile, User


@receiver(post_save, sender=User)
def create_profile(sender, instance, created, **kwargs):
    """Every user (registered, createsuperuser or admin) gets a Free profile."""
    if created:
        Profile.objects.get_or_create(user=instance)
