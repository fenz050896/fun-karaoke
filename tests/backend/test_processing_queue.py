import asyncio
import json
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import Mock, patch

import config
import main


class ProcessingQueueTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.root = Path(self.tempdir.name)
        self.processed = self.root / "processed"
        self.processed.mkdir()
        self.jobs = {}
        self.queue = []
        for target, value in (
            ("main.jobs", self.jobs),
            ("config.jobs", self.jobs),
            ("config.processing_queue", self.queue),
            ("config.processing_job_id", None),
            ("config.processing_worker", None),
            ("config.processing_stopping", False),
            ("config.JOBS_FILE", self.root / "jobs.json"),
            ("main.PROCESSED_DIR", self.processed),
        ):
            patcher = patch(target, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_recovery_requeues_unfinished_jobs_and_starts_one_worker(self):
        statuses = (
            "downloading", "ready", "queued", "separating", "error",
            "encoding", "fetching_lyrics",
        )
        for index, status in enumerate(statuses):
            self.jobs[str(index)] = {
                "videoId": f"video-{index}",
                "status": status,
                "error": "old error" if status != "ready" else None,
                "errorCode": "old_code",
                "errorMessage": "old message",
                "errorDetail": "old detail",
                "lyricsWarning": "old warning",
            }

        with patch("main.threading.Thread") as thread:
            main._recover_processing_jobs()

        self.assertEqual(config.processing_job_id, "0")
        self.assertEqual(self.queue, ["2", "3", "5", "6"])
        self.assertEqual(self.jobs["0"]["status"], "queued")
        for job_id in ("0", "2", "3", "5", "6"):
            self.assertIsNone(self.jobs[job_id]["error"])
            for field in ("errorCode", "errorMessage", "errorDetail", "lyricsWarning"):
                self.assertNotIn(field, self.jobs[job_id])
        self.assertEqual(self.jobs["1"]["status"], "ready")
        self.assertEqual(self.jobs["4"]["status"], "error")
        thread.assert_called_once()
        thread.return_value.start.assert_called_once()
        persisted = json.loads(config.JOBS_FILE.read_text())
        self.assertEqual(persisted, self.jobs)

    def test_cold_start_rebuilds_queue_from_persisted_jobs(self):
        persisted = {
            "interrupted": {"videoId": "one", "status": "separating"},
            "waiting": {"videoId": "two", "status": "queued"},
            "finished": {"videoId": "three", "status": "ready"},
        }
        config.JOBS_FILE.write_text(json.dumps(persisted))
        code = '''
import asyncio
import json
from unittest.mock import patch
import config
import main

async def start():
    with patch("main.threading") as threads:
        worker = threads.Thread
        async with main.app.router.lifespan_context(main.app):
            print(json.dumps({
                "active": config.processing_job_id,
                "queue": config.processing_queue,
                "jobs": config.jobs,
                "workers": worker.call_count,
            }))

asyncio.run(start())
'''
        env = dict(os.environ, KARAOKE_DATA_DIR=str(self.root), PYTHONPATH=str(Path(main.__file__).parent))
        result = subprocess.run(
            [sys.executable, "-c", code], env=env, capture_output=True,
            text=True, check=True, timeout=10,
        )
        state = json.loads(result.stdout)
        self.assertEqual(state["active"], "interrupted")
        self.assertEqual(state["queue"], ["waiting"])
        self.assertEqual(state["jobs"]["interrupted"]["status"], "queued")
        self.assertEqual(state["jobs"]["finished"]["status"], "ready")
        self.assertEqual(state["workers"], 1)
        self.assertEqual(json.loads(config.JOBS_FILE.read_text()), state["jobs"])

    def test_recovery_does_not_reprocess_a_complete_ready_track(self):
        track_dir = self.processed / "complete"
        track_dir.mkdir()
        (track_dir / "meta.json").write_text(json.dumps({"status": "ready", "jobId": "complete-job"}))
        (track_dir / "instrumental.m4a").write_bytes(b"audio")
        (track_dir / "vocals.m4a").write_bytes(b"vocals")
        self.jobs["complete-job"] = {"videoId": "complete", "status": "fetching_lyrics"}
        self.jobs["broken-job"] = {"videoId": "broken", "status": "encoding"}
        broken_dir = self.processed / "broken"
        broken_dir.mkdir()
        (broken_dir / "meta.json").write_text("incomplete json")

        with patch("main.threading.Thread") as thread:
            main._recover_processing_jobs()

        self.assertEqual(self.jobs["complete-job"]["status"], "ready")
        self.assertEqual(config.processing_job_id, "broken-job")
        self.assertEqual(self.queue, [])
        thread.assert_called_once()

    def test_recovery_does_not_complete_a_new_job_using_an_older_jobs_audio(self):
        track_dir = self.processed / "existing"
        track_dir.mkdir()
        (track_dir / "meta.json").write_text(json.dumps({
            "status": "ready", "jobId": "old-job", "mode": "karaoke", "saved": True,
        }))
        (track_dir / "instrumental.m4a").write_bytes(b"old instrumental")
        (track_dir / "vocals.m4a").write_bytes(b"old vocals")
        self.jobs["new-job"] = {
            "videoId": "existing", "status": "downloading", "mode": "full", "saved": False,
        }

        with patch("main.threading.Thread") as thread:
            main._recover_processing_jobs()

        self.assertEqual(self.jobs["new-job"]["status"], "queued")
        self.assertEqual(config.processing_job_id, "new-job")
        self.assertEqual(thread.call_args.kwargs["args"], (
            "new-job", "existing", "", "", "full", False,
        ))
        self.assertEqual((track_dir / "instrumental.m4a").read_bytes(), b"old instrumental")

    def test_recovery_does_not_duplicate_an_active_worker(self):
        self.jobs["one"] = {"videoId": "video-one", "status": "queued"}
        self.jobs["two"] = {"videoId": "video-two", "status": "queued"}

        with patch("main.threading.Thread") as thread:
            main._recover_processing_jobs()
            main._recover_processing_jobs()

        self.assertEqual(config.processing_job_id, "one")
        self.assertEqual(self.queue, ["two"])
        thread.assert_called_once()

    def test_dispatch_skips_terminal_jobs_and_never_releases_another_worker(self):
        self.jobs.update({
            "failed": {"videoId": "failed", "status": "error"},
            "first": {"videoId": "first", "status": "queued"},
            "second": {"videoId": "second", "status": "queued"},
        })
        self.queue.extend(["missing", "failed", "first", "second"])

        with patch("main.threading.Thread") as thread:
            main._start_next_queue_job()
            main._start_next_queue_job()
            main._start_next_queue_job("someone-else")
            self.assertEqual(config.processing_job_id, "first")
            self.assertEqual(self.queue, ["second"])
            self.assertEqual(thread.call_count, 1)
            main._start_next_queue_job("first")

        self.assertEqual(config.processing_job_id, "second")
        self.assertEqual(self.queue, [])
        self.assertEqual(thread.call_count, 2)

    def test_concurrent_submissions_claim_only_one_worker_and_keep_fifo(self):
        barrier = threading.Barrier(2)

        def submit(video_id):
            barrier.wait(timeout=2)
            return asyncio.run(main.process(
                main.ProcessRequest(videoId=video_id),
            ))

        with patch("main.threading") as threads:
            with ThreadPoolExecutor(max_workers=2) as executor:
                results = list(executor.map(submit, ("one", "two")))

        ids = list(self.jobs)
        self.assertEqual(config.processing_job_id, ids[0])
        self.assertEqual(self.queue, ids[1:])
        self.assertEqual({item["jobId"] for item in results}, set(ids))
        threads.Thread.assert_called_once()
        self.assertEqual(json.loads(config.JOBS_FILE.read_text()), self.jobs)

    def test_requests_and_worker_completion_keep_a_single_fifo_worker(self):
        started = []
        remaining = 30

        def submit(index):
            return asyncio.run(main.process(main.ProcessRequest(videoId=f"video-{index}")))

        with patch("main.threading") as threads:
            def record_start(*args, **kwargs):
                started.append(kwargs["args"][0])
                return threads.Thread.return_value

            threads.Thread.side_effect = record_start
            submit(0)

            def finish():
                nonlocal remaining
                deadline = time.monotonic() + 5
                while remaining:
                    if time.monotonic() >= deadline:
                        self.fail("Queue did not finish within the test deadline")
                    with config.processing_lock:
                        job_id = config.processing_job_id
                    if job_id is None:
                        threading.Event().wait(0.001)
                        continue
                    main._set_job_status(job_id, "ready")
                    main._start_next_queue_job(job_id)
                    remaining -= 1

            with ThreadPoolExecutor(max_workers=4) as executor:
                completion = executor.submit(finish)
                list(executor.map(submit, range(1, 30)))
                completion.result(timeout=10)

        self.assertEqual(started, list(self.jobs))
        self.assertEqual(len(set(started)), 30)
        self.assertIsNone(config.processing_job_id)
        self.assertEqual(self.queue, [])
        self.assertTrue(all(job["status"] == "ready" for job in self.jobs.values()))
        self.assertEqual(json.loads(config.JOBS_FILE.read_text()), self.jobs)

    def test_shutdown_stops_active_process_without_starting_the_next_job(self):
        self.jobs.update({
            "active": {"videoId": "one", "status": "queued"},
            "waiting": {"videoId": "two", "status": "queued"},
        })
        config.save_jobs()
        pid_file = self.root / "worker.pid"
        code = '''
import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import patch
import config
import main
from process_runner import run_process

pid_file = config.DATA_DIR / "worker.pid"
child_code = (
    "import os, sys, time; from pathlib import Path; "
    "Path(sys.argv[1]).write_text(str(os.getpid())); time.sleep(30)"
)

def download(*args):
    run_process([sys.executable, "-c", child_code, str(pid_file)], timeout=25)

async def run():
    with patch("main.download_audio", side_effect=download) as download_mock:
        async with main.app.router.lifespan_context(main.app):
            for _ in range(300):
                if pid_file.exists():
                    break
                await asyncio.sleep(0.01)
            else:
                raise RuntimeError("Worker did not start")
            worker = getattr(config, "processing_worker", None)
        pid = int(pid_file.read_text())
        stat = Path(f"/proc/{pid}/stat")
        print(json.dumps({
            "processAlive": stat.exists() and stat.read_text().split()[2] != "Z",
            "workerStopped": worker is not None and not worker.is_alive(),
            "downloads": download_mock.call_count,
            "jobs": json.loads(config.JOBS_FILE.read_text()),
        }))

asyncio.run(run())
'''
        env = dict(os.environ, KARAOKE_DATA_DIR=str(self.root), PYTHONPATH=str(Path(main.__file__).parent))
        try:
            result = subprocess.run(
                [sys.executable, "-c", code], env=env, capture_output=True,
                text=True, check=True, timeout=10,
            )
            state = json.loads(result.stdout)
            self.assertFalse(state["processAlive"], "Audio subprocess outlived backend shutdown")
            self.assertTrue(state["workerStopped"])
            self.assertEqual(state["downloads"], 1)
            self.assertEqual(state["jobs"]["active"]["status"], "downloading")
            self.assertEqual(state["jobs"]["waiting"]["status"], "queued")
        finally:
            if pid_file.exists():
                try:
                    os.killpg(int(pid_file.read_text()), signal.SIGKILL)
                except ProcessLookupError:
                    pass

    def test_clearing_failed_job_does_not_release_worker_before_finally(self):
        self.jobs["active"] = {"videoId": "active", "status": "error"}
        self.jobs["next"] = {"videoId": "next", "status": "queued"}
        config.processing_job_id = "active"
        self.queue.append("next")

        response = asyncio.run(main.clear_failed_processing_jobs())

        self.assertEqual(response, {"success": True, "removed": 1})
        self.assertEqual(config.processing_job_id, "active")
        with patch("main.threading.Thread") as thread:
            main._start_next_queue_job("active")
        self.assertEqual(config.processing_job_id, "next")
        thread.assert_called_once()

    def test_jobs_are_replaced_atomically_without_truncating_existing_state(self):
        config.JOBS_FILE.write_text('{"previous": true}')
        self.jobs["one"] = {"videoId": "one", "status": "queued"}
        original_dump = json.dump

        def write_partial_then_fail(payload, file, **kwargs):
            file.write("{")
            raise OSError("write failed")

        with patch("config.json.dump", side_effect=write_partial_then_fail):
            with self.assertRaises(OSError):
                config.save_jobs()

        self.assertEqual(json.loads(config.JOBS_FILE.read_text()), {"previous": True})
        self.assertFalse(config.JOBS_FILE.with_suffix(".json.tmp").exists())
        with patch("config.json.dump", side_effect=original_dump):
            config.save_jobs()
        self.assertEqual(json.loads(config.JOBS_FILE.read_text()), self.jobs)


class ProcessingLifespanTests(unittest.IsolatedAsyncioTestCase):
    async def test_shutdown_stops_dispatch_before_joining_the_worker(self):
        worker = Mock()
        order = []

        def stop():
            self.assertTrue(config.processing_stopping)
            order.append("stop")

        def join():
            self.assertEqual(order, ["stop"])
            order.append("join")

        worker.join.side_effect = join
        with patch("main._recover_processing_jobs"), \
             patch("main.start_processes"), \
             patch("main.stop_processes", side_effect=stop), \
             patch("config.processing_worker", worker), \
             patch("config.processing_stopping", False):
            async with main.app.router.lifespan_context(main.app):
                pass
        self.assertEqual(order, ["stop", "join"])

    async def test_lifespan_recovers_jobs_before_serving_requests(self):
        with patch("main._recover_processing_jobs") as recover, \
             patch("main.start_processes") as start, \
             patch("main.stop_processes") as stop, \
             patch("config.processing_worker", None), \
             patch("config.processing_stopping", False):
            async with main.app.router.lifespan_context(main.app):
                recover.assert_called_once_with()
                start.assert_called_once_with()
                self.assertFalse(config.processing_stopping)
            stop.assert_called_once_with()
            self.assertTrue(config.processing_stopping)


if __name__ == "__main__":
    unittest.main()
