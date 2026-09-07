from meeting_transcribe import staging_builder


def _words():
    return [
        {"start": 0.0, "end": 0.5, "word": "It's", "speaker": "SPEAKER_00"},
        {"start": 0.5, "end": 1.0, "word": "Bob", "speaker": "SPEAKER_00"},
        {"start": 1.0, "end": 1.5, "word": "here.", "speaker": "SPEAKER_00"},
        {"start": 2.0, "end": 2.5, "word": "Hello", "speaker": "SPEAKER_01"},
        {"start": 2.5, "end": 3.5, "word": "everyone,", "speaker": "SPEAKER_01"},
        {"start": 3.5, "end": 4.0, "word": "thanks.", "speaker": "SPEAKER_01"},
        {"start": 5.0, "end": 5.2, "word": "Sure.", "speaker": "SPEAKER_00"},
    ]


def test_guess_name_from_text_matches_its_x_here():
    assert staging_builder.guess_name_from_text("It's Bob here, sorry I'm late") == "Bob"


def test_guess_name_from_text_matches_this_is_x():
    assert staging_builder.guess_name_from_text("This is Alice speaking") == "Alice"


def test_guess_name_from_text_returns_none_when_no_cue():
    assert staging_builder.guess_name_from_text("I think the budget looks fine") is None


def test_longest_turns_for_speaker_sorts_by_duration_desc():
    turns = staging_builder.longest_turns_for_speaker(_words(), "SPEAKER_00", max_n=5)
    assert [round(t["end"] - t["start"], 2) for t in turns] == [1.5, 0.2]


def test_select_snippets_returns_text_only_fields():
    snippets = staging_builder.select_snippets(_words(), "SPEAKER_01", max_snippets=3)
    assert snippets == [{"start": 2.0, "end": 4.0, "text": "Hello everyone, thanks."}]


def test_build_staging_marks_matched_speaker_above_threshold():
    result = staging_builder.build_staging(
        recording_id="team-standup-123",
        source_path="/tmp/team_standup.m4a",
        recorded_at="2026-09-07T09:00:00+10:00",
        duration_seconds=5.2,
        words=_words(),
        speaker_embeddings={"SPEAKER_00": [1.0, 0.0], "SPEAKER_01": [0.0, 1.0]},
        voiceprint_db={"Alice": {"embedding": [1.0, 0.0]}},
        threshold=0.75,
    )
    assert result["speakers"]["SPEAKER_00"] == {
        "status": "matched",
        "name": "Alice",
        "score": 1.0,
    }


def test_build_staging_marks_unmatched_speaker_with_snippets_and_guess():
    result = staging_builder.build_staging(
        recording_id="team-standup-123",
        source_path="/tmp/team_standup.m4a",
        recorded_at="2026-09-07T09:00:00+10:00",
        duration_seconds=5.2,
        words=_words(),
        speaker_embeddings={"SPEAKER_00": [1.0, 0.0], "SPEAKER_01": [0.0, 1.0]},
        voiceprint_db={"Alice": {"embedding": [1.0, 0.0]}},
        threshold=0.75,
    )
    unmatched = result["speakers"]["SPEAKER_01"]
    assert unmatched["status"] == "unmatched"
    assert unmatched["best_guess"] is None
    assert unmatched["centroid_embedding"] == [0.0, 1.0]
    assert unmatched["snippets"] == [
        {"start": 2.0, "end": 4.0, "text": "Hello everyone, thanks."}
    ]


def test_build_staging_empty_voiceprint_db_marks_everyone_unmatched():
    result = staging_builder.build_staging(
        recording_id="r-1",
        source_path="/tmp/r.m4a",
        recorded_at="2026-09-07T09:00:00+10:00",
        duration_seconds=5.2,
        words=_words(),
        speaker_embeddings={"SPEAKER_00": [1.0, 0.0]},
        voiceprint_db={},
        threshold=0.75,
    )
    assert result["speakers"]["SPEAKER_00"]["status"] == "unmatched"
    assert result["speakers"]["SPEAKER_00"]["best_guess"] == "Bob"
