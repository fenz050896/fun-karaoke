import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from stems import StemSeparationError, separate_stems


class StemTimeoutTests(unittest.TestCase):
    @patch("stems.run_process")
    def test_separation_timeout_raises_structured_error(self, run):
        run.side_effect = subprocess.TimeoutExpired(cmd=["demucs"], timeout=1800)

        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises(StemSeparationError) as raised:
                separate_stems(Path(tmpdir) / "source.wav", Path(tmpdir) / "stems")

        self.assertEqual(raised.exception.code, "stems_timeout")
        self.assertIn("timed out", raised.exception.message.lower())
        self.assertEqual(run.call_args.kwargs["timeout"], 1800)


if __name__ == "__main__":
    unittest.main()
