from pathlib import Path
from typing import Callable

from . import voiceprints

EmbedFn = Callable[[Path, float, float], list[float]]


def load_pyannote_embedder(hf_token: str) -> EmbedFn:
    """Loads pyannote/embedding and returns a callable that embeds one
    (start, end) span of an audio file. Not unit tested — requires the real
    gated model; verify manually per the README setup steps."""
    from pyannote.audio import Inference

    inference = Inference("pyannote/embedding", window="whole", use_auth_token=hf_token)

    def embed(audio_path: Path, start: float, end: float) -> list[float]:
        from pyannote.core import Segment

        embedding = inference.crop(str(audio_path), Segment(start, end))
        return embedding.tolist()

    return embed


def centroid_for_segments(
    embed_fn: EmbedFn, audio_path: Path, spans: list[tuple[float, float]]
) -> list[float]:
    embeddings = [embed_fn(audio_path, start, end) for start, end in spans]
    return voiceprints.compute_centroid(embeddings)
