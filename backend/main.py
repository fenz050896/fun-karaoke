import uuid
import shutil
import asyncio
import json
import threading
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

import config
from config import DOWNLOADS_DIR, PROCESSED_DIR, DEMUCS_MODEL, WHISPER_MODEL, jobs, processing_queue, play_queue, save_jobs, save_play_queue
from youtube import search_youtube_with_status, download_audio, DownloadError
from stems import separate_stems
from lyrics_sync import resolve_lyrics

app = FastAPI(title="Fun Karaoke API")


@app.get("/health")
async def health():
    return {"status": "ok"}

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ProcessRequest(BaseModel):
    videoId: str
    title: Optional[str] = None
    artist: Optional[str] = None
    mode: Optional[str] = "karaoke"
    save: Optional[bool] = True


@app.get("/search")
async def search(q: str, max_results: int = 10, search_type: str = "all"):
    return search_youtube_with_status(q, max_results, search_type)


@app.get("/track/{video_id}/exists")
async def track_exists(video_id: str):
    meta_path = PROCESSED_DIR / video_id / "meta.json"
    if meta_path.exists():
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        return {"exists": True, "status": meta.get("status", "ready")}
    for job in jobs.values():
        if job.get("videoId") == video_id and job.get("status") in ("queued", "downloading", "separating", "fetching_lyrics"):
            return {"exists": True, "status": "processing"}
    return {"exists": False, "status": "not_found"}


@app.get("/audio/{video_id}/full")
async def audio_full(video_id: str):
    path = DOWNLOADS_DIR / f"{video_id}.wav"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Full audio not found")
    return FileResponse(path, media_type="audio/wav")


@app.post("/process")
async def process(req: ProcessRequest, background_tasks: BackgroundTasks):
    video_id = req.videoId
    mode = req.mode or "karaoke"
    save = req.save if req.save is not None else True

    # If save=True and track already ready, return existing job-like response
    if save:
        meta_path = PROCESSED_DIR / video_id / "meta.json"
        if meta_path.exists():
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            if meta.get("status") == "ready":
                return {
                    "jobId": meta.get("videoId", video_id),
                    "status": "ready",
                    "videoId": video_id,
                    "mode": meta.get("mode", mode),
                    "saved": meta.get("saved", True),
                }

    job_id = str(uuid.uuid4())
    jobs[job_id] = {
        "jobId": job_id,
        "videoId": video_id,
        "title": req.title or "",
        "artist": req.artist or "",
        "status": "queued",
        "error": None,
        "mode": mode,
        "saved": save,
    }
    config.processing_queue.append(job_id)
    save_jobs()  # Save jobs to file

    if config.processing_job_id is None:
        config.processing_job_id = job_id
        background_tasks.add_task(
            _process_track,
            job_id,
            video_id,
            req.title or "",
            req.artist or "",
            mode,
            save,
        )
    else:
        jobs[job_id]["status"] = "queued"

    return {"jobId": job_id, "status": "queued", "mode": mode, "saved": save}


@app.get("/processing-queue")
async def get_processing_queue():
    """Get all jobs that are not yet ready (processing queue)"""
    processing = []
    seen = set()

    active_job_ids = []
    if config.processing_job_id:
        active_job_ids.append(config.processing_job_id)
    active_job_ids.extend(config.processing_queue)

    for jid in active_job_ids:
        job = jobs.get(jid)
        if job and job.get("status") != "ready" and jid not in seen:
            processing.append(job)
            seen.add(jid)

    for jid, job in jobs.items():
        if job.get("status") != "ready" and jid not in seen:
            processing.append(job)

    return {"processing": processing}

