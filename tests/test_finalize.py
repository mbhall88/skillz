import json
from pathlib import Path

import pytest

from meeting_transcribe import config, finalize, voiceprints


def _staging(source_path: Path) -> dict:
    return {
        "recording_id": "team-standup-1799500000",
        "source_path": str(source_path),
        "recorded_at": "2026-09-07T09:00:00+10:00",
        "duration_seconds": 4.0,
        "words": [
            {"start": 0.0, "end": 0.5, "word": "Hi", "speaker": "SPEAKER_00"},
            {"start": 1.0, "end": 1.5, "word": "Hello", "speaker": "SPEAKER_01"},
        ],
        "speakers": {
            "SPEAKER_00": {"status": "matched", "name": "Alice", "score": 0.9},
            "SPEAKER_01": {
                "status": "unmatched",
                "best_guess": None,
                "score": 0.4,
                "centroid_embedding": [0.0, 1.0],
                "snippets": [{"start": 1.0, "end": 1.5, "text": "Hello"}],
            },
        },
    }


def _write_staging_and_resolutions(tmp_path, resolutions):
    source = tmp_path / "inbox" / "Team Standup.m4a"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"fake")

    staging_path = tmp_path / "staging" / "team-standup-1799500000.json"
    staging_path.parent.mkdir(parents=True)
    staging_path.write_text(json.dumps(_staging(source)))

    resolutions_path = tmp_path / "staging" / "team-standup-1799500000.resolutions.json"
    resolutions_path.write_text(json.dumps(resolutions))

    return source, staging_path, resolutions_path


def test_apply_resolutions_uses_matched_name_and_resolution_name():
    staging = _staging(Path("/tmp/x.m4a"))
    labels = finalize.apply_resolutions(staging, {"SPEAKER_01": {"name": "Bob", "enroll": True}})
    assert labels == {"SPEAKER_00": "Alice", "SPEAKER_01": "Bob"}


def test_apply_resolutions_falls_back_to_raw_label_when_unknown():
    staging = _staging(Path("/tmp/x.m4a"))
    labels = finalize.apply_resolutions(staging, {"SPEAKER_01": {"name": None, "enroll": False}})
    assert labels == {"SPEAKER_00": "Alice", "SPEAKER_01": "SPEAKER_01"}


def test_finalize_writes_output_enrolls_and_cleans_up(tmp_path, monkeypatch):
    monkeypatch.setenv("MEETINGS_DIR", str(tmp_path / "meetings"))
    paths = config.get_paths()
    config.ensure_directories(paths)

    source, staging_path, resolutions_path = _write_staging_and_resolutions(
        tmp_path, {"SPEAKER_01": {"name": "Bob", "enroll": True}}
    )
    staging = json.loads(staging_path.read_text())
    staging["source_path"] = str(source)
    staging_path.write_text(json.dumps(staging))

    json_path, txt_path = finalize.finalize(staging_path, resolutions_path, paths)

    assert json_path.parent == paths.output_dir
    assert "Alice: Hi" in txt_path.read_text()
    assert "Bob: Hello" in txt_path.read_text()

    db = voiceprints.load_voiceprints(paths.voiceprints_path)
    assert db["Bob"]["embedding"] == [0.0, 1.0]
    assert db["Bob"]["source"] == "session"

    assert not source.exists()
    assert not staging_path.exists()
    assert not resolutions_path.exists()


def test_finalize_leaves_generic_label_when_resolution_says_dont_know(tmp_path, monkeypatch):
    monkeypatch.setenv("MEETINGS_DIR", str(tmp_path / "meetings"))
    paths = config.get_paths()
    config.ensure_directories(paths)

    source, staging_path, resolutions_path = _write_staging_and_resolutions(
        tmp_path, {"SPEAKER_01": {"name": None, "enroll": False}}
    )
    staging = json.loads(staging_path.read_text())
    staging["source_path"] = str(source)
    staging_path.write_text(json.dumps(staging))

    _, txt_path = finalize.finalize(staging_path, resolutions_path, paths)

    assert "SPEAKER_01: Hello" in txt_path.read_text()
    db = voiceprints.load_voiceprints(paths.voiceprints_path)
    assert "Bob" not in db


def test_finalize_leaves_source_and_staging_in_place_on_write_failure(tmp_path, monkeypatch):
    monkeypatch.setenv("MEETINGS_DIR", str(tmp_path / "meetings"))
    paths = config.get_paths()
    config.ensure_directories(paths)

    source, staging_path, resolutions_path = _write_staging_and_resolutions(
        tmp_path, {"SPEAKER_01": {"name": "Bob", "enroll": True}}
    )
    staging = json.loads(staging_path.read_text())
    staging["source_path"] = str(source)
    staging_path.write_text(json.dumps(staging))

    def boom(*args, **kwargs):
        raise RuntimeError("disk full")

    monkeypatch.setattr(finalize, "write_output_files", boom)

    with pytest.raises(RuntimeError):
        finalize.finalize(staging_path, resolutions_path, paths)

    assert source.exists()
    assert staging_path.exists()
    assert resolutions_path.exists()


def test_finalize_leaves_source_and_staging_in_place_on_enrollment_failure(tmp_path, monkeypatch):
    monkeypatch.setenv("MEETINGS_DIR", str(tmp_path / "meetings"))
    paths = config.get_paths()
    config.ensure_directories(paths)

    source, staging_path, resolutions_path = _write_staging_and_resolutions(
        tmp_path, {"SPEAKER_01": {"name": "Bob", "enroll": True}}
    )
    staging = json.loads(staging_path.read_text())
    staging["source_path"] = str(source)
    staging_path.write_text(json.dumps(staging))

    def boom(*args, **kwargs):
        raise RuntimeError("disk full")

    monkeypatch.setattr(voiceprints, "save_voiceprint", boom)

    with pytest.raises(RuntimeError):
        finalize.finalize(staging_path, resolutions_path, paths)

    assert source.exists()
    assert staging_path.exists()
    assert resolutions_path.exists()


def test_finalize_uses_name_but_does_not_enroll_when_enroll_is_false(tmp_path, monkeypatch):
    monkeypatch.setenv("MEETINGS_DIR", str(tmp_path / "meetings"))
    paths = config.get_paths()
    config.ensure_directories(paths)

    source, staging_path, resolutions_path = _write_staging_and_resolutions(
        tmp_path, {"SPEAKER_01": {"name": "Bob", "enroll": False}}
    )
    staging = json.loads(staging_path.read_text())
    staging["source_path"] = str(source)
    staging_path.write_text(json.dumps(staging))

    _, txt_path = finalize.finalize(staging_path, resolutions_path, paths)

    assert "Bob: Hello" in txt_path.read_text()
    db = voiceprints.load_voiceprints(paths.voiceprints_path)
    assert "Bob" not in db
