from pathlib import Path
import json

import pytest

from meeting_transcribe import config, vtt_import

_SAMPLE_VTT = """WEBVTT

00:00:00.000 --> 00:00:02.000
Alice: Hello there

00:00:02.500 --> 00:00:04.000
Alice: how are you

00:00:04.500 --> 00:00:06.000
Bob: Fine thanks
"""


def test_parse_vtt_extracts_speaker_and_text(tmp_path):
    vtt_path = tmp_path / "zoom_meeting.vtt"
    vtt_path.write_text(_SAMPLE_VTT)

    cues = vtt_import.parse_vtt(vtt_path)

    assert cues == [
        {"start": 0.0, "end": 2.0, "speaker": "Alice", "text": "Hello there"},
        {"start": 2.5, "end": 4.0, "speaker": "Alice", "text": "how are you"},
        {"start": 4.5, "end": 6.0, "speaker": "Bob", "text": "Fine thanks"},
    ]


def test_parse_vtt_defaults_speaker_to_unknown_when_no_colon(tmp_path):
    vtt_path = tmp_path / "no_speaker.vtt"
    vtt_path.write_text("WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nHello there\n")

    cues = vtt_import.parse_vtt(vtt_path)

    assert cues == [{"start": 0.0, "end": 1.0, "speaker": "Unknown", "text": "Hello there"}]


def test_import_vtt_writes_output_and_deletes_source(tmp_path, monkeypatch):
    monkeypatch.setenv("MEETINGS_DIR", str(tmp_path / "meetings"))
    paths = config.get_paths()
    config.ensure_directories(paths)

    source = paths.inbox_dir / "zoom_meeting.vtt"
    source.write_text(_SAMPLE_VTT)

    json_path, txt_path = vtt_import.import_vtt(source, paths)

    assert json_path.exists()
    assert txt_path.exists()
    assert not source.exists()
    assert "Alice: Hello there how are you" in txt_path.read_text()


def test_vtt_output_keeps_original_cues_with_fractional_times(tmp_path, monkeypatch):
    monkeypatch.setenv("MEETINGS_DIR", str(tmp_path))
    paths = config.get_paths()
    config.ensure_directories(paths)
    source = paths.inbox_dir / "meeting.vtt"
    source.write_text(_SAMPLE_VTT.replace("00:00:02.500", "01:02:02.123").replace("00:00:04.000", "01:02:04.987"))
    original_cues = vtt_import.parse_vtt(source)
    json_path, txt_path = vtt_import.import_vtt(source, paths)
    output = json.loads(json_path.read_text())
    assert output["cues"] == original_cues
    assert output["cues"][1]["start"] == 3722.123
    assert output["cues"][1]["end"] == 3724.987
    assert len(output["turns"]) == 2
    assert "Alice: Hello there how are you" in txt_path.read_text()


@pytest.mark.parametrize("unsafe", ["outside", "symlink", "extension"])
def test_vtt_rejects_unsafe_source_before_writing(tmp_path, monkeypatch, unsafe):
    monkeypatch.setenv("MEETINGS_DIR", str(tmp_path / "meetings"))
    paths = config.get_paths()
    paths.inbox_dir.mkdir(parents=True)
    outside = tmp_path / "outside.vtt"
    outside.write_text(_SAMPLE_VTT)
    if unsafe == "outside":
        source = outside
    elif unsafe == "extension":
        source = paths.inbox_dir / "wrong.txt"
        source.write_text(_SAMPLE_VTT)
    else:
        source = paths.inbox_dir / "linked.vtt"
        source.symlink_to(outside)
    with pytest.raises(ValueError, match="[Ss]ource"):
        vtt_import.import_vtt(source, paths)
    assert source.exists() and outside.exists()
    assert not paths.output_dir.exists()


def test_vtt_rechecks_source_after_output_before_deletion(tmp_path, monkeypatch):
    monkeypatch.setenv("MEETINGS_DIR", str(tmp_path))
    paths = config.get_paths()
    config.ensure_directories(paths)
    source = paths.inbox_dir / "meeting.vtt"
    source.write_text(_SAMPLE_VTT)
    writer = vtt_import.write_output_files

    def replace_during_write(*args, **kwargs):
        result = writer(*args, **kwargs)
        source.write_text("new transcript")
        return result

    monkeypatch.setattr(vtt_import, "write_output_files", replace_during_write)
    with pytest.raises(ValueError, match="[Ss]ource"):
        vtt_import.import_vtt(source, paths)
    assert source.read_text() == "new transcript"
