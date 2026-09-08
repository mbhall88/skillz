import json
import os
from contextlib import ExitStack
from itertools import groupby
from pathlib import Path


def merge_words_into_turns(
    words: list[dict], speaker_labels: dict[str, str] | None = None
) -> list[dict]:
    return _merge_entries(words, "word", speaker_labels or {})


def merge_cues_into_turns(cues: list[dict]) -> list[dict]:
    return _merge_entries(cues, "text", {})


def _merge_entries(entries: list[dict], text_key: str, labels: dict[str, str]) -> list[dict]:
    def turn(label, records):
        return {
            "start": min(record["start"] for record in records),
            "end": max(record["end"] for record in records),
            "speaker": label,
            "text": " ".join(record[text_key] for record in records),
        }

    return [
        turn(label, tuple(group))
        for label, group in groupby(entries, key=lambda entry: labels.get(entry["speaker"], entry["speaker"]))
    ]


def write_output_files(
    output_dir: Path,
    basename: str,
    turns: list[dict],
    metadata: dict,
    words: list[dict] | None = None,
) -> tuple[Path, Path]:
    if not basename or Path(basename).name != basename or basename in {".", ".."}:
        raise ValueError("Output basename must be a single filename")
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{basename}.json"
    txt_path = output_dir / f"{basename}.txt"

    for path in (json_path, txt_path):
        if path.exists() or path.is_symlink():
            raise FileExistsError(f"Output already exists: {path}")

    payload = json.dumps({**metadata, "turns": turns, "words": words}, indent=2, allow_nan=False)
    transcript = (
        "\n\n".join(f"{turn['speaker']}: {turn['text']}" for turn in turns) + "\n"
        if turns
        else ""
    )

    created = ()
    try:
        with ExitStack() as stack:
            # Exclusive creation also protects against a collision after preflight.
            json_file = stack.enter_context(json_path.open("x", encoding="utf-8"))
            created = (*created, (json_path, os.fstat(json_file.fileno())))
            txt_file = stack.enter_context(txt_path.open("x", encoding="utf-8"))
            created = (*created, (txt_path, os.fstat(txt_file.fileno())))
            json_file.write(payload)
            txt_file.write(transcript)
            for stream in (json_file, txt_file):
                stream.flush()
                os.fsync(stream.fileno())
    except BaseException:
        # Remove only this attempt's incomplete files, never an earlier output.
        for path, identity in created:
            if path.exists() and path.lstat().st_ino == identity.st_ino:
                path.unlink()
        raise

    return json_path, txt_path
