# meeting-transcribe

Transcribes and diarizes local meeting recordings, matches speakers against
enrolled voiceprints, and interactively resolves anyone it can't confidently
match. Also files Zoom `.vtt` exports (which Zoom has already diarized)
without re-running the ML pipeline.

## Setup

1. `uv sync`
2. Accept terms on both gated HuggingFace models (required before first run):
   - https://huggingface.co/pyannote/speaker-diarization-3.1
   - https://huggingface.co/pyannote/embedding
3. `export HF_TOKEN=<your HuggingFace access token>`
4. Optionally set `MEETINGS_DIR` (default `~/Documents/meetings`) and
   `MEETING_MATCH_THRESHOLD` (default `0.75`).

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
