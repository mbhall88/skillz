# meeting-transcribe

Transcribes and diarizes local meeting recordings, matches speakers against
enrolled voiceprints, and interactively resolves anyone it can't confidently
match. Also files Zoom `.vtt` exports (which Zoom has already diarized)
without re-running the ML pipeline.

## Setup

1. `uv sync`
2. For audio/enrollment only, accept the gated model terms:
   - https://huggingface.co/pyannote/speaker-diarization-3.1
   - https://huggingface.co/pyannote/segmentation-3.0 (3.1's segmentation dependency)
   - https://huggingface.co/pyannote/embedding
   - https://huggingface.co/pyannote/speaker-diarization-community-1
     (pyannote.audio 4.0.7 loads an unused PLDA asset even for 3.1)
3. For audio/enrollment, `export HF_TOKEN=<your HuggingFace access token>`.
   Direct enrollment needs only the embedding model. VTT import needs no
   token or model access.
4. Optionally set `MEETINGS_DIR` (default `~/Documents/meetings`) and
   `MEETING_MATCH_THRESHOLD` (default `0.75`).

The pipeline explicitly uses `pyannote/speaker-diarization-3.1`. Embedding
inference loads a `Model` first, as required by the locked API. See
[dependency compatibility](docs/dependency-compatibility.md) for installed
versions and verification limits.

## Output and recovery

Inputs must be regular `.m4a` or `.vtt` files inside the configured inbox;
source symlinks are rejected. Finalization verifies the canonical source
path, device, inode, size, modification time and change time both before
writing and immediately before deletion. A changed source is retained.

User-visible output uses `output_basename` (`<date>-<slug>`), including any
`--title`; `recording_id` is a staging identifier. Pipeline prints the absolute
staging path under `MEETINGS_DIR`, and the resolutions JSON belongs beside
that file. Both arguments to finalization should be absolute paths.

Unaligned text is retained with segment-level timing, and unattributed speech
remains available for naming. JSON retains the original transcription and
alignment records as well as resolved words and turns. Duration comes from
the loaded 16 kHz audio; `recorded_at` is the source mtime in UTC. Finalization
rejects missing or false completeness evidence, including old staging files.
An empty or discrepant transcript requires inspection and restaging; the flag
is a text-retention check, not a measure of ASR accuracy.

Each unmatched speaker requires an explicit `name` (string or null) and
`enroll` (boolean). Naming does not require a centroid; enrollment does.
VTT JSON retains the parsed cues and milliseconds alongside merged turns.

Existing output pairs are never overwritten. A collision leaves the source
and working files in place. Select a distinct title for a new run. If an
enrollment or source recheck fails after output succeeds, those completed
outputs also remain; resolve the failure and choose a new title before
restaging. Voiceprint replacement uses a flushed temporary file in the same
directory and an atomic replace. Source deletion follows all successful
output and approved enrollment writes.

## Deterministic verification

From this repository, use the installed interpreter without uv cache writes:

```bash
HF_HUB_OFFLINE=1 PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider
```

Tests use synthetic data and fake ML boundaries. They do not process the
inbox or load Hugging Face models. Real model compatibility and transcription
quality still require a separately authorized audio run.

## Apple Silicon note

`ctranslate2` (WhisperX's inference backend) is CPU-only on Apple Silicon —
there is no MPS acceleration path. This pipeline always runs WhisperX with
`compute_type="int8"`. Don't "fix" this by trying to force GPU/MPS use; it
isn't a bug, it's a platform limitation. `mlx-whisper` is a plausible faster
alternative transcription backend on Apple Silicon and is worth evaluating
later, but is not wired in here.

## Match threshold

The default cosine-similarity threshold (`0.75`) for matching a diarized
speaker to an enrolled voiceprint is **unvalidated** — a starting point, not
a tuned value. Calibrate it against your own real recordings before trusting
automatic matches blindly; watch for both false matches (wrong name applied
confidently) and false non-matches (a known voice needlessly triggering the
disambiguation questions).

## Skill installation

This project is symlinked into `~/.claude/skills/meeting-transcribe` so
Claude Code picks it up automatically:

```bash
ln -s ~/Projects/skillz/meeting-transcribe ~/.claude/skills/meeting-transcribe
```
