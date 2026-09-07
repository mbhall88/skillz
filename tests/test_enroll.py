from pathlib import Path

from meeting_transcribe import enroll, voiceprints


def test_enroll_from_audio_chunks_full_duration_and_centroids():
    calls = []

    def fake_embed(path: Path, start: float, end: float) -> list[float]:
        calls.append((start, end))
        return [start, end]

    result = enroll.enroll_from_audio(fake_embed, Path("sample.wav"), duration_seconds=12.0, chunk_seconds=5.0)

    assert calls == [(0.0, 5.0), (5.0, 10.0), (10.0, 12.0)]
    assert result == voiceprints.compute_centroid([[0.0, 5.0], [5.0, 10.0], [10.0, 12.0]])
