import subprocess
import shutil
from pathlib import Path


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
