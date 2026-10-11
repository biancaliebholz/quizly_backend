import os
from unittest.mock import patch

from django.test import SimpleTestCase

from core.env import env_bool, env_list

VARIABLE = 'QUIZLY_TEST_VARIABLE'


class EnvBoolTests(SimpleTestCase):
    """Boolean settings such as DJANGO_DEBUG and AUTH_COOKIE_SECURE."""

    def read(self, value, default=False):
        with patch.dict(os.environ, {VARIABLE: value}):
            return env_bool(VARIABLE, default)

    def test_true_values_are_recognized(self):
        for value in ('True', 'true', '1', 'yes', ' ON '):
            with self.subTest(value=value):
                self.assertTrue(self.read(value))

    def test_other_values_are_false(self):
        for value in ('False', '0', 'no', ''):
            with self.subTest(value=value):
                self.assertFalse(self.read(value, default=True))

    def test_missing_variable_uses_default(self):
        with patch.dict(os.environ, clear=False):
            os.environ.pop(VARIABLE, None)
            self.assertTrue(env_bool(VARIABLE, True))
            self.assertFalse(env_bool(VARIABLE, False))


class EnvListTests(SimpleTestCase):
    """Comma-separated settings such as DJANGO_ALLOWED_HOSTS."""

    def test_items_are_trimmed_and_blank_entries_dropped(self):
        raw = ' 127.0.0.1 , localhost,, '
        with patch.dict(os.environ, {VARIABLE: raw}):
            self.assertEqual(
                env_list(VARIABLE), ['127.0.0.1', 'localhost']
            )

    def test_missing_variable_uses_default(self):
        with patch.dict(os.environ, clear=False):
            os.environ.pop(VARIABLE, None)
            result = env_list(VARIABLE, 'http://127.0.0.1:5500')
        self.assertEqual(result, ['http://127.0.0.1:5500'])
