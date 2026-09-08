from functools import lru_cache
from pathlib import Path
from typing import Callable

from . import voiceprints

EmbedFn = Callable[[Path, float, float], list[float]]


def load_pyannote_embedder(hf_token: str) -> EmbedFn:
    """Loads pyannote/embedding and returns a callable that embeds one
    (start, end) span of an audio file. The API contract is tested offline;
    real model execution requires the gated model."""
    from pyannote.audio import Inference, Model

    model = Model.from_pretrained("pyannote/embedding", token=hf_token)
    inference = Inference(model, window="whole")

    @lru_cache(maxsize=4)
    def load_waveform(audio_path_str: str):
        import soundfile
        import torch

        data, sample_rate = soundfile.read(audio_path_str, dtype="float32", always_2d=True)
        return torch.from_numpy(data.T), sample_rate

    def embed(audio_path: Path, start: float, end: float) -> list[float]:
        from pyannote.core import Segment

        # Pass a preloaded waveform rather than a file path: pyannote's
        # crop() otherwise requires torchcodec, which is unavailable in
        # this environment (see docs/dependency-compatibility.md). soundfile
        # is used instead of torchaudio.load() because torchaudio has no
        # working backend here either (no torchcodec, no soundfile backend).
        waveform, sample_rate = load_waveform(str(audio_path))
        embedding = inference.crop(
            {"waveform": waveform, "sample_rate": sample_rate}, Segment(start, end)
        )
        return embedding.tolist()

    return embed


def centroid_for_segments(
    embed_fn: EmbedFn, audio_path: Path, spans: list[tuple[float, float]]
) -> list[float]:
    embeddings = [embed_fn(audio_path, start, end) for start, end in spans]
    return voiceprints.compute_centroid(embeddings)
