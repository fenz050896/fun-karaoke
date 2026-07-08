# Core Stability Pass Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden Fun Karaoke's core search/download, lyrics fallback, and playback flows with clear status/error contracts and recovery UI.

**Architecture:** Keep the current FastAPI file-based backend and Next.js frontend. Add small backend helpers for structured errors, YouTube status responses, and lyrics metadata, then update the existing frontend screens to consume those fields without changing the processing queue or player architecture.

**Tech Stack:** FastAPI, Python standard library `unittest`, yt-dlp subprocess calls, LRCLIB via httpx, faster-whisper fallback, Next.js 16, React 19, TypeScript, Tailwind CSS, Web Audio API.

## Current Project Status

**Last checked:** 2026-07-08

**Implementation:** Complete in local working tree, not committed yet.

**Implemented files currently present:**
- `backend/errors.py`
- `tests/backend/test_errors.py`
- `tests/backend/test_youtube_status.py`
- `tests/backend/test_lyrics_resolution.py`
- Backend structured YouTube search/download errors in `backend/youtube.py`
- Lyrics fallback coordinator in `backend/lyrics_sync.py`
- Search response, job error, and lyrics metadata wiring in `backend/main.py`
- Frontend API parsing and recovery UI changes in `frontend/src/lib/api.ts`, `frontend/src/app/page.tsx`, `frontend/src/components/home/SearchResults.tsx`, `frontend/src/app/processing/page.tsx`, `frontend/src/lib/audio-context.tsx`, and `frontend/src/app/karaoke/[videoId]/page.tsx`

**Verified now:**
- From repo root: `PYTHONPATH=backend python3 -m unittest discover -s tests/backend -p 'test_*.py' -v` passes 14 tests.
- From `backend`: `python3 -m py_compile errors.py youtube.py lyrics_sync.py main.py stems.py config.py` passes.
- From `frontend`: `npm run lint` passes.
- From `frontend`: `npm run build` passes.
- Manual API compatibility review passes: `search_youtube()` still returns a list, `/search` returns status response, `searchYouTube()` returns `results`, home reads `data.results`, and karaoke still calls `playTrack(videoId, initialMode)`.
- From repo root: `podman-compose build backend` passes.
- From repo root: `podman-compose run --rm backend python -c "from main import app; print(app.title)"` prints `Fun Karaoke API`.
- Running Podman dev stack smoke passes: backend `/health` returns `{"status":"ok"}`, frontend `/` returns HTTP 200, and frontend proxy `/api/search?q=test&max_results=1&search_type=all` returns `{ "ok": true, "results": [...], "error": null }`.

**External / not verified now:**
- Host-Python FastAPI import remains intentionally unused because this project runs backend in Podman and host Python lacks `fastapi`, `pip`, and working `venv`.
- Full browser interaction was not clicked manually; smoke coverage is HTTP-level via running Podman stack.
- Task commits not created.

---

## Scope Check

The spec touches backend search/download, backend lyrics metadata, and frontend recovery UI. These are not independent product subsystems for this milestone: they form one user-visible stability pass for the same karaoke loop. Keep them in one implementation plan so each task produces an incrementally more stable flow.

## File Structure

### Backend

- Create `backend/errors.py`
  - Owns small structured error helpers shared by YouTube and processing code.
  - Exposes `AppError`, `error_payload`, and `truncate_detail`.

- Modify `backend/youtube.py`
  - Keeps `search_youtube()` for compatibility.
  - Adds `search_youtube_with_status()` for the new `/search` response contract.
  - Adds `DownloadError` for structured download failures.

- Modify `backend/lyrics_sync.py`
  - Adds `resolve_lyrics()` as the single lyric fallback coordinator.
  - Keeps `fetch_lyrics()`, `parse_lrc()`, and `transcribe_with_whisper()` focused on their current jobs.

- Modify `backend/main.py`
  - Returns the new search response contract.
  - Records structured job errors.
  - Writes `lyricsSource` and `lyricsStatus` into `meta.json`.

- Create `tests/backend/test_errors.py`
- Create `tests/backend/test_youtube_status.py`
- Create `tests/backend/test_lyrics_resolution.py`

### Frontend

- Modify `frontend/src/lib/api.ts`
  - Adds typed API error parsing.
  - Makes `searchYouTube()` understand `{ ok, results, error }`.

- Modify `frontend/src/app/page.tsx`
  - Tracks whether a search has completed.
  - Distinguishes empty results from technical search failures.

- Modify `frontend/src/components/home/SearchResults.tsx`
  - Renders an error state and a zero-results state.

- Modify `frontend/src/app/processing/page.tsx`
  - Displays `errorMessage` and `errorDetail` when available.

- Modify `frontend/src/lib/audio-context.tsx`
  - Uses clearer metadata, instrumental, full-audio, decode, and playback error messages.

- Modify `frontend/src/app/karaoke/[videoId]/page.tsx`
  - Shows recovery actions when playback fails.
  - Treats empty lyrics as a valid playable state.

---

### Task 1: Backend Structured Error Helper

**Files:**
- Create: `backend/errors.py`
- Create: `tests/backend/test_errors.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/backend/test_errors.py`:

