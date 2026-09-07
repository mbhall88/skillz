from pathlib import Path
from meeting_transcribe import config


def test_get_paths_defaults_to_documents_meetings(monkeypatch):
    monkeypatch.delenv("MEETINGS_DIR", raising=False)
    paths = config.get_paths()
    assert paths.meetings_dir == Path.home() / "Documents" / "meetings"
    assert paths.inbox_dir == paths.meetings_dir / "inbox"
    assert paths.output_dir == paths.meetings_dir / "output"
    assert paths.data_dir == paths.meetings_dir / "data"
    assert paths.staging_dir == paths.meetings_dir / ".staging"
    assert paths.voiceprints_path == paths.data_dir / "voiceprints.json"


def test_get_paths_honours_meetings_dir_env_var(monkeypatch, tmp_path):
    monkeypatch.setenv("MEETINGS_DIR", str(tmp_path))
    paths = config.get_paths()
    assert paths.meetings_dir == tmp_path


def test_get_match_threshold_defaults_to_point_seven_five(monkeypatch):
    monkeypatch.delenv("MEETING_MATCH_THRESHOLD", raising=False)
    assert config.get_match_threshold() == 0.75


def test_get_match_threshold_honours_env_var(monkeypatch):
    monkeypatch.setenv("MEETING_MATCH_THRESHOLD", "0.6")
    assert config.get_match_threshold() == 0.6


def test_ensure_directories_creates_all_four(tmp_path, monkeypatch):
    monkeypatch.setenv("MEETINGS_DIR", str(tmp_path / "meetings"))
    paths = config.get_paths()
    config.ensure_directories(paths)
    assert paths.inbox_dir.is_dir()
    assert paths.output_dir.is_dir()
    assert paths.data_dir.is_dir()
    assert paths.staging_dir.is_dir()
