import argparse
import os
from pathlib import Path

from . import config, voiceprints
from .embedding_extraction import EmbedFn, centroid_for_segments, load_pyannote_embedder


def enroll_from_audio(
    embed_fn: EmbedFn, audio_path: Path, duration_seconds: float, chunk_seconds: float = 5.0
) -> list[float]:
    spans = []
    start = 0.0
    while start < duration_seconds:
        end = min(start + chunk_seconds, duration_seconds)
        spans.append((start, end))
        start = end
    return centroid_for_segments(embed_fn, audio_path, spans)


def main() -> None:
    parser = argparse.ArgumentParser(description="Enroll a named voiceprint from a clean audio sample.")
    parser.add_argument("--name", required=True)
    parser.add_argument("--audio", required=True)
    args = parser.parse_args()

    hf_token = os.environ.get(config.HF_TOKEN_ENV_VAR)
    if not hf_token:
        raise SystemExit(f"{config.HF_TOKEN_ENV_VAR} environment variable is required")

    import torchaudio

    audio_path = Path(args.audio)
    info = torchaudio.info(str(audio_path))
    duration_seconds = info.num_frames / info.sample_rate

    embed_fn = load_pyannote_embedder(hf_token)
    embedding = enroll_from_audio(embed_fn, audio_path, duration_seconds)

    paths = config.get_paths()
    config.ensure_directories(paths)
    voiceprints.save_voiceprint(paths.voiceprints_path, args.name, embedding, source="enroll")
    print(f"Enrolled '{args.name}' from {audio_path} into {paths.voiceprints_path}")


if __name__ == "__main__":
    main()
