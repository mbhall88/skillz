# meeting-transcribe: design spec

Date: 2026-09-07

## Purpose

A Claude Code agent skill that turns raw meeting recordings into labelled,
searchable transcripts, with minimal manual effort:

- `.m4a` recordings dropped in an inbox get transcribed, diarized, and
  speaker-matched against a local voiceprint database. Unmatched speakers are
  resolved through a short interactive Q&A with the user rather than left as
  `SPEAKER_00`.
- Zoom `.vtt` files (already transcribed/diarized by Zoom) get lightly
  reformatted and filed alongside the audio-derived output, without
  re-running the ML pipeline.

Single user, local-only, CLI/agent-driven. No GUI, no background services.

## Locations

Code and data are deliberately split:

- **Code**: `~/Projects/skillz/meeting-transcribe/` — a `uv`-managed Python
  project, git repo. Symlinked as `~/.claude/skills/meeting-transcribe`,
  matching the existing convention for this user's other skills (source of
  truth in a dedicated repo, symlinked into `~/.claude/skills/`).
- **Data**: `~/Documents/meetings/` — inbox, output, and the voiceprint
  database. Never contains code. Default location, overridable via the
  `MEETINGS_DIR` environment variable.

```
~/Documents/meetings/
├── inbox/          # drop .m4a / .vtt files here
├── output/         # <date>-<slug>.json and .txt, one pair per recording
├── data/
│   └── voiceprints.json
└── .staging/       # in-flight pipeline output while disambiguation is open
```

## Environment

- `uv`-managed Python project. Dependencies: `whisperx`, `pyannote.audio`,
  `torch`/`torchaudio`, `numpy`, `scipy`.
- Target: Apple Silicon (M4). `ctranslate2` (WhisperX's backend) is CPU-only
  on Apple Silicon — no MPS support. Pipeline hardcodes
  `compute_type="int8"` and must not assume GPU/MPS acceleration. This is
  called out in the README so it isn't "fixed" later by someone assuming
  it's a bug.
- `mlx-whisper` is worth a follow-up as an optional faster transcription
  backend on Apple Silicon, but is out of scope for this build — noted in
  the README as a future option, not wired in.
- Requires an `HF_TOKEN` environment variable (HuggingFace access token)
  with accepted terms on `pyannote/speaker-diarization-3.1` and
  `pyannote/embedding`. README documents this setup step explicitly.

## Speaker embeddings: centroid, not single-segment

Original scaffold used "extract an embedding from the longest segment" to
represent a speaker cluster, for both enrollment and matching. This is
fragile — a single segment can carry cross-talk, laughter, or noise that
skews the vector.

**Change**: take the 3–5 longest segments for a speaker cluster (or all
segments if fewer exist), embed each with `pyannote/embedding`, mean-pool,
and L2-normalize into a single centroid vector. Use the centroid everywhere
a speaker vector is needed — matching, enrollment, and session-based
re-enrollment. Same logic applies to enrollment samples with multiple usable
chunks.

## Pipeline stages (`pipeline.py`)

1. Convert source `.m4a` to 16kHz mono `.wav` via `ffmpeg` if not already in
   that format.
2. Transcribe with WhisperX (`large-v3`, `compute_type="int8"`), align for
   word-level timestamps.
3. Diarize using WhisperX's diarization wrapper (pyannote
   `speaker-diarization-3.1` under the hood) and merge speaker labels onto
   aligned segments.
4. For each diarized speaker cluster, compute the centroid embedding
   (`pyannote/embedding`, see above) and cosine-match it against
   `data/voiceprints.json`.
5. Threshold is configurable (`config.py`, default **0.75**). The README and
   CLI output both state plainly that this default is unvalidated and needs
   calibration against real recordings before being trusted.
6. Speakers above threshold are labelled with the matched name directly.
   Speakers below threshold are left unresolved and carry forward their
   centroid embedding plus representative snippets (their 2–3 longest turns)
   for the disambiguation step.
