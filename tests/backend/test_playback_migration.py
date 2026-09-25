import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from stems import PlaybackEncodeError
from migrate_playback_audio import migrate_playback_audio


class PlaybackMigrationTests(unittest.TestCase):
    @patch("migrate_playback_audio.encode_playback_stems")
    def test_skips_track_with_complete_m4a_outputs(self, encode):
        with tempfile.TemporaryDirectory() as tmpdir:
            track_dir = Path(tmpdir) / "ready"
            track_dir.mkdir()
            (track_dir / "instrumental.m4a").write_bytes(b"instrumental")
            (track_dir / "vocals.m4a").write_bytes(b"vocals")

            converted, skipped, failed = migrate_playback_audio(Path(tmpdir))

        self.assertEqual(converted, [])
        self.assertEqual(skipped, ["ready"])
        self.assertEqual(failed, [])
        encode.assert_not_called()

    @patch("migrate_playback_audio.encode_playback_stems")
    def test_converts_legacy_track_from_existing_stems(self, encode):
        with tempfile.TemporaryDirectory() as tmpdir:
            track_dir = Path(tmpdir) / "legacy"
            track_dir.mkdir()
            (track_dir / "no_vocals.wav").touch()
            (track_dir / "vocals.wav").touch()

            converted, skipped, failed = migrate_playback_audio(Path(tmpdir))

        self.assertEqual(converted, ["legacy"])
        self.assertEqual(skipped, [])
        self.assertEqual(failed, [])
        encode.assert_called_once_with(track_dir)

    @patch("migrate_playback_audio.encode_playback_stems")
    def test_continues_after_a_track_fails(self, encode):
        def encode_track(track_dir):
            if track_dir.name == "broken":
                raise PlaybackEncodeError(
                    code="audio_encode_failed",
                    message="Could not prepare compressed playback audio.",
                    detail="broken stem",
                )

        encode.side_effect = encode_track

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "broken").mkdir()
            (root / "working").mkdir()

            converted, skipped, failed = migrate_playback_audio(root)

        self.assertEqual(converted, ["working"])
        self.assertEqual(skipped, [])
        self.assertEqual(failed, [("broken", "broken stem")])
        self.assertEqual(encode.call_count, 2)


if __name__ == "__main__":
    unittest.main()
