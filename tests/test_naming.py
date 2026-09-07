import time
from pathlib import Path

import pytest

from meeting_transcribe import naming


def test_slugify_lowercases_and_hyphenates_punctuation():
    assert naming.slugify("Team Standup!!") == "team-standup"


def test_slugify_collapses_repeated_separators():
    assert naming.slugify("Q3   Budget -- Review") == "q3-budget-review"


def test_slugify_empty_input_returns_untitled():
    assert naming.slugify("...") == "untitled"


@pytest.mark.parametrize(
    "stem,expected",
    [
        ("recording", True),
        ("Recording (2)", True),
        ("audio_003", True),
        ("New Recording", True),
        ("zoom_0", True),
        ("42", True),
        ("team_standup", False),
        ("2026-budget-review", False),
    ],
)
def test_is_generic_stem(stem, expected):
    assert naming.is_generic_stem(stem) is expected


def test_date_from_mtime_uses_local_date(tmp_path):
    target = tmp_path / "recording.m4a"
    target.write_bytes(b"fake")
    fixed_epoch = 1799500000
    import os

    os.utime(target, (fixed_epoch, fixed_epoch))
    expected = time.strftime("%Y-%m-%d", time.localtime(fixed_epoch))
    assert naming.date_from_mtime(target) == expected


def test_build_recording_id_uses_slug_and_timestamp(monkeypatch, tmp_path):
    source = tmp_path / "Team Standup.m4a"
    source.write_bytes(b"fake")
    monkeypatch.setattr(time, "time", lambda: 1799500000.0)
    assert naming.build_recording_id(source) == "team-standup-1799500000"


def test_build_recording_id_prefers_explicit_title(monkeypatch, tmp_path):
    source = tmp_path / "zoom_0.m4a"
    source.write_bytes(b"fake")
    monkeypatch.setattr(time, "time", lambda: 1799500000.0)
    assert naming.build_recording_id(source, title="Budget Review") == "budget-review-1799500000"


def test_output_basename_combines_date_and_slug(tmp_path):
    source = tmp_path / "Team Standup.m4a"
    source.write_bytes(b"fake")
    fixed_epoch = 1799500000
    import os

    os.utime(source, (fixed_epoch, fixed_epoch))
    expected_date = time.strftime("%Y-%m-%d", time.localtime(fixed_epoch))
    assert naming.output_basename(source) == f"{expected_date}-team-standup"
