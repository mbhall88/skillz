import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import whisperx
import whisperx.diarize

from . import config, naming, voiceprints
from .audio_convert import convert_to_wav16k_mono
from .embedding_extraction import centroid_for_segments, load_pyannote_embedder
from .staging_builder import build_staging, longest_turns_for_speaker

DEVICE = "cpu"
COMPUTE_TYPE = "int8"
WHISPER_MODEL = "large-v3"
MAX_EMBEDDING_SPANS = 5


def run_pipeline(source_path: Path, paths: config.Paths, hf_token: str, title: str | None = None) -> Path:
    config.ensure_directories(paths)

    wav_path = paths.staging_dir / f"{source_path.stem}.wav"
    convert_to_wav16k_mono(source_path, wav_path)

    model = whisperx.load_model(WHISPER_MODEL, DEVICE, compute_type=COMPUTE_TYPE)
    audio = whisperx.load_audio(str(wav_path))
    transcription = model.transcribe(audio)

    align_model, align_metadata = whisperx.load_align_model(
        language_code=transcription["language"], device=DEVICE
    )
    aligned = whisperx.align(transcription["segments"], align_model, align_metadata, audio, DEVICE)

    diarize_model = whisperx.diarize.DiarizationPipeline(token=hf_token, device=DEVICE)
    diarize_segments = diarize_model(str(wav_path))
    result = whisperx.assign_word_speakers(diarize_segments, aligned, fill_nearest=True)

    words = [
        {
            "start": word["start"],
            "end": word["end"],
            "word": word["word"],
            "speaker": word.get("speaker", "SPEAKER_UNKNOWN"),
        }
        for segment in result["segments"]
        for word in segment["words"]
        if "start" in word and "end" in word and "speaker" in word
    ]

    embed_fn = load_pyannote_embedder(hf_token)
    raw_speakers = sorted({word["speaker"] for word in words})
    speaker_embeddings = {}
    for raw_label in raw_speakers:
        spans = [
            (turn["start"], turn["end"])
            for turn in longest_turns_for_speaker(words, raw_label, MAX_EMBEDDING_SPANS)
        ]
        speaker_embeddings[raw_label] = centroid_for_segments(embed_fn, wav_path, spans)

    voiceprint_db = voiceprints.load_voiceprints(paths.voiceprints_path)
    threshold = config.get_match_threshold()

    recording_id = naming.build_recording_id(source_path, title)
    duration_seconds = words[-1]["end"] if words else 0.0
    recorded_at = datetime.now(timezone.utc).isoformat()

    staging = build_staging(
        recording_id=recording_id,
        source_path=str(source_path),
        recorded_at=recorded_at,
        duration_seconds=duration_seconds,
        words=words,
        speaker_embeddings=speaker_embeddings,
        voiceprint_db=voiceprint_db,
        threshold=threshold,
    )

    staging_path = paths.staging_dir / f"{recording_id}.json"
    staging_path.write_text(json.dumps(staging, indent=2))
    wav_path.unlink(missing_ok=True)

    matched = sum(1 for s in staging["speakers"].values() if s["status"] == "matched")
    unmatched = len(staging["speakers"]) - matched
    print(f"Staged {staging_path} — {matched} speaker(s) matched, {unmatched} need disambiguation.")
    print(f"Match threshold in use: {threshold} (unvalidated default unless you've calibrated it).")

    return staging_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Transcribe, diarize, and stage a meeting recording.")
    parser.add_argument("audio_path")
    parser.add_argument("--title", default=None)
    args = parser.parse_args()

    hf_token = os.environ.get(config.HF_TOKEN_ENV_VAR)
    if not hf_token:
        raise SystemExit(f"{config.HF_TOKEN_ENV_VAR} environment variable is required")

    paths = config.get_paths()
    run_pipeline(Path(args.audio_path), paths, hf_token, args.title)


if __name__ == "__main__":
    main()