7. Write a **staging file**: `.staging/<recording-id>.json` (schema below).
   Print a short human-readable summary to stdout (resolved vs unresolved
   speaker count) — the agent reads the JSON file directly for the
   structured data it needs to run the Q&A.

Recording id: `<slug-of-source-filename>-<unix-timestamp-of-run>`, used to
name the staging file and, later, the output files.

### Staging JSON schema

```json
{
  "recording_id": "team-standup-1799500000",
  "source_path": "/Users/michael/Documents/meetings/inbox/team_standup.m4a",
  "recorded_at": "2026-09-07T09:00:00+10:00",
  "duration_seconds": 1820.4,
  "segments": [
    {"start": 0.12, "end": 0.98, "word": "Right,", "speaker": "SPEAKER_00"}
  ],
  "speakers": {
    "SPEAKER_00": {
      "status": "matched",
      "name": "Alice",
      "score": 0.83
    },
    "SPEAKER_01": {
      "status": "unmatched",
      "best_guess": null,
      "score": 0.61,
      "centroid_embedding": [0.0123, -0.045, "... 512 floats"],
      "snippets": [
        {"start": 340.2, "end": 365.9, "text": "So the budget email I sent..."},
        {"start": 900.1, "end": 918.4, "text": "..."}
      ]
    }
  }
}
```

