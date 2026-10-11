from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

User = get_user_model()

FRONTEND_ORIGIN = 'http://127.0.0.1:5500'
CREDENTIALS = {'username': 'devuser', 'password': 'Quiz9x'}


@override_settings(DEBUG=True, CSRF_TRUSTED_ORIGINS=[FRONTEND_ORIGIN])
class DebugModeSmokeTests(APITestCase):
    """Local development (DJANGO_DEBUG=True) keeps auth, API and admin usable.

    The test runner always forces DEBUG=False, so DEBUG is switched on here.
    """

    def post(self, name, data=None):
        url = reverse(name)
        return self.client.post(url, data or {}, HTTP_ORIGIN=FRONTEND_ORIGIN)

    def register_and_login(self):
        registration = {
            **CREDENTIALS,
            'email': 'dev@example.com',
            'confirmed_password': CREDENTIALS['password'],
        }
        self.assertEqual(self.post('register', registration).status_code, 201)
        self.assertEqual(self.post('login', CREDENTIALS).status_code, 200)

    def test_cookie_auth_flow_and_quiz_api_work(self):
        self.register_and_login()
        response = self.client.get(reverse('quiz-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.post('token_refresh').status_code, 200)
        self.assertEqual(self.post('logout').status_code, 200)
        after_logout = self.client.get(reverse('quiz-list'))
        self.assertEqual(after_logout.status_code, 401)

    def test_admin_login_page_and_quiz_admin_work(self):
        login_page = self.client.get(reverse('admin:login'))
        self.assertEqual(login_page.status_code, status.HTTP_200_OK)
        admin_user = User.objects.create(
            username='admin', is_staff=True, is_superuser=True
        )
        self.client.force_login(admin_user)
        changelist = reverse('admin:quizzes_app_quiz_changelist')
        self.assertEqual(self.client.get(changelist).status_code, 200)
