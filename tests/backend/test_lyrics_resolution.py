import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, call, patch

from lyrics_sync import (
    LyricsNotFound,
    LyricsProviderUnavailable,
    _LRCLibNotFound,
    _TemporaryLRCLibError,
    _retry_lrclib,
    _select_search_result,
    normalize_artist,
    normalize_title,
    parse_lrc,
    resolve_lrclib_lyrics,
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


class LRCLibProviderTests(unittest.IsolatedAsyncioTestCase):
    async def test_temporary_failure_retries_and_recovers(self):
        operation = AsyncMock(side_effect=[
            _TemporaryLRCLibError("timeout"),
            _TemporaryLRCLibError("HTTP 503"),
            {"ok": True},
        ])

        with patch("lyrics_sync.asyncio.sleep", new=AsyncMock()) as sleep:
            result = await _retry_lrclib(operation)

        self.assertEqual(result, {"ok": True})
        self.assertEqual(operation.await_count, 3)
        self.assertEqual(sleep.await_args_list, [call(0.5), call(1.0)])

    async def test_temporary_failure_stops_after_three_attempts(self):
        operation = AsyncMock(side_effect=_TemporaryLRCLibError("timeout"))

        with patch("lyrics_sync.asyncio.sleep", new=AsyncMock()):
            with self.assertRaisesRegex(LyricsProviderUnavailable, "timeout"):
                await _retry_lrclib(operation)

        self.assertEqual(operation.await_count, 3)

    async def test_exact_match_returns_before_search(self):
        exact = {
            "id": 17589301,
            "trackName": "everything u are",
            "artistName": "Hindia",
            "duration": 236.0,
            "syncedLyrics": "[00:12.01]Harapanku untukmu",
        }

        with patch("lyrics_sync._request_lrclib", new=AsyncMock(return_value=exact)) as request:
            result = await resolve_lrclib_lyrics(
                "Hindia - everything u are",
                "Hindia",
                237.0,
            )

        self.assertEqual(result["lyricsSource"], "lrclib")
        self.assertEqual(result["lyricsMatch"]["strategy"], "exact")
        request.assert_awaited_once_with(
            "get",
            {
                "track_name": "everything u are",
                "artist_name": "Hindia",
                "duration": 237.0,
            },
        )

    async def test_exact_404_falls_through_to_structured_search(self):
        search_results = [{
            "id": 31515195,
            "trackName": "everything u are",
            "artistName": "Hindia",
            "duration": 236.0,
            "syncedLyrics": "[00:12.01]Harapanku untukmu",
        }]
        request = AsyncMock(side_effect=[_LRCLibNotFound(), search_results])

        with patch("lyrics_sync._request_lrclib", new=request):
            result = await resolve_lrclib_lyrics(
                "Hindia - everything u are",
                "Hindia",
                237.0,
            )

        self.assertEqual(result["lyricsMatch"]["strategy"], "search")
        self.assertEqual(request.await_count, 2)
        self.assertEqual(request.await_args_list[1], call(
            "search",
            {
                "track_name": "everything u are",
                "artist_name": "Hindia",
            },
        ))

    async def test_exact_provider_failure_is_retained_if_search_has_no_match(self):
        request = AsyncMock(side_effect=[
            LyricsProviderUnavailable("LRCLIB returned HTTP 503"),
            [],
        ])

        with patch("lyrics_sync._request_lrclib", new=request):
            with self.assertRaisesRegex(
                LyricsProviderUnavailable,
                "LRCLIB returned HTTP 503",
            ):
                await resolve_lrclib_lyrics("Song", "Artist", 180.0)

    async def test_exact_provider_failure_can_recover_through_search(self):
        search_results = [{
            "id": 10,
            "trackName": "Song",
            "artistName": "Artist",
            "duration": 180.0,
            "syncedLyrics": "[00:01.00]Recovered",
        }]
        request = AsyncMock(side_effect=[
            LyricsProviderUnavailable("LRCLIB returned HTTP 503"),
            search_results,
        ])

        with patch("lyrics_sync._request_lrclib", new=request):
            result = await resolve_lrclib_lyrics("Song", "Artist", 180.0)

        self.assertEqual(result["lyricsMatch"]["strategy"], "search")

    async def test_successful_search_without_valid_candidate_is_not_found(self):
        request = AsyncMock(side_effect=[_LRCLibNotFound(), []])

        with patch("lyrics_sync._request_lrclib", new=request):
            with self.assertRaisesRegex(LyricsNotFound, "No valid LRCLIB match"):
                await resolve_lrclib_lyrics("Song", "Artist", 180.0)

    async def test_unavailable_search_is_reported_as_provider_failure(self):
        request = AsyncMock(side_effect=[
            _LRCLibNotFound(),
            LyricsProviderUnavailable("LRCLIB timed out after 3 attempts"),
        ])

        with patch("lyrics_sync._request_lrclib", new=request):
            with self.assertRaisesRegex(
                LyricsProviderUnavailable,
                "timed out after 3 attempts",
            ):
                await resolve_lrclib_lyrics("Song", "Artist", 180.0)


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
