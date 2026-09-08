import argparse
import re
from datetime import datetime, timezone
from pathlib import Path

import webvtt

from . import config, naming
from .output_writer import merge_cues_into_turns, write_output_files
from .source_files import delete_verified_source, source_identity, verify_source

_SPEAKER_PATTERN = re.compile(r"^\s*([^:\n]{1,60}):\s*(.*)$", re.DOTALL)


def _timestamp_to_seconds(timestamp_str: str) -> float:
    """Convert VTT timestamp (HH:MM:SS.mmm) to seconds as float."""
    # webvtt normalizes caption timestamps to HH:MM:SS.mmm.
    hours, minutes, seconds = timestamp_str.split(":")
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def parse_vtt(path: Path) -> list[dict]:
    cues = []
    for caption in webvtt.read(str(path)):
        text = caption.text.strip()
        match = _SPEAKER_PATTERN.match(text)
        if match:
            speaker, spoken = match.group(1).strip(), match.group(2).strip()
        else:
            speaker, spoken = "Unknown", text
        cues = [*cues,
            {
                "start": _timestamp_to_seconds(caption.start),
                "end": _timestamp_to_seconds(caption.end),
                "speaker": speaker,
                "text": spoken,
            }
        ]
    return cues


def import_vtt(
    source_path: Path, paths: config.Paths, title: str | None = None
) -> tuple[Path, Path]:
    identity = source_identity(source_path, paths.inbox_dir, ".vtt")
    source_path = Path(identity["path"])
    cues = parse_vtt(source_path)
    turns = merge_cues_into_turns(cues)
    basename = naming.output_basename(source_path, title)
    metadata = {
        "output_basename": basename,
        "source_path": str(source_path),
        "source_type": "zoom_vtt",
        "recorded_at": datetime.fromtimestamp(identity["mtime_ns"] / 1e9, timezone.utc).isoformat(),
        "cues": [dict(cue) for cue in cues],
    }
    verify_source(source_path, paths.inbox_dir, ".vtt", identity)
    json_path, txt_path = write_output_files(paths.output_dir, basename, turns, metadata)
    delete_verified_source(source_path, paths.inbox_dir, ".vtt", identity)
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
