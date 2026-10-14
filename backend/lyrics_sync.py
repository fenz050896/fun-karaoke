import asyncio
import json
import re
import subprocess
import sys
from contextlib import redirect_stdout
from pathlib import Path
from typing import Awaitable, Callable, Dict, List, Optional

from errors import truncate_detail
from process_runner import run_process


LRCLIB_BASE_URL = "https://lrclib.net/api"
WHISPER_TIMEOUT_SECONDS = 1200
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


def parse_lrc(lrc_text: str) -> List[Dict]:
    """Parse LRC format into list of {start, text}."""
    lines = []
    pattern = re.compile(r"\[(\d+):(\d+\.?\d*)\](.*)")
    for line in lrc_text.splitlines():
        match = pattern.match(line.strip())
        if match:
            minutes = float(match.group(1))
            seconds = float(match.group(2))
            text = match.group(3).strip()
            if text:
                lines.append({
                    "start": minutes * 60 + seconds,
                    "text": text,
                })
    return lines


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


def transcribe_with_whisper(audio_path: Path, model_size: str = "base") -> List[Dict]:
    """Transcribe vocals in a subprocess that can be stopped on timeout."""
    cmd = [sys.executable, str(Path(__file__).resolve()), str(audio_path), model_size]
    try:
        result = run_process(cmd, timeout=WHISPER_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired as error:
        raise RuntimeError("Whisper transcription timed out.") from error
    except subprocess.CalledProcessError as error:
        raise RuntimeError(truncate_detail(error.stderr) or "Whisper transcription failed.") from error
    return json.loads(result.stdout)


def _transcribe_with_whisper(audio_path: Path, model_size: str) -> List[Dict]:
    from faster_whisper import WhisperModel
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    segments, _ = model.transcribe(str(audio_path), beam_size=5, language=None)
    lines = []
    for seg in segments:
        lines.append({
            "start": seg.start,
            "text": seg.text.strip(),
        })
    return lines


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


if __name__ == "__main__":
    with redirect_stdout(sys.stderr):
        lyrics = _transcribe_with_whisper(Path(sys.argv[1]), sys.argv[2])
    print(json.dumps(lyrics, ensure_ascii=False))
