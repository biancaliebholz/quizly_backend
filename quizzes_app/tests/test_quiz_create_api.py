import json
from unittest.mock import Mock, patch

from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from quizzes_app.models import Question, Quiz
from quizzes_app.services.exceptions import (
    QuizGenerationError,
    TranscriptTooShortError,
    VideoTooLongError,
)

from .factories import (
    GERMAN_ANSWER,
    GERMAN_TITLE,
    build_ai_payload,
    build_german_ai_payload,
    create_user,
)
from .test_gemini_service import (
    INCOMPLETE_JSON_TEXTS,
    MISSING_OR_EMPTY_TEXTS,
    api_aborts,
)
from .test_quiz_api import QUESTION_KEYS, QUIZ_KEYS

FRONTEND_ORIGIN = 'http://127.0.0.1:5500'
PIPELINE = 'quizzes_app.services.quiz_pipeline'
SHARE_URL = 'https://youtu.be/dQw4w9WgXcQ?si=share'
CANONICAL_URL = 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'
GENERIC_ERROR = {
    'detail': 'Quiz could not be generated. Please try again later.'
}
TIMESTAMPED_QUESTION_KEYS = QUESTION_KEYS | {'created_at', 'updated_at'}
SUPPORTED_URLS = (
    'https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=42s',
    SHARE_URL,
    'https://www.youtube.com/shorts/dQw4w9WgXcQ',
)


@override_settings(
    CSRF_TRUSTED_ORIGINS=[FRONTEND_ORIGIN], GEMINI_API_KEY='test-key'
)
class QuizCreateTestCase(APITestCase):
    """POST /api/quizzes/ with yt-dlp and Whisper always mocked."""

    url = reverse('quiz-list')

    def setUp(self):
        self.owner = create_user('owner')
        token = AccessToken.for_user(self.owner)
        self.client.cookies['access_token'] = str(token)
        self.download = self.start_patch(f'{PIPELINE}.download_audio')
        self.download.side_effect = self.fake_download
        self.transcribe = self.start_patch(f'{PIPELINE}.transcribe_audio')
        self.transcribe.return_value = 'Transcript text'

    def start_patch(self, target):
        patcher = patch(target)
        self.addCleanup(patcher.stop)
        return patcher.start()

    def fake_download(self, video_url, target_dir):
        audio_path = target_dir / 'audio.mp3'
        audio_path.write_bytes(b'audio')
        return audio_path

    def post_url(self, url=SHARE_URL, origin=FRONTEND_ORIGIN):
        data = {'url': url}
        return self.client.post(self.url, data, HTTP_ORIGIN=origin)

    def assert_generation_failed(self):
        """500 with the generic message, logged, and nothing stored."""
        with self.assertLogs('quizzes_app.api.views', level='ERROR'):
            response = self.post_url()
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.data, GENERIC_ERROR)
        self.assertFalse(Quiz.objects.exists())
        self.assertFalse(Question.objects.exists())


