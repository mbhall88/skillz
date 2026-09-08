"""Synthetic ML boundaries only: no model imports, downloads or real audio."""

from copy import deepcopy
from datetime import datetime, timezone
import importlib
import json
import os
import subprocess
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest

from meeting_transcribe import config


@pytest.fixture
def run_synthetic_pipeline(tmp_path, monkeypatch):
    monkeypatch.setenv("MEETINGS_DIR", str(tmp_path / "meetings"))
    paths = config.get_paths()
    config.ensure_directories(paths)
    source = paths.inbox_dir / "recording.m4a"
    source.write_bytes(b"synthetic placeholder, never decoded")
    os.utime(source, (1799500000, 1799500000))

    def run(segments, spans=(), original_segments=None, title=None, crop_error=None):
        original = deepcopy(original_segments if original_segments is not None else segments)
        backend = ModuleType("whisperx")
        diarize = ModuleType("whisperx.diarize")
        frame = SimpleNamespace(to_dict=lambda orient: [dict(span) for span in spans])
        factory = Mock(return_value=lambda audio: frame)
        diarize.DiarizationPipeline = factory
        backend.diarize = diarize
        backend.load_model = Mock(return_value=SimpleNamespace(
            transcribe=lambda audio: {"language": "en", "segments": deepcopy(original)},
        ))
        backend.load_audio = lambda path: np.zeros(160000, dtype=np.float32)
        backend.load_align_model = lambda **kwargs: (object(), {})
        backend.align = lambda *args: {"segments": deepcopy(segments)}
        backend.assign_word_speakers = lambda frame, result, **kwargs: deepcopy(result)
        monkeypatch.setitem(sys.modules, "whisperx", backend)
        monkeypatch.setitem(sys.modules, "whisperx.diarize", diarize)
        monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: None)

        crop = Mock(return_value=np.array([1.0, 0.0]), side_effect=crop_error)
        monkeypatch.setitem(sys.modules, "pyannote.audio", SimpleNamespace(
            Model=SimpleNamespace(from_pretrained=lambda *args, **kwargs: object()),
            Inference=lambda *args, **kwargs: SimpleNamespace(crop=crop),
        ))
        monkeypatch.setitem(sys.modules, "pyannote.core", SimpleNamespace(Segment=lambda a, b: (a, b)))
        pipeline = importlib.import_module("meeting_transcribe.pipeline")
        if hasattr(pipeline, "whisperx"):
            monkeypatch.setattr(pipeline, "whisperx", backend)
        path = pipeline.run_pipeline(source, paths, "synthetic-token", title=title)
        return SimpleNamespace(
            staging=json.loads(path.read_text()), staging_path=path, source=source,
            paths=paths, crop=crop, diarization_factory=factory, backend=backend,
        )

    return run


def test_pipeline_preserves_unaligned_text_and_unattributed_or_untimed_words(run_synthetic_pipeline):
    segments = [
        {"start": 0.0, "end": 2.0, "text": "Lost alignment text.", "words": []},
        {"start": 4.0, "end": 6.0, "text": "Hello untimed", "words": [
            {"start": 4.0, "end": 5.0, "word": "Hello"},
            {"word": "untimed", "speaker": "SPEAKER_00"},
        ]},
    ]
    result = run_synthetic_pipeline(segments)
    words = result.staging["words"]
    assert " ".join(word["word"] for word in words) == "Lost alignment text. Hello untimed"
    assert [word["speaker"] for word in words] == ["SPEAKER_UNKNOWN", "SPEAKER_UNKNOWN", "SPEAKER_00"]
    assert words[0]["start"] == 0.0 and words[0]["end"] == 2.0
    assert words[2]["start"] == 4.0 and words[2]["end"] == 6.0
    assert result.staging["speakers"]["SPEAKER_UNKNOWN"]["centroid_embedding"] is None
    result.crop.assert_not_called()


def test_pipeline_uses_five_longest_separate_diarization_spans(run_synthetic_pipeline):
    spans = [
        {"start": start, "end": end, "speaker": "SPEAKER_00"}
        for start, end in [(0, 0.1), (1, 1.9), (3, 3.3), (4, 4.8), (6, 6.7), (8, 8.6)]
    ]
    segments = [{"start": 0, "end": 9, "text": "One Two", "words": [
        {"start": 0, "end": 0.1, "word": "One", "speaker": "SPEAKER_00"},
        {"start": 8, "end": 8.6, "word": "Two", "speaker": "SPEAKER_00"},
    ]}]
    result = run_synthetic_pipeline(segments, spans)
    assert [call.args[1] for call in result.crop.call_args_list] == [
        (1, 1.9), (4, 4.8), (6, 6.7), (8, 8.6), (3, 3.3),
    ]


def test_pipeline_explicitly_selects_approved_diarization_model(run_synthetic_pipeline):
    result = run_synthetic_pipeline([])
    result.diarization_factory.assert_called_once_with(
        model_name="pyannote/speaker-diarization-3.1", token="synthetic-token", device="cpu",
    )


def test_pipeline_records_loaded_duration_source_mtime_title_and_identity(run_synthetic_pipeline):
    result = run_synthetic_pipeline(
        [{"start": 1, "end": 2, "text": "Hello", "words": []}], title="Budget Review",
    )
    staged = result.staging
    assert staged["duration_seconds"] == 10.0
    assert staged["recorded_at"] == datetime.fromtimestamp(1799500000, timezone.utc).isoformat()
    assert staged["output_basename"].endswith("-budget-review")
    assert staged["source_path"] == str(result.source.resolve())
    assert staged["source_identity"]["ino"] == result.source.stat().st_ino
    assert result.staging_path.is_absolute()


@pytest.mark.parametrize("dropped", [False, True])
def test_pipeline_records_completeness_against_original_transcript(run_synthetic_pipeline, dropped):
    original = [
        {"start": 0, "end": 1, "text": "Retained", "words": []},
        {"start": 2, "end": 3, "text": "Last sentence", "words": []},
    ]
    result = run_synthetic_pipeline(original[:1] if dropped else original, original_segments=original)
    assert result.staging["transcript_complete"] is (not dropped)
    assert result.staging["transcription_segments"] == original
    assert result.source.exists()


def test_unembeddable_speaker_can_be_named_without_enrollment(run_synthetic_pipeline):
    from meeting_transcribe.finalize import finalize

    segments = [{"start": 0, "end": 1, "text": "Hello", "speaker": "SPEAKER_00", "words": []}]
    result = run_synthetic_pipeline(
        segments, [{"start": 0, "end": 1, "speaker": "SPEAKER_00"}],
        title="Budget Review", crop_error=ValueError("span cannot be embedded"),
    )
    assert result.staging["speakers"]["SPEAKER_00"]["centroid_embedding"] is None
    resolutions = result.staging_path.with_suffix(".resolutions.json")
    resolutions.write_text(json.dumps({"SPEAKER_00": {"name": "Bob", "enroll": False}}))
    json_path, txt_path = finalize(result.staging_path, resolutions, result.paths)
    assert txt_path.read_text() == "Bob: Hello\n"
    assert json.loads(json_path.read_text())["transcription_segments"] == segments
    assert json_path.name.endswith("-budget-review.json")
    assert not result.paths.voiceprints_path.exists()
    assert not result.source.exists()