@app.delete("/processing-queue/errors")
async def clear_failed_processing_jobs():
    """Remove failed jobs from persisted processing state."""
    failed_job_ids = [
        job_id
        for job_id, job in list(jobs.items())
        if job.get("status") == "error"
    ]

    for job_id in failed_job_ids:
        jobs.pop(job_id, None)

    config.processing_queue[:] = [
        job_id
        for job_id in config.processing_queue
        if job_id not in failed_job_ids
    ]

    if config.processing_job_id in failed_job_ids:
        config.processing_job_id = None

    if failed_job_ids:
        save_jobs()

    return {"success": True, "removed": len(failed_job_ids)}


@app.get("/queue")
async def get_play_queue():
    """Get play queue - songs ready to play (from processed files)"""
    queue_items = []
    for video_id in config.play_queue:
        meta_path = PROCESSED_DIR / video_id / "meta.json"
        if meta_path.exists():
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
                if meta.get("status") == "ready":
                    queue_items.append(meta)
    return {"queue": queue_items}


@app.post("/queue")
async def add_to_play_queue(req: ProcessRequest):
    """Add a song to play queue"""
    video_id = req.videoId
    
    # Check if already in play queue (prevent duplicates)
    if video_id in config.play_queue:
        return {"success": False, "error": "Already in queue"}
    
    # Check if track is already processed
    meta_path = PROCESSED_DIR / video_id / "meta.json"
    if not meta_path.exists():
        return {"success": False, "error": "Track not downloaded yet"}
    
    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)
        if meta.get("status") != "ready":
            return {"success": False, "error": "Track not ready"}
    
    config.play_queue.append(video_id)
    save_play_queue()
    return {"success": True, "videoId": video_id}


@app.delete("/queue/{video_id}")
async def remove_from_queue(video_id: str):
    """Remove from play queue"""
    if video_id in config.play_queue:
        config.play_queue.remove(video_id)
        save_play_queue()
        return {"success": True}
    return {"success": False, "error": "Item not found in queue"}


@app.post("/queue/{video_id}/move")
async def move_queue_item(video_id: str, direction: int = 1):
    current_index = -1
    for i, vid in enumerate(config.play_queue):
        if vid == video_id:
            current_index = i
            break
    
    if current_index < 0:
        return {"success": False, "error": "Item not found in queue"}
    
    new_index = current_index + direction
    if new_index < 0 or new_index >= len(config.play_queue):
        return {"success": False, "error": "Cannot move in that direction"}
    
    config.play_queue[current_index], config.play_queue[new_index] = config.play_queue[new_index], config.play_queue[current_index]
    save_play_queue()
    return {"success": True}


@app.get("/status/{job_id}")
async def status(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.get("/track/{video_id}")
async def track(video_id: str):
    meta_path = PROCESSED_DIR / video_id / "meta.json"
    if not meta_path.exists():
        raise HTTPException(status_code=404, detail="Track not found")
    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)
    return meta


@app.get("/audio/{video_id}/instrumental")
async def audio_instrumental(video_id: str):
    path = PROCESSED_DIR / video_id / "no_vocals.wav"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Instrumental not found")
    return FileResponse(path, media_type="audio/wav")


@app.get("/audio/{video_id}/vocals")
async def audio_vocals(video_id: str):
    path = PROCESSED_DIR / video_id / "vocals.wav"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Vocals not found")
    return FileResponse(path, media_type="audio/wav")


@app.get("/local-files")
async def get_local_files():
    # Scan PROCESSED_DIR for completed tracks
    files = []
    if PROCESSED_DIR.exists():
        for track_dir in PROCESSED_DIR.iterdir():
            if track_dir.is_dir():
                meta_path = track_dir / "meta.json"
                if meta_path.exists():
                    with open(meta_path, "r", encoding="utf-8") as f:
                        meta = json.load(f)
                        if meta.get("status") == "ready":
                            files.append(meta)
    return {"files": files}


