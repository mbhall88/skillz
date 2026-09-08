import json
from pathlib import Path

import pytest

from meeting_transcribe import config, finalize, naming, voiceprints


def _staging(source_path: Path) -> dict:
    stat = source_path.stat() if source_path.exists() else None
    return {
        "recording_id": "team-standup-1799500000",
        "source_path": str(source_path),
        "source_identity": {
            "path": str(source_path.resolve()),
            **{key: getattr(stat, f"st_{key}") for key in
               ("dev", "ino", "size", "mtime_ns", "ctime_ns")},
        } if stat else None,
        "output_basename": naming.output_basename(source_path) if stat else "meeting",
        "transcript_complete": True,
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
    source = tmp_path / "meetings" / "inbox" / "Team Standup.m4a"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"fake")

    staging_path = tmp_path / "meetings" / ".staging" / "team-standup-1799500000.json"
    staging_path.parent.mkdir(parents=True, exist_ok=True)
    staging_path.write_text(json.dumps(_staging(source)))

    resolutions_path = staging_path.with_suffix(".resolutions.json")
    resolutions_path.write_text(json.dumps(resolutions))

    return source, staging_path, resolutions_path


@pytest.mark.parametrize("unsafe", ["outside", "sibling", "symlink", "extension", "changed", "identity_missing"])
def test_finalize_rejects_unsafe_or_stale_source_before_writes(tmp_path, monkeypatch, unsafe):
    monkeypatch.setenv("MEETINGS_DIR", str(tmp_path / "meetings"))
    paths = config.get_paths()
    source, staged, resolutions = _write_staging_and_resolutions(
        tmp_path, {"SPEAKER_01": {"name": "Bob", "enroll": True}}
    )
    original = json.loads(staged.read_text())
    if unsafe in {"outside", "sibling", "extension"}:
        target = {
            "outside": tmp_path / "unrelated.m4a",
            "sibling": paths.meetings_dir / "inbox-other" / "unrelated.m4a",
            "extension": paths.inbox_dir / "unrelated.txt",
        }[unsafe]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"unrelated")
        staged.write_text(json.dumps(_staging(target)))
    elif unsafe == "symlink":
        target = tmp_path / "unrelated.m4a"
        target.write_bytes(b"unrelated")
        source.unlink()
        source.symlink_to(target)
    elif unsafe == "changed":
        source.write_bytes(b"replacement recording")
        target = source
    else:
        staged.write_text(json.dumps({k: v for k, v in original.items() if k != "source_identity"}))
        target = source

    with pytest.raises(ValueError, match="[Ss]ource"):
        finalize.finalize(staged, resolutions, paths)

    assert source.exists() and target.exists() and staged.exists() and resolutions.exists()
    assert not paths.output_dir.exists()
    assert not paths.voiceprints_path.exists()


def test_finalize_rechecks_source_after_output_before_deletion(tmp_path, monkeypatch):
    monkeypatch.setenv("MEETINGS_DIR", str(tmp_path / "meetings"))
    paths = config.get_paths()
    source, staged, resolutions = _write_staging_and_resolutions(
        tmp_path, {"SPEAKER_01": {"name": None, "enroll": False}}
    )
    writer = finalize.write_output_files

    def replace_during_write(*args, **kwargs):
        outputs = writer(*args, **kwargs)
        source.write_bytes(b"changed during finalization")
        return outputs

    monkeypatch.setattr(finalize, "write_output_files", replace_during_write)
    with pytest.raises(ValueError, match="[Ss]ource"):
        finalize.finalize(staged, resolutions, paths)
    assert source.read_bytes() == b"changed during finalization"
    assert staged.exists() and resolutions.exists()