```python
import unittest

from errors import AppError, error_payload, truncate_detail


class ErrorHelperTests(unittest.TestCase):
    def test_error_payload_omits_empty_detail(self):
        payload = error_payload("youtube_timeout", "YouTube search timed out.")

        self.assertEqual(payload, {
            "code": "youtube_timeout",
            "message": "YouTube search timed out.",
        })

    def test_error_payload_includes_truncated_detail(self):
        payload = error_payload("download_failed", "Download failed.", "x" * 510)

        self.assertEqual(payload["code"], "download_failed")
        self.assertEqual(payload["message"], "Download failed.")
        self.assertEqual(len(payload["detail"]), 500)
        self.assertTrue(payload["detail"].endswith("..."))

    def test_app_error_exposes_payload(self):
        error = AppError(
            code="processing_failed",
            message="Processing failed.",
            detail="Demucs failed",
        )

        self.assertEqual(str(error), "Processing failed.")
        self.assertEqual(error.as_dict(), {
            "code": "processing_failed",
            "message": "Processing failed.",
            "detail": "Demucs failed",
        })

    def test_truncate_detail_handles_none(self):
        self.assertIsNone(truncate_detail(None))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
PYTHONPATH=backend python -m unittest discover -s tests/backend -p 'test_errors.py' -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'errors'`.

- [ ] **Step 3: Add the minimal helper implementation**

Create `backend/errors.py`:

```python
from dataclasses import dataclass
from typing import Optional


DETAIL_LIMIT = 500


def truncate_detail(detail: Optional[str], limit: int = DETAIL_LIMIT) -> Optional[str]:
    if not detail:
        return None
    clean = str(detail).strip()
    if not clean:
        return None
    if len(clean) <= limit:
        return clean
    return clean[: limit - 3].rstrip() + "..."


def error_payload(code: str, message: str, detail: Optional[str] = None) -> dict:
    payload = {
        "code": code,
        "message": message,
    }
    short_detail = truncate_detail(detail)
    if short_detail:
        payload["detail"] = short_detail
    return payload


@dataclass
class AppError(Exception):
    code: str
    message: str
    detail: Optional[str] = None

    def __str__(self) -> str:
        return self.message

    def as_dict(self) -> dict:
        return error_payload(self.code, self.message, self.detail)
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
PYTHONPATH=backend python -m unittest discover -s tests/backend -p 'test_errors.py' -v
```

Expected: PASS, four tests run.

- [ ] **Step 5: Commit**

```bash
git add backend/errors.py tests/backend/test_errors.py
git commit -m "test(api): add structured error helpers" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: YouTube Search and Download Error Contract

**Files:**
- Modify: `backend/youtube.py`
- Create: `tests/backend/test_youtube_status.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/backend/test_youtube_status.py`:

```python
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from youtube import (
    DownloadError,
    _classify_search_failure,
    _parse_search_output,
    download_audio,
    search_youtube_with_status,
)


