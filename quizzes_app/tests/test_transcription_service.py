import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings

from quizzes_app.services.exceptions import QuizGenerationError
from quizzes_app.services.transcription import (
    load_whisper_model,
    transcribe_audio,
)

AUDIO_PATH = Path('/tmp/quizly_test/audio.mp3')


class TranscribeAudioTests(SimpleTestCase):
    """Whisper is mocked; torch is never imported."""

    def setUp(self):
        patcher = patch(
            'quizzes_app.services.transcription.load_whisper_model'
        )
        self.addCleanup(patcher.stop)
        self.model = patcher.start().return_value

    def test_transcribes_on_cpu_without_fp16(self):
        self.model.transcribe.return_value = {'text': '  Hello quiz.  '}
        self.assertEqual(transcribe_audio(AUDIO_PATH), 'Hello quiz.')
        self.model.transcribe.assert_called_once_with(
            str(AUDIO_PATH), fp16=False
        )

    def test_empty_transcript_fails(self):
        for result in ({'text': '   '}, {'text': None}, {}):
            with self.subTest(result=result):
                self.model.transcribe.return_value = result
                with self.assertRaises(QuizGenerationError):
                    transcribe_audio(AUDIO_PATH)

    def test_whisper_errors_become_generation_errors(self):
        self.model.transcribe.side_effect = RuntimeError('ffmpeg failed')
        with self.assertRaises(QuizGenerationError):
            transcribe_audio(AUDIO_PATH)


class LoadWhisperModelTests(SimpleTestCase):
    """The configured model is loaded once per process."""

    def setUp(self):
        load_whisper_model.cache_clear()
        self.addCleanup(load_whisper_model.cache_clear)
        self.whisper = MagicMock()
        patcher = patch.dict(sys.modules, {'whisper': self.whisper})
        self.addCleanup(patcher.stop)
        patcher.start()

    @override_settings(WHISPER_MODEL='base')
    def test_loads_configured_model_only_once(self):
        first = load_whisper_model()
        second = load_whisper_model()
        self.assertIs(first, second)
        self.whisper.load_model.assert_called_once_with('base')
