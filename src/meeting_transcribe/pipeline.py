import argparse
import json
import os
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from . import config, naming, voiceprints
from .audio_convert import convert_to_wav16k_mono
from .embedding_extraction import centroid_for_segments, load_pyannote_embedder
from .source_files import source_identity, verify_source
from .staging_builder import build_staging

DEVICE = "cpu"
COMPUTE_TYPE = "int8"
WHISPER_MODEL = "large-v3"
DIARIZATION_MODEL = "pyannote/speaker-diarization-3.1"
MAX_EMBEDDING_SPANS = 5


def transcript_words(segments: list[dict]) -> list[dict]:
    """Retain segment text when word alignment is absent or incomplete."""
    def records(segment):
        aligned_words = segment.get("words") or []
        text = segment.get("text", "")
        represented = "".join(word["word"] for word in aligned_words)
        if text.strip() and "".join(text.split()) != "".join(represented.split()):
            return [{
                "start": segment["start"], "end": segment["end"], "word": text.strip(),
                "speaker": segment.get("speaker") or "SPEAKER_UNKNOWN",
                "timing": "segment",
            }]
        return [
            {
                **word,
                "start": word.get("start", segment["start"]),
                "end": word.get("end", segment["end"]),
                "speaker": word.get("speaker") or segment.get("speaker") or "SPEAKER_UNKNOWN",
                "timing": "word" if "start" in word and "end" in word else "segment",
            }
            for word in aligned_words
        ]

    return [word for segment in segments for word in records(segment)]


def run_pipeline(source_path: Path, paths: config.Paths, hf_token: str, title: str | None = None) -> Path:
    import whisperx
    import whisperx.diarize

    identity = source_identity(source_path, paths.inbox_dir, ".m4a")
    source_path = Path(identity["path"])
    basename = naming.output_basename(source_path, title)
    config.ensure_directories(paths)

    wav_path = paths.staging_dir / f"{source_path.stem}.wav"
    convert_to_wav16k_mono(source_path, wav_path)

    model = whisperx.load_model(WHISPER_MODEL, DEVICE, compute_type=COMPUTE_TYPE)
    audio = whisperx.load_audio(str(wav_path))
    transcription = model.transcribe(audio)

    align_model, align_metadata = whisperx.load_align_model(
        language_code=transcription["language"], device=DEVICE
    )
    aligned = whisperx.align(deepcopy(transcription["segments"]), align_model, align_metadata, audio, DEVICE)

    diarize_model = whisperx.diarize.DiarizationPipeline(
        model_name=DIARIZATION_MODEL, token=hf_token, device=DEVICE,
    )
    diarize_segments = diarize_model(str(wav_path))
    result = whisperx.assign_word_speakers(diarize_segments, deepcopy(aligned), fill_nearest=True)
    words = transcript_words(result["segments"])

    speech_spans = [
        span for span in diarize_segments.to_dict("records") if span["end"] > span["start"]
    ]
    diarized_labels = {span["speaker"] for span in speech_spans}
    raw_speakers = sorted({word["speaker"] for word in words} & diarized_labels)
    embed_fn = load_pyannote_embedder(hf_token) if raw_speakers else None
    speaker_embeddings = {}
    embedding_errors = {}
    for raw_label in raw_speakers:
        spans = [
            (span["start"], span["end"])
            for span in sorted(
                (span for span in speech_spans if span["speaker"] == raw_label),
                key=lambda span: span["end"] - span["start"], reverse=True,
            )[:MAX_EMBEDDING_SPANS]
        ]
        try:
            centroid = centroid_for_segments(embed_fn, wav_path, spans)
        except (ValueError, RuntimeError) as exc:
            centroid = None
            embedding_errors = {**embedding_errors, raw_label: str(exc)}
        speaker_embeddings = {**speaker_embeddings, raw_label: centroid}

    voiceprint_db = voiceprints.load_voiceprints(paths.voiceprints_path)
    threshold = config.get_match_threshold()

    recording_id = naming.build_recording_id(source_path, title)
    # whisperx.load_audio returns a mono waveform resampled to 16 kHz.
    duration_seconds = len(audio) / 16000
    recorded_at = datetime.fromtimestamp(identity["mtime_ns"] / 1e9, timezone.utc).isoformat()

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
    original_text = "".join(segment["text"] for segment in transcription["segments"])
    retained_text = "".join(word["word"] for word in words)
    staging = {
        **staging,
        "output_basename": basename,
        "source_identity": dict(identity),
        "transcription_segments": deepcopy(transcription["segments"]),
        "alignment_segments": deepcopy(result["segments"]),
        "embedding_errors": dict(embedding_errors),
        "transcript_complete": bool(original_text.strip()) and (
            "".join(original_text.split()) == "".join(retained_text.split())
        ),
    }

    verify_source(source_path, paths.inbox_dir, ".m4a", identity)
    staging_path = (paths.staging_dir / f"{recording_id}.json").resolve()
    with staging_path.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(staging, indent=2, allow_nan=False))
    wav_path.unlink(missing_ok=True)

    matched = sum(1 for s in staging["speakers"].values() if s["status"] == "matched")
    unmatched = len(staging["speakers"]) - matched
    print(f"Staged {staging_path} — {matched} speaker(s) matched, {unmatched} need disambiguation.")
    print(f"Match threshold in use: {threshold} (unvalidated default unless you've calibrated it).")
    for label in embedding_errors:
        print(f"No usable centroid for {label}; transcript retained for naming without enrollment.")
    if not staging["transcript_complete"]:
        print("Transcript completeness could not be verified; finalization is blocked and the source is retained.")

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
