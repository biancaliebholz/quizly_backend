from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

User = get_user_model()

FRONTEND_ORIGIN = 'http://127.0.0.1:5500'
REFRESHED = {'detail': 'Token refreshed'}


@override_settings(CSRF_TRUSTED_ORIGINS=[FRONTEND_ORIGIN])
class TokenRefreshTests(APITestCase):
    """POST /api/token/refresh/ reads the refresh token from its cookie."""

    url = reverse('token_refresh')

    def setUp(self):
        self.user = User.objects.create_user(
            'quizfan', 'quizfan@example.com', 'Quiz9x'
        )
        self.refresh = RefreshToken.for_user(self.user)

    def refresh_with(self, token=None, origin=FRONTEND_ORIGIN, **headers):
        """POST to the endpoint with an optional refresh cookie and origin."""
        if token is not None:
            self.client.cookies['refresh_token'] = str(token)
        if origin is not None:
            headers['HTTP_ORIGIN'] = origin
        return self.client.post(self.url, **headers)

    def assert_rejected(self, response, expected_status=401):
        self.assertEqual(response.status_code, expected_status)
        self.assertNotIn('access_token', response.cookies)

    def expired_refresh_token(self):
        token = RefreshToken.for_user(self.user)
        token.set_exp(lifetime=-timedelta(seconds=1))
        return token

    def test_valid_refresh_cookie_returns_documented_body(self):
        response = self.refresh_with(self.refresh)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, REFRESHED)

    def test_new_access_cookie_is_http_only_and_valid(self):
        cookie = self.refresh_with(self.refresh).cookies['access_token']
        self.assertTrue(cookie['httponly'])
        self.assertEqual(cookie['samesite'], 'Lax')
        self.assertEqual(cookie['path'], '/')
        self.assertEqual(cookie['max-age'], 900)
        token = AccessToken(cookie.value)
        self.assertEqual(token['user_id'], str(self.user.id))

    def test_refresh_cookie_is_not_reissued(self):
        response = self.refresh_with(self.refresh)
        self.assertNotIn('refresh_token', response.cookies)

    def test_missing_refresh_cookie_is_rejected(self):
        self.assert_rejected(self.refresh_with())

    def test_unusable_refresh_tokens_are_rejected(self):
        unusable = {
            'garbage': 'not-a-jwt',
            'access token': self.refresh.access_token,
            'expired': self.expired_refresh_token(),
        }
        for label, token in unusable.items():
            with self.subTest(token=label):
                self.assert_rejected(self.refresh_with(token))

    def test_blacklisted_refresh_token_is_rejected(self):
        self.refresh.blacklist()
        self.assert_rejected(self.refresh_with(self.refresh))

    def test_inactive_user_is_rejected(self):
        self.user.is_active = False
        self.user.save()
        self.assert_rejected(self.refresh_with(self.refresh))

    def test_deleted_user_is_rejected(self):
        self.user.delete()
        self.assert_rejected(self.refresh_with(self.refresh))

    def test_untrusted_origins_are_forbidden(self):
        for origin in ('http://evil.example', 'null'):
            with self.subTest(origin=origin):
                response = self.refresh_with(self.refresh, origin=origin)
                self.assert_rejected(response, status.HTTP_403_FORBIDDEN)

    def test_missing_origin_and_referer_is_forbidden(self):
        response = self.refresh_with(self.refresh, origin=None)
        self.assert_rejected(response, status.HTTP_403_FORBIDDEN)

    def test_trusted_referer_without_origin_is_accepted(self):
        referer = f'{FRONTEND_ORIGIN}/pages/library.html'
        response = self.refresh_with(
            self.refresh, origin=None, HTTP_REFERER=referer
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_expired_access_cookie_does_not_block_refresh(self):
        access = AccessToken.for_user(self.user)
        access.set_exp(lifetime=-timedelta(seconds=1))
        self.client.cookies['access_token'] = str(access)
        response = self.refresh_with(self.refresh)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
