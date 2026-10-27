import tempfile
from pathlib import Path

from django.conf import settings

from .audio import download_audio
from .gemini import generate_quiz_payload, generate_quiz_payload_from_video
from .quiz_builder import build_quiz, save_quiz
from .transcription import transcribe_audio


def create_quiz_from_url(owner, video_url):
    """Generate and store a complete quiz for a normalized YouTube URL.

    The quiz is validated completely before it is saved atomically.
    """
    payload = generate_payload(video_url)
    quiz, questions = build_quiz(owner, video_url, payload)
    return save_quiz(quiz, questions)


def generate_payload(video_url):
    """Gemini watches the video directly or reads the Whisper transcript."""
    if settings.QUIZ_USE_DIRECT_GEMINI_VIDEO:
        return generate_quiz_payload_from_video(video_url)
    return generate_payload_from_audio(video_url)


def generate_payload_from_audio(video_url):
    """Audio only lives in a temporary directory that is always removed,
    even if downloading or transcribing fails.
    """
    with tempfile.TemporaryDirectory(prefix='quizly_') as temp_dir:
        audio_path = download_audio(video_url, Path(temp_dir))
        transcript = transcribe_audio(audio_path)
    return generate_quiz_payload(transcript)
