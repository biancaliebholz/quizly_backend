from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Custom user model with a unique email address."""

    email = models.EmailField(unique=True)


class BlockedAccessToken(models.Model):
    """Access token revoked by logout before its regular expiry."""

    jti = models.CharField(max_length=255, unique=True)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.jti
