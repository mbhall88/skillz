from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
import torch

from meeting_transcribe import embedding_extraction, voiceprints


def test_centroid_for_segments_embeds_each_span_and_centroids():
    calls = []

    def fake_embed(path: Path, start: float, end: float) -> list[float]:
        calls.append((start, end))
        return [start, end, 1.0]

    spans = [(0.0, 5.0), (5.0, 10.0)]
    result = embedding_extraction.centroid_for_segments(fake_embed, Path("dummy.wav"), spans)

    expected = voiceprints.compute_centroid([[0.0, 5.0, 1.0], [5.0, 10.0, 1.0]])
    assert result == expected
    assert calls == spans


def test_embedder_loads_model_before_constructing_inference(monkeypatch):
    loaded_model = object()

    def from_pretrained(checkpoint, *, token):
        assert (checkpoint, token) == ("pyannote/embedding", "synthetic-token")
        return loaded_model

    def inference(model, *, window):
        assert model is loaded_model and window == "whole"
        return SimpleNamespace(crop=lambda file, span: SimpleNamespace(tolist=lambda: [1.0, 0.0]))

    monkeypatch.setitem(sys.modules, "pyannote.audio", SimpleNamespace(
        Model=SimpleNamespace(from_pretrained=from_pretrained), Inference=inference,
    ))
    monkeypatch.setitem(sys.modules, "pyannote.core", SimpleNamespace(Segment=lambda start, end: (start, end)))
    monkeypatch.setitem(sys.modules, "soundfile", SimpleNamespace(
        read=lambda path, dtype=None, always_2d=None: (np.zeros((1, 1), dtype=np.float32), 16000),
    ))
    embed = embedding_extraction.load_pyannote_embedder("synthetic-token")
    assert embed(Path("synthetic.wav"), 0.0, 1.0) == [1.0, 0.0]


def test_embed_passes_preloaded_waveform_not_a_bare_path(monkeypatch):
    # pyannote's Inference.crop() requires torchcodec to decode a bare file
    # path, and torchcodec can be unavailable (missing/mismatched ffmpeg
    # libs), and torchaudio.load() has no working backend either in that
    # case. Passing a preloaded {"waveform", "sample_rate"} dict read via
    # soundfile avoids both dependencies entirely.
    crop_calls = []

    def inference(model, *, window):
        return SimpleNamespace(crop=lambda file, span: crop_calls.append(file) or SimpleNamespace(tolist=lambda: [0.0]))

    monkeypatch.setitem(sys.modules, "pyannote.audio", SimpleNamespace(
        Model=SimpleNamespace(from_pretrained=lambda *a, **k: object()), Inference=inference,
    ))
    monkeypatch.setitem(sys.modules, "pyannote.core", SimpleNamespace(Segment=lambda start, end: (start, end)))
    fake_samples = np.array([[0.1], [0.2], [0.3]], dtype=np.float32)  # (time, channels)
    monkeypatch.setitem(sys.modules, "soundfile", SimpleNamespace(
        read=lambda path, dtype=None, always_2d=None: (fake_samples, 16000),
    ))
    embed = embedding_extraction.load_pyannote_embedder("synthetic-token")
    embed(Path("synthetic.wav"), 0.0, 1.0)
    assert len(crop_calls) == 1
    assert crop_calls[0]["sample_rate"] == 16000
    assert torch.equal(crop_calls[0]["waveform"], torch.from_numpy(fake_samples.T))


def test_embed_loads_waveform_once_per_audio_path(monkeypatch):
    load_calls = []

    def fake_read(path, dtype=None, always_2d=None):
        load_calls.append(path)
        return (np.zeros((1, 1), dtype=np.float32), 16000)

    monkeypatch.setitem(sys.modules, "pyannote.audio", SimpleNamespace(
        Model=SimpleNamespace(from_pretrained=lambda *a, **k: object()),
        Inference=lambda model, *, window: SimpleNamespace(
            crop=lambda file, span: SimpleNamespace(tolist=lambda: [0.0])
        ),
    ))
    monkeypatch.setitem(sys.modules, "pyannote.core", SimpleNamespace(Segment=lambda start, end: (start, end)))
    monkeypatch.setitem(sys.modules, "soundfile", SimpleNamespace(read=fake_read))
    embed = embedding_extraction.load_pyannote_embedder("synthetic-token")
    embed(Path("synthetic.wav"), 0.0, 1.0)
    embed(Path("synthetic.wav"), 1.0, 2.0)
    assert load_calls == ["synthetic.wav"]
