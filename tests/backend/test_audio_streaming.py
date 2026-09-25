import tempfile
import unittest
from pathlib import Path

from fastapi import HTTPException
from starlette.requests import Request

from media import _parse_range_header, ranged_file_response


class AudioRangeTests(unittest.TestCase):
    def _request(self, range_header=None):
        headers = []
        if range_header is not None:
            headers.append((b"range", range_header.encode("ascii")))
        return Request({
            "type": "http",
            "method": "GET",
            "path": "/audio/test/instrumental",
            "headers": headers,
        })

    async def _body(self, response):
        body = bytearray()
        async for chunk in response.body_iterator:
            body.extend(chunk)
        return bytes(body)

    def test_parse_range_forms(self):
        self.assertEqual(_parse_range_header("bytes=2-5", 10), (2, 5))
        self.assertEqual(_parse_range_header("bytes=7-", 10), (7, 9))
        self.assertEqual(_parse_range_header("bytes=-3", 10), (7, 9))
        self.assertEqual(_parse_range_header("bytes=0-99", 10), (0, 9))

    def test_parse_rejects_invalid_or_unsatisfiable_ranges(self):
        for value in (
            "bytes=",
            "bytes=5-2",
            "bytes=10-",
            "bytes=-0",
            "bytes=0-1,4-5",
            "items=0-1",
        ):
            with self.subTest(value=value):
                self.assertIsNone(_parse_range_header(value, 10))

    def test_missing_file_returns_404(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises(HTTPException) as raised:
                ranged_file_response(
                    self._request(),
                    Path(tmpdir) / "missing.m4a",
                    "audio/mp4",
                )

        self.assertEqual(raised.exception.status_code, 404)


class AudioRangeResponseTests(unittest.IsolatedAsyncioTestCase):
    def _request(self, range_header=None):
        headers = []
        if range_header is not None:
            headers.append((b"range", range_header.encode("ascii")))
        return Request({
            "type": "http",
            "method": "GET",
            "path": "/audio/test/instrumental",
            "headers": headers,
        })

    async def _body(self, response):
        body = bytearray()
        async for chunk in response.body_iterator:
            body.extend(chunk)
        return bytes(body)

    async def test_full_response_includes_range_support(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "audio.m4a"
            path.write_bytes(b"0123456789")

            response = ranged_file_response(self._request(), path, "audio/mp4")
            body = await self._body(response)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["accept-ranges"], "bytes")
        self.assertEqual(response.headers["content-length"], "10")
        self.assertEqual(response.headers["content-type"], "audio/mp4")
        self.assertEqual(body, b"0123456789")

    async def test_bounded_range_returns_exact_partial_body(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "audio.m4a"
            path.write_bytes(b"0123456789")

            response = ranged_file_response(
                self._request("bytes=2-5"),
                path,
                "audio/mp4",
            )
            body = await self._body(response)

        self.assertEqual(response.status_code, 206)
        self.assertEqual(response.headers["content-range"], "bytes 2-5/10")
        self.assertEqual(response.headers["content-length"], "4")
        self.assertEqual(body, b"2345")

    async def test_suffix_range_returns_file_tail(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "audio.m4a"
            path.write_bytes(b"0123456789")

            response = ranged_file_response(
                self._request("bytes=-3"),
                path,
                "audio/mp4",
            )
            body = await self._body(response)

        self.assertEqual(response.status_code, 206)
        self.assertEqual(response.headers["content-range"], "bytes 7-9/10")
        self.assertEqual(body, b"789")

    async def test_invalid_range_returns_416_without_body(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "audio.m4a"
            path.write_bytes(b"0123456789")

            response = ranged_file_response(
                self._request("bytes=20-"),
                path,
                "audio/mp4",
            )
            body = await self._body(response)

        self.assertEqual(response.status_code, 416)
        self.assertEqual(response.headers["content-range"], "bytes */10")
        self.assertEqual(response.headers["content-length"], "0")
        self.assertEqual(body, b"")


if __name__ == "__main__":
    unittest.main()
