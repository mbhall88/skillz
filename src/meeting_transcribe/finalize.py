import argparse
import json
from pathlib import Path

from . import config, naming, voiceprints
from .output_writer import merge_words_into_turns, write_output_files


def apply_resolutions(staging: dict, resolutions: dict) -> dict[str, str]:
    labels: dict[str, str] = {}
    for raw_label, info in staging["speakers"].items():
        if info["status"] == "matched":
            labels[raw_label] = info["name"]
            continue
        resolution = resolutions.get(raw_label)
        name = resolution["name"] if resolution else None
        labels[raw_label] = name if name else raw_label
    return labels


def finalize(staging_path: Path, resolutions_path: Path, paths: config.Paths) -> tuple[Path, Path]:
    staging = json.loads(staging_path.read_text())
    resolutions = json.loads(resolutions_path.read_text()) if resolutions_path.exists() else {}

    labels = apply_resolutions(staging, resolutions)
    turns = merge_words_into_turns(staging["words"], labels)

    source_path = Path(staging["source_path"])
    basename = naming.output_basename(source_path)
    metadata = {
        "recording_id": staging["recording_id"],
        "source_path": staging["source_path"],
        "source_type": "audio",
        "recorded_at": staging["recorded_at"],
        "duration_seconds": staging["duration_seconds"],
    }

    json_path, txt_path = write_output_files(
        paths.output_dir, basename, turns, metadata, words=staging["words"]
    )

    for raw_label, info in staging["speakers"].items():
        if info["status"] != "unmatched":
            continue
        resolution = resolutions.get(raw_label)
        if resolution and resolution.get("name") and resolution.get("enroll"):
            voiceprints.save_voiceprint(
                paths.voiceprints_path,
                resolution["name"],
                info["centroid_embedding"],
                source="session",
            )

    if source_path.exists():
        source_path.unlink()
    staging_path.unlink()
    if resolutions_path.exists():
        resolutions_path.unlink()

    return json_path, txt_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply speaker resolutions and finalize a transcript.")
    parser.add_argument("--staging", required=True)
    parser.add_argument("--resolutions", required=True)
    args = parser.parse_args()

    paths = config.get_paths()
    json_path, txt_path = finalize(Path(args.staging), Path(args.resolutions), paths)
    print(f"Wrote {json_path} and {txt_path}")


if __name__ == "__main__":
    main()
