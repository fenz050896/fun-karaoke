# LRCLIB Lyrics Resolution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolve synced lyrics through validated LRCLIB metadata lookups before Whisper, persist diagnostics, and let users refresh cached Whisper lyrics without reprocessing audio.

**Architecture:** Keep lyric matching and provider behavior in `backend/lyrics_sync.py`; keep track-file duration, metadata persistence, and the refresh route in `backend/main.py`. The frontend adds one typed API call and one audio-context metadata reload method, then integrates a small refresh action into the existing karaoke lyrics panel without touching the user's current Now Playing or upcoming-queue work.

**Tech Stack:** FastAPI, Python 3.12, `httpx`, `soundfile`, standard-library `unittest`, LRCLIB HTTP API, faster-whisper fallback, Next.js 16, React 19, TypeScript, Tailwind CSS.

---

## Scope Check

This is one end-to-end feature rather than separate subsystems: backend candidate selection determines persisted track metadata, and the frontend refresh action exercises that same backend path for an already processed track. Keep it in one plan so every backend contract is consumed and verified before the UI is considered complete.

Do not add a database, a worker system, fuzzy matching, a Whisper model change, or a manual lyric editor.

## Current Baseline

- The approved design is `docs/superpowers/specs/2026-07-10-lrclib-lyrics-resolution-design.md` at commit `9700919`.
- Backend tests currently pass: 14 tests via `PYTHONPATH=backend python3 -m unittest discover -s tests/backend -p 'test_*.py' -v`.
- Frontend lint currently passes.
- Host Python does not have FastAPI, httpx, or soundfile installed. Pure lyric unit tests can run on the host because provider imports stay lazy; tests importing `backend/main.py` must run in the backend container.
- `frontend/src/app/karaoke/[videoId]/page.tsx` already has uncommitted user changes adding:
  - an `upcomingQueue` filter;
  - a Now Playing card;
  - playback progress;
  - a queue that excludes the current song.
- Those page changes must remain intact and must not be included in an implementation commit. Task 0 backs them up and stashes them; Task 7 commits the refresh UI against the clean tracked page, then restores the user's work as an unstaged diff.

## File Structure

### Backend

- Modify `backend/lyrics_sync.py`
  - Own conservative metadata normalization.
  - Own retry classification and LRCLIB HTTP requests.
  - Own exact lookup, structured search, candidate validation, and Whisper fallback.
  - Expose `resolve_lrclib_lyrics()` for refresh and `resolve_lyrics()` for normal processing.

- Modify `tests/backend/test_lyrics_resolution.py`
  - Cover normalization, candidate validation, retry behavior, exact/search ordering, and fallback diagnostics.

- Modify `backend/main.py`
  - Read full-WAV duration with `soundfile.info()`.
  - Pass duration into normal lyric resolution.
  - Persist `lyricsMatch` and `lyricsWarning`.
  - Atomically update lyric-only metadata.
  - Expose `POST /track/{video_id}/lyrics/refresh` with a per-track lock.

- Create `tests/backend/test_lyrics_refresh.py`
  - Cover metadata preservation, atomic replacement, endpoint errors, and no-Whisper refresh behavior.

### Frontend

- Modify `frontend/src/lib/api.ts`
  - Parse FastAPI's nested structured error payload.
  - Add `refreshLyrics(videoId)`.

- Modify `frontend/src/lib/audio-context.tsx`
  - Add `reloadTrackMetadata(videoId)` without restarting or re-decoding audio.
  - Extend the track metadata type with optional LRCLIB diagnostic fields.

- Modify `frontend/src/app/karaoke/[videoId]/page.tsx`
  - Preserve all existing uncommitted Now Playing and upcoming-queue changes.
  - Add refresh state, action, and inline result messages only in the lyrics panel.

---

### Task 0: Create a Safe Implementation Branch and Record the User Diff

**Files:**
- Inspect only: `frontend/src/app/karaoke/[videoId]/page.tsx`

- [ ] **Step 1: Confirm the baseline working tree**

Run from the repository root:

```bash
git status --short --branch
git diff -- frontend/src/app/karaoke/'[videoId]'/page.tsx
```

Expected:

- current branch is `main`;
- the design commit is ahead of `origin/main`;
- only the karaoke page has a pre-existing modification before this plan file;
- the diff contains `upcomingQueue`, `progress`, and the Now Playing panel.

- [ ] **Step 2: Create a feature branch before implementation commits**

Run:

```bash
git switch -c feat/lrclib-lyrics-resolution
```

Expected: `Switched to a new branch 'feat/lrclib-lyrics-resolution'`. The existing karaoke page modification must remain present.

- [ ] **Step 3: Save a read-only baseline patch outside the repository**

Run:

```bash
git diff -- frontend/src/app/karaoke/'[videoId]'/page.tsx > /tmp/fun-karaoke-page-before-lyrics-refresh.patch
```

Expected: `/tmp/fun-karaoke-page-before-lyrics-refresh.patch` contains the user's Now Playing and queue changes. Keep this as a comparison/recovery artifact.

- [ ] **Step 4: Stash only the user's page change**

Run:

```bash
git stash push -m "user karaoke page before lyric refresh" -- \
  frontend/src/app/karaoke/'[videoId]'/page.tsx
```

Expected: the stash is created, the karaoke page returns to the tracked version, and the untracked implementation plan remains in the working tree.

- [ ] **Step 5: Verify the clean implementation baseline**

Run:

```bash
git status --short --branch
git stash list | head -1
PYTHONPATH=backend python3 -m unittest discover -s tests/backend -p 'test_*.py' -v
cd frontend && npm run lint
```

Expected:

- no tracked source modification remains;
- the plan file is still untracked;
- the top stash is named `user karaoke page before lyric refresh`;
- 14 backend tests pass and ESLint reports no issues.

---

### Task 1: Normalize Metadata and Validate LRCLIB Candidates

**Files:**
- Modify: `backend/lyrics_sync.py:1-42`
- Modify: `tests/backend/test_lyrics_resolution.py`

- [ ] **Step 1: Add failing normalization and candidate tests**

Update the imports in `tests/backend/test_lyrics_resolution.py` to include the new helpers:

```python
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from lyrics_sync import (
    _select_search_result,
    normalize_artist,
    normalize_title,
    parse_lrc,
    resolve_lyrics,
)
```

Add this class before the existing `LyricsResolutionTests` class:

```python
class LyricsMetadataTests(unittest.TestCase):
    def test_normalize_title_removes_matching_artist_prefix_and_label(self):
        title = normalize_title(
            "Hindia - everything u are (Official Music Video)",
            "Hindia - Topic",
        )

        self.assertEqual(title, "everything u are")
        self.assertEqual(normalize_artist("Hindia - Topic"), "Hindia")

    def test_normalize_title_preserves_meaningful_parenthetical_text(self):
        title = normalize_title("Song (Acoustic Version)", "Artist")

        self.assertEqual(title, "Song (Acoustic Version)")

    def test_parse_lrc_ignores_malformed_or_empty_lines(self):
        lyrics = parse_lrc("[00:01.00]\nnot lrc\n[00:02.50]Hello")

        self.assertEqual(lyrics, [{"start": 2.5, "text": "Hello"}])

    def test_search_selection_rejects_mismatches_and_uses_closest_duration(self):
        items = [
            {
                "id": 1,
                "trackName": "everything u are",
                "artistName": "Hindia",
                "duration": 349.0,
                "syncedLyrics": "[00:01.00]Wrong version",
            },
            {
                "id": 2,
                "trackName": "another song",
                "artistName": "Hindia",
                "duration": 237.0,
                "syncedLyrics": "[00:01.00]Wrong title",
            },
            {
                "id": 3,
                "trackName": "everything u are",
                "artistName": "Hindia",
                "duration": 236.0,
                "syncedLyrics": "[00:12.01]Closest",
            },
            {
                "id": 4,
                "trackName": "Hindia - everything u are",
                "artistName": "Hindia",
                "duration": 234.0,
                "syncedLyrics": "[00:12.01]Farther",
            },
        ]

        result = _select_search_result(
            items,
            requested_title="everything u are",
            requested_artist="Hindia",
            audio_duration=237.0,
        )

        self.assertEqual(result["lyrics"], [{"start": 12.01, "text": "Closest"}])
        self.assertEqual(result["lyricsMatch"]["id"], 3)
        self.assertEqual(result["lyricsMatch"]["strategy"], "search")
        self.assertEqual(result["lyricsMatch"]["durationDelta"], 1.0)
```

