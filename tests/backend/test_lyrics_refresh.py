import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

from fastapi import HTTPException
from lyrics_sync import LyricsNotFound, LyricsProviderUnavailable
from main import (
    _audio_duration,
    _merge_lyrics_metadata,
    _write_json_atomic,
    lyrics_refresh_locks,
    refresh_track_lyrics,
)


class TrackLyricsMetadataTests(unittest.TestCase):
    def test_audio_duration_uses_soundfile_metadata(self):
        with patch("main.sf.info", return_value=Mock(duration=237.25)) as info:
            duration = _audio_duration(Path("/tmp/song.wav"))

        self.assertEqual(duration, 237.25)
        info.assert_called_once_with("/tmp/song.wav")

    def test_merge_replaces_only_lyric_fields(self):
        existing = {
            "videoId": "abc",
            "title": "Song",
            "artist": "Artist",
            "status": "ready",
            "mode": "karaoke",
            "saved": True,
            "full_audio_path": "/app/data/downloads/abc.wav",
            "lyrics": [{"start": 0.0, "text": "old"}],
            "lyricsSource": "whisper",
            "lyricsStatus": "generated",
            "lyricsWarning": "old warning",
        }
        result = {
            "lyrics": [{"start": 1.0, "text": "new"}],
            "lyricsSource": "lrclib",
            "lyricsStatus": "synced",
            "lyricsMatch": {"id": 1, "strategy": "exact"},
        }

        merged = _merge_lyrics_metadata(existing, result)

        self.assertEqual(merged["lyrics"], result["lyrics"])
        self.assertEqual(merged["lyricsSource"], "lrclib")
        self.assertEqual(merged["lyricsMatch"], result["lyricsMatch"])
        self.assertNotIn("lyricsWarning", merged)
        self.assertEqual(merged["title"], "Song")
        self.assertEqual(merged["full_audio_path"], "/app/data/downloads/abc.wav")

    def test_atomic_write_replaces_complete_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "meta.json"
            path.write_text('{"lyricsSource": "whisper"}', encoding="utf-8")

            _write_json_atomic(path, {
                "lyricsSource": "lrclib",
                "lyrics": [{"start": 1.0, "text": "hello"}],
            })

            saved = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(saved["lyricsSource"], "lrclib")
            self.assertFalse(path.with_suffix(".json.tmp").exists())


class LyricsRefreshEndpointTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        lyrics_refresh_locks.clear()

    def _track_files(self, root: Path):
        downloads = root / "downloads"
        processed = root / "processed"
        track_dir = processed / "abc"
        downloads.mkdir()
        track_dir.mkdir(parents=True)
        audio_path = downloads / "abc.wav"
        audio_path.touch()
        meta = {
            "videoId": "abc",
            "title": "Hindia - everything u are",
            "artist": "Hindia",
            "status": "ready",
            "mode": "karaoke",
            "saved": True,
            "full_audio_path": str(audio_path),
            "lyrics": [{"start": 0.0, "text": "old"}],
            "lyricsSource": "whisper",
            "lyricsStatus": "generated",
            "lyricsWarning": "old warning",
        }
        meta_path = track_dir / "meta.json"
        meta_path.write_text(json.dumps(meta), encoding="utf-8")
        return downloads, processed, meta_path, meta

    async def test_refresh_updates_only_lyric_fields_without_whisper(self):
        lrclib_result = {
            "lyrics": [{"start": 12.01, "text": "Harapanku untukmu"}],
            "lyricsSource": "lrclib",
            "lyricsStatus": "synced",
            "lyricsMatch": {
                "id": 17589301,
                "strategy": "exact",
                "trackName": "everything u are",
                "artistName": "Hindia",
                "duration": 236.0,
                "durationDelta": 1.0,
            },
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            downloads, processed, meta_path, old_meta = self._track_files(Path(tmpdir))
            with patch("main.DOWNLOADS_DIR", downloads), \
                 patch("main.PROCESSED_DIR", processed), \
                 patch("main._audio_duration", return_value=237.0), \
                 patch(
                     "main.resolve_lrclib_lyrics",
                     new=AsyncMock(return_value=lrclib_result),
                 ) as resolve, \
                 patch("lyrics_sync.transcribe_with_whisper") as whisper:
                response = await refresh_track_lyrics("abc")

            saved = json.loads(meta_path.read_text(encoding="utf-8"))

        self.assertTrue(response["success"])
        self.assertEqual(saved["lyricsSource"], "lrclib")
        self.assertEqual(saved["lyricsMatch"]["id"], 17589301)
        self.assertNotIn("lyricsWarning", saved)
        self.assertEqual(saved["title"], old_meta["title"])
        self.assertEqual(saved["mode"], old_meta["mode"])
        resolve.assert_awaited_once_with(
            "Hindia - everything u are",
            "Hindia",
            237.0,
        )
        whisper.assert_not_called()

    async def test_not_found_preserves_existing_metadata(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            downloads, processed, meta_path, old_meta = self._track_files(Path(tmpdir))
            with patch("main.DOWNLOADS_DIR", downloads), \
                 patch("main.PROCESSED_DIR", processed), \
                 patch("main._audio_duration", return_value=237.0), \
                 patch(
                     "main.resolve_lrclib_lyrics",
                     new=AsyncMock(side_effect=LyricsNotFound(
                         "No valid LRCLIB match"
                     )),
                 ):
                with self.assertRaises(HTTPException) as raised:
                    await refresh_track_lyrics("abc")

            saved = json.loads(meta_path.read_text(encoding="utf-8"))

        self.assertEqual(raised.exception.status_code, 404)
        self.assertEqual(raised.exception.detail["code"], "lyrics_not_found")
        self.assertEqual(saved, old_meta)

    async def test_provider_failure_returns_503_and_preserves_metadata(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            downloads, processed, meta_path, old_meta = self._track_files(Path(tmpdir))
            with patch("main.DOWNLOADS_DIR", downloads), \
                 patch("main.PROCESSED_DIR", processed), \
                 patch("main._audio_duration", return_value=237.0), \
                 patch(
                     "main.resolve_lrclib_lyrics",
                     new=AsyncMock(side_effect=LyricsProviderUnavailable(
                         "LRCLIB returned HTTP 503"
                     )),
                 ):
                with self.assertRaises(HTTPException) as raised:
                    await refresh_track_lyrics("abc")

            saved = json.loads(meta_path.read_text(encoding="utf-8"))

        self.assertEqual(raised.exception.status_code, 503)
        self.assertEqual(
            raised.exception.detail["code"],
            "lyrics_provider_unavailable",
        )
        self.assertEqual(saved, old_meta)

    async def test_same_video_uses_same_refresh_lock(self):
        from main import _lyrics_refresh_lock

        first = _lyrics_refresh_lock("abc")
        second = _lyrics_refresh_lock("abc")
        other = _lyrics_refresh_lock("def")

        self.assertIs(first, second)
        self.assertIsNot(first, other)

    async def test_refresh_uses_meta_full_audio_path_when_available(self):
        lrclib_result = {
            "lyrics": [{"start": 1.0, "text": "synced"}],
            "lyricsSource": "lrclib",
            "lyricsStatus": "synced",
            "lyricsMatch": {"id": 1, "strategy": "exact"},
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            downloads, processed, meta_path, _ = self._track_files(Path(tmpdir))
            configured_path = Path(tmpdir) / "configured.wav"
            configured_path.touch()
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            meta["full_audio_path"] = str(configured_path)
            meta_path.write_text(json.dumps(meta), encoding="utf-8")

            with patch("main.DOWNLOADS_DIR", downloads), \
                 patch("main.PROCESSED_DIR", processed), \
                 patch("main._audio_duration", return_value=237.0) as duration, \
                 patch(
                     "main.resolve_lrclib_lyrics",
                     new=AsyncMock(return_value=lrclib_result),
                 ):
                await refresh_track_lyrics("abc")

        duration.assert_called_once_with(configured_path)


if __name__ == "__main__":
    unittest.main()
