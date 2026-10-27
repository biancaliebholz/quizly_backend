import os
import subprocess
import sys
from pathlib import Path

from django.test import SimpleTestCase

BASE_DIR = Path(__file__).resolve().parent.parent
CONTAINER_DB_PATH = '/app/data/db.sqlite3'
DB_NAME = "s.DATABASES['default']['NAME']"
DIRECT_VIDEO = 's.QUIZ_USE_DIRECT_GEMINI_VIDEO'


class ProductionSettingsTests(SimpleTestCase):
    """Docker settings: SQLite path from env, static root, proxy header.

    Settings are read once at import, so every test imports core.settings
    in a fresh Python process with its own environment.
    """

    def read_setting(self, expression, **env):
        """Return the printed value of an expression on core.settings (s)."""
        code = f'import core.settings as s; print({expression})'
        result = subprocess.run(
            [sys.executable, '-c', code],
            cwd=BASE_DIR,
            env={**os.environ, 'DJANGO_SECRET_KEY': 'test-only', **env},
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()

    def test_sqlite_path_comes_from_environment(self):
        name = self.read_setting(DB_NAME, DJANGO_SQLITE_PATH=CONTAINER_DB_PATH)
        self.assertEqual(name, CONTAINER_DB_PATH)

    def test_empty_sqlite_path_falls_back_to_project_folder(self):
        name = self.read_setting(DB_NAME, DJANGO_SQLITE_PATH='')
        self.assertEqual(name, str(BASE_DIR / 'db.sqlite3'))

    def test_static_root_is_the_staticfiles_folder(self):
        static_root = self.read_setting('s.STATIC_ROOT')
        self.assertEqual(static_root, str(BASE_DIR / 'staticfiles'))

    def test_https_is_detected_behind_the_nginx_proxy(self):
        header = self.read_setting('s.SECURE_PROXY_SSL_HEADER')
        self.assertEqual(header, "('HTTP_X_FORWARDED_PROTO', 'https')")

    def test_direct_gemini_video_is_off_unless_enabled(self):
        """An empty value wins over .env, so this also holds on the VPS."""
        for value in ('', 'False'):
            with self.subTest(value=value):
                mode = self.read_setting(
                    DIRECT_VIDEO, QUIZ_USE_DIRECT_GEMINI_VIDEO=value
                )
                self.assertEqual(mode, 'False')

    def test_direct_gemini_video_can_be_enabled(self):
        mode = self.read_setting(
            DIRECT_VIDEO, QUIZ_USE_DIRECT_GEMINI_VIDEO='True'
        )
        self.assertEqual(mode, 'True')
