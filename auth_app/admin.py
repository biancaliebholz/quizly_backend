from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class QuizlyUserAdmin(UserAdmin):
    """User admin that also asks for the required unique email on creation."""

    add_fieldsets = (
        (
            None,
            {
                'classes': ('wide',),
                'fields': (
                    'username',
                    'email',
                    'usable_password',
                    'password1',
                    'password2',
                ),
            },
        ),
    )
