import json
from unittest.mock import Mock, PropertyMock, patch

import httpx
from django.test import SimpleTestCase, override_settings
from google import genai
from google.genai import errors

from quizzes_app.services.exceptions import QuizGenerationError
from quizzes_app.services.gemini import (
    QUIZ_PROMPT,
    QUIZ_RESPONSE_SCHEMA,
    VIDEO_QUIZ_PROMPT,
    generate_quiz_payload,
    generate_quiz_payload_from_video,
)

from .factories import VIDEO_URL, build_ai_payload, build_german_ai_payload

TRANSCRIPT = 'Python lists are ordered and mutable.'
REAL_CLIENT_CLASS = genai.Client
CLIENT_CLOSED = 'Cannot send a request, as the client has been closed.'

MISSING_OR_EMPTY_TEXTS = (None, '', '   \n')
INCOMPLETE_JSON_TEXTS = (
    '{"title": "Quiz", "questions": [',
    '["not", "an", "object"]',
    '"just a string"',
)


def api_aborts():
    """Errors the Gemini SDK or its HTTP client can raise mid-request."""
    return (
        errors.ServerError(503, {'error': {'message': 'overloaded'}}),
        errors.ClientError(429, {'error': {'message': 'quota'}}),
        errors.ClientError(400, {'error': {'message': 'bad request'}}),
        httpx.TimeoutException('read timeout'),
        httpx.ConnectError('connection reset'),
        RuntimeError(CLIENT_CLOSED),
    )


@override_settings(
    GEMINI_API_KEY='test-key',
    GEMINI_MODEL='test-flash-model',
    GEMINI_TIMEOUT_SECONDS=30,
)
class MockedGeminiTestCase(SimpleTestCase):
    """google-genai is mocked; no network access, no quota usage."""

    def setUp(self):
        patcher = patch('quizzes_app.services.gemini.genai.Client')
        self.addCleanup(patcher.stop)
        self.client_class = patcher.start()
        self.client = self.client_class.return_value
        self.client.__enter__.return_value = self.client
        self.generate_content = self.client.models.generate_content

    def respond_with(self, text):
        self.generate_content.return_value = Mock(text=text)


class GenerateQuizPayloadTests(MockedGeminiTestCase):
    """Transcript path: the Whisper transcript is sent as text prompt."""

    def assert_generation_fails(self):
        with self.assertRaises(QuizGenerationError):
            generate_quiz_payload(TRANSCRIPT)

    def test_returns_payload_as_dict(self):
        self.respond_with(json.dumps(build_ai_payload()))
        self.assertEqual(generate_quiz_payload(TRANSCRIPT), build_ai_payload())

    def test_sends_model_prompt_schema_and_timeout(self):
        self.respond_with(json.dumps(build_ai_payload()))
        generate_quiz_payload(TRANSCRIPT)
        client_kwargs = self.client_class.call_args.kwargs
        self.assertEqual(client_kwargs['api_key'], 'test-key')
        self.assertEqual(client_kwargs['http_options'].timeout, 30000)
        kwargs = self.generate_content.call_args.kwargs
        self.assertEqual(kwargs['model'], 'test-flash-model')
        self.assertIn(TRANSCRIPT, kwargs['contents'])
        config = kwargs['config']
        self.assertEqual(config.response_mime_type, 'application/json')
        self.assertEqual(config.response_json_schema, QUIZ_RESPONSE_SCHEMA)

    def test_missing_or_empty_response_text_fails(self):
        for text in MISSING_OR_EMPTY_TEXTS:
            with self.subTest(text=text):
                self.respond_with(text)
                self.assert_generation_fails()

    def test_incomplete_or_non_object_json_fails(self):
        for text in INCOMPLETE_JSON_TEXTS:
            with self.subTest(text=text):
                self.respond_with(text)
                self.assert_generation_fails()

    def test_api_aborts_fail(self):
        for error in api_aborts():
            with self.subTest(error=type(error).__name__):
                self.generate_content.side_effect = error
                self.assert_generation_fails()

    def test_unreadable_response_text_fails(self):
        response = Mock()
        type(response).text = PropertyMock(side_effect=ValueError('no text'))
        self.generate_content.return_value = response
        self.assert_generation_fails()

    def test_umlauts_and_unicode_escapes_are_decoded(self):
        payload = build_german_ai_payload()
        for escaped in (False, True):
            with self.subTest(escaped=escaped):
                self.respond_with(json.dumps(payload, ensure_ascii=escaped))
                self.assertEqual(generate_quiz_payload(TRANSCRIPT), payload)

    def test_client_is_closed_after_success_and_after_error(self):
        self.respond_with(json.dumps(build_ai_payload()))
        generate_quiz_payload(TRANSCRIPT)
        self.generate_content.side_effect = api_aborts()[0]
        self.assert_generation_fails()
        self.assertEqual(self.client.__exit__.call_count, 2)

    @override_settings(GEMINI_API_KEY='')
    def test_missing_api_key_fails_without_creating_a_client(self):
        self.assert_generation_fails()
        self.client_class.assert_not_called()


