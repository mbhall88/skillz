import re

from . import voiceprints as vp
from .output_writer import merge_words_into_turns

_GUESS_PATTERNS = [
    re.compile(r"\bit'?s\s+([A-Z][a-z]+)\b", re.IGNORECASE),
    re.compile(r"\bthis\s+is\s+([A-Z][a-z]+)\b", re.IGNORECASE),
]


def guess_name_from_text(text: str) -> str | None:
    for pattern in _GUESS_PATTERNS:
        match = pattern.search(text)
        if match:
            return match.group(1).capitalize()
    return None


def longest_turns_for_speaker(words: list[dict], speaker: str, max_n: int) -> list[dict]:
    turns = [turn for turn in merge_words_into_turns(words) if turn["speaker"] == speaker]
    turns.sort(key=lambda turn: turn["end"] - turn["start"], reverse=True)
    return turns[:max_n]


def select_snippets(words: list[dict], speaker: str, max_snippets: int = 3) -> list[dict]:
    turns = longest_turns_for_speaker(words, speaker, max_snippets)
    return [{"start": t["start"], "end": t["end"], "text": t["text"]} for t in turns]


def build_staging(
    recording_id: str,
    source_path: str,
    recorded_at: str,
    duration_seconds: float,
    words: list[dict],
    speaker_embeddings: dict[str, list[float]],
    voiceprint_db: dict,
    threshold: float,
) -> dict:
    speakers_out: dict = {}
    for raw_label, embedding in speaker_embeddings.items():
        name, score = vp.match_speaker(embedding, voiceprint_db, threshold)
        if name is not None:
            speakers_out[raw_label] = {"status": "matched", "name": name, "score": score}
            continue

        snippets = select_snippets(words, raw_label)
        guess = None
        for snippet in snippets:
            guess = guess_name_from_text(snippet["text"])
            if guess:
                break
        speakers_out[raw_label] = {
            "status": "unmatched",
            "best_guess": guess,
            "score": score,
            "centroid_embedding": embedding,
            "snippets": snippets,
        }

    return {
        "recording_id": recording_id,
        "source_path": source_path,
        "recorded_at": recorded_at,
        "duration_seconds": duration_seconds,
        "words": words,
        "speakers": speakers_out,
    }