`best_guess` is populated only when the pipeline has a plausible
content-based guess (e.g. self-identification in the transcript like "it's
Bob here") — this is a hint for the agent's question, never applied
automatically. If no such cue exists, it stays `null`.

## Interactive disambiguation (agent-driven, in SKILL.md)

For each `unmatched` speaker in the staging file, one at a time:

1. Present 2–3 representative snippets and ask who it is. If `best_guess` is
   set, offer it as a clearly-labelled guess ("possibly Bob, based on
   something they said") alongside "I don't know" and free text for a real
   name — never state the guess as fact.
2. **User gives a name** → ask a separate yes/no: enrol this speaker's
   voiceprint (the centroid already computed in the staging file) under
   that name for next time? Only write to `voiceprints.json` on explicit
   yes.
3. **User says "I don't know"** → leave the generic `SPEAKER_NN` label,
   move on. No repeated prompting.
4. Record all resolutions (name-or-null, enroll-yes/no) as they're
   collected.

Once every unmatched speaker is resolved (named or left generic), the agent
writes a resolutions file and calls `finalize.py`.

### Resolutions file (written by the agent via Write tool)

`.staging/<recording-id>.resolutions.json`:

```json
{
  "SPEAKER_01": {"name": "Bob", "enroll": true},
  "SPEAKER_02": {"name": null, "enroll": false}
}
```

Only unmatched speakers need entries; matched speakers are already resolved
in the staging file itself.

## Finalize (`finalize.py`)

`uv run python -m meeting_transcribe.finalize --staging <path> --resolutions <path>`

1. Merge staging speaker resolutions with the disambiguation resolutions
   file to get a final name (or generic label) per speaker.
2. Merge consecutive same-speaker segments into turns.
3. Write final output:
   - `output/<recording-id>.json` — full segments (word-level timestamps
     retained), turns, resolved speaker names.
   - `output/<recording-id>.txt` — `Name: text` per turn, blank line between
     turns.
4. For every resolution with `enroll: true`, write/overwrite that name's
   centroid embedding into `data/voiceprints.json`.
5. Only after (3) and (4) succeed: delete the source `.m4a` from `inbox/`
   and remove the staging + resolutions files from `.staging/`.
6. On any failure in steps 1–4: leave the source file and staging files in
   place, report the error, do not partially delete anything.

## Voiceprint database (`voiceprints.py`, `data/voiceprints.json`)

```json
{
  "Alice": {
    "embedding": [0.0123, -0.045, "... 512 floats"],
    "updated_at": "2026-09-07T09:32:00+10:00",
    "source": "enroll"
  }
}
```

`source` is `"enroll"` (from `enroll.py`, a clean dedicated sample) or
`"session"` (approved during disambiguation on a real recording) — purely
informational, doesn't affect matching, but useful when reviewing the file
later to judge how reliable an entry is likely to be.

`enroll.py`:

```
uv run python -m meeting_transcribe.enroll --name "Alice" --audio sample.wav
```

Extracts the centroid embedding (same multi-segment logic, or single
embedding if the sample is one continuous clean utterance), writes/overwrites
the named entry. Re-enrolling a name always overwrites.

## Zoom `.vtt` ingestion (`vtt_import.py`)

Lightweight path — no ML pipeline, no matching, no disambiguation:

```
uv run python -m meeting_transcribe.vtt_import inbox/zoom_meeting.vtt
```

1. Parse Zoom's WEBVTT cues (`Speaker Name: text` per cue, as Zoom emits
   when it has names; generic labels like `Speaker 1` otherwise).
2. Reshape into the same output shape as the audio pipeline (cue-level
   entries, not word-level — Zoom's VTT doesn't carry word timestamps),
   written to `output/<recording-id>.json` and `.txt` using the same
   `<date>-<slug>` naming convention.
3. Delete the source `.vtt` on success.

No voiceprint interaction at all — trusts whatever Zoom produced, since
there's no separable per-speaker audio to re-derive an embedding from.

## Inbox workflow (SKILL.md, agent-orchestrated, manual trigger only)

Triggered by phrases like "process the inbox", "check for new recordings",
"transcribe this meeting", "diarize this recording", "label the speakers",
"file this Zoom transcript" — no automation, no watcher, no cron.

1. List `inbox/`, oldest file first (by mtime).
2. Dispatch by extension: `.m4a` → `pipeline.py` then the disambiguation
   loop then `finalize.py`; `.vtt` → `vtt_import.py` directly.
3. **Output naming**: date = source file's mtime (`YYYY-MM-DD`), slug =
   sanitized source filename (lowercased, non-alphanumeric → `-`). If the
   filename is generic (purely numeric, or matches
   `recording|audio|new recording|zoom_\d+` case-insensitively), the agent
   asks the user for a short title before running the pipeline, rather than
   filing something as `2026-09-07-zoom-0.json`.
4. One file at a time — finish disambiguation and finalize before moving to
   the next, so questions for different recordings never interleave.
5. On a script failure for one file, report it and continue to the next
   file in the inbox rather than aborting the whole batch.

## SKILL.md

Frontmatter matches this user's existing skill convention (plain `name` +
trigger-oriented `description`, no extra frontmatter fields). Body documents
the CLI entry points above and the disambiguation loop as agent
instructions, since that part has no script to call — it's conversation.

## Testing strategy

Heavy ML/hardware dependencies (WhisperX model loads, pyannote pipelines)
make chasing 80% coverage through the model-call paths impractical and not
very informative for a single-user tool. Scope testing to the deterministic
logic instead:

- Cosine matching + centroid pooling math (`voiceprints.py`)
- VTT cue parsing (`vtt_import.py`)
- Staging → resolutions → final merge logic (`finalize.py`)
- Output naming / slug / generic-filename detection
- Voiceprint JSON read/write, overwrite-on-re-enroll semantics

Model-call boundaries (WhisperX, pyannote `Pipeline`/`Inference`) are thin
wrappers, exercised manually against real recordings rather than mocked in
unit tests.

## Explicitly out of scope

- Overlapping-speech / heavy cross-talk diarization accuracy (accepted
  pyannote limitation).
- GUI of any kind.
- Automatic/background inbox processing (watcher, cron).
- Voiceprint matching or disambiguation for the `.vtt` path.
- Wiring in `mlx-whisper` (noted as a future option only).
