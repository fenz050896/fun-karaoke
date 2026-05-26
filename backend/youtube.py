import subprocess
import json
from pathlib import Path
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)

# Path to cookies file
COOKIES_FILE = Path(__file__).parent / "youtube_cookies.txt"


def search_youtube(query: str, max_results: int = 10, search_type: str = "all") -> List[Dict]:
    """
    Search YouTube using yt-dlp.
    Note: YouTube may require authentication to prevent bot detection.
    If searches fail, export cookies from your browser and save as youtube_cookies.txt
    See YOUTUBE_AUTH.md for instructions.
    """
    # Modify query based on search type
    if search_type == "artist":
        search_query = f"artist:{query}"
    elif search_type == "title":
        search_query = f"track:{query}"
    elif search_type == "genre":
        search_query = f"genre:{query}"
    else:  # all or default
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
    
    # Add cookies if file exists
    # Note: When using cookies with --flat-playlist, we don't need player_client
    if COOKIES_FILE.exists():
        cmd.extend(["--cookies", str(COOKIES_FILE)])
        logger.info("Using cookies from youtube_cookies.txt")
    else:
        # Without cookies, try android client (may fail due to bot detection)
        cmd.extend(["--extractor-args", "youtube:player_client=android"])
        logger.warning("No cookies file found. YouTube search may fail due to bot detection.")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        # Log errors if any
        if result.stderr and "ERROR" in result.stderr:
            logger.warning(f"yt-dlp errors: {result.stderr[:500]}")
        
        if result.returncode != 0 and not result.stdout.strip():
            logger.error(f"yt-dlp failed with code {result.returncode}")
            return []
            
    except subprocess.TimeoutExpired:
        logger.error("yt-dlp search timeout")
        return []
    except Exception as e:
        logger.error(f"yt-dlp error: {e}")
        return []
    
    lines = result.stdout.strip().split("\n")
    items = []
    for line in lines:
        if not line.strip():
            continue
        parts = line.split("|", 3)
        if len(parts) < 4:
            logger.debug(f"Skipping invalid line: {line}")
            continue
        video_id, title, duration, uploader = parts
        # duration from flat-playlist is float, convert to int
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
    
    logger.info(f"Found {len(items)} results for query: '{query}'")
    return items


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
    
    subprocess.run(cmd, check=True, capture_output=True)
    expected = output_dir / f"{video_id}.wav"
    if expected.exists():
        return expected
    # fallback if extension differs
    candidates = list(output_dir.glob(f"{video_id}.*"))
    if candidates:
        return candidates[0]
    raise FileNotFoundError(f"Downloaded audio not found for {video_id}")
