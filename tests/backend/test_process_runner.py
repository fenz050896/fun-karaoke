import os
import signal
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from process_runner import ProcessCancelled, run_process, start_processes, stop_processes


class ProcessRunnerTests(unittest.TestCase):
    def setUp(self):
        start_processes()
        self.addCleanup(start_processes)

    @patch("process_runner.subprocess.Popen")
    def test_shutdown_refuses_new_processes_until_next_startup(self, popen):
        stop_processes()
        with self.assertRaises(ProcessCancelled):
            run_process(["worker"], timeout=1)
        popen.assert_not_called()
        start_processes()
        popen.return_value.communicate.return_value = ("result", "")
        popen.return_value.returncode = 0
        self.assertEqual(run_process(["worker"], timeout=1).stdout, "result")

    def test_returns_captured_output_for_successful_process(self):
        result = run_process(
            [sys.executable, "-c", "import sys; print('result'); print('diagnostic', file=sys.stderr)"],
            timeout=5,
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "result\n")
        self.assertEqual(result.stderr, "diagnostic\n")

    def test_failure_preserves_output_and_raises_called_process_error(self):
        with self.assertRaises(subprocess.CalledProcessError) as raised:
            run_process(
                [sys.executable, "-c", "import sys; print('failed', file=sys.stderr); sys.exit(3)"],
                timeout=5,
            )
        self.assertEqual(raised.exception.returncode, 3)
        self.assertEqual(raised.exception.stderr, "failed\n")

    @patch("process_runner.os.killpg")
    @patch("process_runner.subprocess.Popen")
    def test_timeout_kills_process_group_and_reaps_process(self, popen, killpg):
        process = Mock(pid=123, returncode=-9)
        process.communicate.side_effect = [
            subprocess.TimeoutExpired(cmd=["worker"], timeout=1),
            ("partial", "timeout details"),
        ]
        popen.return_value = process

        with self.assertRaises(subprocess.TimeoutExpired) as raised:
            run_process(["worker"], timeout=1)

        self.assertTrue(popen.call_args.kwargs["start_new_session"])
        killpg.assert_called_once_with(123, signal.SIGKILL)
        self.assertEqual(process.communicate.call_count, 2)
        self.assertEqual(raised.exception.output, "partial")
        self.assertEqual(raised.exception.stderr, "timeout details")

    @unittest.skipUnless(os.name == "posix", "Process groups require POSIX")
    def test_timeout_stops_a_child_process_as_well_as_parent(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pid_file = Path(tmpdir) / "child.pid"
            child_code = (
                "import os, sys, time; from pathlib import Path; "
                "Path(sys.argv[1]).write_text(str(os.getpid())); time.sleep(30)"
            )
            parent_code = (
                "import subprocess, sys, time; "
                "subprocess.Popen([sys.executable, '-c', sys.argv[2], sys.argv[1]]); "
                "time.sleep(30)"
            )
            try:
                with self.assertRaises(subprocess.TimeoutExpired):
                    run_process(
                        [sys.executable, "-c", parent_code, str(pid_file), child_code],
                        timeout=1,
                    )
                self.assertTrue(pid_file.exists(), "Child did not start before timeout")
                pid = int(pid_file.read_text())
                stat = Path(f"/proc/{pid}/stat")
                if stat.exists():
                    self.assertEqual(stat.read_text().split()[2], "Z", "Child is still running")
            finally:
                if pid_file.exists():
                    try:
                        os.kill(int(pid_file.read_text()), signal.SIGKILL)
                    except ProcessLookupError:
                        pass


if __name__ == "__main__":
    unittest.main()
