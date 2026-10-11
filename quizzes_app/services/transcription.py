import threading
from functools import lru_cache

from django.conf import settings

from .exceptions import QuizGenerationError, TranscriptTooShortError

MIN_TRANSCRIPT_WORDS = 20
MIN_TRANSCRIPT_CHARACTERS = 100
TOO_LITTLE_SPEECH_MESSAGE = (
    'The video does not contain enough speech to create a quiz.'
)
TRANSCRIPTION_LOCK = threading.Lock()


@lru_cache(maxsize=1)
def load_whisper_model():
    """Load the configured Whisper model once per process.

    The import happens here on purpose: whisper pulls in torch, which would
    slow down every management command and test that never transcribes.
    """
    import whisper
    return whisper.load_model(settings.WHISPER_MODEL)


def transcribe_audio(audio_path):
    """Transcribe audio locally on the CPU; Whisper detects the language.

    Raises QuizGenerationError if Whisper fails and TranscriptTooShortError
    if the result contains too little speech for a quiz.
    """
    try:
        result = run_whisper(audio_path)
    except (RuntimeError, OSError, ValueError) as error:
        raise QuizGenerationError('Transcription failed.') from error
    text = (result.get('text') or '').strip()
    ensure_usable_transcript(text)
    return text


def run_whisper(audio_path):
    """Load the model and transcribe while holding TRANSCRIPTION_LOCK.

    The shared Whisper model is not thread-safe (it attaches cache hooks to
    the model while decoding). A threading.Lock only serializes threads of
    this process; separate worker processes each use their own model.
    """
    with TRANSCRIPTION_LOCK:
        model = load_whisper_model()
        return model.transcribe(str(audio_path), fp16=False)


def ensure_usable_transcript(text):
    """Heuristic guard against obviously unusable transcripts.

    Too short means fewer than 20 words AND fewer than 100 characters; the
    character rule keeps languages without spaces (e.g. Japanese) usable.
    This is no check of the content quality.
    """
    too_few_words = len(text.split()) < MIN_TRANSCRIPT_WORDS
    if too_few_words and len(text) < MIN_TRANSCRIPT_CHARACTERS:
        raise TranscriptTooShortError(TOO_LITTLE_SPEECH_MESSAGE)
