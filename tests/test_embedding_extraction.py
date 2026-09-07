from pathlib import Path

from meeting_transcribe import embedding_extraction, voiceprints


def test_centroid_for_segments_embeds_each_span_and_centroids():
    calls = []

    def fake_embed(path: Path, start: float, end: float) -> list[float]:
        calls.append((start, end))
        return [start, end, 1.0]

    spans = [(0.0, 5.0), (5.0, 10.0)]
    result = embedding_extraction.centroid_for_segments(fake_embed, Path("dummy.wav"), spans)

    expected = voiceprints.compute_centroid([[0.0, 5.0, 1.0], [5.0, 10.0, 1.0]])
    assert result == expected
    assert calls == spans
