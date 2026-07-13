import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from main import _audio_duration, _merge_lyrics_metadata, _write_json_atomic


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


if __name__ == "__main__":
    unittest.main()
