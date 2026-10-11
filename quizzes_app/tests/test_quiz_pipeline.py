from unittest.mock import patch

from django.test import TestCase

from quizzes_app.models import Question, Quiz
from quizzes_app.services.exceptions import QuizGenerationError
from quizzes_app.services.quiz_pipeline import create_quiz_from_url

from .factories import VIDEO_URL, build_ai_payload, create_user

PIPELINE = 'quizzes_app.services.quiz_pipeline'


class CreateQuizFromUrlTests(TestCase):
    """Download, transcription and Gemini are mocked at the service edge."""

    def setUp(self):
        self.owner = create_user('owner')
        self.download = self.start_patch('download_audio')
        self.download.side_effect = self.fake_download
        self.transcribe = self.start_patch('transcribe_audio')
        self.transcribe.return_value = 'Transcript text'
        self.generate = self.start_patch('generate_quiz_payload')
        self.generate.return_value = build_ai_payload()

    def start_patch(self, name):
        patcher = patch(f'{PIPELINE}.{name}')
        self.addCleanup(patcher.stop)
        return patcher.start()

    def fake_download(self, video_url, target_dir):
        """Write a dummy audio file and remember where it was stored."""
        self.audio_path = target_dir / 'audio.mp3'
        self.audio_path.write_bytes(b'audio')
        return self.audio_path

    def test_creates_quiz_with_ten_questions(self):
        quiz = create_quiz_from_url(self.owner, VIDEO_URL)
        self.assertEqual(Quiz.objects.get(), quiz)
        self.assertEqual(quiz.video_url, VIDEO_URL)
        self.assertEqual(quiz.questions.count(), 10)
        self.transcribe.assert_called_once_with(self.audio_path)
        self.generate.assert_called_once_with('Transcript text')

    def test_temporary_audio_is_removed_after_success(self):
        create_quiz_from_url(self.owner, VIDEO_URL)
        self.assertFalse(self.audio_path.parent.exists())

    def test_temporary_audio_is_removed_after_failure(self):
        self.transcribe.side_effect = QuizGenerationError('whisper failed')
        with self.assertRaises(QuizGenerationError):
            create_quiz_from_url(self.owner, VIDEO_URL)
        self.assertFalse(self.audio_path.parent.exists())

    def test_invalid_ai_payload_saves_nothing(self):
        self.generate.return_value = build_ai_payload(9)
        with self.assertRaises(QuizGenerationError):
            create_quiz_from_url(self.owner, VIDEO_URL)
        self.assertFalse(Quiz.objects.exists())
        self.assertFalse(Question.objects.exists())
