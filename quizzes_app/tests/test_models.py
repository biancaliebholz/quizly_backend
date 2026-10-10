from datetime import timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from quizzes_app.models import Question, Quiz

from .factories import VALID_OPTIONS, create_quiz, create_user

INVALID_OPTIONS = {
    'three options': VALID_OPTIONS[:3],
    'five options': VALID_OPTIONS + ['Option E'],
    'not a list': 'Option A, Option B, Option C, Option D',
    'blank option': VALID_OPTIONS[:3] + ['   '],
    'non-text option': VALID_OPTIONS[:3] + [4],
    'duplicate options': ['Option A', 'Option A', 'Option C', 'Option D'],
}


class QuestionValidationTests(TestCase):
    """A question needs four distinct text options including the answer."""

    def setUp(self):
        self.quiz = create_quiz(create_user('owner'), question_count=0)

    def build_question(self, options, answer='Option A'):
        return Question(
            quiz=self.quiz,
            question_title='Which option is correct?',
            question_options=options,
            answer=answer,
        )

    def test_valid_question_passes_full_clean(self):
        self.build_question(list(VALID_OPTIONS)).full_clean()

    def test_invalid_options_are_rejected(self):
        for label, options in INVALID_OPTIONS.items():
            with self.subTest(label):
                with self.assertRaises(ValidationError) as context:
                    self.build_question(options).full_clean()
                errors = context.exception.message_dict
                self.assertIn('question_options', errors)

    def test_answer_must_be_one_of_the_options(self):
        question = self.build_question(list(VALID_OPTIONS), 'Option E')
        with self.assertRaises(ValidationError) as context:
            question.full_clean()
        self.assertIn('answer', context.exception.message_dict)


class QuizModelTests(TestCase):
    """Ordering, cascading delete and string representations."""

    def setUp(self):
        self.owner = create_user('owner')

    def test_quizzes_are_ordered_newest_first(self):
        older = create_quiz(self.owner, title='Older')
        newer = create_quiz(self.owner, title='Newer')
        yesterday = timezone.now() - timedelta(days=1)
        Quiz.objects.filter(pk=older.pk).update(created_at=yesterday)
        self.assertEqual(list(Quiz.objects.all()), [newer, older])

    def test_deleting_a_quiz_deletes_its_questions(self):
        quiz = create_quiz(self.owner)
        quiz.delete()
        self.assertFalse(Question.objects.exists())

    def test_string_representations(self):
        quiz = create_quiz(self.owner, question_count=1)
        self.assertEqual(str(quiz), 'Quiz Title')
        self.assertEqual(str(quiz.questions.get()), 'Question 1')
