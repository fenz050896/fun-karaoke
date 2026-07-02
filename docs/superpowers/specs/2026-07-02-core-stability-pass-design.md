# Core Stability Pass Design

## Overview

Fun Karaoke already has the main karaoke loop: YouTube search/download, Demucs stem separation, lyrics retrieval/transcription, a play queue, and Web Audio playback. The next milestone should harden that loop before adding larger features.

This design keeps the current FastAPI + file-based backend and Next.js frontend. It does not add a database, a worker system, or new karaoke features. The focus is clearer failure states, safer fallbacks, and frontend recovery actions across three areas: YouTube/search/download, lyrics, and playback.

## Goals

- Make YouTube search and download failures understandable to users.
- Preserve the existing processing flow while recording structured job errors.
- Make lyrics fallback behavior explicit: LRCLIB first, Whisper second, no lyrics as a valid state.
- Let tracks play even when synced lyrics are unavailable.
- Prevent the karaoke page from getting stuck on ambiguous loading or playback errors.
- Keep the implementation small and compatible with the current API shape where practical.

## Non-goals

- No vocal scoring.
- No pitch/key control.
- No party rooms, voting, or remote queue.
- No manual lyric editor.
- No database migration.
- No replacement of Demucs, Whisper, or yt-dlp.

## Backend Design

### Search response

The `/search` endpoint should continue returning `results` so existing frontend code remains easy to adapt. It should also return explicit request status metadata:

```json
{
  "ok": true,
  "results": [],
  "error": null
}
```

When yt-dlp fails, the endpoint should return:

```json
{
  "ok": false,
  "results": [],
  "error": {
    "code": "youtube_timeout",
    "message": "YouTube search timed out. Try again.",
    "detail": "optional short technical detail"
  }
}
```

Initial error codes should stay small:

- `youtube_cookies_missing` — cookies file is missing and YouTube likely blocks requests.
- `youtube_timeout` — yt-dlp search timed out.
- `youtube_search_failed` — yt-dlp returned no usable output because of an error.
- `youtube_unavailable` — unexpected search exception.

### Download and processing errors

Processing jobs should keep the current statuses:

`queued → downloading → separating → fetching_lyrics → ready/error`

For failed jobs, add structured fields alongside the existing `error` field:

```json
{
  "status": "error",
  "error": "Download failed",
  "errorCode": "download_failed",
  "errorMessage": "Could not download audio from YouTube. Check cookies or try another video.",
  "errorDetail": "short yt-dlp stderr excerpt"
}
```

The backend should map required processing failures to readable codes:

- `download_failed`
- `stems_failed`
- `processing_failed`

Lyrics lookup/transcription failures should not fail the whole job if audio and stems are already usable. They should produce `lyrics: []` and metadata showing lyrics are unavailable. If useful, a non-fatal lyrics warning can be kept in job details, but the job should still become `ready`.

### Track metadata

`meta.json` should include lyric metadata:

```json
{
  "lyrics": [],
  "lyricsSource": "none",
  "lyricsStatus": "unavailable"
}
```

Allowed values:

- `lyricsSource`: `lrclib`, `whisper`, `none`
- `lyricsStatus`: `synced`, `generated`, `unavailable`

Interpretation:

- LRCLIB synced lyrics → `lyricsSource: "lrclib"`, `lyricsStatus: "synced"`
- Whisper fallback → `lyricsSource: "whisper"`, `lyricsStatus: "generated"`
- No lyrics available → `lyricsSource: "none"`, `lyricsStatus: "unavailable"`

## Lyrics Flow

The processing flow should become:

1. Download audio.
2. Separate stems.
3. Try LRCLIB using `title + artist`.
4. If LRCLIB returns synced lyrics, save them.
5. If LRCLIB is empty or fails, try Whisper on `vocals.wav`.
6. If Whisper succeeds, save generated timestamped segments.
7. If Whisper fails or vocals are unavailable, save an empty lyrics list with unavailable metadata.

LRCLIB request failures should be logged and recorded in job details if useful, but they should not block playback.

## Frontend Design

### API client

`frontend/src/lib/api.ts` should parse the updated backend responses and surface readable errors. The frontend can remain compatible with the existing `results` shape while checking `ok` and `error` when present.

### Home search

The home page should distinguish these cases:

- Search request failed technically → show the backend error message.
- Search succeeded with zero results → show an empty state.
- Search succeeded with results → show the existing result list.

This avoids treating every empty list as “no results”.

### Processing page

`frontend/src/app/processing/page.tsx` should prefer `errorMessage` for failed jobs. If only the old `error` field exists, it should still display that. The page should keep the current progress bar and polling behavior.

### Karaoke page and audio context

`frontend/src/lib/audio-context.tsx` should produce clearer playback errors:

- metadata fetch failed;
- instrumental audio fetch failed;
- full audio fetch failed;
- audio decode failed;
- playback failed.

`frontend/src/app/karaoke/[videoId]/page.tsx` should display recovery actions when possible:

- go back to Home;
- retry loading the current track;
- continue with queue if another queued song exists.

For lyrics, an empty `lyrics` array should be treated as a valid playable state. The lyrics panel should show a clear message such as: “Lyrics are unavailable for this track, but playback is ready.”

## Error Handling Principles

- Prefer short user-facing messages over raw stack traces.
- Keep short technical details for logs or optional details, not primary UI copy.
- Do not fail the whole track because LRCLIB is unavailable.
- Do fail the job when required audio or stems cannot be produced.
- Preserve existing fields where possible so older data still renders.

## Verification Plan

Backend checks:

- Import FastAPI app successfully.
- `/health` still returns `ok`.
- Search returns `ok`, `results`, and `error` fields.
- A simulated search timeout or yt-dlp failure returns a readable error.
- A lyrics lookup failure can still fall back to Whisper or save unavailable metadata.

Frontend checks:

- Lint passes.
- Build passes if feasible in the current environment.
- Search technical failure shows a toast/message distinct from empty results.
- Processing page displays `errorMessage` for failed jobs.
- Karaoke page can render a ready track with `lyrics: []`.
- Audio loading errors show a recovery action instead of an indefinite loading state.

## Implementation Notes

- Keep changes surgical and focused on existing files.
- Avoid introducing abstractions for single-use error mapping unless the code becomes repetitive.
- Use small helper functions only where they make backend error formatting or frontend error parsing clearer.
- Do not refactor unrelated UI components or queue behavior.