- [ ] **Step 2: Run the tests and verify the new tests fail**

Run:

```bash
PYTHONPATH=backend:tests/backend python3 -m unittest test_lyrics_resolution.LyricsMetadataTests -v
```

Expected: import failure for `normalize_title` or `_select_search_result` because the helpers do not exist yet.

- [ ] **Step 3: Add normalization and candidate helpers**

In `backend/lyrics_sync.py`, replace the top-level imports and add constants/helpers before `parse_lrc()`:

```python
import asyncio
import re
from pathlib import Path
from typing import Awaitable, Callable, Dict, List, Optional


LRCLIB_BASE_URL = "https://lrclib.net/api"
DURATION_TOLERANCE_SECONDS = 10.0
RETRY_DELAYS_SECONDS = (0.5, 1.0)
PRESENTATION_LABEL_RE = re.compile(
    r"\s*[\[(](official music video|official audio|lyrics)[\])]\s*$",
    re.IGNORECASE,
)
TOPIC_SUFFIX_RE = re.compile(r"\s+-\s+topic\s*$", re.IGNORECASE)


class LyricsNotFound(Exception):
    pass


class LyricsProviderUnavailable(Exception):
    pass


class _LRCLibNotFound(Exception):
    pass


class _TemporaryLRCLibError(Exception):
    pass


def _collapse_whitespace(value: str) -> str:
    return " ".join((value or "").strip().split())


def _comparison_key(value: str) -> str:
    return _collapse_whitespace(value).casefold()


def normalize_artist(artist: str) -> str:
    return _collapse_whitespace(TOPIC_SUFFIX_RE.sub("", artist or ""))


def normalize_title(title: str, artist: str) -> str:
    cleaned = _collapse_whitespace(title)
    cleaned_artist = normalize_artist(artist)

    while PRESENTATION_LABEL_RE.search(cleaned):
        cleaned = PRESENTATION_LABEL_RE.sub("", cleaned).strip()

    for separator in (" - ", " – ", " — "):
        if separator not in cleaned:
            continue
        prefix, remainder = cleaned.split(separator, 1)
        if _comparison_key(prefix) == _comparison_key(cleaned_artist):
            cleaned = remainder.strip()
            break

    return _collapse_whitespace(cleaned)
```

Keep the existing `parse_lrc()` implementation, then add these helpers immediately after it:

```python
def _candidate_result(
    item: Dict,
    requested_title: str,
    requested_artist: str,
    audio_duration: float,
    strategy: str,
) -> Optional[Dict]:
    track_name = str(item.get("trackName") or "")
    artist_name = str(item.get("artistName") or "")
    synced = item.get("syncedLyrics")

    if not synced:
        return None

    candidate_title = normalize_title(track_name, artist_name)
    candidate_artist = normalize_artist(artist_name)
    if _comparison_key(candidate_title) != _comparison_key(requested_title):
        return None
    if _comparison_key(candidate_artist) != _comparison_key(requested_artist):
        return None

    try:
        candidate_duration = float(item.get("duration"))
    except (TypeError, ValueError):
        return None

    duration_delta = abs(candidate_duration - audio_duration)
    if duration_delta > DURATION_TOLERANCE_SECONDS:
        return None

    lyrics = parse_lrc(str(synced))
    if not lyrics:
        return None

    return {
        "lyrics": lyrics,
        "lyricsSource": "lrclib",
        "lyricsStatus": "synced",
        "lyricsMatch": {
            "id": item.get("id"),
            "strategy": strategy,
            "trackName": track_name,
            "artistName": artist_name,
            "duration": candidate_duration,
            "durationDelta": round(duration_delta, 3),
        },
    }


def _select_search_result(
    items: List[Dict],
    requested_title: str,
    requested_artist: str,
    audio_duration: float,
) -> Optional[Dict]:
    matches = []
    for index, item in enumerate(items):
        result = _candidate_result(
            item,
            requested_title=requested_title,
            requested_artist=requested_artist,
            audio_duration=audio_duration,
            strategy="search",
        )
        if result:
            matches.append((result["lyricsMatch"]["durationDelta"], index, result))

    if not matches:
        return None

    return min(matches, key=lambda match: (match[0], match[1]))[2]
```

- [ ] **Step 4: Run the focused tests**

Run:

```bash
PYTHONPATH=backend:tests/backend python3 -m unittest test_lyrics_resolution.LyricsMetadataTests -v
```

Expected: all four `LyricsMetadataTests` pass.

- [ ] **Step 5: Run all current backend tests**

Run:

```bash
PYTHONPATH=backend python3 -m unittest discover -s tests/backend -p 'test_*.py' -v
```

Expected: the original 14 tests plus the four new tests pass.

- [ ] **Step 6: Commit the metadata validation unit**

Run:

```bash
git add backend/lyrics_sync.py tests/backend/test_lyrics_resolution.py
git commit -m "feat(lyrics): validate LRCLIB metadata"
```

Expected: a commit containing only candidate normalization/validation and its tests.

---

### Task 2: Add Retry, Exact Lookup, and Structured Search

**Files:**
- Modify: `backend/lyrics_sync.py`
- Modify: `tests/backend/test_lyrics_resolution.py`

- [ ] **Step 1: Add failing provider-flow tests**

Extend the test imports:

```python
from unittest.mock import AsyncMock, call, patch

from lyrics_sync import (
    LyricsNotFound,
    LyricsProviderUnavailable,
    _LRCLibNotFound,
    _TemporaryLRCLibError,
    _retry_lrclib,
    _select_search_result,
    normalize_artist,
    normalize_title,
    parse_lrc,
    resolve_lrclib_lyrics,
    resolve_lyrics,
)
```

Add this async test class before `LyricsResolutionTests`:

```python
class LRCLibProviderTests(unittest.IsolatedAsyncioTestCase):
    async def test_temporary_failure_retries_and_recovers(self):
        operation = AsyncMock(side_effect=[
            _TemporaryLRCLibError("timeout"),
            _TemporaryLRCLibError("HTTP 503"),
            {"ok": True},
        ])

        with patch("lyrics_sync.asyncio.sleep", new=AsyncMock()) as sleep:
            result = await _retry_lrclib(operation)

        self.assertEqual(result, {"ok": True})
        self.assertEqual(operation.await_count, 3)
        self.assertEqual(sleep.await_args_list, [call(0.5), call(1.0)])

    async def test_temporary_failure_stops_after_three_attempts(self):
        operation = AsyncMock(side_effect=_TemporaryLRCLibError("timeout"))

        with patch("lyrics_sync.asyncio.sleep", new=AsyncMock()):
            with self.assertRaisesRegex(LyricsProviderUnavailable, "timeout"):
                await _retry_lrclib(operation)

        self.assertEqual(operation.await_count, 3)

    async def test_exact_match_returns_before_search(self):
        exact = {
            "id": 17589301,
            "trackName": "everything u are",
            "artistName": "Hindia",
            "duration": 236.0,
            "syncedLyrics": "[00:12.01]Harapanku untukmu",
        }

        with patch("lyrics_sync._request_lrclib", new=AsyncMock(return_value=exact)) as request:
            result = await resolve_lrclib_lyrics(
                "Hindia - everything u are",
                "Hindia",
                237.0,
            )

        self.assertEqual(result["lyricsSource"], "lrclib")
        self.assertEqual(result["lyricsMatch"]["strategy"], "exact")
        request.assert_awaited_once_with(
            "get",
            {
                "track_name": "everything u are",
                "artist_name": "Hindia",
                "duration": 237.0,
            },
        )

    async def test_exact_404_falls_through_to_structured_search(self):
        search_results = [{
            "id": 31515195,
            "trackName": "everything u are",
            "artistName": "Hindia",
            "duration": 236.0,
            "syncedLyrics": "[00:12.01]Harapanku untukmu",
        }]
        request = AsyncMock(side_effect=[_LRCLibNotFound(), search_results])

        with patch("lyrics_sync._request_lrclib", new=request):
            result = await resolve_lrclib_lyrics(
                "Hindia - everything u are",
                "Hindia",
                237.0,
            )

        self.assertEqual(result["lyricsMatch"]["strategy"], "search")
        self.assertEqual(request.await_count, 2)
        self.assertEqual(request.await_args_list[1], call(
            "search",
            {
                "track_name": "everything u are",
                "artist_name": "Hindia",
            },
        ))

    async def test_exact_provider_failure_is_retained_if_search_has_no_match(self):
        request = AsyncMock(side_effect=[
            LyricsProviderUnavailable("LRCLIB returned HTTP 503"),
            [],
        ])

        with patch("lyrics_sync._request_lrclib", new=request):
            with self.assertRaisesRegex(
                LyricsProviderUnavailable,
                "LRCLIB returned HTTP 503",
            ):
                await resolve_lrclib_lyrics("Song", "Artist", 180.0)

    async def test_exact_provider_failure_can_recover_through_search(self):
        search_results = [{
            "id": 10,
            "trackName": "Song",
            "artistName": "Artist",
            "duration": 180.0,
            "syncedLyrics": "[00:01.00]Recovered",
        }]
        request = AsyncMock(side_effect=[
            LyricsProviderUnavailable("LRCLIB returned HTTP 503"),
            search_results,
        ])

        with patch("lyrics_sync._request_lrclib", new=request):
            result = await resolve_lrclib_lyrics("Song", "Artist", 180.0)

        self.assertEqual(result["lyricsMatch"]["strategy"], "search")

    async def test_successful_search_without_valid_candidate_is_not_found(self):
        request = AsyncMock(side_effect=[_LRCLibNotFound(), []])

        with patch("lyrics_sync._request_lrclib", new=request):
            with self.assertRaisesRegex(LyricsNotFound, "No valid LRCLIB match"):
                await resolve_lrclib_lyrics("Song", "Artist", 180.0)

    async def test_unavailable_search_is_reported_as_provider_failure(self):
        request = AsyncMock(side_effect=[
            _LRCLibNotFound(),
            LyricsProviderUnavailable("LRCLIB timed out after 3 attempts"),
        ])

        with patch("lyrics_sync._request_lrclib", new=request):
            with self.assertRaisesRegex(
                LyricsProviderUnavailable,
                "timed out after 3 attempts",
            ):
                await resolve_lrclib_lyrics("Song", "Artist", 180.0)
```

- [ ] **Step 2: Run the new provider tests and verify failure**

Run:

```bash
PYTHONPATH=backend:tests/backend python3 -m unittest test_lyrics_resolution.LRCLibProviderTests -v
```

Expected: import failure for `_retry_lrclib` or `resolve_lrclib_lyrics`.

- [ ] **Step 3: Add bounded retry and the actual HTTP request helper**

Add these functions after `_select_search_result()` in `backend/lyrics_sync.py`:

```python
async def _retry_lrclib(operation: Callable[[], Awaitable[Dict | List]]) -> Dict | List:
    last_error = None
    for attempt in range(len(RETRY_DELAYS_SECONDS) + 1):
        try:
            return await operation()
        except _TemporaryLRCLibError as error:
            last_error = error
            if attempt >= len(RETRY_DELAYS_SECONDS):
                break
            await asyncio.sleep(RETRY_DELAYS_SECONDS[attempt])

    raise LyricsProviderUnavailable(
        str(last_error) or "LRCLIB is temporarily unavailable"
    )


async def _request_lrclib(endpoint: str, params: Dict) -> Dict | List:
    import httpx

    url = f"{LRCLIB_BASE_URL}/{endpoint}"
    async with httpx.AsyncClient() as client:
        async def request_once():
            try:
                response = await client.get(url, params=params, timeout=30)
            except httpx.TransportError as error:
                raise _TemporaryLRCLibError(
                    f"LRCLIB request failed: {error}"
                ) from error

            if response.status_code == 404:
                raise _LRCLibNotFound()
            if response.status_code == 429 or response.status_code >= 500:
                raise _TemporaryLRCLibError(
                    f"LRCLIB returned HTTP {response.status_code}"
                )

            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as error:
                raise LyricsProviderUnavailable(
                    f"LRCLIB returned HTTP {response.status_code}"
                ) from error

            try:
                return response.json()
            except ValueError as error:
                raise LyricsProviderUnavailable(
                    "LRCLIB returned an invalid response"
                ) from error

        return await _retry_lrclib(request_once)
```

- [ ] **Step 4: Add exact-then-search orchestration**

Add this public function after `_request_lrclib()`:

```python
async def resolve_lrclib_lyrics(
    title: str,
    artist: str,
    audio_duration: float,
) -> Dict:
    requested_artist = normalize_artist(artist)
    requested_title = normalize_title(title, requested_artist)
    if not requested_title or not requested_artist:
        raise LyricsNotFound("No valid LRCLIB match")

    exact = None
    exact_warning = None
    try:
        exact = await _request_lrclib(
            "get",
            {
                "track_name": requested_title,
                "artist_name": requested_artist,
                "duration": audio_duration,
            },
        )
    except _LRCLibNotFound:
        pass
    except LyricsProviderUnavailable as error:
        # Structured search can still recover from an exact endpoint failure.
        exact_warning = str(error)

    if isinstance(exact, dict):
        result = _candidate_result(
            exact,
            requested_title=requested_title,
            requested_artist=requested_artist,
            audio_duration=audio_duration,
            strategy="exact",
        )
        if result:
            return result

    try:
        search_results = await _request_lrclib(
            "search",
            {
                "track_name": requested_title,
                "artist_name": requested_artist,
            },
        )
    except _LRCLibNotFound:
        search_results = []

    if not isinstance(search_results, list):
        raise LyricsProviderUnavailable("LRCLIB search returned an invalid response")

    result = _select_search_result(
        search_results,
        requested_title=requested_title,
        requested_artist=requested_artist,
        audio_duration=audio_duration,
    )
    if result:
        return result

    if exact_warning:
        raise LyricsProviderUnavailable(exact_warning)
    raise LyricsNotFound("No valid LRCLIB match")
```

Keep the old `fetch_lyrics()` function temporarily so the existing `resolve_lyrics()` contract and baseline fallback tests remain green in this commit. Task 3 replaces `resolve_lyrics()` and removes `fetch_lyrics()` once all callers and tests move to the exact/search flow.

- [ ] **Step 5: Run the provider-flow tests**

Run:

```bash
PYTHONPATH=backend:tests/backend python3 -m unittest test_lyrics_resolution.LRCLibProviderTests -v
```

Expected: all eight provider tests pass. The tests mock `_request_lrclib`, so host Python does not need httpx installed.

- [ ] **Step 6: Run all backend tests**

Run:

```bash
PYTHONPATH=backend python3 -m unittest discover -s tests/backend -p 'test_*.py' -v
```

Expected: all tests pass. The existing fallback tests still exercise the temporary legacy `fetch_lyrics()` path until Task 3 migrates the coordinator.

- [ ] **Step 7: Commit the provider lookup unit**