@pytest.mark.parametrize("resolutions", [
    {}, {"SPEAKER_01": None}, {"SPEAKER_01": {}},
    {"SPEAKER_01": {"name": "Bob", "enroll": "false"}},
    {"SPEAKER_01": {"name": "Bob", "enroll": 1}},
    {"SPEAKER_01": {"name": "Bob"}},
    {"SPEAKER_01": {"enroll": False}},
    {"SPEAKER_01": {"name": " ", "enroll": False}},
    {"SPEAKER_01": {"name": 42, "enroll": False}},
    {"SPEAKER_01": {"name": None, "enroll": True}},
    [],
])
def test_finalize_requires_explicit_valid_resolutions_before_any_writes(tmp_path, monkeypatch, resolutions):
    monkeypatch.setenv("MEETINGS_DIR", str(tmp_path / "meetings"))
    paths = config.get_paths()
    source, staged, resolved = _write_staging_and_resolutions(tmp_path, resolutions)
    with pytest.raises(ValueError, match="[Rr]esolution"):
        finalize.finalize(staged, resolved, paths)
    assert source.exists() and staged.exists() and resolved.exists()
    assert not paths.output_dir.exists() and not paths.voiceprints_path.exists()


def test_finalize_requires_resolutions_file(tmp_path, monkeypatch):
    monkeypatch.setenv("MEETINGS_DIR", str(tmp_path / "meetings"))
    source, staged, resolved = _write_staging_and_resolutions(tmp_path, {})
    resolved.unlink()
    with pytest.raises(FileNotFoundError):
        finalize.finalize(staged, resolved, config.get_paths())
    assert source.exists() and staged.exists()


def test_finalize_rejects_enrollment_without_centroid_before_output(tmp_path, monkeypatch):
    monkeypatch.setenv("MEETINGS_DIR", str(tmp_path / "meetings"))
    paths = config.get_paths()
    source, staged, resolved = _write_staging_and_resolutions(
        tmp_path, {"SPEAKER_01": {"name": "Bob", "enroll": True}}
    )
    original = json.loads(staged.read_text())
    staged.write_text(json.dumps({**original, "speakers": {
        **original["speakers"], "SPEAKER_01": {
            **original["speakers"]["SPEAKER_01"], "centroid_embedding": None,
        },
    }}))
    with pytest.raises(ValueError, match="centroid"):
        finalize.finalize(staged, resolved, paths)
    assert source.exists() and staged.exists() and resolved.exists()
    assert not paths.output_dir.exists() and not paths.voiceprints_path.exists()


def test_finalize_uses_staged_title_and_resolves_copied_word_labels(tmp_path, monkeypatch):
    monkeypatch.setenv("MEETINGS_DIR", str(tmp_path / "meetings"))
    paths = config.get_paths()
    _, staged, resolved = _write_staging_and_resolutions(
        tmp_path, {"SPEAKER_01": {"name": "Bob", "enroll": False}}
    )
    original = json.loads(staged.read_text())
    staged.write_text(json.dumps({**original, "output_basename": "2026-09-07-budget-review"}))
    json_path, txt_path = finalize.finalize(staged, resolved, paths)
    assert json_path.name == "2026-09-07-budget-review.json"
    assert txt_path.name == "2026-09-07-budget-review.txt"
    assert [w["speaker"] for w in json.loads(json_path.read_text())["words"]] == ["Alice", "Bob"]
    assert [w["speaker"] for w in original["words"]] == ["SPEAKER_00", "SPEAKER_01"]


@pytest.mark.parametrize("complete", [False, None, "true"])
def test_finalize_rejects_incomplete_or_legacy_staging(tmp_path, monkeypatch, complete):
    monkeypatch.setenv("MEETINGS_DIR", str(tmp_path / "meetings"))
    paths = config.get_paths()
    source, staged, resolved = _write_staging_and_resolutions(
        tmp_path, {"SPEAKER_01": {"name": None, "enroll": False}}
    )
    original = json.loads(staged.read_text())
    staged.write_text(json.dumps({**original, "transcript_complete": complete}))
    with pytest.raises(ValueError, match="complete"):
        finalize.finalize(staged, resolved, paths)
    assert source.exists() and staged.exists() and resolved.exists()
    assert not paths.output_dir.exists()


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
