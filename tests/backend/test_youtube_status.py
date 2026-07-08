import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from youtube import (
    DownloadError,
    _classify_search_failure,
    _parse_search_output,
    download_audio,
    search_youtube_with_status,
)


class YouTubeStatusTests(unittest.TestCase):
    def test_parse_search_output_keeps_valid_rows(self):
        stdout = "abc123|Song Title|183|Artist Name\ninvalid row\ndef456|Other Song||Uploader\n"

        results = _parse_search_output(stdout)

        self.assertEqual(results, [
            {
                "videoId": "abc123",
                "title": "Song Title",
                "artist": "Artist Name",
                "duration": 183,
            },
            {
                "videoId": "def456",
                "title": "Other Song",
                "artist": "Uploader",
                "duration": 0,
            },
        ])

    def test_classify_timeout(self):
        error = _classify_search_failure("", cookies_present=True, timed_out=True)

        self.assertEqual(error["code"], "youtube_timeout")
        self.assertEqual(error["message"], "YouTube search timed out. Try again.")

    def test_classify_missing_cookies(self):
        error = _classify_search_failure("Sign in to confirm you are not a bot", cookies_present=False)

        self.assertEqual(error["code"], "youtube_cookies_missing")
        self.assertIn("cookies", error["message"].lower())

    @patch("youtube.subprocess.run")
    @patch("youtube.COOKIES_FILE")
    def test_search_timeout_returns_status_response(self, cookies_file, run):
        cookies_file.exists.return_value = True
        run.side_effect = subprocess.TimeoutExpired(cmd="yt-dlp", timeout=30)

        response = search_youtube_with_status("hello", max_results=3, search_type="all")

        self.assertFalse(response["ok"])
        self.assertEqual(response["results"], [])
        self.assertEqual(response["error"]["code"], "youtube_timeout")

    @patch("youtube.subprocess.run")
    @patch("youtube.COOKIES_FILE")
    def test_search_success_returns_status_response(self, cookies_file, run):
        cookies_file.exists.return_value = True
        run.return_value = Mock(
            returncode=0,
            stdout="abc123|Song Title|183|Artist Name\n",
            stderr="",
        )

        response = search_youtube_with_status("hello", max_results=3, search_type="all")

        self.assertTrue(response["ok"])
        self.assertEqual(response["error"], None)
        self.assertEqual(response["results"][0]["videoId"], "abc123")

    @patch("youtube.subprocess.run")
    @patch("youtube.COOKIES_FILE")
    def test_download_failure_raises_structured_error(self, cookies_file, run):
        cookies_file.exists.return_value = True
        run.side_effect = subprocess.CalledProcessError(
            returncode=1,
            cmd=["yt-dlp"],
            stderr="Sign in to confirm you are not a bot",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises(DownloadError) as raised:
                download_audio("abc123", Path(tmpdir))

        self.assertEqual(raised.exception.code, "download_failed")
        self.assertIn("YouTube", raised.exception.message)
        self.assertIn("Sign in", raised.exception.detail)


if __name__ == "__main__":
    unittest.main()
