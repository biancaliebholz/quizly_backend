import re
import unicodedata
from urllib.parse import parse_qs, urlsplit

from django.utils.html import strip_tags

YOUTUBE_ID_PATTERN = re.compile(r'[A-Za-z0-9_-]{11}')
YOUTUBE_HOSTS = {'youtube.com', 'www.youtube.com', 'm.youtube.com'}
SHORT_LINK_HOST = 'youtu.be'
VIDEO_PATH_PREFIXES = ('/shorts/', '/embed/', '/live/')
CONTROL_CHARACTERS = re.compile(r'[\x00-\x1f\x7f]')


def clean_text(value):
    """Remove HTML tags and outer whitespace; compose umlauts (NFC)."""
    if not isinstance(value, str):
        return ''
    return unicodedata.normalize('NFC', strip_tags(value)).strip()


def normalize_plain_text(value):
    """Collapse whitespace, drop control characters, compose umlauts (NFC).

    Angle brackets stay, and nothing is transliterated: 'ä' never becomes
    'ae', and words such as 'Queue' or 'Wasser' remain unchanged.
    """
    if not isinstance(value, str):
        return value
    text = unicodedata.normalize('NFC', value)
    return ' '.join(CONTROL_CHARACTERS.sub(' ', text).split())


def normalize_youtube_url(url):
    """Return 'https://www.youtube.com/watch?v=<id>' or None if invalid."""
    video_id = extract_youtube_video_id(url)
    if video_id is None:
        return None
    return f'https://www.youtube.com/watch?v={video_id}'


def extract_youtube_video_id(url):
    """Return the 11-character video id of a YouTube URL or None."""
    parts = urlsplit(url.strip())
    if parts.scheme not in ('http', 'https'):
        return None
    candidate = find_video_id_candidate(parts)
    if candidate and YOUTUBE_ID_PATTERN.fullmatch(candidate):
        return candidate
    return None


def find_video_id_candidate(parts):
    """Read the id from youtu.be, /watch?v=, /shorts/, /embed/ or /live/."""
    host = (parts.hostname or '').lower()
    if host == SHORT_LINK_HOST:
        return parts.path.lstrip('/')
    if host not in YOUTUBE_HOSTS:
        return None
    if parts.path == '/watch':
        return parse_qs(parts.query).get('v', [None])[0]
    for prefix in VIDEO_PATH_PREFIXES:
        if parts.path.startswith(prefix):
            return parts.path[len(prefix):].rstrip('/')
    return None
