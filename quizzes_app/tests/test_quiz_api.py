from datetime import timedelta

from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from quizzes_app.models import Question, Quiz

from .factories import VALID_OPTIONS, VIDEO_URL, create_quiz, create_user

FRONTEND_ORIGIN = 'http://127.0.0.1:5500'
UNKNOWN_ID = 99999
QUIZ_KEYS = {
    'id', 'title', 'description', 'created_at', 'updated_at',
    'video_url', 'questions',
}
QUESTION_KEYS = {'id', 'question_title', 'question_options', 'answer'}


@override_settings(CSRF_TRUSTED_ORIGINS=[FRONTEND_ORIGIN])
class QuizApiTestCase(APITestCase):
    """Owner with one quiz, another user with a foreign quiz."""

    def setUp(self):
        self.owner = create_user('owner')
        self.quiz = create_quiz(self.owner)
        self.foreign_quiz = create_quiz(create_user('other'), 'Foreign')
        token = AccessToken.for_user(self.owner)
        self.client.cookies['access_token'] = str(token)

    def detail_url(self, pk):
        return reverse('quiz-detail', args=[pk])

    def get_detail(self, pk):
        return self.client.get(self.detail_url(pk))

    def patch(self, pk, data, origin=FRONTEND_ORIGIN):
        return self.client.patch(self.detail_url(pk), data, HTTP_ORIGIN=origin)

    def delete(self, pk):
        url = self.detail_url(pk)
        return self.client.delete(url, HTTP_ORIGIN=FRONTEND_ORIGIN)

    def assert_quiz_shape(self, quiz_data):
        """Contract shape for list/detail/patch: no question timestamps."""
        self.assertEqual(set(quiz_data), QUIZ_KEYS)
        self.assertTrue(quiz_data['created_at'].endswith('Z'))
        for question in quiz_data['questions']:
            self.assertEqual(set(question), QUESTION_KEYS)


class QuizListTests(QuizApiTestCase):
    """GET /api/quizzes/"""

    url = reverse('quiz-list')

    def test_unauthenticated_request_returns_401(self):
        self.client.cookies.clear()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_lists_only_own_quizzes_newest_first(self):
        newer = create_quiz(self.owner, 'Newer')
        yesterday = timezone.now() - timedelta(days=1)
        Quiz.objects.filter(pk=self.quiz.pk).update(created_at=yesterday)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [quiz['id'] for quiz in response.data]
        self.assertEqual(ids, [newer.id, self.quiz.id])

    def test_list_items_match_documented_shape(self):
        quiz_data = self.client.get(self.url).data[0]
        self.assert_quiz_shape(quiz_data)
        self.assertEqual(len(quiz_data['questions']), 2)


class QuizDetailTests(QuizApiTestCase):
    """GET /api/quizzes/{id}/"""

    def test_own_quiz_returns_documented_quiz(self):
        response = self.get_detail(self.quiz.pk)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assert_quiz_shape(response.data)
        self.assertEqual(response.data['video_url'], VIDEO_URL)
        expected_question = {
            'id': self.quiz.questions.first().id,
            'question_title': 'Question 1',
            'question_options': VALID_OPTIONS,
            'answer': 'Option A',
        }
        self.assertEqual(response.data['questions'][0], expected_question)

    def test_foreign_quiz_returns_403(self):
        response = self.get_detail(self.foreign_quiz.pk)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unknown_quiz_returns_404(self):
        response = self.get_detail(UNKNOWN_ID)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_unauthenticated_request_returns_401(self):
        self.client.cookies.clear()
        response = self.get_detail(self.quiz.pk)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class QuizPatchTests(QuizApiTestCase):
    """PATCH /api/quizzes/{id}/ (the frontend sends title and description)."""

    def test_patch_returns_full_updated_quiz(self):
        data = {'title': 'New Title', 'description': 'New Description'}
        response = self.patch(self.quiz.pk, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assert_quiz_shape(response.data)
        self.assertEqual(response.data['title'], 'New Title')
        self.assertEqual(response.data['description'], 'New Description')
        self.assertEqual(len(response.data['questions']), 2)

    def test_patch_title_only_keeps_description(self):
        self.patch(self.quiz.pk, {'title': 'Only Title'})
        self.quiz.refresh_from_db()
        self.assertEqual(self.quiz.description, 'Quiz Description')

    def test_empty_description_is_allowed(self):
        response = self.patch(self.quiz.pk, {'description': ''})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['description'], '')

    def test_html_is_stripped_from_title(self):
        response = self.patch(self.quiz.pk, {'title': '<b>X</b>Test'})
        self.assertEqual(response.data['title'], 'XTest')
        self.quiz.refresh_from_db()
        self.assertEqual(self.quiz.title, 'XTest')

    def test_blank_or_html_only_title_is_rejected(self):
        for title in ('', '   ', '<img src=x onerror=alert(1)>'):
            with self.subTest(title=title):
                response = self.patch(self.quiz.pk, {'title': title})
                self.assertEqual(response.status_code, 400)
                self.assertIn('title', response.data)

    def test_read_only_fields_are_ignored(self):
        data = {
            'title': 'Title',
            'video_url': 'https://www.youtube.com/watch?v=other',
            'id': UNKNOWN_ID,
            'created_at': '2000-01-01T00:00:00Z',
        }
        response = self.patch(self.quiz.pk, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.quiz.pk)
        self.assertEqual(response.data['video_url'], VIDEO_URL)
        self.assertFalse(response.data['created_at'].startswith('2000'))

    def test_foreign_quiz_cannot_be_patched(self):
        response = self.patch(self.foreign_quiz.pk, {'title': 'Hacked'})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.foreign_quiz.refresh_from_db()
        self.assertEqual(self.foreign_quiz.title, 'Foreign')

    def test_unknown_quiz_patch_returns_404(self):
        response = self.patch(UNKNOWN_ID, {'title': 'Title'})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_patch_from_foreign_origin_is_forbidden(self):
        data = {'title': 'Hacked'}
        response = self.patch(self.quiz.pk, data, 'http://evil.example')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.quiz.refresh_from_db()
        self.assertEqual(self.quiz.title, 'Quiz Title')

    def test_put_is_not_allowed(self):
        url = self.detail_url(self.quiz.pk)
        data = {'title': 'Title', 'description': ''}
        response = self.client.put(url, data, HTTP_ORIGIN=FRONTEND_ORIGIN)
        self.assertEqual(response.status_code, 405)


class QuizDeleteTests(QuizApiTestCase):
    """DELETE /api/quizzes/{id}/"""

    def test_delete_returns_204_and_removes_questions(self):
        response = self.delete(self.quiz.pk)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(response.content, b'')
        self.assertFalse(Quiz.objects.filter(pk=self.quiz.pk).exists())
        orphans = Question.objects.filter(quiz_id=self.quiz.pk)
        self.assertFalse(orphans.exists())

    def test_foreign_quiz_cannot_be_deleted(self):
        response = self.delete(self.foreign_quiz.pk)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        exists = Quiz.objects.filter(pk=self.foreign_quiz.pk).exists()
        self.assertTrue(exists)

    def test_unknown_quiz_delete_returns_404(self):
        response = self.delete(UNKNOWN_ID)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
