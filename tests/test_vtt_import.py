from pathlib import Path

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
