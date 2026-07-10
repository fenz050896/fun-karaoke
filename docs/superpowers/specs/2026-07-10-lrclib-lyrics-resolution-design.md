# LRCLIB Lyrics Resolution Design

**Date:** 2026-07-10
**Status:** approved
**Scope:** Backend lyric resolution plus a small refresh action in the existing karaoke UI

## Overview

The current pipeline sends a free-text `q` query to LRCLIB, accepts the first result with `syncedLyrics`, and falls back to Whisper whenever no parsed LRCLIB lines are produced. This makes two failures difficult to distinguish: LRCLIB can return the wrong candidate, or a temporary request/parse failure can silently send a song to Whisper.

The saved result for `Hindia - everything u are` demonstrates the second outcome: LRCLIB currently has suitable synced lyrics, but the processed track contains low-quality Whisper output. Because ready tracks are cached, normal processing will not retry lyric resolution.

This design makes LRCLIB resolution deterministic and observable while keeping Whisper as a last resort. It does not change Demucs, playback, or the Whisper model.

## Goals

- Prefer a metadata-based LRCLIB exact lookup over free-text search.
- Use the downloaded audio duration to reject live, remix, sped-up, extended, or otherwise mismatched candidates.
- Retry temporary LRCLIB failures before falling back.
- Preserve enough diagnostic metadata to explain why LRCLIB or Whisper was used.
- Allow an already processed track to refresh only its lyrics without downloading or separating audio again.
- Keep existing `lyrics`, `lyricsSource`, and `lyricsStatus` fields compatible with the frontend.

## Non-goals

- No Whisper model upgrade or GPU support.
- No combination of Whisper text with LRCLIB timestamps.
- No fuzzy or machine-learning candidate ranking.
- No manual lyric editor.
- No database or background worker migration.
- No re-download or Demucs rerun during lyric refresh.

## Architecture

Lyric resolution remains owned by `backend/lyrics_sync.py`, with small, independently testable responsibilities:

1. **Metadata normalization** — derive conservative LRCLIB lookup values from the original title and artist.
2. **LRCLIB request handling** — call exact lookup or structured search with bounded retry behavior.
3. **Candidate validation** — require synced lyrics, matching normalized title/artist, and acceptable duration.
4. **LRC parsing** — retain the existing conversion to `{start, text}` rows.
5. **Resolution orchestration** — exact lookup, then structured search, then optional Whisper fallback.

`backend/main.py` remains responsible for invoking resolution, persisting metadata, and exposing the refresh endpoint. A new small duration helper reads the downloaded full WAV metadata through `soundfile`; both initial processing and refresh use that same helper.

## Metadata Normalization

The original YouTube title and artist remain unchanged in `meta.json`. Normalization is used only for LRCLIB lookup and candidate comparison.

Normalization should be conservative:

- trim and collapse whitespace;
- compare case-insensitively;
- remove a leading `Artist - `, `Artist – `, or `Artist — ` prefix only when it matches the supplied artist;
- remove common trailing presentation labels such as `Official Music Video`, `Official Audio`, and `Lyrics` only when they appear in brackets or parentheses;
- remove a trailing ` - Topic` suffix from a YouTube uploader name;
- avoid removing arbitrary parenthetical text because it may be part of the real track name.

Example:

```text
Original title:  Hindia - everything u are
Original artist: Hindia
Lookup title:    everything u are
Lookup artist:   Hindia
```

Apply these rules to the requested title/artist and to LRCLIB's `trackName` and `artistName` fields. The generic LRCLIB `name` field is not used for matching. Comparisons use case-folded, whitespace-collapsed normalized values.

## Duration Source

Add a small helper that reads the downloaded full WAV at `DOWNLOADS_DIR/{video_id}.wav` through `soundfile.info()` and returns its duration in seconds. Do not derive duration from `vocals.wav`, because stem output is not the canonical recording metadata. This is new shared backend logic used by initial processing and lyric refresh; it does not require a new dependency or frontend request field.

Pass the floating-point duration to LRCLIB `/api/get`. Candidate comparison uses the original floating-point values and accepts a candidate when the absolute difference is no more than 10 seconds.

## LRCLIB Resolution Flow

### 1. Exact lookup

Call:

```http
GET https://lrclib.net/api/get
    ?track_name=<normalized title>
    &artist_name=<normalized artist>
    &duration=<audio duration>
```

`/api/get` returns a single object. Accept it only when:

