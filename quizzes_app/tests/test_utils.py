import unicodedata

from django.test import SimpleTestCase

from quizzes_app.utils import (
    clean_text,
    normalize_plain_text,
    normalize_youtube_url,
)

VIDEO_ID = 'dQw4w9WgXcQ'
CANONICAL_URL = f'https://www.youtube.com/watch?v={VIDEO_ID}'

VALID_YOUTUBE_URLS = (
    f'https://www.youtube.com/watch?v={VIDEO_ID}',
    f'https://youtube.com/watch?v={VIDEO_ID}&t=42s',
    f'https://www.youtube.com/watch?list=PL123&v={VIDEO_ID}',
    f'https://m.youtube.com/watch?v={VIDEO_ID}',
    f'https://WWW.YouTube.com/watch?v={VIDEO_ID}',
    f'http://www.youtube.com/watch?v={VIDEO_ID}',
    f'https://youtu.be/{VIDEO_ID}',
    f'https://youtu.be/{VIDEO_ID}?si=share',
    f'https://www.youtube.com/shorts/{VIDEO_ID}',
    f'https://www.youtube.com/embed/{VIDEO_ID}',
    f'https://www.youtube.com/live/{VIDEO_ID}',
    f'  https://www.youtube.com/watch?v={VIDEO_ID}  ',
)

INVALID_YOUTUBE_URLS = (
    '',
    'not a url',
    f'https://vimeo.com/{VIDEO_ID}',
    'https://www.youtube.com/watch',
    'https://www.youtube.com/channel/UC1234567890',
    'https://www.youtube.com/playlist?list=PL123',
    'https://www.youtube.com/watch?v=tooShort',
    f'https://www.youtube.com/watch?v={VIDEO_ID}X',
    'https://www.youtube.com/watch?v=dQw4w9WgXc!',
    f'ftp://www.youtube.com/watch?v={VIDEO_ID}',
    f'javascript:alert(1)//www.youtube.com/watch?v={VIDEO_ID}',
    f'https://youtube.com.evil.example/watch?v={VIDEO_ID}',
    'https://youtu.be/',
    'https://www.youtube.com/shorts/',
)


class NormalizeYoutubeUrlTests(SimpleTestCase):
    """Only YouTube video URLs are accepted, always as watch?v=<id>."""

    def test_supported_formats_are_normalized(self):
        for url in VALID_YOUTUBE_URLS:
            with self.subTest(url=url):
                self.assertEqual(normalize_youtube_url(url), CANONICAL_URL)

    def test_other_urls_are_rejected(self):
        for url in INVALID_YOUTUBE_URLS:
            with self.subTest(url=url):
                self.assertIsNone(normalize_youtube_url(url))


class TextUtilsTests(SimpleTestCase):
    """Text cleaning for AI output and user input."""

    def test_clean_text_removes_html_and_outer_whitespace(self):
        self.assertEqual(clean_text('  <b>Bold</b> Quiz '), 'Bold Quiz')

    def test_clean_text_turns_non_text_into_empty_string(self):
        for value in (None, 42, ['title']):
            with self.subTest(value=value):
                self.assertEqual(clean_text(value), '')

    def test_plain_text_collapses_whitespace_and_control_characters(self):
        text = normalize_plain_text('  Option\n\t A\x00B  ')
        self.assertEqual(text, 'Option A B')

    def test_plain_text_keeps_angle_brackets(self):
        self.assertEqual(normalize_plain_text('<div>'), '<div>')

    def test_plain_text_leaves_non_text_unchanged(self):
        self.assertEqual(normalize_plain_text(4), 4)
        self.assertIsNone(normalize_plain_text(None))


GERMAN_TEXT = 'Künstliche Intelligenz – Größe, Äpfel, Öl, Übung, Straße'
UNCHANGED_TEXTS = (
    'café naïve',
    'Ελληνικά',
    '日本語',
    'Queue, Feuer, aktuell, dass, Wasser',
)
TEXT_CLEANERS = (clean_text, normalize_plain_text)


class UnicodeTextTests(SimpleTestCase):
    """Umlauts stay real characters; nothing is transliterated."""

    def test_umlauts_and_sharp_s_are_kept(self):
        for clean in TEXT_CLEANERS:
            with self.subTest(function=clean.__name__):
                self.assertEqual(clean(GERMAN_TEXT), GERMAN_TEXT)

    def test_other_languages_and_ue_words_are_unchanged(self):
        for text in UNCHANGED_TEXTS:
            for clean in TEXT_CLEANERS:
                with self.subTest(text=text, function=clean.__name__):
                    self.assertEqual(clean(text), text)

    def test_decomposed_umlauts_are_composed_to_nfc(self):
        decomposed = unicodedata.normalize('NFD', 'verlässt')
        for clean in TEXT_CLEANERS:
            with self.subTest(function=clean.__name__):
                self.assertEqual(clean(decomposed), 'verlässt')
