import subprocess
import shutil
from pathlib import Path

from errors import AppError, truncate_detail


class PlaybackEncodeError(AppError):
    pass


def separate_stems(audio_path: Path, output_dir: Path, model: str = "htdemucs") -> Path:
    """Run demucs on audio_path and return the folder containing stems."""
    output_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        "python3", "-m", "demucs.separate",
        "-n", model,  # Changed from --model to -n
        "--out", str(output_dir),
        "--filename", "{stem}.{ext}",
        str(audio_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    
    # demucs creates output_dir/{model}/ with stem files directly
    stems_dir = output_dir / model
    if not stems_dir.exists():
        raise FileNotFoundError(f"Demucs output not found at {stems_dir}")
    
    # Check if stems were created
    stem_files = list(stems_dir.glob("*.wav"))
    if not stem_files:
        raise FileNotFoundError(f"No stem files found in {stems_dir}")
    
    return stems_dir


def encode_playback_stems(track_dir: Path):
    instrumental_source = track_dir / "no_vocals.wav"
    vocals_source = track_dir / "vocals.wav"
    missing = [path.name for path in (instrumental_source, vocals_source) if not path.is_file()]
    if missing:
        raise PlaybackEncodeError(
            code="audio_encode_failed",
            message="Could not prepare compressed playback audio.",
            detail=f"Missing playback stem: {', '.join(missing)}",
        )

    instrumental_path = track_dir / "instrumental.m4a"
    vocals_path = track_dir / "vocals.m4a"
    instrumental_temp = track_dir / "instrumental.tmp.m4a"
    vocals_temp = track_dir / "vocals.tmp.m4a"

    for temp_path in (instrumental_temp, vocals_temp):
        temp_path.unlink(missing_ok=True)

    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel", "error",
        "-y",
        "-i", str(instrumental_source),
        "-i", str(vocals_source),
        "-map", "0:a:0",
        "-c:a", "aac",
        "-profile:a", "aac_low",
        "-b:a", "192k",
        "-ar", "44100",
        "-ac", "2",
        "-movflags", "+faststart",
        str(instrumental_temp),
        "-map", "1:a:0",
        "-c:a", "aac",
        "-profile:a", "aac_low",
        "-b:a", "128k",
        "-ar", "44100",
        "-ac", "2",
        "-movflags", "+faststart",
        str(vocals_temp),
    ]

    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        if any(not path.is_file() or path.stat().st_size == 0 for path in (instrumental_temp, vocals_temp)):
            raise PlaybackEncodeError(
                code="audio_encode_failed",
                message="Could not prepare compressed playback audio.",
                detail="FFmpeg did not create both playback files.",
            )
        instrumental_temp.replace(instrumental_path)
        vocals_temp.replace(vocals_path)
    except PlaybackEncodeError:
        raise
    except subprocess.CalledProcessError as error:
        detail = error.stderr or error.stdout or str(error)
        raise PlaybackEncodeError(
            code="audio_encode_failed",
            message="Could not prepare compressed playback audio.",
            detail=truncate_detail(detail),
        ) from error
    except Exception as error:
        raise PlaybackEncodeError(
            code="audio_encode_failed",
            message="Could not prepare compressed playback audio.",
            detail=truncate_detail(str(error)),
        ) from error
    finally:
        for temp_path in (instrumental_temp, vocals_temp):
            temp_path.unlink(missing_ok=True)

    return instrumental_path, vocals_path