class QuizCreateSuccessTests(QuizCreateTestCase):
    """Gemini is mocked at the pipeline boundary."""

    def setUp(self):
        super().setUp()
        self.generate = self.start_patch(f'{PIPELINE}.generate_quiz_payload')
        self.generate.return_value = build_ai_payload()

    def test_returns_201_with_complete_quiz_and_question_timestamps(self):
        response = self.post_url()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(set(response.data), QUIZ_KEYS)
        self.assertEqual(response.data['video_url'], CANONICAL_URL)
        self.assertEqual(len(response.data['questions']), 10)
        for question in response.data['questions']:
            self.assertEqual(set(question), TIMESTAMPED_QUESTION_KEYS)

    def test_pipeline_receives_normalized_url_and_stores_owner(self):
        self.post_url()
        self.assertEqual(self.download.call_args.args[0], CANONICAL_URL)
        self.assertEqual(Quiz.objects.get().owner, self.owner)

    def test_supported_url_formats_are_normalized_automatically(self):
        for url in SUPPORTED_URLS:
            with self.subTest(url=url):
                response = self.post_url(url)
                self.assertEqual(response.status_code, 201)
                self.assertEqual(response.data['video_url'], CANONICAL_URL)
                pipeline_url = self.download.call_args.args[0]
                self.assertEqual(pipeline_url, CANONICAL_URL)

    def test_umlauts_are_stored_and_returned_as_utf8(self):
        self.generate.return_value = build_german_ai_payload()
        response = self.post_url()
        self.assertIn(GERMAN_TITLE.encode('utf-8'), response.content)
        self.assertNotIn(b'\\u00fc', response.content)
        quiz = Quiz.objects.get()
        self.assertEqual(quiz.title, GERMAN_TITLE)
        detail = self.client.get(reverse('quiz-detail', args=[quiz.pk]))
        self.assertEqual(detail.data['questions'][0]['answer'], GERMAN_ANSWER)

    def test_created_quiz_is_listed_without_question_timestamps(self):
        quiz_id = self.post_url().data['id']
        listed = self.client.get(self.url).data[0]
        self.assertEqual(listed['id'], quiz_id)
        self.assertEqual(set(listed['questions'][0]), QUESTION_KEYS)

    def test_invalid_or_missing_url_returns_400_without_pipeline(self):
        for data in ({'url': 'https://vimeo.com/1'}, {'url': ''}, {}):
            with self.subTest(data=data):
                response = self.client.post(
                    self.url, data, HTTP_ORIGIN=FRONTEND_ORIGIN
                )
                self.assertEqual(response.status_code, 400)
                self.assertIn('url', response.data)
        self.download.assert_not_called()

    def test_too_long_video_returns_400(self):
        message = 'The video must be at most 10 minutes long.'
        self.download.side_effect = VideoTooLongError(message)
        response = self.post_url()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {'url': [message]})
        self.assertFalse(Quiz.objects.exists())

    def test_too_short_transcript_returns_400_without_gemini(self):
        message = 'The video does not contain enough speech to create a quiz.'
        self.transcribe.side_effect = TranscriptTooShortError(message)
        response = self.post_url()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {'url': [message]})
        self.generate.assert_not_called()
        self.assertFalse(Quiz.objects.exists())

    def test_unauthenticated_request_returns_401(self):
        self.client.cookies.clear()
        response = self.post_url()
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.download.assert_not_called()

    def test_foreign_origin_returns_403(self):
        response = self.post_url(origin='http://evil.example')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.download.assert_not_called()


class QuizCreateGeminiTests(QuizCreateTestCase):
    """Real Gemini service and builder; only the SDK client is mocked."""

    def setUp(self):
        super().setUp()
        client_class = self.start_patch(
            'quizzes_app.services.gemini.genai.Client'
        )
        client = client_class.return_value
        client.__enter__.return_value = client
        self.generate_content = client.models.generate_content

    def respond_with(self, text):
        self.generate_content.return_value = Mock(text=text)
        self.generate_content.side_effect = None

    def test_valid_gemini_json_creates_quiz(self):
        self.respond_with(json.dumps(build_ai_payload()))
        response = self.post_url()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Question.objects.count(), 10)

    def test_missing_empty_or_incomplete_text_returns_500(self):
        for text in MISSING_OR_EMPTY_TEXTS + INCOMPLETE_JSON_TEXTS:
            with self.subTest(text=text):
                self.respond_with(text)
                self.assert_generation_failed()

    def test_api_aborts_return_500(self):
        for error in api_aborts():
            with self.subTest(error=type(error).__name__):
                self.generate_content.side_effect = error
                self.assert_generation_failed()

    def test_incomplete_quiz_data_returns_500(self):
        missing_answer = build_ai_payload()
        del missing_answer['questions'][0]['answer']
        three_options = build_ai_payload()
        three_options['questions'][0]['question_options'].pop()
        for payload in (build_ai_payload(9), missing_answer, three_options):
            with self.subTest(payload=len(payload['questions'])):
                self.respond_with(json.dumps(payload))
                self.assert_generation_failed()

    def test_download_or_transcription_failure_returns_500(self):
        for mock in (self.download, self.transcribe):
            with self.subTest(service=mock):
                mock.side_effect = QuizGenerationError('external failure')
                self.assert_generation_failed()
