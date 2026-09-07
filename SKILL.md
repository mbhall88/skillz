---
name: meeting-transcribe
description: Transcribe and diarize local meeting recordings, match speakers against enrolled voiceprints, and interactively resolve any it can't confidently identify. Also files Zoom .vtt transcripts. Use when the user says things like "transcribe this meeting", "diarize this recording", "label the speakers in this recording", "process the inbox", "check for new recordings", or "file this Zoom transcript".
---

# Meeting Transcribe

Turns recordings dropped in `~/Documents/meetings/inbox/` (or `$MEETINGS_DIR/inbox/`
if set) into labelled transcripts in `output/`. Manual trigger only — nothing
runs automatically.

## Setup check (once per machine)

Before the first run, confirm:
- `HF_TOKEN` is set in the environment.
- Terms are accepted on both https://huggingface.co/pyannote/speaker-diarization-3.1
  and https://huggingface.co/pyannote/embedding.

If either is missing, tell the user and stop rather than running the pipeline.

## Processing the inbox

1. List `$MEETINGS_DIR/inbox/` (default `~/Documents/meetings/inbox/`),
   oldest file first by modification time.
2. For each file, dispatch by extension and handle **one file fully**
   (through Finalize) before moving to the next — never interleave
   disambiguation questions for two different recordings.
   - `.m4a` → the **Audio pipeline** below.
   - `.vtt` → run `uv run python -m meeting_transcribe.vtt_import <path>`
     directly from `~/Projects/skillz/meeting-transcribe`. No disambiguation,
     no voiceprint interaction — report the two output paths it prints and
     move to the next file.
3. Before running either command, check whether the filename looks generic
   (purely numeric, or something like "recording", "audio", "new recording",
   "zoom_3"). To check deterministically, run:
   ```
   cd ~/Projects/skillz/meeting-transcribe && uv run python -c "from meeting_transcribe.naming import is_generic_stem; print(is_generic_stem('<filename-without-extension>'))"
   ```
   If it prints `True`, ask the user for a short meeting title first and pass
   it as `--title "..."`.
4. If a file fails to process, report the error and continue to the next
   file rather than stopping the whole batch.

## Audio pipeline (`.m4a`)

From `~/Projects/skillz/meeting-transcribe`:

1. Run `uv run python -m meeting_transcribe.pipeline <path-to-m4a> [--title "..."]`.
   This writes a staging file under `.staging/` and prints how many speakers
   were matched vs. need disambiguation.
2. Read the printed staging JSON path and open it to see each unmatched
   speaker's snippets and `best_guess`.
3. For each unmatched speaker, **one at a time**:
   - Show 2-3 of their snippets and ask who it is. If `best_guess` is set,
     offer it explicitly as a guess ("possibly Bob, based on something they
     said") alongside "I don't know" and room for a real name — never state
     the guess as settled fact.
   - If given a name: ask a separate yes/no — enrol this voiceprint under
     that name for next time? Record the answer.
   - If told "I don't know": leave the generic speaker label, move on. Do
     not ask again for the same speaker.
4. Once every unmatched speaker is resolved, write
   `.staging/<recording_id>.resolutions.json` (the recording_id is in the
   staging filename) with one entry per unmatched speaker:
   ```json
   {"SPEAKER_01": {"name": "Bob", "enroll": true}, "SPEAKER_02": {"name": null, "enroll": false}}
   ```
5. Run:
   ```
   uv run python -m meeting_transcribe.finalize --staging .staging/<recording_id>.json --resolutions .staging/<recording_id>.resolutions.json
   ```
   This writes the final `.json`/`.txt` to `output/`, updates
   `data/voiceprints.json` for any approved enrollments, and deletes the
   source `.m4a` plus the staging files. Report the two output paths to the
   user.

## Enrolling a voiceprint directly

When the user wants to enrol someone from a clean sample (not from a
disambiguation answer):

```
uv run python -m meeting_transcribe.enroll --name "Alice" --audio /path/to/sample.wav
```

Re-running with the same `--name` overwrites that entry.

## Threshold reminder

The match threshold (`MEETING_MATCH_THRESHOLD`, default `0.75`) is an
unvalidated starting point. If matches seem consistently wrong (false
matches or someone known keeps triggering disambiguation), say so — this
likely needs recalibrating rather than being trusted as-is.
