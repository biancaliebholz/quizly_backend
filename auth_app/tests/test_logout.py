from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from auth_app.models import BlockedAccessToken

User = get_user_model()

FRONTEND_ORIGIN = 'http://127.0.0.1:5500'
FOREIGN_ORIGIN = 'http://evil.example'
TOKEN_COOKIES = ('access_token', 'refresh_token')
LOGOUT_DETAIL = {
    'detail': (
        'Log-Out successfully! All Tokens will be deleted. '
        'Refresh token is now invalid.'
    ),
}


@override_settings(CSRF_TRUSTED_ORIGINS=[FRONTEND_ORIGIN])
class LogoutTests(APITestCase):
    """POST /api/logout/ revokes both JWTs and deletes their cookies."""

    url = reverse('logout')

    def setUp(self):
        self.user = User.objects.create_user(
            'quizfan', 'quizfan@example.com', 'Quiz9x'
        )
        self.refresh = RefreshToken.for_user(self.user)
        self.access = self.refresh.access_token
        self.set_token_cookies(self.access)

    def set_token_cookies(self, access):
        self.client.cookies['access_token'] = str(access)
        self.client.cookies['refresh_token'] = str(self.refresh)

    def logout(self, origin=FRONTEND_ORIGIN):
        headers = {'HTTP_ORIGIN': origin} if origin else {}
        return self.client.post(self.url, **headers)

    def expired_access_token(self):
        token = AccessToken.for_user(self.user)
        token.set_exp(lifetime=-timedelta(seconds=1))
        return token

    def is_refresh_blacklisted(self):
        jti = self.refresh['jti']
        return BlacklistedToken.objects.filter(token__jti=jti).exists()

    def is_access_blocked(self):
        jti = self.access['jti']
        return BlockedAccessToken.objects.filter(jti=jti).exists()

    def assert_cookies_deleted(self, response):
        for name in TOKEN_COOKIES:
            with self.subTest(cookie=name):
                self.assertEqual(response.cookies[name].value, '')
                self.assertEqual(response.cookies[name]['max-age'], 0)

    def assert_nothing_revoked(self, response):
        self.assertFalse(self.is_refresh_blacklisted())
        self.assertFalse(self.is_access_blocked())
        for name in TOKEN_COOKIES:
            self.assertNotIn(name, response.cookies)

    def test_logout_returns_documented_detail_and_deletes_cookies(self):
        response = self.logout()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, LOGOUT_DETAIL)
        self.assert_cookies_deleted(response)

    def test_logout_revokes_refresh_and_access_token(self):
        self.logout()
        self.assertTrue(self.is_refresh_blacklisted())
        self.assertTrue(self.is_access_blocked())

    def test_old_refresh_token_cannot_refresh_after_logout(self):
        self.logout()
        self.set_token_cookies(self.access)
        response = self.client.post(
            reverse('token_refresh'), HTTP_ORIGIN=FRONTEND_ORIGIN
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_second_logout_with_old_tokens_returns_401(self):
        self.logout()
        self.set_token_cookies(self.access)
        response = self.logout()
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_without_cookies_returns_401(self):
        self.client.cookies.clear()
        response = self.logout()
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_expired_access_from_frontend_still_logs_out(self):
        self.set_token_cookies(self.expired_access_token())
        response = self.logout()
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertTrue(self.is_refresh_blacklisted())
        self.assert_cookies_deleted(response)

    def test_expired_access_from_foreign_origin_revokes_nothing(self):
        self.set_token_cookies(self.expired_access_token())
        response = self.logout(origin=FOREIGN_ORIGIN)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assert_nothing_revoked(response)

    def test_untrusted_or_missing_origin_is_forbidden(self):
        for origin in (FOREIGN_ORIGIN, None):
            with self.subTest(origin=origin):
                response = self.logout(origin=origin)
                self.assertEqual(response.status_code, 403)
                self.assert_nothing_revoked(response)
