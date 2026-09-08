---
name: meeting-transcribe
description: Transcribe and diarize local meeting recordings, match speakers against enrolled voiceprints, and interactively resolve any it can't confidently identify. Also files Zoom .vtt transcripts. Use when the user says things like "transcribe this meeting", "diarize this recording", "label the speakers in this recording", "process the inbox", "check for new recordings", or "file this Zoom transcript".
---

# Meeting Transcribe

Turns recordings dropped in `~/Documents/meetings/inbox/` (or `$MEETINGS_DIR/inbox/`
if set) into labelled transcripts in `output/`. Manual trigger only — nothing
runs automatically.

## Setup check (audio and enrollment only)

VTT import needs neither `HF_TOKEN` nor Hugging Face model access. For the
audio pipeline or direct enrollment, confirm `uv sync` has completed and:

- `HF_TOKEN` is set in the environment.
- Enrollment requires access to https://huggingface.co/pyannote/embedding.
- Audio also requires https://huggingface.co/pyannote/speaker-diarization-3.1
  and its https://huggingface.co/pyannote/segmentation-3.0 dependency.
  With locked pyannote.audio 4.0.7, accept
  https://huggingface.co/pyannote/speaker-diarization-community-1 terms too:
  the library loads an unused PLDA asset from it, even for 3.1. The diarization
  model remains 3.1. See `docs/dependency-compatibility.md` for evidence.

If required access is missing, report it and skip that audio/enrollment action.
Continue processing VTT files.

## Processing the inbox

1. List `$MEETINGS_DIR/inbox/` (default `~/Documents/meetings/inbox/`),
   oldest file first by modification time.
2. Before running either command, check whether the filename looks generic
   (purely numeric, or something like "recording", "audio", "new recording",
   "zoom_3"). Pass the stem as one shell argument, using proper shell quoting
   when setting `stem`. Keep the Python program constant:
   ```
   uv run python -c 'import sys; from meeting_transcribe.naming import is_generic_stem; print(is_generic_stem(sys.argv[1]))' "$stem"
   ```
   If it prints `True`, ask the user for a short meeting title first and pass
   it as `--title "..."`.
3. From `~/Projects/skillz/meeting-transcribe`, dispatch by extension and
   handle **one file fully** before moving to the next:
   - `.m4a` → the **Audio pipeline** below, after its setup check.
   - `.vtt` → run `uv run python -m meeting_transcribe.vtt_import <absolute-path> [--title "..."]`.
     Report the two output paths it prints. VTT uses Zoom's labels directly.
4. If a file fails to process, report the error and continue to the next
   file rather than stopping the whole batch.

## Audio pipeline (`.m4a`)

From `~/Projects/skillz/meeting-transcribe`:

1. Run `uv run python -m meeting_transcribe.pipeline <path-to-m4a> [--title "..."]`.
   This prints an **absolute staging path** under `$MEETINGS_DIR/.staging/`
   (default `~/Documents/meetings/.staging/`) and speaker counts.
2. Read the printed staging JSON path and open it to see each unmatched
   speaker's snippets and `best_guess`. Save this exact absolute path as
   `staging_path`; staging is outside the code repository. If
   `transcript_complete` is not `true`, report the incomplete transcript and
   leave the source and staging in place. Do not override this field.
3. For each unmatched speaker, **one at a time**:
   - Show 2-3 of their snippets and ask who it is. If `best_guess` is set,
     offer it explicitly as a guess ("possibly Bob, based on something they
     said") alongside "I don't know" and room for a real name — never state
     the guess as settled fact.
   - If given a name and `centroid_embedding` is present: ask a separate
     yes/no — enrol this voiceprint under that name for next time? Record
     the answer. Without a centroid, use the name for this transcript and
     record `enroll: false`; explain that no usable voiceprint is available.
   - If told "I don't know": leave the generic speaker label, move on. Do
     not ask again for the same speaker.
4. Once every unmatched speaker is resolved, write
   the resolutions JSON **beside that exact staging file**, using
   `Path(staging_path).with_suffix(".resolutions.json")`. Save that absolute
   path as `resolutions_path`. Include exactly one explicit entry per
   unmatched speaker; `name` must be null or a non-empty string and `enroll`
   must be a JSON boolean, never a string. With no unmatched speakers,
   write `{}`. Example:
   ```json
   {"SPEAKER_01": {"name": "Bob", "enroll": true}, "SPEAKER_02": {"name": null, "enroll": false}}
   ```
5. Run:
   ```
   uv run python -m meeting_transcribe.finalize --staging "$staging_path" --resolutions "$resolutions_path"
   ```
   This writes the final `.json`/`.txt` to `output/`, updates
   `data/voiceprints.json` for any approved enrollments, and deletes the
   source `.m4a` plus the staging files. Report the two output paths to the
   user. Output filenames use the staged `output_basename` (`<date>-<slug>`),
   including the chosen title; `recording_id` names staging files only.
   Existing output files are never replaced. If there is a collision,
   retain those outputs and report it; ask for a distinct title before a
   new run. A changed source or staging from an older version must be
   restaged before finalization. Keep the source and working files on failure.

## Enrolling a voiceprint directly

When the user wants to enrol someone from a clean sample (not from a
disambiguation answer), perform the enrollment setup check above, then run:

```
uv run python -m meeting_transcribe.enroll --name "Alice" --audio /path/to/sample.wav
```

Re-running with the same `--name` overwrites that entry.

## Threshold reminder

The match threshold (`MEETING_MATCH_THRESHOLD`, default `0.75`) is an
unvalidated starting point. If matches seem consistently wrong (false
matches or someone known keeps triggering disambiguation), say so — this
likely needs recalibrating rather than being trusted as-is.
