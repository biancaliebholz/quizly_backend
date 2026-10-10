from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Custom user model with a unique email address."""

    email = models.EmailField(unique=True)
