import argparse
import json
from pathlib import Path

from . import config, voiceprints
from .output_writer import merge_words_into_turns, write_output_files
from .source_files import delete_verified_source, verify_source


def apply_resolutions(staging: dict, resolutions: dict) -> dict[str, str]:
    unmatched = {label for label, info in staging["speakers"].items() if info["status"] == "unmatched"}
    if not isinstance(resolutions, dict) or set(resolutions) != unmatched:
        raise ValueError("Resolutions must contain exactly one explicit entry per unmatched speaker")
    for raw_label, info in staging["speakers"].items():
        if info["status"] == "matched":
            continue
        resolution = resolutions.get(raw_label)
        if not isinstance(resolution, dict) or not {"name", "enroll"} <= resolution.keys():
            raise ValueError(f"Resolution for {raw_label} must specify name and enroll")
        name, enroll = resolution["name"], resolution["enroll"]
        if name is not None and (not isinstance(name, str) or not name.strip()):
            raise ValueError(f"Resolution name for {raw_label} must be null or a non-empty string")
        if type(enroll) is not bool or (enroll and name is None):
            raise ValueError(f"Resolution enroll for {raw_label} must be a boolean and requires a name")
        if enroll and not voiceprints.is_usable_embedding(info.get("centroid_embedding")):
            raise ValueError(f"Cannot enroll {raw_label} without a usable centroid")
    return {
        label: info["name"] if info["status"] == "matched" else resolutions[label]["name"] or label
        for label, info in staging["speakers"].items()
    }


def finalize(staging_path: Path, resolutions_path: Path, paths: config.Paths) -> tuple[Path, Path]:
    staging = json.loads(staging_path.read_text())
    resolutions = json.loads(resolutions_path.read_text())

    source_path = Path(staging["source_path"])
    verify_source(source_path, paths.inbox_dir, ".m4a", staging.get("source_identity"))
    if staging.get("transcript_complete") is not True:
        raise ValueError("Transcript is not verified complete; retain source and restage it")

    labels = apply_resolutions(staging, resolutions)
    words = [
        {**word, "raw_speaker": word["speaker"], "speaker": labels[word["speaker"]]}
        for word in staging["words"]
    ]
    turns = merge_words_into_turns(words)

    basename = staging["output_basename"]
    metadata = {
        "recording_id": staging["recording_id"],
        "output_basename": basename,
        "source_path": staging["source_path"],
        "source_type": "audio",
        "recorded_at": staging["recorded_at"],
        "duration_seconds": staging["duration_seconds"],
        "transcript_complete": True,
        "transcription_segments": staging.get("transcription_segments"),
        "alignment_segments": staging.get("alignment_segments"),
        "embedding_errors": staging.get("embedding_errors", {}),
    }

    json_path, txt_path = write_output_files(
        paths.output_dir, basename, turns, metadata, words=words
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

    delete_verified_source(source_path, paths.inbox_dir, ".m4a", staging["source_identity"])
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
