import subprocess
from pathlib import Path


def convert_to_wav16k_mono(source_path: Path, dest_path: Path) -> None:
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(source_path), "-ar", "16000", "-ac", "1", str(dest_path)],
        check=True,
        capture_output=True,
    )