def _start_next_queue_job():
    config.processing_job_id = None
    while config.processing_queue:
        next_job_id = config.processing_queue.pop(0)
        job = jobs.get(next_job_id)
        if job and job.get("status") == "queued":
            config.processing_job_id = next_job_id
            def run_next():
                _process_track(
                    next_job_id,
                    job["videoId"],
                    job.get("title", ""),
                    job.get("artist", ""),
                    job.get("mode", "karaoke"),
                    job.get("saved", True),
                )
            threading.Thread(target=run_next, daemon=True).start()
            break


def _set_job_error(job_id: str, code: str, message: str, detail: Optional[str] = None):
    jobs[job_id]["status"] = "error"
    jobs[job_id]["error"] = message
    jobs[job_id]["errorCode"] = code
    jobs[job_id]["errorMessage"] = message
    if detail:
        jobs[job_id]["errorDetail"] = detail
    else:
        jobs[job_id].pop("errorDetail", None)
    save_jobs()


def _process_track(job_id: str, video_id: str, title: str, artist: str, mode: str, save: bool):
    try:
        jobs[job_id]["status"] = "downloading"
        save_jobs()  # Save job status
        audio_path = download_audio(video_id, DOWNLOADS_DIR)

        jobs[job_id]["status"] = "separating"
        save_jobs()  # Save job status
        track_dir = PROCESSED_DIR / video_id
        track_dir.mkdir(parents=True, exist_ok=True)
        stems_dir = separate_stems(audio_path, track_dir, model=DEMUCS_MODEL)

        # Move stems to track_dir
        for stem_file in stems_dir.iterdir():
            dest = track_dir / stem_file.name
            if dest.exists():
                dest.unlink()
            shutil.move(str(stem_file), str(dest))
        # Clean up the empty stems_dir (the model directory)
        shutil.rmtree(stems_dir, ignore_errors=True)

        # Create no_vocals.wav by mixing bass + drums + other
        import soundfile as sf
        
        bass_path = track_dir / "bass.wav"
        drums_path = track_dir / "drums.wav"
        other_path = track_dir / "other.wav"
        
        if bass_path.exists() and drums_path.exists() and other_path.exists():
            bass, sr = sf.read(str(bass_path))
            drums, _ = sf.read(str(drums_path))
            other, _ = sf.read(str(other_path))
            
            # Mix the three stems
            no_vocals = bass + drums + other
            
            # Save as no_vocals.wav
            no_vocals_path = track_dir / "no_vocals.wav"
            sf.write(str(no_vocals_path), no_vocals, sr)

        jobs[job_id]["status"] = "fetching_lyrics"
        save_jobs()  # Save job status
        vocals_path = track_dir / "vocals.wav"
        lyrics_result = asyncio.run(resolve_lyrics(title, artist, vocals_path, model_size=WHISPER_MODEL))
        if lyrics_result.get("lyricsWarning"):
            jobs[job_id]["lyricsWarning"] = lyrics_result["lyricsWarning"]
            save_jobs()

        meta = {
            "videoId": video_id,
            "title": title,
            "artist": artist,
            "status": "ready",
            "lyrics": lyrics_result["lyrics"],
            "lyricsSource": lyrics_result["lyricsSource"],
            "lyricsStatus": lyrics_result["lyricsStatus"],
            "mode": mode,
            "saved": save,
            "full_audio_path": str(DOWNLOADS_DIR / f"{video_id}.wav"),
        }
        meta_path = track_dir / "meta.json"
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

        jobs[job_id]["status"] = "ready"
        save_jobs()  # Save job status
    except DownloadError as e:
        _set_job_error(job_id, e.code, e.message, e.detail)
    except Exception as e:
        current_status = jobs[job_id].get("status")
        if current_status == "separating":
            _set_job_error(
                job_id,
                "stems_failed",
                "Could not separate vocals and instrumental stems for this track.",
                str(e),
            )
        else:
            _set_job_error(
                job_id,
                "processing_failed",
                "Processing failed. Try another video or retry this track.",
                str(e),
            )
    finally:
        _start_next_queue_job()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