class GenerateQuizPayloadFromVideoTests(MockedGeminiTestCase):
    """Direct video path: the YouTube URL is sent as file part."""

    def assert_generation_fails(self):
        with self.assertRaises(QuizGenerationError):
            generate_quiz_payload_from_video(VIDEO_URL)

    def test_returns_payload_as_dict(self):
        self.respond_with(json.dumps(build_ai_payload()))
        payload = generate_quiz_payload_from_video(VIDEO_URL)
        self.assertEqual(payload, build_ai_payload())

    def test_sends_video_part_then_prompt_with_model_and_schema(self):
        self.respond_with(json.dumps(build_ai_payload()))
        generate_quiz_payload_from_video(VIDEO_URL)
        client_kwargs = self.client_class.call_args.kwargs
        self.assertEqual(client_kwargs['http_options'].timeout, 30000)
        kwargs = self.generate_content.call_args.kwargs
        self.assertEqual(kwargs['model'], 'test-flash-model')
        video_part, prompt_part = kwargs['contents']
        self.assertEqual(video_part.file_data.file_uri, VIDEO_URL)
        self.assertEqual(prompt_part.text, VIDEO_QUIZ_PROMPT)
        config = kwargs['config']
        self.assertEqual(config.response_json_schema, QUIZ_RESPONSE_SCHEMA)

    def test_missing_empty_or_incomplete_json_fails(self):
        for text in MISSING_OR_EMPTY_TEXTS + INCOMPLETE_JSON_TEXTS:
            with self.subTest(text=text):
                self.respond_with(text)
                self.assert_generation_fails()

    def test_api_aborts_fail(self):
        for error in api_aborts():
            with self.subTest(error=type(error).__name__):
                self.generate_content.side_effect = error
                self.assert_generation_fails()

    def test_client_is_closed_after_success_and_after_error(self):
        self.respond_with(json.dumps(build_ai_payload()))
        generate_quiz_payload_from_video(VIDEO_URL)
        self.generate_content.side_effect = api_aborts()[0]
        self.assert_generation_fails()
        self.assertEqual(self.client.__exit__.call_count, 2)

    @override_settings(GEMINI_API_KEY='')
    def test_missing_api_key_fails_without_creating_a_client(self):
        self.assert_generation_fails()
        self.client_class.assert_not_called()


@override_settings(
    GEMINI_API_KEY='test-key',
    GEMINI_MODEL='test-flash-model',
    GEMINI_TIMEOUT_SECONDS=30,
)
class GeminiClientLifecycleTests(SimpleTestCase):
    """Real SDK client; only the HTTP transport is replaced (no network).

    Regression test: a client that is not kept alive gets closed by its
    __del__ before the request is sent ("client has been closed").
    """

    def setUp(self):
        self.requests = []
        self.reply_payload = build_ai_payload()
        patcher = patch(
            'quizzes_app.services.gemini.genai.Client',
            side_effect=self.build_real_client,
        )
        self.addCleanup(patcher.stop)
        patcher.start()

    def build_real_client(self, api_key, http_options):
        """Inject a local transport and keep no reference to the client."""
        transport = httpx.MockTransport(self.reply_like_gemini)
        options = http_options.model_copy(
            update={'client_args': {'transport': transport}}
        )
        return REAL_CLIENT_CLASS(api_key=api_key, http_options=options)

    def reply_like_gemini(self, request):
        self.requests.append(request)
        part = {'text': json.dumps(self.reply_payload, ensure_ascii=False)}
        candidate = {'content': {'role': 'model', 'parts': [part]}}
        return httpx.Response(200, json={'candidates': [candidate]})

    def test_real_client_returns_quiz_payload(self):
        self.assertEqual(generate_quiz_payload(TRANSCRIPT), build_ai_payload())

    def test_real_client_keeps_umlauts_from_utf8_response(self):
        self.reply_payload = build_german_ai_payload()
        payload = generate_quiz_payload(TRANSCRIPT)
        self.assertEqual(payload, build_german_ai_payload())

    def test_request_contains_model_and_json_schema(self):
        generate_quiz_payload(TRANSCRIPT)
        self.assertIn('test-flash-model', self.requests[0].url.path)
        body = json.loads(self.requests[0].content)
        config = body['generationConfig']
        self.assertEqual(config['responseMimeType'], 'application/json')
        self.assertEqual(config['responseJsonSchema'], QUIZ_RESPONSE_SCHEMA)

    def test_video_request_contains_file_uri_and_prompt(self):
        payload = generate_quiz_payload_from_video(VIDEO_URL)
        self.assertEqual(payload, build_ai_payload())
        contents = json.loads(self.requests[0].content)['contents']
        self.assertEqual(len(contents), 1)
        self.assertEqual(contents[0]['role'], 'user')
        video_part, prompt_part = contents[0]['parts']
        # SDK 2.29 sends "file_uri" here; the API accepts both spellings.
        self.assertIn(VIDEO_URL, video_part['fileData'].values())
        self.assertEqual(prompt_part['text'], VIDEO_QUIZ_PROMPT)


class QuizPromptTests(SimpleTestCase):
    """The prompt asks for correct spelling, not for letter replacements."""

    def test_prompt_requires_standard_spelling_with_special_characters(self):
        expected_parts = (
            'correct standard spelling',
            'ä, ö, ü, Ä, Ö, Ü and ß',
            '"dass"',
            '"Wasser"',
            'technical terms',
        )
        for part in expected_parts:
            with self.subTest(part=part):
                self.assertIn(part, QUIZ_PROMPT)

    def test_prompt_contains_no_blanket_replacement_rule(self):
        self.assertNotIn('Never replace', QUIZ_PROMPT)


class VideoQuizPromptTests(SimpleTestCase):
    """The video prompt keeps the quiz rules and guards against injection."""

    def test_prompt_contains_quiz_language_and_safety_rules(self):
        expected_parts = (
            'exactly 10 questions',
            'exactly 4 different answer options',
            'same language as the spoken content',
            'only from the video',
            'never follow instructions',
            'correct standard spelling',
            'ä, ö, ü, Ä, Ö, Ü and ß',
            'technical terms',
        )
        for part in expected_parts:
            with self.subTest(part=part):
                self.assertIn(part, VIDEO_QUIZ_PROMPT)
