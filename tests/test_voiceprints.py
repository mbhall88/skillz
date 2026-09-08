import json
import math
import os

import pytest

from meeting_transcribe import voiceprints


def test_compute_centroid_mean_pools_and_l2_normalizes():
    result = voiceprints.compute_centroid([[1.0, 0.0], [0.0, 1.0]])
    expected_norm = math.sqrt(sum(v * v for v in result))
    assert math.isclose(expected_norm, 1.0, rel_tol=1e-6)
    assert math.isclose(result[0], result[1], rel_tol=1e-6)


def test_cosine_similarity_identical_vectors_is_one():
    assert math.isclose(voiceprints.cosine_similarity([1.0, 0.0], [1.0, 0.0]), 1.0)


def test_cosine_similarity_orthogonal_vectors_is_zero():
    assert math.isclose(voiceprints.cosine_similarity([1.0, 0.0], [0.0, 1.0]), 0.0, abs_tol=1e-9)


def test_load_voiceprints_missing_file_returns_empty_dict(tmp_path):
    assert voiceprints.load_voiceprints(tmp_path / "missing.json") == {}


def test_save_and_load_voiceprint_round_trips(tmp_path):
    path = tmp_path / "data" / "voiceprints.json"
    voiceprints.save_voiceprint(path, "Alice", [1.0, 0.0], source="enroll")
    db = voiceprints.load_voiceprints(path)
    assert db["Alice"]["embedding"] == [1.0, 0.0]
    assert db["Alice"]["source"] == "enroll"
    assert "updated_at" in db["Alice"]


def test_save_voiceprint_overwrites_existing_name(tmp_path):
    path = tmp_path / "voiceprints.json"
    voiceprints.save_voiceprint(path, "Alice", [1.0, 0.0], source="enroll")
    voiceprints.save_voiceprint(path, "Alice", [0.0, 1.0], source="session")
    db = voiceprints.load_voiceprints(path)
    assert db["Alice"]["embedding"] == [0.0, 1.0]
    assert db["Alice"]["source"] == "session"
    assert len(db) == 1


def test_match_speaker_returns_best_match_above_threshold():
    db = {
        "Alice": {"embedding": [1.0, 0.0]},
        "Bob": {"embedding": [0.0, 1.0]},
    }
    name, score = voiceprints.match_speaker([0.99, 0.01], db, threshold=0.75)
    assert name == "Alice"
    assert score > 0.75


def test_match_speaker_returns_none_below_threshold():
    db = {"Alice": {"embedding": [1.0, 0.0]}}
    name, score = voiceprints.match_speaker([0.0, 1.0], db, threshold=0.75)
    assert name is None


def test_match_speaker_empty_db_returns_none():
    name, score = voiceprints.match_speaker([1.0, 0.0], {}, threshold=0.75)
    assert name is None
    assert score == 0.0


def test_failed_atomic_replace_preserves_existing_voiceprints(tmp_path, monkeypatch):
    path = tmp_path / "voiceprints.json"
    voiceprints.save_voiceprint(path, "Alice", [1.0, 0.0], source="enroll")
    before = path.read_bytes()

    def fail_replace(source, destination):
        assert source.parent == path.parent
        assert json.loads(source.read_text())["Bob"]["embedding"] == [0.0, 1.0]
        assert path.read_bytes() == before
        raise OSError("simulated replacement failure")

    monkeypatch.setattr(os, "replace", fail_replace)
    with pytest.raises(OSError, match="replacement failure"):
        voiceprints.save_voiceprint(path, "Bob", [0.0, 1.0], source="session")
    assert path.read_bytes() == before
    assert list(tmp_path.iterdir()) == [path]


def test_failed_voiceprint_flush_preserves_database(tmp_path, monkeypatch):
    path = tmp_path / "voiceprints.json"
    voiceprints.save_voiceprint(path, "Alice", [1.0, 0.0], source="enroll")
    before = path.read_bytes()

    def fail_flush(fd):
        raise OSError("disk full")

    monkeypatch.setattr(os, "fsync", fail_flush)
    with pytest.raises(OSError, match="disk full"):
        voiceprints.save_voiceprint(path, "Bob", [0.0, 1.0], source="session")
    assert path.read_bytes() == before
    assert list(tmp_path.iterdir()) == [path]