Run:

```bash
git add backend/lyrics_sync.py tests/backend/test_lyrics_resolution.py
git commit -m "feat(lyrics): add exact LRCLIB lookup"
```

Expected: a commit containing retry behavior and exact/search LRCLIB orchestration.

---

### Task 3: Integrate Whisper Fallback and Preserve Diagnostics

**Files:**
- Modify: `backend/lyrics_sync.py:45-97`
- Modify: `tests/backend/test_lyrics_resolution.py`

- [ ] **Step 1: Replace the old fallback tests with the new contract**

Replace the existing `LyricsResolutionTests` class with:

```python
class LyricsResolutionTests(unittest.IsolatedAsyncioTestCase):
    async def test_lrclib_lyrics_win_without_whisper(self):
        synced = {
            "lyrics": [{"start": 1.0, "text": "hello"}],
            "lyricsSource": "lrclib",
            "lyricsStatus": "synced",
            "lyricsMatch": {
                "id": 1,
                "strategy": "exact",
                "trackName": "Song",
                "artistName": "Artist",
                "duration": 180.0,
                "durationDelta": 0.0,
            },
        }

        with patch(
            "lyrics_sync.resolve_lrclib_lyrics",
            new=AsyncMock(return_value=synced),
        ):
            with patch("lyrics_sync.transcribe_with_whisper") as whisper:
                result = await resolve_lyrics(
                    "Song",
                    "Artist",
                    180.0,
                    Path("missing.wav"),
                    "small",
                )

        self.assertEqual(result, synced)
        whisper.assert_not_called()

    async def test_whisper_used_when_lrclib_has_no_valid_match(self):
        generated = [{"start": 2.0, "text": "generated"}]
        with tempfile.NamedTemporaryFile(suffix=".wav") as audio:
            with patch(
                "lyrics_sync.resolve_lrclib_lyrics",
                new=AsyncMock(side_effect=LyricsNotFound("No valid LRCLIB match")),
            ):
                with patch(
                    "lyrics_sync.transcribe_with_whisper",
                    return_value=generated,
                ):
                    result = await resolve_lyrics(
                        "Song",
                        "Artist",
                        180.0,
                        Path(audio.name),
                        "small",
                    )

        self.assertEqual(result["lyrics"], generated)
        self.assertEqual(result["lyricsSource"], "whisper")
        self.assertEqual(result["lyricsStatus"], "generated")
        self.assertEqual(result["lyricsWarning"], "No valid LRCLIB match")

    async def test_provider_warning_is_retained_when_whisper_succeeds(self):
        generated = [{"start": 2.0, "text": "generated"}]
        with tempfile.NamedTemporaryFile(suffix=".wav") as audio:
            with patch(
                "lyrics_sync.resolve_lrclib_lyrics",
                new=AsyncMock(side_effect=LyricsProviderUnavailable(
                    "LRCLIB returned HTTP 503"
                )),
            ):
                with patch(
                    "lyrics_sync.transcribe_with_whisper",
                    return_value=generated,
                ):
                    result = await resolve_lyrics(
                        "Song",
                        "Artist",
                        180.0,
                        Path(audio.name),
                        "small",
                    )

        self.assertEqual(result["lyricsSource"], "whisper")
        self.assertEqual(result["lyricsWarning"], "LRCLIB returned HTTP 503")

    async def test_unavailable_when_provider_fails_and_vocals_missing(self):
        with patch(
            "lyrics_sync.resolve_lrclib_lyrics",
            new=AsyncMock(side_effect=LyricsProviderUnavailable("LRCLIB down")),
        ):
            result = await resolve_lyrics(
                "Song",
                "Artist",
                180.0,
                Path("missing.wav"),
                "small",
            )

        self.assertEqual(result["lyrics"], [])
        self.assertEqual(result["lyricsSource"], "none")
        self.assertEqual(result["lyricsStatus"], "unavailable")
        self.assertEqual(result["lyricsWarning"], "LRCLIB down")

    async def test_unavailable_combines_lrclib_and_whisper_failures(self):
        with tempfile.NamedTemporaryFile(suffix=".wav") as audio:
            with patch(
                "lyrics_sync.resolve_lrclib_lyrics",
                new=AsyncMock(side_effect=LyricsNotFound("No valid LRCLIB match")),
            ):
                with patch(
                    "lyrics_sync.transcribe_with_whisper",
                    side_effect=RuntimeError("Whisper failed"),
                ):
                    result = await resolve_lyrics(
                        "Song",
                        "Artist",
                        180.0,
                        Path(audio.name),
                        "small",
                    )

        self.assertEqual(result["lyrics"], [])
        self.assertEqual(result["lyricsSource"], "none")
        self.assertEqual(result["lyricsStatus"], "unavailable")
        self.assertEqual(
            result["lyricsWarning"],
            "No valid LRCLIB match; Whisper failed: Whisper failed",
        )
```

- [ ] **Step 2: Run fallback tests and verify failure**

Run:

```bash
PYTHONPATH=backend:tests/backend python3 -m unittest test_lyrics_resolution.LyricsResolutionTests -v
```

Expected: failures because `resolve_lyrics()` still has the old signature and calls the deleted `fetch_lyrics()`.

- [ ] **Step 3: Replace `resolve_lyrics()` with the new fallback coordinator**

Keep `transcribe_with_whisper()` unchanged. Remove the now-unused legacy `fetch_lyrics()` function, then replace the current `resolve_lyrics()` function with:

```python
async def resolve_lyrics(
    title: str,
    artist: str,
    audio_duration: float,
    vocals_path: Path,
    model_size: str = "base",
) -> Dict:
    """Resolve LRCLIB first, then Whisper, then an unavailable state."""
    warning = None

    try:
        return await resolve_lrclib_lyrics(title, artist, audio_duration)
    except (LyricsNotFound, LyricsProviderUnavailable) as error:
        warning = str(error)

    if vocals_path.exists():
        try:
            generated_lyrics = transcribe_with_whisper(
                vocals_path,
                model_size=model_size,
            )
        except Exception as error:
            whisper_warning = f"Whisper failed: {error}"
            warning = (
                f"{warning}; {whisper_warning}"
                if warning
                else whisper_warning
            )
            generated_lyrics = []

        if generated_lyrics:
            result = {
                "lyrics": generated_lyrics,
                "lyricsSource": "whisper",
                "lyricsStatus": "generated",
            }
            if warning:
                result["lyricsWarning"] = warning
            return result

    result = {
        "lyrics": [],
        "lyricsSource": "none",
        "lyricsStatus": "unavailable",
    }
    if warning:
        result["lyricsWarning"] = warning
    return result
```

- [ ] **Step 4: Run all lyric tests**

Run:

```bash
PYTHONPATH=backend:tests/backend python3 -m unittest test_lyrics_resolution -v
```

Expected: normalization, provider-flow, and fallback tests all pass.

- [ ] **Step 5: Run the entire host-safe backend suite**

Run:

```bash
PYTHONPATH=backend python3 -m unittest discover -s tests/backend -p 'test_*.py' -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit the fallback integration**

Run:

```bash
git add backend/lyrics_sync.py tests/backend/test_lyrics_resolution.py
git commit -m "fix(lyrics): preserve fallback diagnostics"
```

Expected: a commit containing the new duration-aware `resolve_lyrics()` contract and updated fallback tests.

---

### Task 4: Pass Full-Audio Duration and Persist Lyric Metadata

**Files:**
- Modify: `backend/main.py:1-18,322-384`
- Create: `tests/backend/test_lyrics_refresh.py`

- [ ] **Step 1: Add failing tests for duration and lyric metadata replacement**

Create `tests/backend/test_lyrics_refresh.py`:

```python
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from main import _audio_duration, _merge_lyrics_metadata, _write_json_atomic


