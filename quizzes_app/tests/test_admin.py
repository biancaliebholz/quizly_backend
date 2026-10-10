import json

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from quizzes_app.admin import QuestionInline
from quizzes_app.models import Question, Quiz

from .factories import create_quiz

User = get_user_model()


class QuizAdminTests(TestCase):
    """Quizzes and single questions must be editable in the Django admin."""

    def setUp(self):
        self.admin_user = User.objects.create(
            username='admin', is_staff=True, is_superuser=True
        )
        self.client.force_login(self.admin_user)
        self.quiz = create_quiz(self.admin_user)
        self.question = self.quiz.questions.first()

    def test_quiz_and_question_are_registered(self):
        for model in (Quiz, Question):
            with self.subTest(model=model.__name__):
                self.assertTrue(admin.site.is_registered(model))

    def test_quiz_admin_edits_questions_inline(self):
        quiz_admin = admin.site.get_model_admin(Quiz)
        self.assertIn(QuestionInline, quiz_admin.inlines)

    def test_change_pages_render(self):
        urls = (
            reverse('admin:quizzes_app_quiz_change', args=[self.quiz.pk]),
            reverse(
                'admin:quizzes_app_question_change', args=[self.question.pk]
            ),
        )
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_admin_rejects_question_with_three_options(self):
        url = reverse(
            'admin:quizzes_app_question_change', args=[self.question.pk]
        )
        response = self.client.post(url, {
            'quiz': self.quiz.pk,
            'question_title': 'Changed?',
            'question_options': json.dumps(['A', 'B', 'C']),
            'answer': 'A',
        })
        self.assertEqual(response.status_code, 200)
        self.question.refresh_from_db()
        self.assertEqual(self.question.question_title, 'Question 1')
