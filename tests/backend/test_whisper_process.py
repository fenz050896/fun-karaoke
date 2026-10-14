import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from lyrics_sync import transcribe_with_whisper


class WhisperProcessTests(unittest.TestCase):
    @patch("lyrics_sync.run_process", create=True)
    def test_transcription_uses_bounded_subprocess_and_decodes_segments(self, run):
        segments = [{"start": 1.25, "text": "hello"}]
        run.return_value = Mock(stdout=json.dumps(segments))

        result = transcribe_with_whisper(Path("vocals.wav"), model_size="small")

        self.assertEqual(result, segments)
        cmd = run.call_args.args[0]
        self.assertEqual(cmd[0], sys.executable)
        self.assertEqual(Path(cmd[1]).name, "lyrics_sync.py")
        self.assertEqual(cmd[2:], ["vocals.wav", "small"])
        self.assertEqual(run.call_args.kwargs["timeout"], 1200)

    @patch("lyrics_sync.run_process", create=True)
    def test_timeout_is_a_readable_failure_for_lyrics_fallback(self, run):
        run.side_effect = subprocess.TimeoutExpired(cmd=["whisper"], timeout=1200)
        with self.assertRaisesRegex(RuntimeError, "timed out"):
            transcribe_with_whisper(Path("vocals.wav"))

    def test_child_entrypoint_returns_only_json_without_loading_real_model(self):
        fake_module = '''
from types import SimpleNamespace

class WhisperModel:
    def __init__(self, model_size, device, compute_type):
        assert (model_size, device, compute_type) == ("small", "cpu", "int8")
        print("Model diagnostic")

    def transcribe(self, audio_path, beam_size, language):
        assert audio_path == "vocals.wav"
        assert (beam_size, language) == (5, None)
        print("Transcription diagnostic")
        return [SimpleNamespace(start=1.25, text="  Halo dunia  ")], None
'''
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "faster_whisper.py").write_text(fake_module)
            with patch.dict(os.environ, {"PYTHONPATH": tmpdir}):
                result = transcribe_with_whisper(Path("vocals.wav"), model_size="small")
        self.assertEqual(result, [{"start": 1.25, "text": "Halo dunia"}])

    @patch("lyrics_sync.run_process", create=True)
    def test_failed_process_has_bounded_diagnostics(self, run):
        run.side_effect = subprocess.CalledProcessError(
            1, ["whisper"], stderr="x" * 1000,
        )
        with self.assertRaises(RuntimeError) as raised:
            transcribe_with_whisper(Path("vocals.wav"))
        self.assertLessEqual(len(str(raised.exception)), 500)


if __name__ == "__main__":
    unittest.main()
