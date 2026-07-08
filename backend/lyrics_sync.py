import re
import json
from pathlib import Path
from typing import List, Dict, Optional


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
