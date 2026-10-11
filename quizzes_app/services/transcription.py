from functools import lru_cache

from django.conf import settings

from .exceptions import QuizGenerationError


@lru_cache(maxsize=1)
def load_whisper_model():
    """Load the configured Whisper model once per process.

    The import happens here on purpose: whisper pulls in torch, which would
    slow down every management command and test that never transcribes.
    """
    import whisper
    return whisper.load_model(settings.WHISPER_MODEL)


def transcribe_audio(audio_path):
    """Transcribe audio locally on the CPU; Whisper detects the language."""
    try:
        result = load_whisper_model().transcribe(str(audio_path), fp16=False)
    except (RuntimeError, OSError, ValueError) as error:
        raise QuizGenerationError('Transcription failed.') from error
    text = (result.get('text') or '').strip()
    if not text:
        raise QuizGenerationError('The transcript is empty.')
    return text
