import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from main import _process_track
from stems import PlaybackEncodeError


class TrackPlaybackProcessingTests(unittest.TestCase):
    def _run_process(self, root: Path, encode):
        downloads = root / "downloads"
        processed = root / "processed"
        downloads.mkdir()
        processed.mkdir()
        audio_path = downloads / "abc.wav"
        audio_path.touch()
        jobs = {"job": {"videoId": "abc", "status": "queued"}}
        statuses = []

        def separate(_audio_path, track_dir, model):
            stems_dir = track_dir / model
            stems_dir.mkdir()
            (stems_dir / "no_vocals.wav").write_bytes(b"instrumental")
            (stems_dir / "vocals.wav").write_bytes(b"vocals")
            return stems_dir

        def save():
            statuses.append(jobs["job"]["status"])

        with patch("main.DOWNLOADS_DIR", downloads), \
             patch("main.PROCESSED_DIR", processed), \
             patch("main.jobs", jobs), \
             patch("main.save_jobs", side_effect=save), \
             patch("main.download_audio", return_value=audio_path), \
             patch("main.separate_stems", side_effect=separate), \
             patch("main.encode_playback_stems", side_effect=encode) as encoder, \
             patch("main._audio_duration", return_value=10.0), \
             patch("main.resolve_lyrics", new=AsyncMock(return_value={"lyrics": []})) as lyrics, \
             patch("main._start_next_queue_job"):
            _process_track("job", "abc", "Song", "Artist", "karaoke", True)

        return processed / "abc", jobs["job"], statuses, encoder, lyrics

    def test_track_is_ready_only_after_both_playback_files_are_encoded(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            def encode(track_dir):
                self.assertEqual((track_dir / "no_vocals.wav").read_bytes(), b"instrumental")
                self.assertEqual((track_dir / "vocals.wav").read_bytes(), b"vocals")
                (track_dir / "instrumental.m4a").write_bytes(b"compressed instrumental")
                (track_dir / "vocals.m4a").write_bytes(b"compressed vocals")

            track_dir, job, statuses, encoder, lyrics = self._run_process(Path(tmpdir), encode)
            meta = json.loads((track_dir / "meta.json").read_text(encoding="utf-8"))

            self.assertEqual(job["status"], "ready")
            self.assertEqual(meta["status"], "ready")
            self.assertEqual(statuses, ["downloading", "separating", "encoding", "fetching_lyrics", "ready"])
            self.assertTrue((track_dir / "no_vocals.wav").exists())
            self.assertTrue((track_dir / "vocals.wav").exists())
            encoder.assert_called_once_with(track_dir)
            lyrics.assert_awaited_once()

    def test_encoding_failure_does_not_mark_track_ready_or_fetch_lyrics(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            def encode(_track_dir):
                raise PlaybackEncodeError(
                    code="audio_encode_failed",
                    message="Could not prepare compressed playback audio.",
                    detail="encoder failed",
                )

            track_dir, job, statuses, encoder, lyrics = self._run_process(Path(tmpdir), encode)

            self.assertEqual(job["status"], "error")
            self.assertEqual(job["errorCode"], "audio_encode_failed")
            self.assertEqual(statuses, ["downloading", "separating", "encoding", "error"])
            self.assertFalse((track_dir / "meta.json").exists())
            self.assertTrue((track_dir / "no_vocals.wav").exists())
            self.assertTrue((track_dir / "vocals.wav").exists())
            encoder.assert_called_once_with(track_dir)
            lyrics.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
