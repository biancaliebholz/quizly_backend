from django.contrib.auth import get_user_model

from quizzes_app.models import Question, Quiz

User = get_user_model()

VALID_OPTIONS = ['Option A', 'Option B', 'Option C', 'Option D']
VIDEO_URL = 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'


def create_user(username):
    """Create a user without password hashing (fast; tests never log in)."""
    return User.objects.create(
        username=username, email=f'{username}@example.com'
    )


def create_question(quiz, title='Question 1'):
    return Question.objects.create(
        quiz=quiz,
        question_title=title,
        question_options=list(VALID_OPTIONS),
        answer='Option A',
    )


def build_ai_question(number):
    """One question as Gemini is asked to return it."""
    return {
        'question_title': f'Question {number}?',
        'question_options': [f'Option {letter}{number}' for letter in 'ABCD'],
        'answer': f'Option A{number}',
    }


def build_ai_payload(question_count=10):
    """A complete Gemini quiz payload with the given number of questions."""
    return {
        'title': 'Generated Quiz',
        'description': 'A quiz generated from a video.',
        'questions': [
            build_ai_question(number)
            for number in range(1, question_count + 1)
        ],
    }


GERMAN_TITLE = 'Künstliche Intelligenz Quiz'
GERMAN_ANSWER = 'Mehr Übung'
GERMAN_OPTIONS = [
    'Größere Büros', GERMAN_ANSWER, 'Weniger Straßen', 'Fließendes Wasser',
]


def build_german_ai_payload():
    """A payload with real umlauts and ß, as Gemini should return it."""
    payload = build_ai_payload()
    payload.update(
        title=GERMAN_TITLE, description='Wer das Haus verlässt, nutzt KI.'
    )
    payload['questions'][0].update(
        question_title='Was erwarten Fachleute für die nächsten Jahre?',
        question_options=list(GERMAN_OPTIONS),
        answer=GERMAN_ANSWER,
    )
    return payload


def create_quiz(owner, title='Quiz Title', question_count=2):
    quiz = Quiz.objects.create(
        owner=owner,
        title=title,
        description='Quiz Description',
        video_url=VIDEO_URL,
    )
    for number in range(1, question_count + 1):
        create_question(quiz, f'Question {number}')
    return quiz