- `syncedLyrics` is non-empty;
- parsing produces at least one lyric line;
- normalized title and artist match the requested metadata;
- duration differs by at most 10 seconds.

A `404` means no exact match and should proceed directly to structured search. Other permanent `4xx` responses are recorded and also proceed to structured search without retry.

### 2. Structured search

If exact lookup has no valid result, call:

```http
GET https://lrclib.net/api/search
    ?track_name=<normalized title>
    &artist_name=<normalized artist>
```

The response is an array. LRCLIB `/api/search` does not accept a duration parameter, so duration validation remains client-side. Do not select the first row blindly. A candidate is eligible only when:

- it has non-empty `syncedLyrics` that parse into at least one line;
- its normalized title equals the normalized requested title;
- its normalized artist equals the normalized requested artist;
- its duration differs from the audio by no more than 10 seconds.

If several candidates are eligible, select the one with the smallest duration difference. Preserve LRCLIB response order only as the tie-breaker.

This is intentionally stricter than fuzzy scoring. A false negative safely reaches Whisper; a false positive stores lyrics for the wrong recording.

### 3. Whisper fallback

Whisper runs only when both LRCLIB strategies produce no valid synced lyrics or LRCLIB remains unavailable after retry. Existing Whisper settings remain unchanged.

The normal processing flow is therefore:

```text
normalize metadata
  → exact LRCLIB lookup
  → validated structured LRCLIB search
  → Whisper
  → unavailable lyrics
```

A successful LRCLIB result returns immediately and Whisper is not loaded.

## Retry and Error Handling

Retry only temporary failures:

- connection errors;
- timeouts;
- HTTP `429`;
- HTTP `5xx`.

Use at most three total attempts per request, with delays of 0.5 seconds and 1 second before attempts two and three. Do not retry `404` or other permanent `4xx` responses.

Exact lookup and structured search have separate request attempts because a successful search can still recover from an exact-lookup miss. Diagnostics should retain the latest meaningful LRCLIB failure even if Whisper later succeeds. If no candidate matches but no provider error occurred, record a concise `No valid LRCLIB match` warning only when the final source is Whisper or none.

A lyric provider failure remains non-fatal to normal track processing. Audio and stems can still become ready with Whisper-generated or unavailable lyrics.

## Persisted Track Metadata

Keep the existing fields:

```json
{
  "lyrics": [],
  "lyricsSource": "lrclib | whisper | none",
  "lyricsStatus": "synced | generated | unavailable"
}
```

When LRCLIB succeeds, add the selected candidate:

```json
{
  "lyricsMatch": {
    "id": 17589301,
    "strategy": "exact",
    "trackName": "everything u are",
    "artistName": "Hindia",
    "duration": 236,
    "durationDelta": 1
  }
}
```

`strategy` is `exact` or `search`.

When LRCLIB fails or has no valid match and Whisper is used, preserve a concise diagnostic:

```json
{
  "lyricsSource": "whisper",
  "lyricsStatus": "generated",
  "lyricsWarning": "LRCLIB timed out after 3 attempts"
}
```

Warnings must be written to `meta.json`, not only transient job state. Do not store full response bodies or stack traces.

Existing tracks without `lyricsMatch` or `lyricsWarning` remain valid.

## Lyrics-Only Refresh

Add:

```http
POST /track/{video_id}/lyrics/refresh
```

Behavior:

1. Load the existing ready `meta.json`.
2. Verify the downloaded full audio exists.
3. Calculate its duration.
4. Run metadata normalization, exact LRCLIB lookup, and structured LRCLIB search.
5. Do **not** run Whisper during refresh.
6. On success, replace only the lyric-related keys: `lyrics`, `lyricsSource`, `lyricsStatus`, `lyricsMatch`, and `lyricsWarning`.
7. Remove a stale `lyricsWarning` or `lyricsMatch` when the successful result no longer needs that key.
8. Preserve every other `meta.json` key unchanged, including `videoId`, `title`, `artist`, `status`, `mode`, `saved`, `full_audio_path`, and any future non-lyric fields. Audio files, stems, jobs, and queue state are untouched.
9. Write metadata atomically through a temporary file in the same directory followed by `Path.replace()`, so an interrupted write cannot corrupt the track. Initial processing remains unchanged because its metadata file is created only after processing completes; atomic writes are required here because refresh replaces a playable track's existing file.

