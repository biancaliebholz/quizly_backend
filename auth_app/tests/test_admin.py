from django.contrib import admin
from django.contrib.admin.utils import flatten_fieldsets
from django.contrib.auth import get_user_model
from django.test import TestCase

User = get_user_model()


class UserAdminTests(TestCase):
    """The custom user model must be maintainable in the Django admin."""

    def test_user_model_is_registered(self):
        self.assertTrue(admin.site.is_registered(User))

    def test_add_form_asks_for_email(self):
        user_admin = admin.site.get_model_admin(User)
        self.assertIn('email', flatten_fieldsets(user_admin.add_fieldsets))
