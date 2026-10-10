from urllib.parse import urlencode

from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

User = get_user_model()

FRONTEND_ORIGIN = 'http://127.0.0.1:5500'
SUCCESS_DETAIL = {'detail': 'User created successfully!'}


def build_payload(**overrides):
    """Return a valid registration payload with optional overrides."""
    payload = {
        'username': 'quizfan',
        'email': 'quizfan@example.com',
        'password': 'Quiz9x',
        'confirmed_password': 'Quiz9x',
    }
    payload.update(overrides)
    return payload


def build_password_payload(password):
    """Return a valid payload that uses password for both password fields."""
    return build_payload(password=password, confirmed_password=password)


class RegistrationSuccessTests(APITestCase):
    """Successful registrations via POST /api/register/."""

    url = reverse('register')

    def test_register_returns_201_with_documented_detail(self):
        response = self.client.post(self.url, build_payload())
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data, SUCCESS_DETAIL)

    def test_register_creates_user_with_hashed_password(self):
        self.client.post(self.url, build_payload())
        user = User.objects.get(username='quizfan')
        self.assertEqual(user.email, 'quizfan@example.com')
        self.assertNotEqual(user.password, 'Quiz9x')
        self.assertTrue(user.check_password('Quiz9x'))


class RegistrationValidationTests(APITestCase):
    """Invalid registrations must return 400 with field errors."""

    url = reverse('register')

    def assert_rejected(self, payload, field):
        """Assert a 400 response with an error for field and no new user."""
        response = self.client.post(self.url, payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(field, response.data)
        self.assertFalse(User.objects.filter(username='quizfan').exists())

    def test_mismatched_passwords_are_rejected(self):
        payload = build_payload(confirmed_password='Quiz9y')
        self.assert_rejected(payload, 'confirmed_password')

    def test_duplicate_username_is_rejected(self):
        User.objects.create_user('quizfan', 'other@example.com', 'Quiz9x')
        response = self.client.post(self.url, build_payload())
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('username', response.data)

    def test_duplicate_email_is_rejected_case_insensitively(self):
        User.objects.create_user('someone', 'quizfan@example.com', 'Quiz9x')
        payload = build_payload(email='QuizFan@Example.com')
        self.assert_rejected(payload, 'email')

    def test_missing_fields_are_rejected(self):
        response = self.client.post(self.url, {})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        for field in ('username', 'email', 'password', 'confirmed_password'):
            self.assertIn(field, response.data)

    def test_invalid_email_is_rejected(self):
        self.assert_rejected(build_payload(email='not-an-email'), 'email')

    def test_password_shorter_than_six_characters_is_rejected(self):
        payload = build_password_payload('Qz9xy')
        self.assert_rejected(payload, 'password')

    def test_numeric_password_is_rejected(self):
        payload = build_password_payload('73914826')
        self.assert_rejected(payload, 'password')

    def test_password_similar_to_username_is_rejected(self):
        payload = build_password_payload('Quizfan1')
        self.assert_rejected(payload, 'password')


class ApiBaseConfigurationTests(APITestCase):
    """JSON-only parsing and CORS behaviour, checked on /api/register/."""

    url = reverse('register')

    def send_preflight(self, origin):
        """Send a browser-like CORS preflight request for a JSON POST."""
        return self.client.options(
            self.url,
            HTTP_ORIGIN=origin,
            HTTP_ACCESS_CONTROL_REQUEST_METHOD='POST',
            HTTP_ACCESS_CONTROL_REQUEST_HEADERS='content-type',
        )

    def test_form_encoded_request_is_rejected_with_415(self):
        body = urlencode(build_payload())
        form_type = 'application/x-www-form-urlencoded'
        response = self.client.post(self.url, body, content_type=form_type)
        self.assertEqual(response.status_code, 415)
        self.assertFalse(User.objects.exists())

    @override_settings(CORS_ALLOWED_ORIGINS=[FRONTEND_ORIGIN])
    def test_preflight_from_frontend_origin_allows_credentials(self):
        headers = self.send_preflight(FRONTEND_ORIGIN).headers
        allowed_origin = headers['access-control-allow-origin']
        self.assertEqual(allowed_origin, FRONTEND_ORIGIN)
        allow_credentials = headers['access-control-allow-credentials']
        self.assertEqual(allow_credentials, 'true')

    @override_settings(CORS_ALLOWED_ORIGINS=[FRONTEND_ORIGIN])
    def test_preflight_from_foreign_origin_gets_no_cors_headers(self):
        headers = self.send_preflight('http://evil.example').headers
        self.assertNotIn('access-control-allow-origin', headers)
