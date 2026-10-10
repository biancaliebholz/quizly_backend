from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken
from rest_framework_simplejwt.tokens import AccessToken

User = get_user_model()

FRONTEND_ORIGIN = 'http://127.0.0.1:5500'
CREDENTIALS = {'username': 'quizfan', 'password': 'Quiz9x'}
INVALID_LOGIN = {'detail': 'Invalid username or password.'}
TOKEN_COOKIES = ('access_token', 'refresh_token')


class LoginTestCase(APITestCase):
    """Shared fixture: one registered user and a login helper."""

    url = reverse('login')

    def setUp(self):
        self.user = User.objects.create_user(
            'quizfan', 'quizfan@example.com', 'Quiz9x'
        )

    def login(self, payload=CREDENTIALS, **headers):
        return self.client.post(self.url, payload, **headers)

    def assert_no_token_cookies(self, response):
        for name in TOKEN_COOKIES:
            self.assertNotIn(name, response.cookies)


class LoginSuccessTests(LoginTestCase):
    """POST /api/login/ with valid credentials."""

    def test_login_returns_documented_body_without_tokens(self):
        response = self.login()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        expected_user = {
            'id': self.user.id,
            'username': 'quizfan',
            'email': 'quizfan@example.com',
        }
        expected = {'detail': 'Login successfully!', 'user': expected_user}
        self.assertEqual(response.data, expected)

    def test_login_sets_http_only_token_cookies(self):
        cookies = self.login().cookies
        for name, max_age in zip(TOKEN_COOKIES, (900, 86400)):
            with self.subTest(cookie=name):
                self.assert_auth_cookie(cookies[name], max_age)

    def assert_auth_cookie(self, cookie, max_age):
        self.assertTrue(cookie['httponly'])
        self.assertEqual(cookie['samesite'], 'Lax')
        self.assertEqual(cookie['path'], '/')
        self.assertFalse(cookie['secure'])
        self.assertEqual(cookie['max-age'], max_age)

    def test_access_cookie_holds_valid_token_for_user(self):
        cookie = self.login().cookies['access_token']
        token = AccessToken(cookie.value)
        self.assertEqual(token['user_id'], str(self.user.id))

    def test_login_registers_refresh_token_as_outstanding(self):
        self.login()
        tokens = OutstandingToken.objects.filter(user=self.user)
        self.assertEqual(tokens.count(), 1)

    def test_invalid_access_cookie_does_not_block_login(self):
        self.client.cookies['access_token'] = 'not-a-jwt'
        self.assertEqual(self.login().status_code, status.HTTP_200_OK)


class LoginFailureTests(LoginTestCase):
    """Every failed login returns the same generic 401 and no cookies."""

    def assert_login_rejected(self, payload):
        response = self.login(payload)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data, INVALID_LOGIN)
        self.assert_no_token_cookies(response)

    def test_wrong_password_is_rejected(self):
        self.assert_login_rejected({**CREDENTIALS, 'password': 'Wrong9x'})

    def test_unknown_username_is_rejected(self):
        self.assert_login_rejected({**CREDENTIALS, 'username': 'nobody'})

    def test_inactive_user_is_rejected(self):
        self.user.is_active = False
        self.user.save()
        self.assert_login_rejected(CREDENTIALS)

    def test_missing_fields_are_rejected(self):
        self.assert_login_rejected({})


@override_settings(
    CORS_ALLOWED_ORIGINS=[FRONTEND_ORIGIN],
    CSRF_TRUSTED_ORIGINS=[FRONTEND_ORIGIN],
)
class LoginOriginTests(LoginTestCase):
    """Login CSRF protection: Origin/Referer must be trusted if present."""

    def test_frontend_origin_receives_credentialed_cors_response(self):
        response = self.login(HTTP_ORIGIN=FRONTEND_ORIGIN)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        headers = response.headers
        allowed_origin = headers['access-control-allow-origin']
        self.assertEqual(allowed_origin, FRONTEND_ORIGIN)
        allow_credentials = headers['access-control-allow-credentials']
        self.assertEqual(allow_credentials, 'true')

    def test_untrusted_origins_are_forbidden_without_cookies(self):
        for origin in ('http://evil.example', 'null'):
            with self.subTest(origin=origin):
                response = self.login(HTTP_ORIGIN=origin)
                self.assertEqual(response.status_code, 403)
                self.assert_no_token_cookies(response)

    def test_untrusted_referer_is_forbidden(self):
        referer = 'http://evil.example/pages/login.html'
        response = self.login(HTTP_REFERER=referer)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_request_without_origin_headers_is_allowed(self):
        self.assertEqual(self.login().status_code, status.HTTP_200_OK)
