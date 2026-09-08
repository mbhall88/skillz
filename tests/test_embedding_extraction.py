from pathlib import Path
import sys
from types import SimpleNamespace

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
    monkeypatch.setitem(sys.modules, "torchaudio", SimpleNamespace(
        load=lambda path: (object(), 16000),
    ))
    embed = embedding_extraction.load_pyannote_embedder("synthetic-token")
    assert embed(Path("synthetic.wav"), 0.0, 1.0) == [1.0, 0.0]


def test_embed_passes_preloaded_waveform_not_a_bare_path(monkeypatch):
    # pyannote's Inference.crop() requires torchcodec to decode a bare file
    # path, and torchcodec can be unavailable (missing/mismatched ffmpeg
    # libs). Passing a preloaded {"waveform", "sample_rate"} dict avoids
    # that dependency entirely.
    sentinel_waveform = object()
    crop_calls = []

    def inference(model, *, window):
        return SimpleNamespace(crop=lambda file, span: crop_calls.append(file) or SimpleNamespace(tolist=lambda: [0.0]))

    monkeypatch.setitem(sys.modules, "pyannote.audio", SimpleNamespace(
        Model=SimpleNamespace(from_pretrained=lambda *a, **k: object()), Inference=inference,
    ))
    monkeypatch.setitem(sys.modules, "pyannote.core", SimpleNamespace(Segment=lambda start, end: (start, end)))
    monkeypatch.setitem(sys.modules, "torchaudio", SimpleNamespace(
        load=lambda path: (sentinel_waveform, 16000),
    ))
    embed = embedding_extraction.load_pyannote_embedder("synthetic-token")
    embed(Path("synthetic.wav"), 0.0, 1.0)
    assert crop_calls == [{"waveform": sentinel_waveform, "sample_rate": 16000}]


def test_embed_loads_waveform_once_per_audio_path(monkeypatch):
    load_calls = []

    def fake_load(path):
        load_calls.append(path)
        return (object(), 16000)

    monkeypatch.setitem(sys.modules, "pyannote.audio", SimpleNamespace(
        Model=SimpleNamespace(from_pretrained=lambda *a, **k: object()),
        Inference=lambda model, *, window: SimpleNamespace(
            crop=lambda file, span: SimpleNamespace(tolist=lambda: [0.0])
        ),
    ))
    monkeypatch.setitem(sys.modules, "pyannote.core", SimpleNamespace(Segment=lambda start, end: (start, end)))
    monkeypatch.setitem(sys.modules, "torchaudio", SimpleNamespace(load=fake_load))
    embed = embedding_extraction.load_pyannote_embedder("synthetic-token")
    embed(Path("synthetic.wav"), 0.0, 1.0)
    embed(Path("synthetic.wav"), 1.0, 2.0)
    assert load_calls == ["synthetic.wav"]
