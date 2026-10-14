import asyncio
import threading
import unittest
from unittest.mock import patch

import httpx
from main import app


class SearchConcurrencyTests(unittest.IsolatedAsyncioTestCase):
    async def test_slow_search_does_not_block_health_or_job_status(self):
        started = threading.Event()
        release = threading.Event()
        timed_out = threading.Event()
        result = {"ok": True, "results": [], "error": None}

        def slow_search(*args):
            started.set()
            if not release.wait(timeout=2):
                timed_out.set()
            return result

        with patch("main.search_youtube_with_status", side_effect=slow_search) as search, \
             patch("main.jobs", {"job": {"status": "queued"}}):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://test",
            ) as client:
                search_task = asyncio.create_task(client.get("/search?q=song&max_results=3&search_type=title"))
                try:
                    self.assertTrue(await asyncio.to_thread(started.wait, 1))
                    health = await asyncio.wait_for(client.get("/health"), timeout=0.5)
                    status = await asyncio.wait_for(client.get("/status/job"), timeout=0.5)
                    self.assertEqual(health.json(), {"status": "ok"})
                    self.assertEqual(status.json(), {"status": "queued"})
                    self.assertFalse(timed_out.is_set(), "Search blocked the API event loop")
                    self.assertFalse(search_task.done())
                finally:
                    release.set()
                    response = await search_task

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), result)
        search.assert_called_once_with("song", 3, "title")

    async def test_search_preserves_structured_failure_response(self):
        result = {
            "ok": False,
            "results": [],
            "error": {"code": "youtube_timeout", "message": "YouTube search timed out. Try again."},
        }
        with patch("main.search_youtube_with_status", return_value=result):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://test",
            ) as client:
                response = await client.get("/search?q=song")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), result)


if __name__ == "__main__":
    unittest.main()
