import subprocess
from pathlib import Path

from meeting_transcribe import audio_convert


def test_convert_to_wav16k_mono_invokes_ffmpeg_with_expected_args(monkeypatch, tmp_path):
    calls = []

    def fake_run(cmd, check, capture_output):
        calls.append((cmd, check, capture_output))

    monkeypatch.setattr(subprocess, "run", fake_run)

    source = tmp_path / "in.m4a"
    source.write_bytes(b"fake")
    dest = tmp_path / "converted" / "out.wav"

    audio_convert.convert_to_wav16k_mono(source, dest)

    assert dest.parent.is_dir()
    cmd, check, capture_output = calls[0]
    assert cmd[0] == "ffmpeg"
    assert str(source) in cmd
    assert str(dest) in cmd
    assert "-ar" in cmd and "16000" in cmd
    assert "-ac" in cmd and "1" in cmd
    assert check is True
    assert capture_output is True


def test_convert_to_wav16k_mono_propagates_ffmpeg_failures(monkeypatch, tmp_path):
    def fake_run(cmd, check, capture_output):
        raise subprocess.CalledProcessError(returncode=1, cmd=cmd)

    monkeypatch.setattr(subprocess, "run", fake_run)

    source = tmp_path / "in.m4a"
    source.write_bytes(b"fake")
    dest = tmp_path / "out.wav"

    try:
        audio_convert.convert_to_wav16k_mono(source, dest)
        assert False, "expected CalledProcessError"
    except subprocess.CalledProcessError:
        pass
