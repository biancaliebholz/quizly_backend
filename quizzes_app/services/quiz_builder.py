from django.core.exceptions import ValidationError
from django.db import transaction

from ..models import Question, Quiz
from ..utils import clean_text, normalize_plain_text
from ..validators import QUESTION_COUNT
from .exceptions import QuizGenerationError


def build_quiz(owner, video_url, payload):
    """Build validated, unsaved Quiz and Question objects from AI data.

    The same model rules as in the admin apply (full_clean), so nothing can
    be saved unless the quiz and all ten questions are valid.
    """
    questions_data = get_questions_data(payload)
    quiz = build_quiz_object(owner, video_url, payload)
    questions = [build_question(data) for data in questions_data]
    validate_models(quiz, questions)
    return quiz, questions


def build_quiz_object(owner, video_url, payload):
    """Strip HTML from title/description (the frontend uses innerHTML)."""
    return Quiz(
        owner=owner,
        video_url=video_url,
        title=clean_text(payload.get('title')),
        description=clean_text(payload.get('description')),
    )


def get_questions_data(payload):
    """Return exactly ten question dicts or raise QuizGenerationError."""
    questions = payload.get('questions') if isinstance(payload, dict) else None
    if not isinstance(questions, list) or len(questions) != QUESTION_COUNT:
        raise QuizGenerationError(
            f'Exactly {QUESTION_COUNT} questions are required.'
        )
    if not all(isinstance(question, dict) for question in questions):
        raise QuizGenerationError('Every question must be an object.')
    return questions


def build_question(data):
    """Normalize plain text; '<' stays as the frontend uses textContent."""
    options = data.get('question_options')
    if isinstance(options, list):
        options = [normalize_plain_text(option) for option in options]
    return Question(
        question_title=normalize_plain_text(data.get('question_title')),
        question_options=options,
        answer=normalize_plain_text(data.get('answer')),
    )


def validate_models(quiz, questions):
    """Apply the model rules (full_clean) and map errors for the API."""
    try:
        quiz.full_clean()
        for question in questions:
            question.full_clean(exclude=['quiz'])
    except ValidationError as error:
        raise QuizGenerationError(
            f'Invalid quiz data: {error.messages}'
        ) from error


@transaction.atomic
def save_quiz(quiz, questions):
    """Save the quiz and all its questions together or not at all."""
    quiz.save()
    for question in questions:
        question.quiz = quiz
    Question.objects.bulk_create(questions)
    return quiz