class YouTubeStatusTests(unittest.TestCase):
    def test_parse_search_output_keeps_valid_rows(self):
        stdout = "abc123|Song Title|183|Artist Name\ninvalid row\ndef456|Other Song||Uploader\n"

        results = _parse_search_output(stdout)

        self.assertEqual(results, [
            {
                "videoId": "abc123",
                "title": "Song Title",
                "artist": "Artist Name",
                "duration": 183,
            },
            {
                "videoId": "def456",
                "title": "Other Song",
                "artist": "Uploader",
                "duration": 0,
            },
        ])

    def test_classify_timeout(self):
        error = _classify_search_failure("", cookies_present=True, timed_out=True)

        self.assertEqual(error["code"], "youtube_timeout")
        self.assertEqual(error["message"], "YouTube search timed out. Try again.")

    def test_classify_missing_cookies(self):
        error = _classify_search_failure("Sign in to confirm you are not a bot", cookies_present=False)

        self.assertEqual(error["code"], "youtube_cookies_missing")
        self.assertIn("cookies", error["message"].lower())

    @patch("youtube.subprocess.run")
    @patch("youtube.COOKIES_FILE")
    def test_search_timeout_returns_status_response(self, cookies_file, run):
        cookies_file.exists.return_value = True
        run.side_effect = subprocess.TimeoutExpired(cmd="yt-dlp", timeout=30)

        response = search_youtube_with_status("hello", max_results=3, search_type="all")

        self.assertFalse(response["ok"])
        self.assertEqual(response["results"], [])
        self.assertEqual(response["error"]["code"], "youtube_timeout")

    @patch("youtube.subprocess.run")
    @patch("youtube.COOKIES_FILE")
    def test_search_success_returns_status_response(self, cookies_file, run):
        cookies_file.exists.return_value = True
        run.return_value = Mock(
            returncode=0,
            stdout="abc123|Song Title|183|Artist Name\n",
            stderr="",
        )

        response = search_youtube_with_status("hello", max_results=3, search_type="all")

        self.assertTrue(response["ok"])
        self.assertEqual(response["error"], None)
        self.assertEqual(response["results"][0]["videoId"], "abc123")

    @patch("youtube.subprocess.run")
    @patch("youtube.COOKIES_FILE")
    def test_download_failure_raises_structured_error(self, cookies_file, run):
        cookies_file.exists.return_value = True
        run.side_effect = subprocess.CalledProcessError(
            returncode=1,
            cmd=["yt-dlp"],
            stderr="Sign in to confirm you are not a bot",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises(DownloadError) as raised:
                download_audio("abc123", Path(tmpdir))

        self.assertEqual(raised.exception.code, "download_failed")
        self.assertIn("YouTube", raised.exception.message)
        self.assertIn("Sign in", raised.exception.detail)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
PYTHONPATH=backend python -m unittest discover -s tests/backend -p 'test_youtube_status.py' -v
```

Expected: FAIL because `DownloadError`, `_classify_search_failure`, `_parse_search_output`, and `search_youtube_with_status` are not defined yet.

- [ ] **Step 3: Update imports and add structured search helpers**

Modify the imports at the top of `backend/youtube.py` to include `CalledProcessError`, `TimeoutExpired`, and the new helper module:

```python
import subprocess
import json
from pathlib import Path
from typing import List, Dict, Optional
import logging

from errors import AppError, error_payload, truncate_detail
```

Add these helper functions and classes above `search_youtube()`:

```python
class DownloadError(AppError):
    pass


class SearchError(AppError):
    pass


def _parse_search_output(stdout: str) -> List[Dict]:
    lines = stdout.strip().split("\n") if stdout else []
    items = []
    for line in lines:
        if not line.strip():
            continue
        parts = line.split("|", 3)
        if len(parts) < 4:
            logger.debug(f"Skipping invalid line: {line}")
            continue
        video_id, title, duration, uploader = parts
        try:
            duration_int = int(float(duration.strip())) if duration.strip() else 0
        except (ValueError, AttributeError):
            duration_int = 0
        items.append({
            "videoId": video_id.strip(),
            "title": title.strip(),
            "artist": uploader.strip(),
            "duration": duration_int,
        })
    return items


def _classify_search_failure(
    stderr: str,
    cookies_present: bool,
    timed_out: bool = False,
) -> Dict:
    if timed_out:
        return error_payload(
            "youtube_timeout",
            "YouTube search timed out. Try again.",
            stderr,
        )

    lower_stderr = (stderr or "").lower()
    if not cookies_present and (
        "sign in" in lower_stderr
        or "bot" in lower_stderr
        or "cookies" in lower_stderr
        or "confirm" in lower_stderr
    ):
        return error_payload(
            "youtube_cookies_missing",
            "YouTube blocked the request. Export fresh YouTube cookies and try again.",
            stderr,
        )

    if "sign in" in lower_stderr or "bot" in lower_stderr or "cookies" in lower_stderr:
        return error_payload(
            "youtube_search_failed",
            "YouTube search failed. Refresh the cookies file or try again later.",
            stderr,
        )

    return error_payload(
        "youtube_search_failed",
        "YouTube search failed. Try again.",
        stderr,
    )
```

- [ ] **Step 4: Replace search implementation with status response plus compatibility wrapper**

Replace the current `search_youtube()` implementation in `backend/youtube.py` with this pair of functions:

```python
def search_youtube_with_status(query: str, max_results: int = 10, search_type: str = "all") -> Dict:
    """Search YouTube using yt-dlp and return an API-ready status response."""
    if search_type == "artist":
        search_query = f"artist:{query}"
    elif search_type == "title":
        search_query = f"track:{query}"
    elif search_type == "genre":
        search_query = f"genre:{query}"
    else:
        search_query = query

    cmd = [
        "yt-dlp",
        "--flat-playlist",
        "--print", "%(id)s|%(title)s|%(duration)s|%(uploader)s",
        "--no-playlist",
        "--socket-timeout", "10",
        "--ignore-errors",
        f"ytsearch{max_results}:{search_query}",
    ]

    cookies_present = COOKIES_FILE.exists()
    if cookies_present:
        cmd.extend(["--cookies", str(COOKIES_FILE)])
        logger.info("Using cookies from youtube_cookies.txt")
    else:
        cmd.extend(["--extractor-args", "youtube:player_client=android"])
        logger.warning("No cookies file found. YouTube search may fail due to bot detection.")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except subprocess.TimeoutExpired:
        logger.error("yt-dlp search timeout")
        return {
            "ok": False,
            "results": [],
            "error": _classify_search_failure("", cookies_present, timed_out=True),
        }
    except Exception as e:
        logger.error(f"yt-dlp search unavailable: {e}")
        return {
            "ok": False,
            "results": [],
            "error": error_payload(
                "youtube_unavailable",
                "YouTube search is unavailable. Try again.",
                str(e),
            ),
        }

    stderr = result.stderr or ""
    if stderr and "ERROR" in stderr:
        logger.warning(f"yt-dlp errors: {stderr[:500]}")

    items = _parse_search_output(result.stdout)
    if result.returncode != 0 and not items:
        logger.error(f"yt-dlp failed with code {result.returncode}")
        return {
            "ok": False,
            "results": [],
            "error": _classify_search_failure(stderr, cookies_present),
        }

    logger.info(f"Found {len(items)} results for query: '{query}'")
    return {
        "ok": True,
        "results": items,
        "error": None,
    }


def search_youtube(query: str, max_results: int = 10, search_type: str = "all") -> List[Dict]:
    """Compatibility wrapper for callers that only need result rows."""
    return search_youtube_with_status(query, max_results, search_type).get("results", [])
```

- [ ] **Step 5: Update download failure handling**

Replace the final `subprocess.run(...)` block in `download_audio()` with this code:

```python
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        detail = e.stderr or e.stdout or str(e)
        raise DownloadError(
            code="download_failed",
            message="Could not download audio from YouTube. Check cookies or try another video.",
            detail=truncate_detail(detail),
        ) from e
    except Exception as e:
        raise DownloadError(
            code="download_failed",
            message="Could not download audio from YouTube. Check cookies or try another video.",
            detail=str(e),
        ) from e

    expected = output_dir / f"{video_id}.wav"
    if expected.exists():
        return expected
    candidates = list(output_dir.glob(f"{video_id}.*"))
    if candidates:
        return candidates[0]
    raise DownloadError(
        code="download_failed",
        message="Downloaded audio file was not found after YouTube download finished.",
        detail=f"Expected {expected}",
    )
```

- [ ] **Step 6: Run backend tests**

Run:

```bash
PYTHONPATH=backend python -m unittest discover -s tests/backend -p 'test_*.py' -v
```

Expected: PASS for `test_errors.py` and `test_youtube_status.py`.

- [ ] **Step 7: Commit**

```bash
git add backend/youtube.py tests/backend/test_youtube_status.py
git commit -m "fix(api): return structured youtube errors" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Lyrics Fallback Metadata and Processing Job Errors

**Files:**
- Modify: `backend/lyrics_sync.py`
- Modify: `backend/main.py`
- Create: `tests/backend/test_lyrics_resolution.py`

- [ ] **Step 1: Write the failing lyrics resolution tests**

Create `tests/backend/test_lyrics_resolution.py`:

```python
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from lyrics_sync import resolve_lyrics


class LyricsResolutionTests(unittest.IsolatedAsyncioTestCase):
    async def test_lrclib_lyrics_win(self):
        synced = [{"start": 1.0, "text": "hello"}]
        with patch("lyrics_sync.fetch_lyrics", new=AsyncMock(return_value=synced)):
            result = await resolve_lyrics("Song", "Artist", Path("missing.wav"), "small")

        self.assertEqual(result["lyrics"], synced)
        self.assertEqual(result["lyricsSource"], "lrclib")
        self.assertEqual(result["lyricsStatus"], "synced")
        self.assertNotIn("lyricsWarning", result)

    async def test_whisper_used_when_lrclib_empty(self):
        generated = [{"start": 2.0, "text": "generated"}]
        with tempfile.NamedTemporaryFile(suffix=".wav") as audio:
            with patch("lyrics_sync.fetch_lyrics", new=AsyncMock(return_value=None)):
                with patch("lyrics_sync.transcribe_with_whisper", return_value=generated):
                    result = await resolve_lyrics("Song", "Artist", Path(audio.name), "small")

        self.assertEqual(result["lyrics"], generated)
        self.assertEqual(result["lyricsSource"], "whisper")
        self.assertEqual(result["lyricsStatus"], "generated")

    async def test_unavailable_when_lrclib_fails_and_vocals_missing(self):
        with patch("lyrics_sync.fetch_lyrics", new=AsyncMock(side_effect=RuntimeError("LRCLIB down"))):
            result = await resolve_lyrics("Song", "Artist", Path("missing.wav"), "small")

        self.assertEqual(result["lyrics"], [])
        self.assertEqual(result["lyricsSource"], "none")
        self.assertEqual(result["lyricsStatus"], "unavailable")
        self.assertIn("LRCLIB down", result["lyricsWarning"])

    async def test_unavailable_when_whisper_fails(self):
        with tempfile.NamedTemporaryFile(suffix=".wav") as audio:
            with patch("lyrics_sync.fetch_lyrics", new=AsyncMock(return_value=None)):
                with patch("lyrics_sync.transcribe_with_whisper", side_effect=RuntimeError("Whisper failed")):
                    result = await resolve_lyrics("Song", "Artist", Path(audio.name), "small")

        self.assertEqual(result["lyrics"], [])
        self.assertEqual(result["lyricsSource"], "none")
        self.assertEqual(result["lyricsStatus"], "unavailable")
        self.assertIn("Whisper failed", result["lyricsWarning"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
PYTHONPATH=backend python -m unittest discover -s tests/backend -p 'test_lyrics_resolution.py' -v
```

Expected: FAIL because `resolve_lyrics` is not defined yet.

- [ ] **Step 3: Add lyrics fallback coordinator**

Append this function to `backend/lyrics_sync.py` below `transcribe_with_whisper()`:

```python
async def resolve_lyrics(title: str, artist: str, vocals_path: Path, model_size: str = "base") -> Dict:
    """Resolve lyrics with LRCLIB first, then Whisper, then an explicit unavailable state."""
    warning = None

    try:
        synced_lyrics = await fetch_lyrics(title, artist)
    except Exception as e:
        warning = str(e)
        synced_lyrics = None

    if synced_lyrics:
        return {
            "lyrics": synced_lyrics,
            "lyricsSource": "lrclib",
            "lyricsStatus": "synced",
        }

    if vocals_path.exists():
        try:
            generated_lyrics = transcribe_with_whisper(vocals_path, model_size=model_size)
        except Exception as e:
            warning = str(e)
            generated_lyrics = []

        if generated_lyrics:
            return {
                "lyrics": generated_lyrics,
                "lyricsSource": "whisper",
                "lyricsStatus": "generated",
            }

    result = {
        "lyrics": [],
        "lyricsSource": "none",
        "lyricsStatus": "unavailable",
    }
    if warning:
        result["lyricsWarning"] = warning
    return result
```

- [ ] **Step 4: Run lyrics tests**

Run:

```bash
PYTHONPATH=backend python -m unittest discover -s tests/backend -p 'test_lyrics_resolution.py' -v
```

Expected: PASS, four tests run.

- [ ] **Step 5: Wire search response, job errors, and lyrics metadata in FastAPI app**

Modify the imports in `backend/main.py`:

```python
from youtube import search_youtube_with_status, download_audio, DownloadError
from stems import separate_stems
from lyrics_sync import resolve_lyrics
```

Replace the `/search` endpoint body:

```python
@app.get("/search")
async def search(q: str, max_results: int = 10, search_type: str = "all"):
    return search_youtube_with_status(q, max_results, search_type)
```

Add this helper above `_process_track()`:

```python
def _set_job_error(job_id: str, code: str, message: str, detail: Optional[str] = None):
    jobs[job_id]["status"] = "error"
    jobs[job_id]["error"] = message
    jobs[job_id]["errorCode"] = code
    jobs[job_id]["errorMessage"] = message
    if detail:
        jobs[job_id]["errorDetail"] = detail
    else:
        jobs[job_id].pop("errorDetail", None)
    save_jobs()
```

Replace the old lyrics block inside `_process_track()`:

```python
        jobs[job_id]["status"] = "fetching_lyrics"
        save_jobs()  # Save job status
        lyrics = asyncio.run(fetch_lyrics(title, artist))
        if not lyrics:
            vocals_path = track_dir / "vocals.wav"
            if vocals_path.exists():
                lyrics = transcribe_with_whisper(vocals_path, model_size=WHISPER_MODEL)
            else:
                lyrics = []
```

with:

```python
        jobs[job_id]["status"] = "fetching_lyrics"
        save_jobs()  # Save job status
        vocals_path = track_dir / "vocals.wav"
        lyrics_result = asyncio.run(resolve_lyrics(title, artist, vocals_path, model_size=WHISPER_MODEL))
        if lyrics_result.get("lyricsWarning"):
            jobs[job_id]["lyricsWarning"] = lyrics_result["lyricsWarning"]
            save_jobs()
```

Update the `meta` dictionary lyrics fields:

```python
        meta = {
            "videoId": video_id,
            "title": title,
            "artist": artist,
            "status": "ready",
            "lyrics": lyrics_result["lyrics"],
            "lyricsSource": lyrics_result["lyricsSource"],
            "lyricsStatus": lyrics_result["lyricsStatus"],
            "mode": mode,
            "saved": save,
            "full_audio_path": str(DOWNLOADS_DIR / f"{video_id}.wav"),
        }
```

Replace the generic exception handling at the bottom of `_process_track()`:

```python
    except Exception as e:
        jobs[job_id]["status"] = "error"
        jobs[job_id]["error"] = str(e)
        save_jobs()  # Save error status
```

with:

```python
    except DownloadError as e:
        _set_job_error(job_id, e.code, e.message, e.detail)
    except Exception as e:
        current_status = jobs[job_id].get("status")
        if current_status == "separating":
            _set_job_error(
                job_id,
                "stems_failed",
                "Could not separate vocals and instrumental stems for this track.",
                str(e),
            )
        else:
            _set_job_error(
                job_id,
                "processing_failed",
                "Processing failed. Try another video or retry this track.",
                str(e),
            )
```

- [ ] **Step 6: Run all backend unit tests**

Run:

```bash
PYTHONPATH=backend python -m unittest discover -s tests/backend -p 'test_*.py' -v
```

Expected: PASS for all backend unit tests.

- [ ] **Step 7: Verify FastAPI app import**

Run:

```bash
PYTHONPATH=backend python - <<'PY'
from main import app
print(app.title)
PY
```

Expected output contains:

```text
Fun Karaoke API
```

- [ ] **Step 8: Commit**

```bash
git add backend/lyrics_sync.py backend/main.py tests/backend/test_lyrics_resolution.py
git commit -m "fix(api): add lyrics fallback metadata" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Frontend Search API and Empty/Error States

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/app/page.tsx`
- Modify: `frontend/src/components/home/SearchResults.tsx`

- [ ] **Step 1: Update API client types and search parsing**

Modify the top of `frontend/src/lib/api.ts` so the file begins with these types and helpers:

```typescript
type ApiErrorPayload = {
  code: string
  message: string
  detail?: string
}

export type SearchResponse = {
  ok?: boolean
  results: Array<{
    videoId: string
    title: string
    artist: string
    duration: number
  }>
  error?: ApiErrorPayload | null
}

export class ApiClientError extends Error {
  code?: string
  detail?: string

  constructor(message: string, code?: string, detail?: string) {
    super(message)
    this.name = 'ApiClientError'
    this.code = code
    this.detail = detail
  }
}

const API_BASE = typeof window !== 'undefined'
  ? (process.env.NEXT_PUBLIC_API_URL || "/api")
  : "http://backend:8000";

async function readJsonError(res: Response, fallback: string) {
  try {
    const data = await res.json()
    const payload = data?.error
    if (payload?.message) {
      return new ApiClientError(payload.message, payload.code, payload.detail)
    }
    if (data?.detail) {
      return new ApiClientError(String(data.detail))
    }
  } catch {
    return new ApiClientError(fallback)
  }
  return new ApiClientError(fallback)
}
```

Replace `searchYouTube()` with:

```typescript
export async function searchYouTube(query: string, maxResults: number = 10, searchType: string = "all"): Promise<SearchResponse> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 30000);

  try {
    const res = await fetch(`${API_BASE}/search?q=${encodeURIComponent(query)}&max_results=${maxResults}&search_type=${searchType}`, {
      signal: controller.signal,
    });
    clearTimeout(timeoutId);
    if (!res.ok) throw await readJsonError(res, "Search failed");

    const data = await res.json()
    if (data?.ok === false && data?.error?.message) {
      throw new ApiClientError(data.error.message, data.error.code, data.error.detail)
    }

    return {
      ok: data?.ok ?? true,
      results: data?.results || [],
      error: data?.error ?? null,
    }
  } catch (error) {
    clearTimeout(timeoutId);
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new ApiClientError('Search timed out. Try again.', 'request_timeout')
    }
    throw error;
  }
}
```

- [ ] **Step 2: Update home page search state**

In `frontend/src/app/page.tsx`, add state next to the existing `loading` state:

```typescript
  const [hasSearched, setHasSearched] = useState(false)
  const [searchError, setSearchError] = useState<string | null>(null)
```

Replace `handleSearch` with:

```typescript
  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!query.trim()) return
    setLoading(true)
    setSearchError(null)
    setHasSearched(true)
    try {
      const data = await searchYouTube(query, 10, searchType)
      const items: SearchResult[] = data.results || []
      setResults(items)

      const map: Record<string, { exists: boolean; status: string }> = {}
      await Promise.all(
        items.map(async (item) => {
          try {
            const res = await checkTrackExists(item.videoId)
            map[item.videoId] = res
          } catch {
            map[item.videoId] = { exists: false, status: 'not_found' }
          }
        }),
      )
      setExistingMap(map)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unknown error'
      setResults([])
      setExistingMap({})
      setSearchError(message)
      error('Search failed: ' + message)
    } finally {
      setLoading(false)
    }
  }
```

Pass the new props into `SearchResults`:

```tsx
          <SearchResults
            results={results}
            existingMap={existingMap}
            playQueue={playQueue}
            onProcess={handleProcess}
            onPlay={navigateToKaraoke}
            onAddToQueue={handleAddToQueue}
            loading={loading}
            hasSearched={hasSearched}
            errorMessage={searchError}
          />
```

- [ ] **Step 3: Render search error and empty states**

Update the props interface in `frontend/src/components/home/SearchResults.tsx`:

```typescript
interface SearchResultsProps {
  results: SearchResult[]
  existingMap: Record<string, { exists: boolean; status: string }>
  playQueue: { videoId: string }[]
  onProcess: (item: SearchResult) => void
  onPlay: (videoId: string) => void
  onAddToQueue: (item: SearchResult) => void
  loading?: boolean
  hasSearched?: boolean
  errorMessage?: string | null
}
```

Update the destructuring:

```typescript
export default function SearchResults({
  results,
  existingMap,
  playQueue,
  onProcess,
  onPlay,
  onAddToQueue,
  loading = false,
  hasSearched = false,
  errorMessage = null,
}: SearchResultsProps) {
```

Replace the current `if (results.length === 0) return null` block with:

```tsx
  if (errorMessage) {
    return (
      <div className="mt-6 rounded-2xl border border-red-500/20 bg-red-500/5">
        <EmptyState
          title="Search failed"
          description={errorMessage}
        />
      </div>
    )
  }

  if (hasSearched && results.length === 0) {
    return (
      <div className="mt-6 rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900/60">
        <EmptyState
          title="No results found"
          description="Try a different song title, artist, or search type."
        />
      </div>
    )
  }

  if (results.length === 0) return null
```

- [ ] **Step 4: Run frontend lint**

Run:

```bash
cd frontend && npm run lint
```

Expected: PASS with no ESLint errors.

- [ ] **Step 5: Run frontend build**

Run:

```bash
cd frontend && npm run build
```

Expected: PASS and produce a Next.js production build.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/lib/api.ts frontend/src/app/page.tsx frontend/src/components/home/SearchResults.tsx
git commit -m "fix(ui): distinguish search errors from empty results" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: Processing Page Structured Error Display

**Files:**
- Modify: `frontend/src/app/processing/page.tsx`

- [ ] **Step 1: Extend the processing job type**

Update `ProcessingJob` in `frontend/src/app/processing/page.tsx`:

```typescript
interface ProcessingJob {
  videoId: string
  title: string
  artist: string
  status: string
  error?: string
  errorCode?: string
  errorMessage?: string
  errorDetail?: string
  lyricsWarning?: string
  mode: string
}
```

- [ ] **Step 2: Add display helpers**

Add these helper functions below `getProgressColor`:

```typescript
  const getJobErrorMessage = (job: ProcessingJob) => {
    return job.errorMessage || job.error || 'Processing failed. Try another video or retry this track.'
  }

  const getJobErrorDetail = (job: ProcessingJob) => {
    return job.errorDetail || job.lyricsWarning || null
  }
```

- [ ] **Step 3: Replace failed job rendering**

Replace the existing error paragraph:

```tsx
              {job.error && (
                <p className="mt-2 text-sm text-red-500 dark:text-red-400">{job.error}</p>
              )}
```

with:

```tsx
              {job.status === 'error' && (
                <div className="mt-3 rounded-lg border border-red-500/20 bg-red-500/5 px-3 py-2">
                  <p className="text-sm font-medium text-red-600 dark:text-red-400">
                    {getJobErrorMessage(job)}
                  </p>
                  {getJobErrorDetail(job) && (
                    <p className="mt-1 text-xs text-red-500/80 dark:text-red-400/80 break-words">
                      {getJobErrorDetail(job)}
                    </p>
                  )}
                </div>
              )}
```

- [ ] **Step 4: Run frontend lint**

Run:

```bash
cd frontend && npm run lint
```

Expected: PASS with no ESLint errors.

- [ ] **Step 5: Run frontend build**

Run:

```bash
cd frontend && npm run build
```

Expected: PASS and produce a Next.js production build.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/app/processing/page.tsx
git commit -m "fix(ui): show structured processing errors" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: Karaoke Playback Recovery and Empty Lyrics State

**Files:**
- Modify: `frontend/src/lib/audio-context.tsx`
- Modify: `frontend/src/app/karaoke/[videoId]/page.tsx`

- [ ] **Step 1: Extend track metadata type**

In `frontend/src/lib/audio-context.tsx`, replace the `Track` type with:

```typescript
type Track = {
  videoId: string
  title: string
  artist: string
  status: string
  lyrics: LyricLine[]
  lyricsSource?: 'lrclib' | 'whisper' | 'none'
  lyricsStatus?: 'synced' | 'generated' | 'unavailable'
  mode?: string
  saved?: boolean
}
```

- [ ] **Step 2: Add audio response helpers inside `AudioProvider`**

Inside `AudioProvider`, above `playTrack`, add:

```typescript
  const fetchAudioBuffer = useCallback(async (ctx: AudioContext, url: string, label: string) => {
    let response: Response
    try {
      response = await fetch(url)
    } catch (e) {
      throw new Error(`${label} audio could not be reached.`)
    }

    if (!response.ok) {
      throw new Error(`${label} audio could not be loaded.`)
    }

    try {
      const data = await response.arrayBuffer()
      return await ctx.decodeAudioData(data)
    } catch {
      throw new Error(`${label} audio could not be decoded.`)
    }
  }, [])
```

- [ ] **Step 3: Replace audio and metadata loading in `playTrack`**

Inside `playTrack`, replace the block from `// Fetch both audio files in parallel` through the metadata `try/catch` with:

```typescript
      let data: Track
      try {
        data = await getTrack(vid)
      } catch {
        throw new Error('Track metadata could not be loaded.')
      }

      const [instAudio, fullAudio] = await Promise.all([
        fetchAudioBuffer(ctx, getInstrumentalUrl(vid), 'Instrumental'),
        fetchAudioBuffer(ctx, getFullAudioUrl(vid), 'Full'),
      ])

      karaokeBufferRef.current = instAudio
      fullBufferRef.current = fullAudio

      setTrack(data)
      setVideoId(vid)
      setDuration(instAudio.duration)

      if (!mode && data.mode) {
        const trackMode = data.mode as PlaybackMode
        modeRef.current = trackMode
        setPlaybackMode(trackMode)
      }

      startOffsetRef.current = 0
      createSources(0)
      isPlayingRef.current = true
      setIsPlaying(true)
      startTick()
```

Update the `catch` block at the end of `playTrack`:

```typescript
    } catch (e) {
      stopSources()
      isPlayingRef.current = false
      setIsPlaying(false)
      setError(e instanceof Error ? e.message : 'Failed to load audio')
    } finally {
```

Update the dependency list for `playTrack`:

```typescript
  }, [ensureCtx, stopSources, createSources, startTick, fetchAudioBuffer])
```

- [ ] **Step 4: Add recovery helpers in karaoke page**

In `frontend/src/app/karaoke/[videoId]/page.tsx`, add this memo below `activeIndex`:

```typescript
  const nextQueueItem = useMemo(() => {
    return queue.find((item) => item.videoId !== videoId) || null
  }, [queue, videoId])
```

Add this handler near `handlePlayFromQueue`:

```typescript
  const handleRetry = () => {
    playTrack(videoId, playbackMode)
  }
```

- [ ] **Step 5: Replace karaoke error UI with recovery actions**

Replace the error branch inside the lyrics panel:

```tsx
            ) : error ? (
              <div className="flex flex-col items-center justify-center h-full gap-3">
                <p className="text-zinc-400 text-sm">{error}</p>
                <Link
                  href="/"
                  className="rounded-lg bg-zinc-100 px-4 py-2 text-sm font-medium text-zinc-950"
                >
                  Back to search
                </Link>
              </div>
```

with:

```tsx
            ) : error ? (
              <div className="flex flex-col items-center justify-center h-full gap-3 text-center">
                <p className="text-zinc-300 text-sm font-medium">{error}</p>
                <div className="flex flex-wrap items-center justify-center gap-2">
                  <button
                    onClick={handleRetry}
                    className="rounded-lg bg-fuchsia-500 px-4 py-2 text-sm font-medium text-white hover:bg-fuchsia-400"
                  >
                    Try again
                  </button>
                  {nextQueueItem && (
                    <button
                      onClick={() => handlePlayFromQueue(nextQueueItem.videoId)}
                      className="rounded-lg bg-zinc-800 px-4 py-2 text-sm font-medium text-zinc-100 hover:bg-zinc-700"
                    >
                      Play next song
                    </button>
                  )}
                  <Link
                    href="/"
                    className="rounded-lg bg-zinc-100 px-4 py-2 text-sm font-medium text-zinc-950 hover:bg-zinc-200"
                  >
                    Back to home
                  </Link>
                </div>
              </div>
```

- [ ] **Step 6: Replace empty lyrics text**

Replace:

```tsx
            ) : !track || track.lyrics.length === 0 ? (
              <p className="text-zinc-500 text-sm">No lyrics generated.</p>
```

with:

```tsx
            ) : !track || track.lyrics.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-center px-6">
                <p className="text-zinc-300 text-sm font-medium">
                  Lyrics are unavailable for this track, but playback is ready.
                </p>
                <p className="mt-1 text-xs text-zinc-500">
                  You can still sing using karaoke or full mode.
                </p>
              </div>
```

- [ ] **Step 7: Run frontend lint**

Run:

```bash
cd frontend && npm run lint
```

Expected: PASS with no ESLint errors.

- [ ] **Step 8: Run frontend build**

Run:

```bash
cd frontend && npm run build
```

Expected: PASS and produce a Next.js production build.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/lib/audio-context.tsx frontend/src/app/karaoke/[videoId]/page.tsx
git commit -m "fix(ui): add karaoke playback recovery" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 7: Final Verification and Integration Check

**Files:**
- Verify: `backend/errors.py`
- Verify: `backend/youtube.py`
- Verify: `backend/lyrics_sync.py`
- Verify: `backend/main.py`
- Verify: `frontend/src/lib/api.ts`
- Verify: `frontend/src/app/page.tsx`
- Verify: `frontend/src/components/home/SearchResults.tsx`
- Verify: `frontend/src/app/processing/page.tsx`
- Verify: `frontend/src/lib/audio-context.tsx`
- Verify: `frontend/src/app/karaoke/[videoId]/page.tsx`

- [ ] **Step 1: Run backend unit tests**

```bash
PYTHONPATH=backend python -m unittest discover -s tests/backend -p 'test_*.py' -v
```

Expected: PASS for all backend tests.

- [ ] **Step 2: Run backend compile check**

```bash
python -m compileall backend
```

Expected: PASS with no syntax errors.

- [ ] **Step 3: Verify FastAPI app import**

```bash
PYTHONPATH=backend python - <<'PY'
from main import app
print(app.title)
PY
```

Expected output:

```text
Fun Karaoke API
```

- [ ] **Step 4: Run frontend lint**

```bash
cd frontend && npm run lint
```

Expected: PASS with no ESLint errors.

- [ ] **Step 5: Run frontend build**

```bash
cd frontend && npm run build
```

Expected: PASS and produce a Next.js production build.

- [ ] **Step 6: Review API compatibility manually**

Check these exact compatibility points in the diff:

```text
backend/youtube.py keeps search_youtube(query, max_results, search_type) returning a list.
backend/main.py /search returns ok, results, and error.
frontend/src/lib/api.ts searchYouTube() returns an object with results.
frontend/src/app/page.tsx still reads data.results.
frontend/src/app/karaoke/[videoId]/page.tsx still calls playTrack(videoId, initialMode) on mount.
```

Expected: all five statements are true.

- [ ] **Step 7: Check working tree**

```bash
git status --short
```

Expected: only files intentionally changed by this milestone are listed. If every task committed successfully, the output is empty.

- [ ] **Step 8: Final commit if verification changes were needed**

If Step 6 or Step 7 required a small correction, commit it:

```bash
git add backend frontend tests
git commit -m "fix(core): complete stability pass verification" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

If no files changed during verification, do not create an empty commit.

---

## Self-Review Checklist

- Search failures are covered by Task 2 and Task 4.
- Download failures and structured job errors are covered by Task 2 and Task 3.
- LRCLIB-first, Whisper-second, unavailable lyrics metadata is covered by Task 3.
- Empty lyrics playback state is covered by Task 6.
- Karaoke loading/playback recovery actions are covered by Task 6.
- Processing page structured errors are covered by Task 5.
- Backend import, unit tests, frontend lint, and frontend build are covered by Task 7.
