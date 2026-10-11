import sys
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings

from quizzes_app.services.exceptions import (
    QuizGenerationError,
    TranscriptTooShortError,
)
from quizzes_app.services.transcription import (
    load_whisper_model,
    transcribe_audio,
)

AUDIO_PATH = Path('/tmp/quizly_test/audio.mp3')
USABLE_TRANSCRIPT = (
    'Python lists are ordered and mutable. Tuples are ordered but '
    'immutable. Dictionaries store key value pairs and sets store unique '
    'values without any order.'
)
TOO_SHORT_TRANSCRIPTS = ('', 'Vielen Dank fürs Zuschauen.', '♪ ♪')


class MockedWhisperModelTestCase(SimpleTestCase):
    """Base: the cached Whisper model is a mock; torch is never imported."""

    def setUp(self):
        patcher = patch(
            'quizzes_app.services.transcription.load_whisper_model'
        )
        self.addCleanup(patcher.stop)
        self.model = patcher.start().return_value

    def transcribe_text(self, text):
        self.model.transcribe.return_value = {'text': text}
        return transcribe_audio(AUDIO_PATH)


class TranscribeAudioTests(MockedWhisperModelTestCase):
    """Whisper call, text cleanup and error mapping."""

    def test_transcribes_on_cpu_without_fp16(self):
        text = self.transcribe_text(f'  {USABLE_TRANSCRIPT}  ')
        self.assertEqual(text, USABLE_TRANSCRIPT)
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


class TranscriptUsabilityTests(MockedWhisperModelTestCase):
    """Heuristic guard against transcripts with obviously too little speech."""

    def test_too_short_transcripts_are_rejected(self):
        for text in TOO_SHORT_TRANSCRIPTS:
            with self.subTest(text=text):
                with self.assertRaises(TranscriptTooShortError):
                    self.transcribe_text(text)

    def test_twenty_short_words_are_enough(self):
        text = ' '.join(['Wort'] * 20)
        self.assertEqual(self.transcribe_text(text), text)

    def test_long_text_without_spaces_is_enough(self):
        japanese = 'これはテストです' * 13
        self.assertEqual(self.transcribe_text(japanese), japanese)


class FakeWhisperModuleTestCase(SimpleTestCase):
    """Base: the whisper module itself is faked and the cache is empty."""

    def setUp(self):
        load_whisper_model.cache_clear()
        self.addCleanup(load_whisper_model.cache_clear)
        self.whisper = MagicMock()
        patcher = patch.dict(sys.modules, {'whisper': self.whisper})
        self.addCleanup(patcher.stop)
        patcher.start()


class LoadWhisperModelTests(FakeWhisperModuleTestCase):
    """The configured model is loaded once per process."""

    @override_settings(WHISPER_MODEL='base')
    def test_loads_configured_model_only_once(self):
        first = load_whisper_model()
        second = load_whisper_model()
        self.assertIs(first, second)
        self.whisper.load_model.assert_called_once_with('base')


class TranscriptionLockTests(FakeWhisperModuleTestCase):
    """Parallel requests in one process must not share Whisper at once."""

    def setUp(self):
        super().setUp()
        self.active_calls = 0
        self.max_active_calls = 0
        self.counter_lock = threading.Lock()
        self.model = MagicMock()
        self.model.transcribe.side_effect = self.slow_transcribe
        self.whisper.load_model.side_effect = self.slow_load

    def slow_load(self, name):
        time.sleep(0.05)
        return self.model

    def slow_transcribe(self, path, fp16):
        """Count how many transcriptions run at the same time."""
        with self.counter_lock:
            self.active_calls += 1
            self.max_active_calls = max(
                self.max_active_calls, self.active_calls
            )
        time.sleep(0.05)
        with self.counter_lock:
            self.active_calls -= 1
        return {'text': USABLE_TRANSCRIPT}

    def run_two_requests_in_parallel(self):
        threads = [
            threading.Thread(target=transcribe_audio, args=(AUDIO_PATH,))
            for _ in range(2)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

    def test_parallel_first_calls_load_the_model_only_once(self):
        self.run_two_requests_in_parallel()
        self.whisper.load_model.assert_called_once()

    def test_transcriptions_never_run_in_parallel(self):
        self.run_two_requests_in_parallel()
        self.assertEqual(self.max_active_calls, 1)
        self.assertEqual(self.model.transcribe.call_count, 2)
