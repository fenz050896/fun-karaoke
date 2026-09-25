import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from stems import PlaybackEncodeError, encode_playback_stems


class PlaybackAudioTests(unittest.TestCase):
    @patch("stems.subprocess.run")
    def test_encode_playback_stems_creates_atomic_aac_outputs(self, run):
        def create_outputs(cmd, **kwargs):
            for value in cmd:
                if value.endswith(".tmp.m4a"):
                    Path(value).write_bytes(b"encoded")
            return Mock(returncode=0, stderr="")

        run.side_effect = create_outputs

        with tempfile.TemporaryDirectory() as tmpdir:
            track_dir = Path(tmpdir)
            (track_dir / "no_vocals.wav").touch()
            (track_dir / "vocals.wav").touch()

            instrumental_path, vocals_path = encode_playback_stems(track_dir)

            self.assertEqual(instrumental_path, track_dir / "instrumental.m4a")
            self.assertEqual(vocals_path, track_dir / "vocals.m4a")
            self.assertTrue(instrumental_path.exists())
            self.assertTrue(vocals_path.exists())
            self.assertFalse((track_dir / "instrumental.tmp.m4a").exists())
            self.assertFalse((track_dir / "vocals.tmp.m4a").exists())

        cmd = run.call_args.args[0]
        self.assertEqual(cmd.count("-map"), 2)
        self.assertIn("0:a:0", cmd)
        self.assertIn("1:a:0", cmd)
        self.assertEqual(cmd.count("aac"), 2)
        self.assertIn("192k", cmd)
        self.assertIn("128k", cmd)
        self.assertEqual(cmd.count("44100"), 2)
        self.assertEqual(cmd.count("aac_low"), 2)
        self.assertEqual(cmd.count("2"), 2)
        self.assertEqual(cmd.count("+faststart"), 2)

    @patch("stems.subprocess.run")
    def test_empty_output_is_rejected_and_keeps_old_files(self, run):
        def create_outputs(cmd, **kwargs):
            for value in cmd:
                if value.endswith(".tmp.m4a"):
                    Path(value).touch()

        run.side_effect = create_outputs

        with tempfile.TemporaryDirectory() as tmpdir:
            track_dir = Path(tmpdir)
            (track_dir / "no_vocals.wav").touch()
            (track_dir / "vocals.wav").touch()
            (track_dir / "instrumental.m4a").write_bytes(b"old instrumental")
            (track_dir / "vocals.m4a").write_bytes(b"old vocals")

            with self.assertRaises(PlaybackEncodeError):
                encode_playback_stems(track_dir)

            self.assertEqual((track_dir / "instrumental.m4a").read_bytes(), b"old instrumental")
            self.assertEqual((track_dir / "vocals.m4a").read_bytes(), b"old vocals")
            self.assertFalse((track_dir / "instrumental.tmp.m4a").exists())
            self.assertFalse((track_dir / "vocals.tmp.m4a").exists())

    @patch("stems.subprocess.run")
    def test_encode_failure_removes_temporary_outputs_and_keeps_old_files(self, run):
        def fail_with_partial_output(cmd, **kwargs):
            Path(cmd[-1]).touch()
            raise subprocess.CalledProcessError(
                returncode=1,
                cmd=cmd,
                stderr="encoder failed",
            )

        run.side_effect = fail_with_partial_output

        with tempfile.TemporaryDirectory() as tmpdir:
            track_dir = Path(tmpdir)
            (track_dir / "no_vocals.wav").touch()
            (track_dir / "vocals.wav").touch()
            instrumental_path = track_dir / "instrumental.m4a"
            vocals_path = track_dir / "vocals.m4a"
            instrumental_path.write_bytes(b"old instrumental")
            vocals_path.write_bytes(b"old vocals")

            with self.assertRaises(PlaybackEncodeError) as raised:
                encode_playback_stems(track_dir)

            self.assertEqual(instrumental_path.read_bytes(), b"old instrumental")
            self.assertEqual(vocals_path.read_bytes(), b"old vocals")
            self.assertFalse((track_dir / "instrumental.tmp.m4a").exists())
            self.assertFalse((track_dir / "vocals.tmp.m4a").exists())

        self.assertEqual(raised.exception.code, "audio_encode_failed")
        self.assertIn("encoder failed", raised.exception.detail)

    def test_encode_requires_both_wav_stems(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            track_dir = Path(tmpdir)
            (track_dir / "no_vocals.wav").touch()

            with self.assertRaises(PlaybackEncodeError) as raised:
                encode_playback_stems(track_dir)

        self.assertEqual(raised.exception.code, "audio_encode_failed")
        self.assertIn("vocals.wav", raised.exception.detail)


if __name__ == "__main__":
    unittest.main()
