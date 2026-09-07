import argparse
import re
from pathlib import Path

import webvtt

from . import config, naming
from .output_writer import merge_cues_into_turns, write_output_files

_SPEAKER_PATTERN = re.compile(r"^\s*([^:\n]{1,60}):\s*(.*)$", re.DOTALL)


def _timestamp_to_seconds(timestamp_str: str) -> float:
    """Convert VTT timestamp (HH:MM:SS.mmm) to seconds as float."""
    timestamp_str = timestamp_str.strip()
    # Split on colons and period
    parts = timestamp_str.replace('.', ':').split(':')
    if len(parts) == 4:  # HH:MM:SS:mmm
        hours, minutes, seconds, millis = map(int, parts)
    elif len(parts) == 3:  # MM:SS:mmm or HH:MM:SS
        # Assume MM:SS.mmm format or HH:MM:SS
        if '.' in timestamp_str:
            # MM:SS.mmm format
            minutes, seconds_str = timestamp_str.split(':')
            seconds, millis_str = seconds_str.split('.')
            hours = 0
            minutes = int(minutes)
            seconds = int(seconds)
            # Pad millis to 3 digits
            millis_str = millis_str.ljust(3, '0')[:3]
            millis = int(millis_str)
        else:
            # HH:MM:SS format - shouldn't happen in VTT
            hours, minutes, seconds = map(int, parts)
            millis = 0
    else:
        raise ValueError(f"Invalid timestamp format: {timestamp_str}")

    total_seconds = hours * 3600 + minutes * 60 + seconds + millis / 1000.0
    return total_seconds


def parse_vtt(path: Path) -> list[dict]:
    cues = []
    for caption in webvtt.read(str(path)):
        text = caption.text.strip()
        match = _SPEAKER_PATTERN.match(text)
        if match:
            speaker, spoken = match.group(1).strip(), match.group(2).strip()
        else:
            speaker, spoken = "Unknown", text
        cues.append(
            {
                "start": _timestamp_to_seconds(caption.start),
                "end": _timestamp_to_seconds(caption.end),
                "speaker": speaker,
                "text": spoken,
            }
        )
    return cues


def import_vtt(
    source_path: Path, paths: config.Paths, title: str | None = None
) -> tuple[Path, Path]:
    cues = parse_vtt(source_path)
    turns = merge_cues_into_turns(cues)
    basename = naming.output_basename(source_path, title)
    metadata = {
        "recording_id": basename,
        "source_path": str(source_path),
        "source_type": "zoom_vtt",
    }
    json_path, txt_path = write_output_files(paths.output_dir, basename, turns, metadata)
    source_path.unlink()
    return json_path, txt_path


def main() -> None:
    parser = argparse.ArgumentParser(description="File a Zoom .vtt export as a meeting note.")
    parser.add_argument("vtt_path")
    parser.add_argument("--title", default=None)
    args = parser.parse_args()

    paths = config.get_paths()
    config.ensure_directories(paths)
    json_path, txt_path = import_vtt(Path(args.vtt_path), paths, args.title)
    print(f"Wrote {json_path} and {txt_path}")


if __name__ == "__main__":
    main()
