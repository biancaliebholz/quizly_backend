from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import AccessToken

User = get_user_model()

FRONTEND_ORIGIN = 'http://127.0.0.1:5500'
FOREIGN_ORIGIN = 'http://evil.example'
UNSAFE_METHODS = ('post', 'patch', 'delete')


class ProbeView(APIView):
    """Test-only endpoint protected by the project's default auth settings."""

    def get(self, request):
        return Response({'username': request.user.username})

    post = patch = delete = get


@override_settings(CSRF_TRUSTED_ORIGINS=[FRONTEND_ORIGIN])
class CookieJWTAuthenticationTests(TestCase):
    """Cookie-only JWT authentication plus Origin/Referer CSRF check."""

    def setUp(self):
        self.user = User.objects.create_user(
            'quizfan', 'quizfan@example.com', 'Quiz9x'
        )
        self.token = str(AccessToken.for_user(self.user))
        self.factory = APIRequestFactory()

    def call(self, method, token=None, **headers):
        """Send a request to the probe view, optionally with access cookie."""
        if token is not None:
            headers['HTTP_COOKIE'] = f'access_token={token}'
        request = getattr(self.factory, method)('/probe/', **headers)
        return ProbeView.as_view()(request)

    def test_get_with_valid_cookie_authenticates_without_origin(self):
        response = self.call('get', self.token)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {'username': 'quizfan'})

    def test_get_without_cookie_returns_401(self):
        response = self.call('get')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_invalid_token_returns_401(self):
        response = self.call('get', 'not-a-jwt')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_expired_token_returns_401(self):
        token = AccessToken.for_user(self.user)
        token.set_exp(lifetime=-timedelta(seconds=1))
        response = self.call('get', str(token))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_bearer_header_without_cookie_returns_401(self):
        bearer = f'Bearer {self.token}'
        response = self.call('get', HTTP_AUTHORIZATION=bearer)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def assert_unsafe_methods_return(self, origin, expected_status):
        """Send POST, PATCH and DELETE from origin and check the status."""
        for method in UNSAFE_METHODS:
            with self.subTest(method=method):
                response = self.call(method, self.token, HTTP_ORIGIN=origin)
                self.assertEqual(response.status_code, expected_status)

    def test_unsafe_methods_from_trusted_origin_pass(self):
        self.assert_unsafe_methods_return(FRONTEND_ORIGIN, status.HTTP_200_OK)

    def test_unsafe_methods_from_foreign_origin_are_forbidden(self):
        forbidden = status.HTTP_403_FORBIDDEN
        self.assert_unsafe_methods_return(FOREIGN_ORIGIN, forbidden)

    def test_null_origin_is_forbidden(self):
        response = self.call('post', self.token, HTTP_ORIGIN='null')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_trusted_referer_without_origin_passes(self):
        referer = f'{FRONTEND_ORIGIN}/pages/library.html'
        response = self.call('post', self.token, HTTP_REFERER=referer)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_foreign_referer_without_origin_is_forbidden(self):
        referer = f'{FOREIGN_ORIGIN}/attack.html'
        response = self.call('post', self.token, HTTP_REFERER=referer)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_missing_origin_and_referer_is_forbidden(self):
        response = self.call('post', self.token)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_unsafe_request_returns_401_not_403(self):
        response = self.call('post', HTTP_ORIGIN=FOREIGN_ORIGIN)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
