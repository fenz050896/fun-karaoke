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


async def fetch_lyrics(title: str, artist: str, album: str = "", duration: int = 0) -> Optional[List[Dict]]:
    """Fetch synced lyrics from LRCLIB. Returns parsed lyrics or None."""
    import httpx

    url = "https://lrclib.net/api/search"
    params = {"q": f"{title} {artist}"}
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    if not data:
        return None
    # pick best match
    for item in data:
        synced = item.get("syncedLyrics")
        if synced:
            return parse_lrc(synced)
    return None


def transcribe_with_whisper(audio_path: Path, model_size: str = "base") -> List[Dict]:
    """Transcribe vocals with faster-whisper and return lyrics-like segments."""
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