If no valid LRCLIB match exists, return HTTP `404` with code `lyrics_not_found` and keep the old lyrics unchanged. If LRCLIB remains unavailable after retry, return HTTP `503` with code `lyrics_provider_unavailable` and keep the old lyrics unchanged. Missing track metadata or full audio returns HTTP `404` without modifying metadata.

Only one refresh request for a track should run at a time. Maintain a module-level dictionary of `asyncio.Lock` instances keyed by video ID; acquire the track's lock around lookup and metadata replacement. This in-process guard is sufficient for the current single-backend architecture, so no distributed locking is needed. The POST handler may remain synchronous from the user's perspective and return after refresh finishes.

## Frontend Refresh Action

Add a small `Refresh lyrics` action to the existing karaoke page when the track source is `whisper` or `none`.

Behavior:

- keep a page-local `refreshingLyrics` boolean and disable the action while the request is running;
- show a readable success or failure message using the page's existing error/recovery presentation; adding a new toast dependency is not required;
- after success, call the existing track-loading path again so the LRCLIB lyrics render immediately;
- do not enqueue or reprocess the song;
- do not expose LRCLIB candidate selection to the user in this iteration.

The action is intentionally limited to tracks that can benefit from replacing generated or unavailable lyrics. Manual replacement of an existing LRCLIB match is outside this scope.

## Data Flow

### New track

```text
YouTube download
  → actual WAV duration
  → Demucs stems
  → normalize title/artist
  → LRCLIB exact lookup with duration
      → valid: save synced lyrics + lyricsMatch
      → miss: structured search and validation
          → valid: save synced lyrics + lyricsMatch
          → miss/failure: Whisper
              → success: save generated lyrics + warning if applicable
              → failure: save unavailable state + warning if applicable
```

### Existing track refresh

```text
Refresh lyrics action
  → refresh endpoint
  → existing audio duration + metadata
  → LRCLIB exact lookup
  → validated structured search
      → success: atomically update lyric fields
      → failure: preserve existing metadata and lyrics
```

## Testing Strategy

Add a new focused backend test module around lyric resolution; the repository currently has no committed Python tests. Use the standard library `unittest` facilities so no new test dependency is required. External LRCLIB calls and Whisper should be mocked; tests must not depend on live network access or model downloads. Existing `resolve_lyrics` callers and tests, if any are added concurrently, must be updated for its new duration input and additive result metadata.

Required cases:

- title normalization removes a matching artist prefix and known presentation suffix;
- normalization preserves meaningful unrelated parenthetical text;
- exact lookup accepts a matching synced result within the duration tolerance;
- exact lookup `404` proceeds to structured search without retry;
- temporary exact-lookup failure retries and can recover;
- structured search skips rows without synced lyrics;
- structured search rejects wrong title, wrong artist, and duration differences above 10 seconds;
- structured search selects the smallest duration difference rather than the first row;
- malformed or empty LRC is rejected;
- valid LRCLIB lyrics prevent Whisper from running;
- no valid LRCLIB result invokes Whisper during normal processing;
- an LRCLIB warning is retained when Whisper succeeds;
- refresh success replaces only lyric-related metadata;
- refresh failure preserves existing lyrics;
- refresh never invokes Whisper.

Frontend verification:

- lint passes;
- the refresh action appears for `whisper` and `none`, but not `lrclib`;
- the action disables while running;
- success reloads the current track metadata;
- failure leaves the current lyrics visible and shows a readable message.

Manual acceptance case:

1. In the current development data, use processed track `lB8ASupNtlw` (`Hindia - everything u are`), whose metadata currently reports `lyricsSource: "whisper"`.
2. Trigger lyric refresh.
3. Confirm the track changes from `lyricsSource: "whisper"` to `lyricsSource: "lrclib"`.
4. Confirm approximately 49 synced lyric lines are stored and displayed.
5. Confirm no YouTube download, Demucs separation, or Whisper transcription runs.

## Compatibility and Scope Control

- Existing ready tracks continue to load without migration.
- Existing API consumers remain compatible; the refresh endpoint and metadata fields are additive.
- No unrelated playback, queue, stem separation, or visual redesign work is included.
- `frontend/src/app/karaoke/[videoId]/page.tsx` currently has uncommitted user work that adds a Now Playing card, playback progress, and a queue filtered to upcoming tracks. Implementation must inspect and preserve that diff, adding the refresh action only around the lyric-source/empty-lyrics UI rather than rewriting the queue panel.