class TrackLyricsMetadataTests(unittest.TestCase):
    def test_audio_duration_uses_soundfile_metadata(self):
        with patch("main.sf.info", return_value=Mock(duration=237.25)) as info:
            duration = _audio_duration(Path("/tmp/song.wav"))

        self.assertEqual(duration, 237.25)
        info.assert_called_once_with("/tmp/song.wav")

    def test_merge_replaces_only_lyric_fields(self):
        existing = {
            "videoId": "abc",
            "title": "Song",
            "artist": "Artist",
            "status": "ready",
            "mode": "karaoke",
            "saved": True,
            "full_audio_path": "/app/data/downloads/abc.wav",
            "lyrics": [{"start": 0.0, "text": "old"}],
            "lyricsSource": "whisper",
            "lyricsStatus": "generated",
            "lyricsWarning": "old warning",
        }
        result = {
            "lyrics": [{"start": 1.0, "text": "new"}],
            "lyricsSource": "lrclib",
            "lyricsStatus": "synced",
            "lyricsMatch": {"id": 1, "strategy": "exact"},
        }

        merged = _merge_lyrics_metadata(existing, result)

        self.assertEqual(merged["lyrics"], result["lyrics"])
        self.assertEqual(merged["lyricsSource"], "lrclib")
        self.assertEqual(merged["lyricsMatch"], result["lyricsMatch"])
        self.assertNotIn("lyricsWarning", merged)
        self.assertEqual(merged["title"], "Song")
        self.assertEqual(merged["full_audio_path"], "/app/data/downloads/abc.wav")

    def test_atomic_write_replaces_complete_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "meta.json"
            path.write_text('{"lyricsSource": "whisper"}', encoding="utf-8")

            _write_json_atomic(path, {
                "lyricsSource": "lrclib",
                "lyrics": [{"start": 1.0, "text": "hello"}],
            })

            saved = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(saved["lyricsSource"], "lrclib")
            self.assertFalse(path.with_suffix(".json.tmp").exists())
```

- [ ] **Step 2: Run the tests in the backend container and verify failure**

Run:

```bash
podman-compose build backend
podman-compose run --rm \
  -v "$PWD/tests:/app/tests:ro" \
  backend python -m unittest discover \
    -s /app/tests/backend -p 'test_lyrics_refresh.py' -v
```

Expected: import failure for `_audio_duration`, `_merge_lyrics_metadata`, or `_write_json_atomic`.

- [ ] **Step 3: Add metadata helpers and imports to `backend/main.py`**

Add `soundfile` and the lyric exceptions/functions to the imports:

```python
import soundfile as sf

from errors import error_payload
from lyrics_sync import (
    LyricsNotFound,
    LyricsProviderUnavailable,
    resolve_lrclib_lyrics,
    resolve_lyrics,
)
```

Replace the old `from lyrics_sync import resolve_lyrics` import. Add these definitions after `app = FastAPI(...)`:

```python
LYRIC_METADATA_KEYS = (
    "lyrics",
    "lyricsSource",
    "lyricsStatus",
    "lyricsMatch",
    "lyricsWarning",
)
lyrics_refresh_locks = {}


def _audio_duration(audio_path: Path) -> float:
    return float(sf.info(str(audio_path)).duration)


def _merge_lyrics_metadata(meta: dict, lyrics_result: dict) -> dict:
    merged = dict(meta)
    for key in LYRIC_METADATA_KEYS:
        merged.pop(key, None)
    for key in LYRIC_METADATA_KEYS:
        if key in lyrics_result:
            merged[key] = lyrics_result[key]
    return merged


