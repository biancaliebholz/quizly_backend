import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings
from yt_dlp.utils import DownloadError, ExtractorError

from quizzes_app.services.audio import build_download_options, download_audio
from quizzes_app.services.exceptions import (
    QuizGenerationError,
    VideoTooLongError,
)

VIDEO_URL = 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'


@override_settings(QUIZ_MAX_VIDEO_SECONDS=600, YTDLP_JS_RUNTIME='node')
class DownloadAudioTests(SimpleTestCase):
    """yt-dlp is mocked; no network access."""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.temp_dir, ignore_errors=True)
        patcher = patch('quizzes_app.services.audio.YoutubeDL')
        self.addCleanup(patcher.stop)
        youtube_dl_class = patcher.start()
        self.ydl = youtube_dl_class.return_value.__enter__.return_value

    def write_audio_file(self, info, download):
        (self.temp_dir / 'audio.mp3').write_bytes(b'audio')

    def test_downloads_audio_after_checking_metadata(self):
        info = {'duration': 120}
        self.ydl.extract_info.return_value = info
        self.ydl.process_ie_result.side_effect = self.write_audio_file
        path = download_audio(VIDEO_URL, self.temp_dir)
        self.assertEqual(path, self.temp_dir / 'audio.mp3')
        self.ydl.extract_info.assert_called_once_with(
            VIDEO_URL, download=False, process=False
        )
        self.ydl.process_ie_result.assert_called_once_with(info, download=True)

    def test_download_options(self):
        options = build_download_options(self.temp_dir)
        self.assertTrue(options['noplaylist'])
        self.assertEqual(options['socket_timeout'], 30)
        self.assertEqual(options['js_runtimes'], {'node': {}})
        self.assertTrue(options['outtmpl'].startswith(str(self.temp_dir)))
        postprocessor = options['postprocessors'][0]
        self.assertEqual(postprocessor['key'], 'FFmpegExtractAudio')
        self.assertEqual(postprocessor['preferredcodec'], 'mp3')

    def test_too_long_or_unknown_duration_is_rejected_before_download(self):
        for info in ({'duration': 601}, {'duration': None}, {}):
            with self.subTest(info=info):
                self.ydl.extract_info.return_value = info
                with self.assertRaises(VideoTooLongError):
                    download_audio(VIDEO_URL, self.temp_dir)
                self.ydl.process_ie_result.assert_not_called()

    def test_yt_dlp_errors_become_generation_errors(self):
        for error in (DownloadError('blocked'), ExtractorError('private')):
            with self.subTest(error=type(error).__name__):
                self.ydl.extract_info.side_effect = error
                with self.assertRaises(QuizGenerationError):
                    download_audio(VIDEO_URL, self.temp_dir)

    def test_missing_audio_file_is_reported(self):
        self.ydl.extract_info.return_value = {'duration': 120}
        with self.assertRaises(QuizGenerationError):
            download_audio(VIDEO_URL, self.temp_dir)
