from pathlib import Path

from django.conf import settings
from yt_dlp import YoutubeDL
from yt_dlp.utils import YoutubeDLError

from .exceptions import QuizGenerationError, VideoTooLongError

AUDIO_BASENAME = 'audio'
AUDIO_CODEC = 'mp3'
AUDIO_POSTPROCESSORS = [
    {'key': 'FFmpegExtractAudio', 'preferredcodec': AUDIO_CODEC},
]


def download_audio(video_url, target_dir):
    """Download the audio track of a YouTube video as mp3 into target_dir.

    The duration is read from the metadata before anything is downloaded,
    so videos that are too long are rejected within seconds.
    """
    try:
        with YoutubeDL(build_download_options(target_dir)) as ydl:
            info = ydl.extract_info(video_url, download=False, process=False)
            ensure_allowed_duration(info)
            ydl.process_ie_result(info, download=True)
    except (YoutubeDLError, OSError) as error:
        raise QuizGenerationError('Audio download failed.') from error
    return find_audio_file(target_dir)


def build_download_options(target_dir):
    return {
        'format': 'bestaudio/best',
        'outtmpl': str(Path(target_dir) / f'{AUDIO_BASENAME}.%(ext)s'),
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'socket_timeout': 30,
        'retries': 3,
        'js_runtimes': {settings.YTDLP_JS_RUNTIME: {}},
        'postprocessors': AUDIO_POSTPROCESSORS,
    }


def ensure_allowed_duration(info):
    """Reject videos without a known duration or above the limit (400)."""
    duration = info.get('duration')
    limit = settings.QUIZ_MAX_VIDEO_SECONDS
    if not duration or duration > limit:
        raise VideoTooLongError(
            f'The video must be at most {limit // 60} minutes long.'
        )


def find_audio_file(target_dir):
    audio_path = Path(target_dir) / f'{AUDIO_BASENAME}.{AUDIO_CODEC}'
    if not audio_path.is_file():
        raise QuizGenerationError('No audio file was produced.')
    return audio_path
