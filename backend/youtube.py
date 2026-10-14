import json
import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import List, Dict

from errors import AppError, error_payload, truncate_detail
from process_runner import run_process

logger = logging.getLogger(__name__)
DOWNLOAD_TIMEOUT_SECONDS = 600

# Path to cookies file
COOKIES_FILE = Path(__file__).parent / "youtube-auth" / "youtube_cookies.txt"


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


def _cookies_file() -> Path:
    return Path(os.environ.get("YOUTUBE_COOKIES_FILE", COOKIES_FILE))


def _cookies_available(cookies_file: Path) -> bool:
    try:
        return cookies_file.is_file() and cookies_file.stat().st_size > 0
    except OSError:
        return False


def _yt_dlp_js_runtime_args() -> List[str]:
    deno_path = shutil.which("deno")
    if deno_path:
        return ["--js-runtimes", f"deno:{deno_path}", "--remote-components", "ejs:github"]
    return []


def _download_error_message(detail: str) -> str:
    lower_detail = (detail or "").lower()
    if "sign in" in lower_detail or "not a bot" in lower_detail or "cookies" in lower_detail:
        return "YouTube blocked the download. Export fresh YouTube cookies and try again."
    if "no supported javascript runtime" in lower_detail or "js runtime" in lower_detail:
        return "YouTube download needs the Deno JavaScript runtime in the backend container."
    return "Could not download audio from YouTube. Check cookies or try another video."


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

    cookies_file = _cookies_file()
    cookies_present = _cookies_available(cookies_file)
    if cookies_present:
        cmd.extend(["--cookies", str(cookies_file)])
        logger.info(f"Using YouTube cookies from {cookies_file}")
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
    cookies_file = _cookies_file()
    if _cookies_available(cookies_file):
        cmd.extend(["--cookies", str(cookies_file)])
        cmd.extend(_yt_dlp_js_runtime_args())
        logger.info(f"Downloading {video_id} with cookies from {cookies_file}")
    else:
        logger.warning(f"Downloading {video_id} without cookies - may fail")

    try:
        run_process(cmd, timeout=DOWNLOAD_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired as e:
        raise DownloadError(
            code="download_timeout",
            message="YouTube download timed out. Try again or choose a shorter video.",
            detail=truncate_detail(str(e)),
        ) from e
    except subprocess.CalledProcessError as e:
        detail = e.stderr or e.stdout or str(e)
        raise DownloadError(
            code="download_failed",
            message=_download_error_message(detail),
            detail=truncate_detail(detail),
        ) from e
    except Exception as e:
        detail = str(e)
        raise DownloadError(
            code="download_failed",
            message=_download_error_message(detail),
            detail=detail,
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
