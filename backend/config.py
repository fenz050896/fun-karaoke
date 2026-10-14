import json
import os
import threading
from pathlib import Path

# Global variables
DATA_DIR = Path(os.environ.get("KARAOKE_DATA_DIR", "/app/data"))
DOWNLOADS_DIR = DATA_DIR / "downloads"
PROCESSED_DIR = DATA_DIR / "processed"
DEMUCS_MODEL = "htdemucs"
WHISPER_MODEL = "small"
processing_lock = threading.RLock()

# Persistent state files
DATA_DIR.mkdir(parents=True, exist_ok=True)
JOBS_FILE = DATA_DIR / "jobs.json"
PLAY_QUEUE_FILE = DATA_DIR / "play_queue.json"

# Load jobs from file
try:
    with open(JOBS_FILE, "r", encoding="utf-8") as f:
        jobs = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    jobs = {}

# Processing job ID
processing_job_id = None
processing_worker = None
processing_stopping = False

# Processing queue (songs being downloaded/processed)
processing_queue = []

# Play queue (songs ready to play)
try:
    with open(PLAY_QUEUE_FILE, "r", encoding="utf-8") as f:
        play_queue = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    play_queue = []

# Save jobs to file
def save_jobs():
    with processing_lock:
        temp_path = JOBS_FILE.with_suffix(".json.tmp")
        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(jobs, f, ensure_ascii=False, indent=2)
            temp_path.replace(JOBS_FILE)
        finally:
            temp_path.unlink(missing_ok=True)

def save_play_queue():
    with open(PLAY_QUEUE_FILE, "w", encoding="utf-8") as f:
        json.dump(play_queue, f, ensure_ascii=False, indent=2)

# Clean up old jobs
def cleanup_old_jobs():
    # Implement cleanup logic if needed
    pass
