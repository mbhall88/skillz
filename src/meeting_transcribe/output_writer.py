import json
from pathlib import Path


def merge_words_into_turns(
    words: list[dict], speaker_labels: dict[str, str] | None = None
) -> list[dict]:
    speaker_labels = speaker_labels or {}
    turns: list[dict] = []
    for word in words:
        label = speaker_labels.get(word["speaker"], word["speaker"])
        if turns and turns[-1]["speaker"] == label:
            turns[-1]["end"] = word["end"]
            turns[-1]["text"] += f" {word['word']}"
        else:
            turns.append(
                {
                    "start": word["start"],
                    "end": word["end"],
                    "speaker": label,
                    "text": word["word"],
                }
            )
    return turns


def merge_cues_into_turns(cues: list[dict]) -> list[dict]:
    turns: list[dict] = []
    for cue in cues:
        if turns and turns[-1]["speaker"] == cue["speaker"]:
            turns[-1]["end"] = cue["end"]
            turns[-1]["text"] += f" {cue['text']}"
        else:
            turns.append(dict(cue))
    return turns


def write_output_files(
    output_dir: Path,
    basename: str,
    turns: list[dict],
    metadata: dict,
    words: list[dict] | None = None,
) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{basename}.json"
    txt_path = output_dir / f"{basename}.txt"

    payload = {**metadata, "turns": turns, "words": words}
    json_path.write_text(json.dumps(payload, indent=2))

    txt_path.write_text(
        "\n\n".join(f"{turn['speaker']}: {turn['text']}" for turn in turns) + "\n"
        if turns
        else ""
    )

    return json_path, txt_path
