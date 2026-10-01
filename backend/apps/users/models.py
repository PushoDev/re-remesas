from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Custom user so email can be unique and used as the login identifier.

    Kept minimal for Day 1 (foundation). Membership state, roles and profile
    fields are fleshed out in Day 2 per the project's development plan.
    """

    email = models.EmailField(unique=True)
