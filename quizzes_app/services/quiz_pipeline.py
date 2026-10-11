import tempfile
from pathlib import Path

from .audio import download_audio
from .gemini import generate_quiz_payload
from .quiz_builder import build_quiz, save_quiz
from .transcription import transcribe_audio


def create_quiz_from_url(owner, video_url):
    """Generate and store a complete quiz for a normalized YouTube URL.

    Audio only lives in a temporary directory that is always removed, even
    if downloading or transcribing fails. The quiz is validated completely
    before it is saved atomically.
    """
    with tempfile.TemporaryDirectory(prefix='quizly_') as temp_dir:
        audio_path = download_audio(video_url, Path(temp_dir))
        transcript = transcribe_audio(audio_path)
    payload = generate_quiz_payload(transcript)
    quiz, questions = build_quiz(owner, video_url, payload)
    return save_quiz(quiz, questions)
