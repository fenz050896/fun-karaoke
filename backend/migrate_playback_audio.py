from pathlib import Path

from config import PROCESSED_DIR
from stems import PlaybackEncodeError, encode_playback_stems


def migrate_playback_audio(processed_dir: Path = PROCESSED_DIR):
    converted = []
    skipped = []
    failed = []

    if not processed_dir.exists():
        return converted, skipped, failed

    for track_dir in sorted(path for path in processed_dir.iterdir() if path.is_dir()):
        outputs = (track_dir / "instrumental.m4a", track_dir / "vocals.m4a")
        if all(path.is_file() and path.stat().st_size > 0 for path in outputs):
            skipped.append(track_dir.name)
            continue

        try:
            encode_playback_stems(track_dir)
            converted.append(track_dir.name)
        except PlaybackEncodeError as error:
            failed.append((track_dir.name, error.detail or error.message))

    return converted, skipped, failed


def main():
    converted, skipped, failed = migrate_playback_audio()
    print(f"Converted: {len(converted)}")
    print(f"Skipped: {len(skipped)}")
    print(f"Failed: {len(failed)}")
    for video_id, detail in failed:
        print(f"- {video_id}: {detail}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
