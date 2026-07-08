import subprocess
import json
from pathlib import Path
from typing import List, Dict
import logging

from errors import AppError, error_payload, truncate_detail

logger = logging.getLogger(__name__)

# Path to cookies file
COOKIES_FILE = Path(__file__).parent / "youtube_cookies.txt"


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


def download_audio(video_id: str, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_template = str(output_dir / f"{video_id}.%(ext)s")
    cmd = [
        "yt-dlp",
        "-f", "bestaudio/best",
        "--extract-audio",
        "--audio-format", "wav",
        "--audio-quality", "0",
        "-o", output_template,
        f"https://www.youtube.com/watch?v={video_id}",
    ]

    # Add cookies and JS runtime for download if available
    if COOKIES_FILE.exists():
        cmd.extend([
            "--cookies", str(COOKIES_FILE),
            "--js-runtimes", "node",
            "--remote-components", "ejs:github"
        ])
        logger.info(f"Downloading {video_id} with cookies and node runtime")
    else:
        logger.warning(f"Downloading {video_id} without cookies - may fail")

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
