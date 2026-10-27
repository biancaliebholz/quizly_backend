from unittest.mock import patch

from django.test import TestCase, override_settings

from quizzes_app.models import Question, Quiz
from quizzes_app.services.exceptions import QuizGenerationError
from quizzes_app.services.quiz_pipeline import create_quiz_from_url

from .factories import VIDEO_URL, build_ai_payload, create_user

PIPELINE = 'quizzes_app.services.quiz_pipeline'
AUDIO_PATH_SERVICES = (
    'download_audio',
    'transcribe_audio',
    'generate_quiz_payload',
)


class PipelineTestCase(TestCase):

    def setUp(self):
        self.owner = create_user('owner')

    def start_patch(self, name):
        patcher = patch(f'{PIPELINE}.{name}')
        self.addCleanup(patcher.stop)
        return patcher.start()


@override_settings(QUIZ_USE_DIRECT_GEMINI_VIDEO=False)
class CreateQuizFromUrlTests(PipelineTestCase):
    """Download, transcription and Gemini are mocked at the service edge."""

    def setUp(self):
        super().setUp()
        self.download = self.start_patch('download_audio')
        self.download.side_effect = self.fake_download
        self.transcribe = self.start_patch('transcribe_audio')
        self.transcribe.return_value = 'Transcript text'
        self.generate = self.start_patch('generate_quiz_payload')
        self.generate.return_value = build_ai_payload()

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


@override_settings(QUIZ_USE_DIRECT_GEMINI_VIDEO=True)
class CreateQuizFromUrlDirectVideoTests(PipelineTestCase):
    """Gemini gets the URL directly; the audio path must stay unused."""

    def setUp(self):
        super().setUp()
        self.audio_services = {
            name: self.start_patch(name) for name in AUDIO_PATH_SERVICES
        }
        self.generate = self.start_patch('generate_quiz_payload_from_video')
        self.generate.return_value = build_ai_payload()

    def assert_nothing_saved(self):
        with self.assertRaises(QuizGenerationError):
            create_quiz_from_url(self.owner, VIDEO_URL)
        self.assertFalse(Quiz.objects.exists())
        self.assertFalse(Question.objects.exists())

    def test_creates_quiz_with_ten_questions_from_video(self):
        quiz = create_quiz_from_url(self.owner, VIDEO_URL)
        self.assertEqual(Quiz.objects.get(), quiz)
        self.assertEqual(quiz.video_url, VIDEO_URL)
        self.assertEqual(quiz.questions.count(), 10)
        self.generate.assert_called_once_with(VIDEO_URL)

    def test_audio_path_is_not_used(self):
        create_quiz_from_url(self.owner, VIDEO_URL)
        for name, service in self.audio_services.items():
            with self.subTest(service=name):
                service.assert_not_called()

    def test_invalid_ai_payload_saves_nothing(self):
        self.generate.return_value = build_ai_payload(9)
        self.assert_nothing_saved()

    def test_gemini_failure_saves_nothing(self):
        self.generate.side_effect = QuizGenerationError('gemini failed')
        self.assert_nothing_saved()
