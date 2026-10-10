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
