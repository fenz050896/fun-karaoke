import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from lyrics_sync import resolve_lyrics


class LyricsResolutionTests(unittest.IsolatedAsyncioTestCase):
    async def test_lrclib_lyrics_win(self):
        synced = [{"start": 1.0, "text": "hello"}]
        with patch("lyrics_sync.fetch_lyrics", new=AsyncMock(return_value=synced)):
            result = await resolve_lyrics("Song", "Artist", Path("missing.wav"), "small")

        self.assertEqual(result["lyrics"], synced)
        self.assertEqual(result["lyricsSource"], "lrclib")
        self.assertEqual(result["lyricsStatus"], "synced")
        self.assertNotIn("lyricsWarning", result)

    async def test_whisper_used_when_lrclib_empty(self):
        generated = [{"start": 2.0, "text": "generated"}]
        with tempfile.NamedTemporaryFile(suffix=".wav") as audio:
            with patch("lyrics_sync.fetch_lyrics", new=AsyncMock(return_value=None)):
                with patch("lyrics_sync.transcribe_with_whisper", return_value=generated):
                    result = await resolve_lyrics("Song", "Artist", Path(audio.name), "small")

        self.assertEqual(result["lyrics"], generated)
        self.assertEqual(result["lyricsSource"], "whisper")
        self.assertEqual(result["lyricsStatus"], "generated")

    async def test_unavailable_when_lrclib_fails_and_vocals_missing(self):
        with patch("lyrics_sync.fetch_lyrics", new=AsyncMock(side_effect=RuntimeError("LRCLIB down"))):
            result = await resolve_lyrics("Song", "Artist", Path("missing.wav"), "small")

        self.assertEqual(result["lyrics"], [])
        self.assertEqual(result["lyricsSource"], "none")
        self.assertEqual(result["lyricsStatus"], "unavailable")
        self.assertIn("LRCLIB down", result["lyricsWarning"])

    async def test_unavailable_when_whisper_fails(self):
        with tempfile.NamedTemporaryFile(suffix=".wav") as audio:
            with patch("lyrics_sync.fetch_lyrics", new=AsyncMock(return_value=None)):
                with patch("lyrics_sync.transcribe_with_whisper", side_effect=RuntimeError("Whisper failed")):
                    result = await resolve_lyrics("Song", "Artist", Path(audio.name), "small")

        self.assertEqual(result["lyrics"], [])
        self.assertEqual(result["lyricsSource"], "none")
        self.assertEqual(result["lyricsStatus"], "unavailable")
        self.assertIn("Whisper failed", result["lyricsWarning"])


if __name__ == "__main__":
    unittest.main()