def _write_json_atomic(path: Path, payload: dict):
    temp_path = path.with_suffix(f"{path.suffix}.tmp")
    try:
        with open(temp_path, "w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2)
        temp_path.replace(path)
    finally:
        if temp_path.exists():
            temp_path.unlink()
```

- [ ] **Step 4: Pass duration into normal processing and persist additive fields**

In `_process_track()`, replace the current lyric-resolution block:

```python
        vocals_path = track_dir / "vocals.wav"
        audio_duration = _audio_duration(audio_path)
        lyrics_result = asyncio.run(resolve_lyrics(
            title,
            artist,
            audio_duration,
            vocals_path,
            model_size=WHISPER_MODEL,
        ))
        if lyrics_result.get("lyricsWarning"):
            jobs[job_id]["lyricsWarning"] = lyrics_result["lyricsWarning"]
            save_jobs()
```

Build the non-lyric metadata first, then merge the lyric result:

```python
        meta = _merge_lyrics_metadata({
            "videoId": video_id,
            "title": title,
            "artist": artist,
            "status": "ready",
            "mode": mode,
            "saved": save,
            "full_audio_path": str(DOWNLOADS_DIR / f"{video_id}.wav"),
        }, lyrics_result)
```

Keep the existing initial `meta.json` write for now; atomic replacement is required only for refresh.

- [ ] **Step 5: Run the container metadata tests**

Run:

```bash
podman-compose build backend
podman-compose run --rm \
  -v "$PWD/tests:/app/tests:ro" \
  backend python -m unittest discover \
    -s /app/tests/backend -p 'test_lyrics_refresh.py' -v
```

Expected: all three tests pass.

- [ ] **Step 6: Compile and run all backend tests in the container**

Run:

```bash
podman-compose run --rm \
  -v "$PWD/tests:/app/tests:ro" \
  backend python -m unittest discover -s /app/tests/backend -p 'test_*.py' -v

podman-compose run --rm backend python -m py_compile \
  errors.py youtube.py lyrics_sync.py main.py stems.py config.py
```

Expected: all backend tests pass and `py_compile` exits with status 0.

- [ ] **Step 7: Commit duration and persistence wiring**

Run:

```bash
git add backend/main.py tests/backend/test_lyrics_refresh.py
git commit -m "feat(api): persist lyric match metadata"
```

Expected: a commit containing full-audio duration, lyric metadata merge, and atomic JSON helpers.

---

### Task 5: Add the Lyrics-Only Refresh Endpoint

**Files:**
- Modify: `backend/main.py:20-255`
- Modify: `tests/backend/test_lyrics_refresh.py`

- [ ] **Step 1: Add failing endpoint tests**

Extend `tests/backend/test_lyrics_refresh.py` imports:

```python
import asyncio
from unittest.mock import AsyncMock, Mock, patch

from fastapi import HTTPException
from lyrics_sync import LyricsNotFound, LyricsProviderUnavailable
from main import (
    _audio_duration,
    _merge_lyrics_metadata,
    _write_json_atomic,
    lyrics_refresh_locks,
    refresh_track_lyrics,
)
```

Add this class after `TrackLyricsMetadataTests`:

```python
class LyricsRefreshEndpointTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        lyrics_refresh_locks.clear()

    def _track_files(self, root: Path):
        downloads = root / "downloads"
        processed = root / "processed"
        track_dir = processed / "abc"
        downloads.mkdir()
        track_dir.mkdir(parents=True)
        audio_path = downloads / "abc.wav"
        audio_path.touch()
        meta = {
            "videoId": "abc",
            "title": "Hindia - everything u are",
            "artist": "Hindia",
            "status": "ready",
            "mode": "karaoke",
            "saved": True,
            "full_audio_path": str(audio_path),
            "lyrics": [{"start": 0.0, "text": "old"}],
            "lyricsSource": "whisper",
            "lyricsStatus": "generated",
            "lyricsWarning": "old warning",
        }
        meta_path = track_dir / "meta.json"
        meta_path.write_text(json.dumps(meta), encoding="utf-8")
        return downloads, processed, meta_path, meta

    async def test_refresh_updates_only_lyric_fields_without_whisper(self):
        lrclib_result = {
            "lyrics": [{"start": 12.01, "text": "Harapanku untukmu"}],
            "lyricsSource": "lrclib",
            "lyricsStatus": "synced",
            "lyricsMatch": {
                "id": 17589301,
                "strategy": "exact",
                "trackName": "everything u are",
                "artistName": "Hindia",
                "duration": 236.0,
                "durationDelta": 1.0,
            },
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            downloads, processed, meta_path, old_meta = self._track_files(Path(tmpdir))
            with patch("main.DOWNLOADS_DIR", downloads), \
                 patch("main.PROCESSED_DIR", processed), \
                 patch("main._audio_duration", return_value=237.0), \
                 patch(
                     "main.resolve_lrclib_lyrics",
                     new=AsyncMock(return_value=lrclib_result),
                 ) as resolve, \
                 patch("lyrics_sync.transcribe_with_whisper") as whisper:
                response = await refresh_track_lyrics("abc")

            saved = json.loads(meta_path.read_text(encoding="utf-8"))

        self.assertTrue(response["success"])
        self.assertEqual(saved["lyricsSource"], "lrclib")
        self.assertEqual(saved["lyricsMatch"]["id"], 17589301)
        self.assertNotIn("lyricsWarning", saved)
        self.assertEqual(saved["title"], old_meta["title"])
        self.assertEqual(saved["mode"], old_meta["mode"])
        resolve.assert_awaited_once_with(
            "Hindia - everything u are",
            "Hindia",
            237.0,
        )
        whisper.assert_not_called()

    async def test_not_found_preserves_existing_metadata(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            downloads, processed, meta_path, old_meta = self._track_files(Path(tmpdir))
            with patch("main.DOWNLOADS_DIR", downloads), \
                 patch("main.PROCESSED_DIR", processed), \
                 patch("main._audio_duration", return_value=237.0), \
                 patch(
                     "main.resolve_lrclib_lyrics",
                     new=AsyncMock(side_effect=LyricsNotFound(
                         "No valid LRCLIB match"
                     )),
                 ):
                with self.assertRaises(HTTPException) as raised:
                    await refresh_track_lyrics("abc")

            saved = json.loads(meta_path.read_text(encoding="utf-8"))

        self.assertEqual(raised.exception.status_code, 404)
        self.assertEqual(raised.exception.detail["code"], "lyrics_not_found")
        self.assertEqual(saved, old_meta)

    async def test_provider_failure_returns_503_and_preserves_metadata(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            downloads, processed, meta_path, old_meta = self._track_files(Path(tmpdir))
            with patch("main.DOWNLOADS_DIR", downloads), \
                 patch("main.PROCESSED_DIR", processed), \
                 patch("main._audio_duration", return_value=237.0), \
                 patch(
                     "main.resolve_lrclib_lyrics",
                     new=AsyncMock(side_effect=LyricsProviderUnavailable(
                         "LRCLIB returned HTTP 503"
                     )),
                 ):
                with self.assertRaises(HTTPException) as raised:
                    await refresh_track_lyrics("abc")

            saved = json.loads(meta_path.read_text(encoding="utf-8"))

        self.assertEqual(raised.exception.status_code, 503)
        self.assertEqual(
            raised.exception.detail["code"],
            "lyrics_provider_unavailable",
        )
        self.assertEqual(saved, old_meta)

    async def test_same_video_uses_same_refresh_lock(self):
        from main import _lyrics_refresh_lock

        first = _lyrics_refresh_lock("abc")
        second = _lyrics_refresh_lock("abc")
        other = _lyrics_refresh_lock("def")

        self.assertIs(first, second)
        self.assertIsNot(first, other)

    async def test_refresh_uses_meta_full_audio_path_when_available(self):
        lrclib_result = {
            "lyrics": [{"start": 1.0, "text": "synced"}],
            "lyricsSource": "lrclib",
            "lyricsStatus": "synced",
            "lyricsMatch": {"id": 1, "strategy": "exact"},
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            downloads, processed, meta_path, _ = self._track_files(Path(tmpdir))
            configured_path = Path(tmpdir) / "configured.wav"
            configured_path.touch()
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            meta["full_audio_path"] = str(configured_path)
            meta_path.write_text(json.dumps(meta), encoding="utf-8")

            with patch("main.DOWNLOADS_DIR", downloads), \
                 patch("main.PROCESSED_DIR", processed), \
                 patch("main._audio_duration", return_value=237.0) as duration, \
                 patch(
                     "main.resolve_lrclib_lyrics",
                     new=AsyncMock(return_value=lrclib_result),
                 ):
                await refresh_track_lyrics("abc")

        duration.assert_called_once_with(configured_path)
```

- [ ] **Step 2: Run endpoint tests and verify failure**

Run:

```bash
podman-compose build backend
podman-compose run --rm \
  -v "$PWD/tests:/app/tests:ro" \
  backend python -m unittest discover \
    -s /app/tests/backend -p 'test_lyrics_refresh.py' -v
```

Expected: import failure for `refresh_track_lyrics` or `_lyrics_refresh_lock`.

- [ ] **Step 3: Add the lock helper**

Add this helper beside the metadata helpers in `backend/main.py`:

```python
def _lyrics_refresh_lock(video_id: str) -> asyncio.Lock:
    lock = lyrics_refresh_locks.get(video_id)
    if lock is None:
        lock = asyncio.Lock()
        lyrics_refresh_locks[video_id] = lock
    return lock
```

- [ ] **Step 4: Add the refresh endpoint**

Add this endpoint immediately after the existing `GET /track/{video_id}` endpoint:

```python
@app.post("/track/{video_id}/lyrics/refresh")
async def refresh_track_lyrics(video_id: str):
    async with _lyrics_refresh_lock(video_id):
        meta_path = PROCESSED_DIR / video_id / "meta.json"

        if not meta_path.exists():
            raise HTTPException(
                status_code=404,
                detail=error_payload(
                    "track_not_found",
                    "Track metadata was not found.",
                ),
            )

        with open(meta_path, "r", encoding="utf-8") as file:
            meta = json.load(file)

        configured_audio_path = meta.get("full_audio_path")
        audio_path = (
            Path(configured_audio_path)
            if configured_audio_path
            else DOWNLOADS_DIR / f"{video_id}.wav"
        )
        if not audio_path.exists():
            raise HTTPException(
                status_code=404,
                detail=error_payload(
                    "full_audio_not_found",
                    "Full audio was not found for this track.",
                ),
            )

        if meta.get("status") != "ready":
            raise HTTPException(
                status_code=409,
                detail=error_payload(
                    "track_not_ready",
                    "Track is not ready for lyric refresh.",
                ),
            )

        try:
            lyrics_result = await resolve_lrclib_lyrics(
                meta.get("title", ""),
                meta.get("artist", ""),
                _audio_duration(audio_path),
            )
        except LyricsNotFound as error:
            raise HTTPException(
                status_code=404,
                detail=error_payload(
                    "lyrics_not_found",
                    "No matching synced lyrics were found on LRCLIB.",
                    str(error),
                ),
            ) from error
        except LyricsProviderUnavailable as error:
            raise HTTPException(
                status_code=503,
                detail=error_payload(
                    "lyrics_provider_unavailable",
                    "LRCLIB is temporarily unavailable. Try again later.",
                    str(error),
                ),
            ) from error

        updated_meta = _merge_lyrics_metadata(meta, lyrics_result)
        _write_json_atomic(meta_path, updated_meta)
        return {"success": True, "track": updated_meta}
```

This endpoint calls only `resolve_lrclib_lyrics()`. Do not call `resolve_lyrics()` or `transcribe_with_whisper()` from refresh.

- [ ] **Step 5: Run endpoint and metadata tests**

Run:

```bash
podman-compose build backend
podman-compose run --rm \
  -v "$PWD/tests:/app/tests:ro" \
  backend python -m unittest discover \
    -s /app/tests/backend -p 'test_lyrics_refresh.py' -v
```

Expected: all refresh tests pass.

- [ ] **Step 6: Run the full backend suite in the container**

Run:

```bash
podman-compose run --rm \
  -v "$PWD/tests:/app/tests:ro" \
  backend python -m unittest discover -s /app/tests/backend -p 'test_*.py' -v
```

Expected: all backend tests pass.

- [ ] **Step 7: Commit the refresh endpoint**

Run:

```bash
git add backend/main.py tests/backend/test_lyrics_refresh.py
git commit -m "feat(api): add lyric refresh endpoint"
```

Expected: a commit containing only the route, locking, endpoint errors, and endpoint tests.

---

### Task 6: Add the Frontend Refresh Client and Metadata Reload Method

**Files:**
- Modify: `frontend/src/lib/api.ts:34-48,162-175`
- Modify: `frontend/src/lib/audio-context.tsx:5-36,218-365`

- [ ] **Step 1: Make nested FastAPI errors readable**

Replace `readJsonError()` in `frontend/src/lib/api.ts` with:

```typescript
async function readJsonError(res: Response, fallback: string) {
  try {
    const data = await res.json()
    const nestedDetail = data?.detail
    const payload = data?.error
      ?? (nestedDetail && typeof nestedDetail === 'object' ? nestedDetail : null)

    if (payload?.message) {
      return new ApiClientError(payload.message, payload.code, payload.detail)
    }
    if (typeof nestedDetail === 'string' && nestedDetail) {
      return new ApiClientError(nestedDetail)
    }
  } catch {
    return new ApiClientError(fallback)
  }
  return new ApiClientError(fallback)
}
```

- [ ] **Step 2: Add the typed refresh request**

Add this function after `getTrack()` in `frontend/src/lib/api.ts`:

```typescript
export async function refreshLyrics(videoId: string) {
  const res = await fetch(`${API_BASE}/track/${videoId}/lyrics/refresh`, {
    method: 'POST',
  })
  if (!res.ok) {
    throw await readJsonError(res, 'Lyrics could not be refreshed.')
  }
  return res.json()
}
```

- [ ] **Step 3: Extend track diagnostics and the audio context contract**

In `frontend/src/lib/audio-context.tsx`, extend `Track`:

```typescript
type Track = {
  videoId: string
  title: string
  artist: string
  status: string
  lyrics: LyricLine[]
  lyricsSource?: 'lrclib' | 'whisper' | 'none'
  lyricsStatus?: 'synced' | 'generated' | 'unavailable'
  lyricsWarning?: string
  lyricsMatch?: {
    id?: number
    strategy: 'exact' | 'search'
    trackName: string
    artistName: string
    duration: number
    durationDelta: number
  }
  mode?: string
  saved?: boolean
}
```

Add this member to `AudioContextValue`:

```typescript
reloadTrackMetadata: (videoId: string) => Promise<void>
```

- [ ] **Step 4: Add metadata-only reload behavior**

Add this callback immediately after `playTrack()`:

```typescript
  const reloadTrackMetadata = useCallback(async (vid: string) => {
    const data: Track = await getTrack(vid)
    if (videoIdRef.current === vid) {
      setTrack(data)
    }
  }, [])
```

Add it to the context value and dependency list:

```typescript
  const value = useMemo(() => ({
    videoId, track, playbackMode, isPlaying, currentTime, duration, loading, error,
    playTrack, reloadTrackMetadata, setMode, togglePlay, seek,
  }), [videoId, track, playbackMode, isPlaying, currentTime, duration, loading, error,
      playTrack, reloadTrackMetadata, setMode, togglePlay, seek])
```

This method must not stop sources, fetch audio, decode audio, seek, or alter playback mode.

- [ ] **Step 5: Run lint and build**

Run:

```bash
cd frontend
npm run lint
npm run build
```

Expected: ESLint reports no issues and the Next.js production build completes successfully.

- [ ] **Step 6: Commit the frontend client contract**

Run from the repository root:

```bash
git add frontend/src/lib/api.ts frontend/src/lib/audio-context.tsx
git commit -m "feat(ui): add lyric refresh client"
```

Expected: a commit containing only the API helper, error parsing, track types, and metadata reload method.

---

### Task 7: Add the Karaoke Lyrics Refresh Action and Restore User Work

**Files:**
- Modify and commit against the tracked baseline: `frontend/src/app/karaoke/[videoId]/page.tsx`
- Restore afterward as an unstaged user diff: `frontend/src/app/karaoke/[videoId]/page.tsx`

- [ ] **Step 1: Confirm the implementation baseline is clean**

Run:

```bash
git status --short -- frontend/src/app/karaoke/'[videoId]'/page.tsx
grep -n "upcomingQueue\|Now Playing\|const progress" \
  frontend/src/app/karaoke/'[videoId]'/page.tsx || true
git stash list | head -1
```

Expected:

- the karaoke page has no working-tree modification;
- the tracked page does not yet contain the user's `upcomingQueue`, Now Playing, or `progress` additions;
- the top stash is `user karaoke page before lyric refresh`.

- [ ] **Step 2: Add the refresh API import**

Change the API import to:

```typescript
import { getQueue, refreshLyrics, removeFromQueue } from '@/lib/api'
```

- [ ] **Step 3: Read the metadata reload method from audio context**

Add `reloadTrackMetadata` beside `playTrack` in the `useAudio()` destructuring:

```typescript
    playTrack,
    reloadTrackMetadata,
    setMode,
```

- [ ] **Step 4: Add page-local refresh state**

Add these states after the existing queue/seek state:

```typescript
  const [refreshingLyrics, setRefreshingLyrics] = useState(false)
  const [lyricsRefreshMessage, setLyricsRefreshMessage] = useState<string | null>(null)
  const [lyricsRefreshError, setLyricsRefreshError] = useState<string | null>(null)
```

Add this derived value after `nextQueueItem`:

```typescript
  const canRefreshLyrics = track?.lyricsSource === 'whisper'
    || track?.lyricsSource === 'none'
```

- [ ] **Step 5: Add the refresh handler**

Add this handler after `handleRetry()`:

```typescript
  const handleRefreshLyrics = async () => {
    setRefreshingLyrics(true)
    setLyricsRefreshMessage(null)
    setLyricsRefreshError(null)

    try {
      await refreshLyrics(videoId)
      await reloadTrackMetadata(videoId)
      setLyricsRefreshMessage('Synced lyrics loaded from LRCLIB.')
    } catch (err) {
      setLyricsRefreshError(
        err instanceof Error ? err.message : 'Lyrics could not be refreshed.'
      )
    } finally {
      setRefreshingLyrics(false)
    }
  }
```

- [ ] **Step 6: Add the action to the lyrics header**

Replace only the current lyrics-header block at the top of the lyrics card:

```tsx
          <div className="shrink-0 flex items-center justify-between gap-3 px-5 pt-3 pb-2">
            <h2 className="text-sm font-semibold text-zinc-500 uppercase tracking-wider">
              Lyrics
            </h2>
            <div className="flex items-center gap-3">
              <p className="text-xs text-zinc-600">{track?.lyrics.length ?? 0} lines</p>
              {canRefreshLyrics && (
                <button
                  type="button"
                  onClick={handleRefreshLyrics}
                  disabled={refreshingLyrics}
                  className="rounded-md border border-zinc-700 px-2.5 py-1 text-xs font-medium text-zinc-300 hover:border-fuchsia-500 hover:text-white disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {refreshingLyrics ? 'Refreshing...' : 'Refresh lyrics'}
                </button>
              )}
            </div>
          </div>
```

- [ ] **Step 7: Render an inline success/error notice**

Add this block immediately after the lyrics header and before the scrollable lyrics body:

```tsx
          {(lyricsRefreshError || lyricsRefreshMessage) && (
            <div
              className={[
                'mx-5 mb-2 rounded-lg border px-3 py-2 text-xs',
                lyricsRefreshError
                  ? 'border-red-500/40 bg-red-500/10 text-red-200'
                  : 'border-emerald-500/40 bg-emerald-500/10 text-emerald-200',
              ].join(' ')}
            >
              {lyricsRefreshError || lyricsRefreshMessage}
            </div>
          )}
```

Do not add unrelated queue, playback, or layout changes while the tracked baseline is active.

- [ ] **Step 8: Run frontend verification**

Run:

```bash
cd frontend
npm run lint
npm run build
```

Expected: ESLint reports no issues and the production build succeeds.

- [ ] **Step 9: Review and commit only the refresh UI**

Run from the repository root:

```bash
git diff -- frontend/src/app/karaoke/'[videoId]'/page.tsx
grep -n "Refresh lyrics\|refreshingLyrics\|handleRefreshLyrics" \
  frontend/src/app/karaoke/'[videoId]'/page.tsx
```

Expected: the diff contains only the refresh import, context method, three state values, eligibility expression, handler, header button, and inline notice.

Commit it:

```bash
git add frontend/src/app/karaoke/'[videoId]'/page.tsx
git commit -m "feat(ui): add lyric refresh action"
```

Expected: the refresh UI is committed without the user's Now Playing/upcoming-queue diff.

- [ ] **Step 10: Restore the user's stashed page changes**

Run:

```bash
git stash pop
```

Expected: the user's `upcomingQueue`, Now Playing card, and `progress` changes are restored on top of the committed refresh UI as an unstaged modification. If Git reports a conflict, preserve both the committed refresh blocks and the saved user blocks, use `/tmp/fun-karaoke-page-before-lyrics-refresh.patch` as the reference, then remove conflict markers.

- [ ] **Step 11: Verify the merged working page and leave user work unstaged**

Run:

```bash
grep -n "upcomingQueue\|Now Playing\|const progress\|Refresh lyrics" \
  frontend/src/app/karaoke/'[videoId]'/page.tsx
cd frontend && npm run lint && npm run build
git -C .. status --short -- frontend/src/app/karaoke/'[videoId]'/page.tsx
```

Expected:

- both refresh UI and all user additions are present;
- lint and build pass;
- the karaoke page is modified but unstaged, representing only the restored user work relative to the new refresh-UI commit.

---

### Task 8: Full Verification and Hindia Acceptance Test

**Files:**
- Verify: all files changed in Tasks 1-7
- Exercise local data: `data/processed/lB8ASupNtlw/meta.json`

- [ ] **Step 1: Run host-safe backend tests**

Run:

```bash
PYTHONPATH=backend python3 -m unittest discover -s tests/backend -p 'test_*.py' -v
```

Expected: all tests that do not import `main.py` pass. If host dependency imports prevent discovery after adding `test_lyrics_refresh.py`, run the lyric-only host suite instead:

```bash
PYTHONPATH=backend:tests/backend python3 -m unittest \
  test_errors \
  test_youtube_status \
  test_lyrics_resolution -v
```

Expected: all selected tests pass.

- [ ] **Step 2: Run the complete backend suite in the container**

Run:

```bash
podman-compose build backend
podman-compose run --rm \
  -v "$PWD/tests:/app/tests:ro" \
  backend python -m unittest discover -s /app/tests/backend -p 'test_*.py' -v

podman-compose run --rm backend python -m py_compile \
  errors.py youtube.py lyrics_sync.py main.py stems.py config.py
```

Expected: all tests pass and compilation exits with status 0.

- [ ] **Step 3: Run frontend checks**

Run:

```bash
cd frontend
npm run lint
npm run build
```

Expected: both commands succeed.

- [ ] **Step 4: Start the rebuilt local stack**

Run from the repository root:

```bash
podman-compose up -d --build backend frontend
curl -fsS http://localhost:8000/health
```

Expected: health response is `{"status":"ok"}`.

- [ ] **Step 5: Record media-file timestamps before refresh**

Run:

```bash
stat -c '%n %Y' \
  data/downloads/lB8ASupNtlw.wav \
  data/processed/lB8ASupNtlw/vocals.wav \
  data/processed/lB8ASupNtlw/no_vocals.wav \
  > /tmp/lB8ASupNtlw-before-refresh.stat
```

Expected: the file exists and three timestamp rows are recorded.

- [ ] **Step 6: Refresh the Hindia track through the new endpoint**

Run:

```bash
curl -fsS -X POST \
  http://localhost:8000/track/lB8ASupNtlw/lyrics/refresh \
  > /tmp/lB8ASupNtlw-refresh-response.json

python3 - <<'PY'
import json
from pathlib import Path

meta = json.loads(Path("data/processed/lB8ASupNtlw/meta.json").read_text())
assert meta["lyricsSource"] == "lrclib", meta["lyricsSource"]
assert meta["lyricsStatus"] == "synced", meta["lyricsStatus"]
assert len(meta["lyrics"]) >= 40, len(meta["lyrics"])
assert meta["lyricsMatch"]["strategy"] in {"exact", "search"}
assert meta["lyricsMatch"]["artistName"].casefold() == "hindia"
print(meta["lyricsSource"], len(meta["lyrics"]), meta["lyricsMatch"])
PY
```

Expected: source is `lrclib`, status is `synced`, at least 40 lyric lines exist, and `lyricsMatch` identifies Hindia's track.

- [ ] **Step 7: Verify refresh did not reprocess audio**

Run:

```bash
stat -c '%n %Y' \
  data/downloads/lB8ASupNtlw.wav \
  data/processed/lB8ASupNtlw/vocals.wav \
  data/processed/lB8ASupNtlw/no_vocals.wav \
  > /tmp/lB8ASupNtlw-after-refresh.stat

diff -u \
  /tmp/lB8ASupNtlw-before-refresh.stat \
  /tmp/lB8ASupNtlw-after-refresh.stat
```

Expected: `diff` produces no output, proving the full audio and stems were not rewritten.

- [ ] **Step 8: Verify the browser behavior manually**

Open:

```text
http://localhost:3000/karaoke/lB8ASupNtlw?mode=karaoke
```

Confirm:

1. Before refresh on a Whisper/none track, `Refresh lyrics` is visible.
2. The button becomes disabled and reads `Refreshing...` during the request.
3. A successful refresh shows `Synced lyrics loaded from LRCLIB.`.
4. The lyric list updates without playback restarting or seeking to zero.
5. After metadata reload reports `lyricsSource: "lrclib"`, the refresh button disappears.
6. The existing Now Playing card and upcoming queue behave exactly as before.

- [ ] **Step 9: Run final repository checks**

Run:

```bash
git diff --check
git status --short --branch
git log --oneline -6
```

Expected:

- no whitespace errors;
- backend/API/context implementation commits are present on `feat/lrclib-lyrics-resolution`;
- the refresh UI is committed, while `frontend/src/app/karaoke/[videoId]/page.tsx` remains modified and unstaged only for the user's restored Now Playing/upcoming-queue work;
- this plan file may remain uncommitted unless the user separately asks to commit documentation.

## Final Handoff Checklist

- Exact LRCLIB lookup uses normalized `track_name`, `artist_name`, and full-WAV duration.
- Structured search validates title, artist, parsed synced lyrics, and a 10-second duration tolerance.
- Temporary provider failures retry at 0.5 and 1 second delays.
- Whisper runs only after both LRCLIB strategies fail.
- Whisper/none results retain a concise `lyricsWarning`.
- LRCLIB results persist `lyricsMatch`.
- Existing tracks can refresh LRCLIB lyrics without YouTube, Demucs, or Whisper.
- Refresh failures preserve old metadata.
- Refresh requests for one video are serialized with an `asyncio.Lock`.
- Metadata-only reload does not restart audio.
- The Hindia acceptance case resolves to LRCLIB synced lyrics.
- The refresh UI has its own commit; the user's pre-existing karaoke page changes are restored afterward and remain present as an unstaged diff.
