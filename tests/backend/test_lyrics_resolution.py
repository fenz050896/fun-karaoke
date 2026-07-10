import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from lyrics_sync import (
    _select_search_result,
    normalize_artist,
    normalize_title,
    parse_lrc,
    resolve_lyrics,
)


class LyricsMetadataTests(unittest.TestCase):
    def test_normalize_title_removes_matching_artist_prefix_and_label(self):
        title = normalize_title(
            "Hindia - everything u are (Official Music Video)",
            "Hindia - Topic",
        )

        self.assertEqual(title, "everything u are")
        self.assertEqual(normalize_artist("Hindia - Topic"), "Hindia")

    def test_normalize_title_preserves_meaningful_parenthetical_text(self):
        title = normalize_title("Song (Acoustic Version)", "Artist")

        self.assertEqual(title, "Song (Acoustic Version)")

    def test_parse_lrc_ignores_malformed_or_empty_lines(self):
        lyrics = parse_lrc("[00:01.00]\nnot lrc\n[00:02.50]Hello")

        self.assertEqual(lyrics, [{"start": 2.5, "text": "Hello"}])

    def test_search_selection_rejects_mismatches_and_uses_closest_duration(self):
        items = [
            {
                "id": 1,
                "trackName": "everything u are",
                "artistName": "Hindia",
                "duration": 349.0,
                "syncedLyrics": "[00:01.00]Wrong version",
            },
            {
                "id": 2,
                "trackName": "another song",
                "artistName": "Hindia",
                "duration": 237.0,
                "syncedLyrics": "[00:01.00]Wrong title",
            },
            {
                "id": 3,
                "trackName": "everything u are",
                "artistName": "Hindia",
                "duration": 236.0,
                "syncedLyrics": "[00:12.01]Closest",
            },
            {
                "id": 4,
                "trackName": "Hindia - everything u are",
                "artistName": "Hindia",
                "duration": 234.0,
                "syncedLyrics": "[00:12.01]Farther",
            },
        ]

        result = _select_search_result(
            items,
            requested_title="everything u are",
            requested_artist="Hindia",
            audio_duration=237.0,
        )

        self.assertEqual(result["lyrics"], [{"start": 12.01, "text": "Closest"}])
        self.assertEqual(result["lyricsMatch"]["id"], 3)
        self.assertEqual(result["lyricsMatch"]["strategy"], "search")
        self.assertEqual(result["lyricsMatch"]["durationDelta"], 1.0)


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
