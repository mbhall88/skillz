import json
from pathlib import Path

from meeting_transcribe import output_writer


def test_merge_words_into_turns_groups_consecutive_same_speaker():
    words = [
        {"start": 0.0, "end": 0.5, "word": "Hello", "speaker": "SPEAKER_00"},
        {"start": 0.5, "end": 1.0, "word": "there", "speaker": "SPEAKER_00"},
        {"start": 1.0, "end": 1.5, "word": "Hi", "speaker": "SPEAKER_01"},
        {"start": 1.5, "end": 2.0, "word": "back", "speaker": "SPEAKER_00"},
    ]
    turns = output_writer.merge_words_into_turns(words)
    assert turns == [
        {"start": 0.0, "end": 1.0, "speaker": "SPEAKER_00", "text": "Hello there"},
        {"start": 1.0, "end": 1.5, "speaker": "SPEAKER_01", "text": "Hi"},
        {"start": 1.5, "end": 2.0, "speaker": "SPEAKER_00", "text": "back"},
    ]


def test_merge_words_into_turns_applies_speaker_label_mapping():
    words = [{"start": 0.0, "end": 1.0, "word": "Hi", "speaker": "SPEAKER_00"}]
    turns = output_writer.merge_words_into_turns(words, {"SPEAKER_00": "Alice"})
    assert turns[0]["speaker"] == "Alice"


def test_merge_words_into_turns_falls_back_to_raw_label_when_unmapped():
    words = [{"start": 0.0, "end": 1.0, "word": "Hi", "speaker": "SPEAKER_00"}]
    turns = output_writer.merge_words_into_turns(words, {})
    assert turns[0]["speaker"] == "SPEAKER_00"


def test_merge_cues_into_turns_joins_consecutive_same_speaker_cues():
    cues = [
        {"start": 0.0, "end": 2.0, "speaker": "Alice", "text": "Hello there"},
        {"start": 2.5, "end": 4.0, "speaker": "Alice", "text": "how are you"},
        {"start": 4.5, "end": 6.0, "speaker": "Bob", "text": "Fine thanks"},
    ]
    turns = output_writer.merge_cues_into_turns(cues)
    assert turns == [
        {"start": 0.0, "end": 4.0, "speaker": "Alice", "text": "Hello there how are you"},
        {"start": 4.5, "end": 6.0, "speaker": "Bob", "text": "Fine thanks"},
    ]


def test_write_output_files_writes_json_and_txt(tmp_path):
    turns = [
        {"start": 0.0, "end": 1.0, "speaker": "Alice", "text": "Hello there"},
        {"start": 1.0, "end": 1.5, "speaker": "Bob", "text": "Hi"},
    ]
    metadata = {"recording_id": "team-standup-123", "source_type": "audio"}
    json_path, txt_path = output_writer.write_output_files(
        tmp_path, "2026-09-07-team-standup", turns, metadata
    )

    assert json_path == tmp_path / "2026-09-07-team-standup.json"
    assert txt_path == tmp_path / "2026-09-07-team-standup.txt"

    data = json.loads(json_path.read_text())
    assert data["recording_id"] == "team-standup-123"
    assert data["turns"] == turns
    assert data["words"] is None

    assert txt_path.read_text() == "Alice: Hello there\n\nBob: Hi\n"


def test_write_output_files_includes_words_when_given(tmp_path):
    words = [{"start": 0.0, "end": 1.0, "word": "Hi", "speaker": "Alice"}]
    json_path, _ = output_writer.write_output_files(
        tmp_path, "2026-09-07-team-standup", [], {}, words=words
    )
    data = json.loads(json_path.read_text())
    assert data["words"] == words
