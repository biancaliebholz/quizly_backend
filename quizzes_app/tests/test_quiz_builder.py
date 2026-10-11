import unicodedata
from unittest.mock import patch

from django.db import DatabaseError
from django.test import TestCase

from quizzes_app.models import Question, Quiz
from quizzes_app.services.exceptions import QuizGenerationError
from quizzes_app.services.quiz_builder import build_quiz, save_quiz

from .factories import (
    GERMAN_ANSWER,
    GERMAN_OPTIONS,
    GERMAN_TITLE,
    VIDEO_URL,
    build_ai_payload,
    build_german_ai_payload,
    create_user,
)


def payload_with_first_question(**changes):
    payload = build_ai_payload()
    payload['questions'][0].update(changes)
    return payload


INVALID_PAYLOADS = {
    'nine questions': build_ai_payload(9),
    'eleven questions': build_ai_payload(11),
    'no object': ['not', 'a', 'quiz'],
    'questions not a list': {**build_ai_payload(), 'questions': 'none'},
    'question not an object': {**build_ai_payload(), 'questions': ['x'] * 10},
    'three options': payload_with_first_question(
        question_options=['A', 'B', 'C'], answer='A'
    ),
    'duplicate options': payload_with_first_question(
        question_options=['A', 'A', 'B', 'C'], answer='A'
    ),
    'answer not an option': payload_with_first_question(answer='Unknown'),
    'missing question title': payload_with_first_question(question_title=None),
    'blank title': {**build_ai_payload(), 'title': '   '},
    'html-only title': {**build_ai_payload(), 'title': '<img src=x>'},
    'too long title': {**build_ai_payload(), 'title': 'T' * 256},
}


class BuildQuizTests(TestCase):
    """AI output is cleaned and validated with the model rules."""

    def setUp(self):
        self.owner = create_user('owner')

    def build(self, payload):
        return build_quiz(self.owner, VIDEO_URL, payload)

    def test_valid_payload_builds_unsaved_quiz_with_ten_questions(self):
        quiz, questions = self.build(build_ai_payload())
        self.assertIsNone(quiz.pk)
        self.assertEqual(len(questions), 10)
        self.assertEqual(quiz.title, 'Generated Quiz')
        self.assertEqual(quiz.video_url, VIDEO_URL)

    def test_html_is_removed_from_title_and_description(self):
        payload = build_ai_payload()
        payload.update(title='<b>Bold</b> Quiz', description='<i>Desc</i>')
        quiz, _ = self.build(payload)
        self.assertEqual(quiz.title, 'Bold Quiz')
        self.assertEqual(quiz.description, 'Desc')

    def test_angle_brackets_in_options_are_kept(self):
        options = ['<div>', '<span>', '<p>', '<a>']
        payload = payload_with_first_question(
            question_options=options, answer='<div>'
        )
        _, questions = self.build(payload)
        self.assertEqual(questions[0].question_options, options)

    def test_whitespace_is_normalized_so_answer_matches_option(self):
        options = [' Option  A ', 'Option B', 'Option C', 'Option\nD']
        payload = payload_with_first_question(
            question_options=options, answer='Option A'
        )
        _, questions = self.build(payload)
        self.assertEqual(questions[0].question_options[0], 'Option A')
        self.assertEqual(questions[0].question_options[3], 'Option D')

    def test_decomposed_option_matches_composed_answer(self):
        options = ['bleibt', 'geht', 'kommt']
        options.insert(0, unicodedata.normalize('NFD', 'verlässt'))
        payload = payload_with_first_question(
            question_options=options, answer='verlässt'
        )
        _, questions = self.build(payload)
        self.assertEqual(questions[0].question_options[0], 'verlässt')
        self.assertEqual(questions[0].answer, 'verlässt')

    def test_invalid_payloads_are_rejected(self):
        for label, payload in INVALID_PAYLOADS.items():
            with self.subTest(label):
                with self.assertRaises(QuizGenerationError):
                    self.build(payload)


class SaveQuizTests(TestCase):
    """The quiz and its questions are stored atomically."""

    def setUp(self):
        owner = create_user('owner')
        self.quiz, self.questions = build_quiz(
            owner, VIDEO_URL, build_ai_payload()
        )

    def test_saves_quiz_with_all_questions(self):
        quiz = save_quiz(self.quiz, self.questions)
        self.assertEqual(Quiz.objects.get(), quiz)
        self.assertEqual(quiz.questions.count(), 10)

    def test_umlauts_survive_validation_and_saving(self):
        quiz = save_quiz(*build_quiz(
            self.quiz.owner, VIDEO_URL, build_german_ai_payload()
        ))
        stored = Quiz.objects.get(pk=quiz.pk)
        question = stored.questions.first()
        self.assertEqual(stored.title, GERMAN_TITLE)
        self.assertEqual(question.question_options, GERMAN_OPTIONS)
        self.assertEqual(question.answer, GERMAN_ANSWER)

    def test_database_error_saves_nothing(self):
        bulk_create = patch.object(
            Question.objects, 'bulk_create', side_effect=DatabaseError
        )
        with bulk_create, self.assertRaises(DatabaseError):
            save_quiz(self.quiz, self.questions)
        self.assertFalse(Quiz.objects.exists())
