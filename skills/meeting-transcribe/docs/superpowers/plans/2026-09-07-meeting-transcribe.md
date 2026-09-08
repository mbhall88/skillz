# Meeting Transcribe Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `meeting-transcribe` Claude Code skill: transcribe/diarize/speaker-label `.m4a` recordings dropped in an inbox, interactively resolve unmatched speakers via chat, and lightly file Zoom `.vtt` exports — all local, manual-trigger, no GUI.

**Architecture:** A `uv`-managed Python package (`src/meeting_transcribe/`) split into small pure-logic modules (naming, output writing, voiceprint math, staging construction) that are fully unit tested, plus thin CLI glue modules (`pipeline.py`, `enroll.py`, `vtt_import.py`, `finalize.py`) that wire those modules to WhisperX/pyannote/ffmpeg and are verified manually against real audio. `SKILL.md` documents the CLIs and carries the agent-side instructions for the interactive disambiguation loop and inbox dispatch, since that part is conversation, not code.

**Tech Stack:** Python 3.11+, `uv`, WhisperX (`large-v3`, `int8`), `pyannote.audio` (`speaker-diarization-3.1`, `embedding`), `torch`/`torchaudio`, `numpy`, `webvtt-py`, `pytest`.

**Spec:** `docs/superpowers/specs/2026-09-07-meeting-transcribe-design.md`

## Global Constraints

- `compute_type="int8"` is hardcoded for WhisperX — Apple Silicon has no MPS/GPU path via ctranslate2. Never assume GPU acceleration is available.
- Data lives in `MEETINGS_DIR` (env var, default `~/Documents/meetings`): `inbox/`, `output/`, `data/voiceprints.json`, `.staging/`. Code lives only in this repo (`~/Projects/skillz/meeting-transcribe`) — the two never mix.
- Match threshold: `MEETING_MATCH_THRESHOLD` env var, default **0.75** — explicitly unvalidated, must be surfaced as such in CLI output/README, never silently trusted.
- `HF_TOKEN` env var is required for any code path touching pyannote models (`pyannote/speaker-diarization-3.1`, `pyannote/embedding`). Terms must be accepted on both model pages first.
- Every speaker vector (matching, enrollment, session re-enrollment) is a **centroid**: mean-pool then L2-normalize the embeddings of up to 5 longest segments. Never a single-segment embedding.
- The `.vtt` path never touches `voiceprints.json` and never runs matching or disambiguation — it trusts Zoom's own labels verbatim.
- Source files (`.m4a`/`.vtt`) are deleted only after their output files are fully written. On any failure, source and any staging/resolutions files are left untouched.
- No GUI, no background watcher/cron. Every entry point is a manual CLI invocation the agent runs on request.
- **Naming clarification (resolves an ambiguity in the spec):** `output_basename` (`<date>-<slug>`, e.g. `2026-09-07-team-standup`) is used for every file the user sees in `output/` — both `.m4a`-derived and `.vtt`-derived. `recording_id` (`<slug>-<unix-timestamp>`) is an internal identifier used only for the `.staging/` working files during disambiguation, never for `output/` filenames.

---

## File Structure

```
~/Projects/skillz/meeting-transcribe/
├── pyproject.toml
├── README.md
├── SKILL.md
├── src/meeting_transcribe/
│   ├── __init__.py
│   ├── config.py              # paths, threshold, HF token env var name
│   ├── naming.py               # slugs, dates, generic-filename detection
│   ├── output_writer.py        # turn merging + json/txt writers (shared)
│   ├── voiceprints.py           # centroid math, cosine match, db read/write
│   ├── staging_builder.py       # pure staging-JSON construction logic
│   ├── embedding_extraction.py  # pyannote embedding wrapper (injectable)
│   ├── audio_convert.py         # ffmpeg wrapper
│   ├── vtt_import.py            # Zoom .vtt lightweight path (CLI)
│   ├── enroll.py                 # voiceprint enrollment (CLI)
│   ├── pipeline.py               # full audio pipeline → staging (CLI)
│   └── finalize.py               # staging + resolutions → final output (CLI)
└── tests/
    ├── test_config.py
    ├── test_naming.py
    ├── test_output_writer.py
    ├── test_voiceprints.py
    ├── test_staging_builder.py
    ├── test_embedding_extraction.py
    ├── test_audio_convert.py
    ├── test_vtt_import.py
    ├── test_enroll.py
    └── test_finalize.py
```

---

### Task 1: Project scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `README.md`
- Create: `src/meeting_transcribe/__init__.py`
- Create: `.gitignore`

**Interfaces:**
- Produces: an installable `meeting_transcribe` package importable as `import meeting_transcribe`, and a working `uv` environment with `pytest` available for every later task.

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[project]
name = "meeting-transcribe"
version = "0.1.0"
description = "Transcribe, diarize, and speaker-label local meeting recordings and Zoom VTT exports."
requires-python = ">=3.11"
dependencies = [
    "whisperx",
    "pyannote.audio>=3.1",
    "torch",
    "torchaudio",
    "numpy",
    "webvtt-py>=0.5",
]

[dependency-groups]
dev = [
    "pytest>=8.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/meeting_transcribe"]
```

- [ ] **Step 2: Write `src/meeting_transcribe/__init__.py`**

```python
"""meeting-transcribe: local meeting transcription, diarization, and speaker labelling."""
```

- [ ] **Step 3: Write `.gitignore`**

```
.venv/
__pycache__/
*.pyc
.pytest_cache/
uv.lock.tmp
```

- [ ] **Step 4: Write README skeleton**

```markdown
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
```

- [ ] **Step 5: Install and verify**

Run: `cd ~/Projects/skillz/meeting-transcribe && uv sync`
Expected: creates `.venv/` and `uv.lock` without error (this will take a
while the first time — `torch`/`whisperx`/`pyannote.audio` are large).

Run: `uv run python -c "import meeting_transcribe; print('ok')"`
Expected: prints `ok`

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml README.md .gitignore src/meeting_transcribe/__init__.py uv.lock
git commit -m "chore: scaffold meeting-transcribe uv project"
```

---

### Task 2: `config.py` — paths and settings

**Files:**
- Create: `src/meeting_transcribe/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `Paths` (dataclass: `meetings_dir, inbox_dir, output_dir, data_dir, staging_dir, voiceprints_path`, all `pathlib.Path`), `get_paths() -> Paths`, `get_match_threshold() -> float`, `ensure_directories(paths: Paths) -> None`, `HF_TOKEN_ENV_VAR: str`, `DEFAULT_MEETINGS_DIR: Path`, `DEFAULT_MATCH_THRESHOLD: float`. Every later task that touches the filesystem consumes `Paths` from here — never hardcode a path elsewhere.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_config.py
from pathlib import Path
from meeting_transcribe import config


def test_get_paths_defaults_to_documents_meetings(monkeypatch):
    monkeypatch.delenv("MEETINGS_DIR", raising=False)
    paths = config.get_paths()
    assert paths.meetings_dir == Path.home() / "Documents" / "meetings"
    assert paths.inbox_dir == paths.meetings_dir / "inbox"
    assert paths.output_dir == paths.meetings_dir / "output"
    assert paths.data_dir == paths.meetings_dir / "data"
    assert paths.staging_dir == paths.meetings_dir / ".staging"
    assert paths.voiceprints_path == paths.data_dir / "voiceprints.json"


def test_get_paths_honours_meetings_dir_env_var(monkeypatch, tmp_path):
    monkeypatch.setenv("MEETINGS_DIR", str(tmp_path))
    paths = config.get_paths()
    assert paths.meetings_dir == tmp_path


def test_get_match_threshold_defaults_to_point_seven_five(monkeypatch):
    monkeypatch.delenv("MEETING_MATCH_THRESHOLD", raising=False)
    assert config.get_match_threshold() == 0.75


def test_get_match_threshold_honours_env_var(monkeypatch):
    monkeypatch.setenv("MEETING_MATCH_THRESHOLD", "0.6")
    assert config.get_match_threshold() == 0.6


def test_ensure_directories_creates_all_four(tmp_path, monkeypatch):
    monkeypatch.setenv("MEETINGS_DIR", str(tmp_path / "meetings"))
    paths = config.get_paths()
    config.ensure_directories(paths)
    assert paths.inbox_dir.is_dir()
    assert paths.output_dir.is_dir()
    assert paths.data_dir.is_dir()
    assert paths.staging_dir.is_dir()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError` or `AttributeError` (module doesn't exist yet)

- [ ] **Step 3: Write the implementation**

```python
# src/meeting_transcribe/config.py
import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_MEETINGS_DIR = Path.home() / "Documents" / "meetings"
DEFAULT_MATCH_THRESHOLD = 0.75
HF_TOKEN_ENV_VAR = "HF_TOKEN"


@dataclass(frozen=True)
class Paths:
    meetings_dir: Path
    inbox_dir: Path
    output_dir: Path
    data_dir: Path
    staging_dir: Path
    voiceprints_path: Path


def get_paths() -> Paths:
    meetings_dir = Path(os.environ.get("MEETINGS_DIR", str(DEFAULT_MEETINGS_DIR)))
    data_dir = meetings_dir / "data"
    return Paths(
        meetings_dir=meetings_dir,
        inbox_dir=meetings_dir / "inbox",
        output_dir=meetings_dir / "output",
        data_dir=data_dir,
        staging_dir=meetings_dir / ".staging",
        voiceprints_path=data_dir / "voiceprints.json",
    )


def get_match_threshold() -> float:
    return float(os.environ.get("MEETING_MATCH_THRESHOLD", str(DEFAULT_MATCH_THRESHOLD)))


def ensure_directories(paths: Paths) -> None:
    for directory in (paths.inbox_dir, paths.output_dir, paths.data_dir, paths.staging_dir):
        directory.mkdir(parents=True, exist_ok=True)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_config.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add src/meeting_transcribe/config.py tests/test_config.py
git commit -m "feat: add config module for paths and thresholds"
```

---

### Task 3: `naming.py` — slugs, dates, generic-filename detection

**Files:**
- Create: `src/meeting_transcribe/naming.py`
- Test: `tests/test_naming.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `slugify(text: str) -> str`, `is_generic_stem(stem: str) -> bool`, `date_from_mtime(path: Path) -> str`, `build_recording_id(source_path: Path, title: str | None = None) -> str`, `output_basename(source_path: Path, title: str | None = None) -> str`. `finalize.py` and `vtt_import.py` both consume `output_basename`; `pipeline.py` consumes `build_recording_id`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_naming.py
import time
from pathlib import Path

import pytest

from meeting_transcribe import naming


def test_slugify_lowercases_and_hyphenates_punctuation():
    assert naming.slugify("Team Standup!!") == "team-standup"


def test_slugify_collapses_repeated_separators():
    assert naming.slugify("Q3   Budget -- Review") == "q3-budget-review"


def test_slugify_empty_input_returns_untitled():
    assert naming.slugify("...") == "untitled"


@pytest.mark.parametrize(
    "stem,expected",
    [
        ("recording", True),
        ("Recording (2)", True),
        ("audio_003", True),
        ("New Recording", True),
        ("zoom_0", True),
        ("42", True),
        ("team_standup", False),
        ("2026-budget-review", False),
    ],
)
def test_is_generic_stem(stem, expected):
    assert naming.is_generic_stem(stem) is expected


def test_date_from_mtime_uses_local_date(tmp_path):
    target = tmp_path / "recording.m4a"
    target.write_bytes(b"fake")
    fixed_epoch = 1799500000
    import os

    os.utime(target, (fixed_epoch, fixed_epoch))
    expected = time.strftime("%Y-%m-%d", time.localtime(fixed_epoch))
    assert naming.date_from_mtime(target) == expected


def test_build_recording_id_uses_slug_and_timestamp(monkeypatch, tmp_path):
    source = tmp_path / "Team Standup.m4a"
    source.write_bytes(b"fake")
    monkeypatch.setattr(time, "time", lambda: 1799500000.0)
    assert naming.build_recording_id(source) == "team-standup-1799500000"


def test_build_recording_id_prefers_explicit_title(monkeypatch, tmp_path):
    source = tmp_path / "zoom_0.m4a"
    source.write_bytes(b"fake")
    monkeypatch.setattr(time, "time", lambda: 1799500000.0)
    assert naming.build_recording_id(source, title="Budget Review") == "budget-review-1799500000"


def test_output_basename_combines_date_and_slug(tmp_path):
    source = tmp_path / "Team Standup.m4a"
    source.write_bytes(b"fake")
    fixed_epoch = 1799500000
    import os

    os.utime(source, (fixed_epoch, fixed_epoch))
    expected_date = time.strftime("%Y-%m-%d", time.localtime(fixed_epoch))
    assert naming.output_basename(source) == f"{expected_date}-team-standup"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_naming.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

```python
# src/meeting_transcribe/naming.py
import re
import time
from pathlib import Path

_GENERIC_PATTERNS = [
    re.compile(r"^recording(\s*\(?\d+\)?)?$"),
    re.compile(r"^audio(\s*\(?\d+\)?)?$"),
    re.compile(r"^new recording(\s*\(?\d+\)?)?$"),
    re.compile(r"^zoom\s*\d*$"),
    re.compile(r"^\d+$"),
]


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "untitled"


def is_generic_stem(stem: str) -> bool:
    normalized = re.sub(r"[_-]+", " ", stem.strip().lower())
    normalized = re.sub(r"\s+", " ", normalized)
    return any(pattern.match(normalized) for pattern in _GENERIC_PATTERNS)


def date_from_mtime(path: Path) -> str:
    return time.strftime("%Y-%m-%d", time.localtime(path.stat().st_mtime))


def _base_name(source_path: Path, title: str | None) -> str:
    return title if title else source_path.stem


def build_recording_id(source_path: Path, title: str | None = None) -> str:
    slug = slugify(_base_name(source_path, title))
    return f"{slug}-{int(time.time())}"


def output_basename(source_path: Path, title: str | None = None) -> str:
    date = date_from_mtime(source_path)
    slug = slugify(_base_name(source_path, title))
    return f"{date}-{slug}"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_naming.py -v`
Expected: PASS (11 passed)

- [ ] **Step 5: Commit**

```bash
git add src/meeting_transcribe/naming.py tests/test_naming.py
git commit -m "feat: add naming module for slugs, dates, and generic-filename detection"
```

---

### Task 4: `output_writer.py` — turn merging and file writers

**Files:**
- Create: `src/meeting_transcribe/output_writer.py`
- Test: `tests/test_output_writer.py`

**Interfaces:**
- Consumes: nothing from earlier tasks (pure logic + stdlib `json`).
- Produces: `merge_words_into_turns(words: list[dict], speaker_labels: dict[str, str] | None = None) -> list[dict]` (each turn: `{"start": float, "end": float, "speaker": str, "text": str}`), `merge_cues_into_turns(cues: list[dict]) -> list[dict]` (same turn shape; cues already have `speaker`+`text`), `write_output_files(output_dir: Path, basename: str, turns: list[dict], metadata: dict, words: list[dict] | None = None) -> tuple[Path, Path]`. Consumed by `staging_builder.py`, `finalize.py`, and `vtt_import.py`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_output_writer.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_output_writer.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

```python
# src/meeting_transcribe/output_writer.py
import json
from pathlib import Path


def merge_words_into_turns(
    words: list[dict], speaker_labels: dict[str, str] | None = None
) -> list[dict]:
    speaker_labels = speaker_labels or {}
    turns: list[dict] = []
    for word in words:
        label = speaker_labels.get(word["speaker"], word["speaker"])
        if turns and turns[-1]["speaker"] == label:
            turns[-1]["end"] = word["end"]
            turns[-1]["text"] += f" {word['word']}"
        else:
            turns.append(
                {
                    "start": word["start"],
                    "end": word["end"],
                    "speaker": label,
                    "text": word["word"],
                }
            )
    return turns


def merge_cues_into_turns(cues: list[dict]) -> list[dict]:
    turns: list[dict] = []
    for cue in cues:
        if turns and turns[-1]["speaker"] == cue["speaker"]:
            turns[-1]["end"] = cue["end"]
            turns[-1]["text"] += f" {cue['text']}"
        else:
            turns.append(dict(cue))
    return turns


def write_output_files(
    output_dir: Path,
    basename: str,
    turns: list[dict],
    metadata: dict,
    words: list[dict] | None = None,
) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{basename}.json"
    txt_path = output_dir / f"{basename}.txt"

    payload = {**metadata, "turns": turns, "words": words}
    json_path.write_text(json.dumps(payload, indent=2))

    txt_path.write_text(
        "\n\n".join(f"{turn['speaker']}: {turn['text']}" for turn in turns) + "\n"
        if turns
        else ""
    )

    return json_path, txt_path
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_output_writer.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add src/meeting_transcribe/output_writer.py tests/test_output_writer.py
git commit -m "feat: add output_writer for turn merging and json/txt writing"
```

---

### Task 5: `voiceprints.py` — centroid math and database

**Files:**
- Create: `src/meeting_transcribe/voiceprints.py`
- Test: `tests/test_voiceprints.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `compute_centroid(embeddings: list[list[float]]) -> list[float]`, `cosine_similarity(a: list[float], b: list[float]) -> float`, `load_voiceprints(path: Path) -> dict`, `save_voiceprint(path: Path, name: str, embedding: list[float], source: str) -> None`, `match_speaker(embedding: list[float], db: dict, threshold: float) -> tuple[str | None, float]`. Consumed by `staging_builder.py`, `embedding_extraction.py`, `finalize.py`, `enroll.py`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_voiceprints.py
import json
import math

from meeting_transcribe import voiceprints


def test_compute_centroid_mean_pools_and_l2_normalizes():
    result = voiceprints.compute_centroid([[1.0, 0.0], [0.0, 1.0]])
    expected_norm = math.sqrt(sum(v * v for v in result))
    assert math.isclose(expected_norm, 1.0, rel_tol=1e-6)
    assert math.isclose(result[0], result[1], rel_tol=1e-6)


def test_cosine_similarity_identical_vectors_is_one():
    assert math.isclose(voiceprints.cosine_similarity([1.0, 0.0], [1.0, 0.0]), 1.0)


def test_cosine_similarity_orthogonal_vectors_is_zero():
    assert math.isclose(voiceprints.cosine_similarity([1.0, 0.0], [0.0, 1.0]), 0.0, abs_tol=1e-9)


def test_load_voiceprints_missing_file_returns_empty_dict(tmp_path):
    assert voiceprints.load_voiceprints(tmp_path / "missing.json") == {}


def test_save_and_load_voiceprint_round_trips(tmp_path):
    path = tmp_path / "data" / "voiceprints.json"
    voiceprints.save_voiceprint(path, "Alice", [1.0, 0.0], source="enroll")
    db = voiceprints.load_voiceprints(path)
    assert db["Alice"]["embedding"] == [1.0, 0.0]
    assert db["Alice"]["source"] == "enroll"
    assert "updated_at" in db["Alice"]


def test_save_voiceprint_overwrites_existing_name(tmp_path):
    path = tmp_path / "voiceprints.json"
    voiceprints.save_voiceprint(path, "Alice", [1.0, 0.0], source="enroll")
    voiceprints.save_voiceprint(path, "Alice", [0.0, 1.0], source="session")
    db = voiceprints.load_voiceprints(path)
    assert db["Alice"]["embedding"] == [0.0, 1.0]
    assert db["Alice"]["source"] == "session"
    assert len(db) == 1


def test_match_speaker_returns_best_match_above_threshold():
    db = {
        "Alice": {"embedding": [1.0, 0.0]},
        "Bob": {"embedding": [0.0, 1.0]},
    }
    name, score = voiceprints.match_speaker([0.99, 0.01], db, threshold=0.75)
    assert name == "Alice"
    assert score > 0.75


def test_match_speaker_returns_none_below_threshold():
    db = {"Alice": {"embedding": [1.0, 0.0]}}
    name, score = voiceprints.match_speaker([0.0, 1.0], db, threshold=0.75)
    assert name is None


def test_match_speaker_empty_db_returns_none():
    name, score = voiceprints.match_speaker([1.0, 0.0], {}, threshold=0.75)
    assert name is None
    assert score == 0.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_voiceprints.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

```python
# src/meeting_transcribe/voiceprints.py
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np


def compute_centroid(embeddings: list[list[float]]) -> list[float]:
    array = np.array(embeddings, dtype=np.float64)
    mean = array.mean(axis=0)
    norm = np.linalg.norm(mean)
    if norm == 0:
        return mean.tolist()
    return (mean / norm).tolist()


def cosine_similarity(a: list[float], b: list[float]) -> float:
    va, vb = np.array(a, dtype=np.float64), np.array(b, dtype=np.float64)
    denom = np.linalg.norm(va) * np.linalg.norm(vb)
    if denom == 0:
        return 0.0
    return float(np.dot(va, vb) / denom)


def load_voiceprints(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def save_voiceprint(path: Path, name: str, embedding: list[float], source: str) -> None:
    db = load_voiceprints(path)
    db[name] = {
        "embedding": embedding,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "source": source,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(db, indent=2))


def match_speaker(
    embedding: list[float], db: dict, threshold: float
) -> tuple[str | None, float]:
    best_name: str | None = None
    best_score = 0.0
    for name, entry in db.items():
        score = cosine_similarity(embedding, entry["embedding"])
        if score > best_score:
            best_name, best_score = name, score
    if best_name is None or best_score < threshold:
        return None, best_score
    return best_name, best_score
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_voiceprints.py -v`
Expected: PASS (9 passed)

- [ ] **Step 5: Commit**

```bash
git add src/meeting_transcribe/voiceprints.py tests/test_voiceprints.py
git commit -m "feat: add voiceprints module for centroid math and database"
```

---

### Task 6: `staging_builder.py` — pure staging-JSON construction

**Files:**
- Create: `src/meeting_transcribe/staging_builder.py`
- Test: `tests/test_staging_builder.py`

**Interfaces:**
- Consumes: `output_writer.merge_words_into_turns` (Task 4), `voiceprints.match_speaker` (Task 5).
- Produces: `guess_name_from_text(text: str) -> str | None`, `longest_turns_for_speaker(words: list[dict], speaker: str, max_n: int) -> list[dict]`, `select_snippets(words: list[dict], speaker: str, max_snippets: int = 3) -> list[dict]` (each `{"start", "end", "text"}`), `build_staging(recording_id: str, source_path: str, recorded_at: str, duration_seconds: float, words: list[dict], speaker_embeddings: dict[str, list[float]], voiceprint_db: dict, threshold: float) -> dict`. Consumed by `pipeline.py`; `finalize.py` reads the staging dict this produces (via JSON on disk).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_staging_builder.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_staging_builder.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

```python
# src/meeting_transcribe/staging_builder.py
import re

from . import voiceprints as vp
from .output_writer import merge_words_into_turns

_GUESS_PATTERNS = [
    re.compile(r"\bit'?s\s+([A-Z][a-z]+)\b", re.IGNORECASE),
    re.compile(r"\bthis\s+is\s+([A-Z][a-z]+)\b", re.IGNORECASE),
]


def guess_name_from_text(text: str) -> str | None:
    for pattern in _GUESS_PATTERNS:
        match = pattern.search(text)
        if match:
            return match.group(1).capitalize()
    return None


def longest_turns_for_speaker(words: list[dict], speaker: str, max_n: int) -> list[dict]:
    turns = [turn for turn in merge_words_into_turns(words) if turn["speaker"] == speaker]
    turns.sort(key=lambda turn: turn["end"] - turn["start"], reverse=True)
    return turns[:max_n]


def select_snippets(words: list[dict], speaker: str, max_snippets: int = 3) -> list[dict]:
    turns = longest_turns_for_speaker(words, speaker, max_snippets)
    return [{"start": t["start"], "end": t["end"], "text": t["text"]} for t in turns]


def build_staging(
    recording_id: str,
    source_path: str,
    recorded_at: str,
    duration_seconds: float,
    words: list[dict],
    speaker_embeddings: dict[str, list[float]],
    voiceprint_db: dict,
    threshold: float,
) -> dict:
    speakers_out: dict = {}
    for raw_label, embedding in speaker_embeddings.items():
        name, score = vp.match_speaker(embedding, voiceprint_db, threshold)
        if name is not None:
            speakers_out[raw_label] = {"status": "matched", "name": name, "score": score}
            continue

        snippets = select_snippets(words, raw_label)
        guess = None
        for snippet in snippets:
            guess = guess_name_from_text(snippet["text"])
            if guess:
                break
        speakers_out[raw_label] = {
            "status": "unmatched",
            "best_guess": guess,
            "score": score,
            "centroid_embedding": embedding,
            "snippets": snippets,
        }

    return {
        "recording_id": recording_id,
        "source_path": source_path,
        "recorded_at": recorded_at,
        "duration_seconds": duration_seconds,
        "words": words,
        "speakers": speakers_out,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_staging_builder.py -v`
Expected: PASS (8 passed)

- [ ] **Step 5: Commit**

```bash
git add src/meeting_transcribe/staging_builder.py tests/test_staging_builder.py
git commit -m "feat: add staging_builder for speaker matching and snippet selection"
```

---

### Task 7: `embedding_extraction.py` — pyannote embedding wrapper

**Files:**
- Create: `src/meeting_transcribe/embedding_extraction.py`
- Test: `tests/test_embedding_extraction.py`

**Interfaces:**
- Consumes: `voiceprints.compute_centroid` (Task 5).
- Produces: `EmbedFn = Callable[[Path, float, float], list[float]]`, `load_pyannote_embedder(hf_token: str) -> EmbedFn` (real model load — not unit tested, manually verified in Task 11/13), `centroid_for_segments(embed_fn: EmbedFn, audio_path: Path, spans: list[tuple[float, float]]) -> list[float]`. Consumed by `enroll.py` and `pipeline.py`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_embedding_extraction.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_embedding_extraction.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

```python
# src/meeting_transcribe/embedding_extraction.py
from pathlib import Path
from typing import Callable

from . import voiceprints

EmbedFn = Callable[[Path, float, float], list[float]]


def load_pyannote_embedder(hf_token: str) -> EmbedFn:
    """Loads pyannote/embedding and returns a callable that embeds one
    (start, end) span of an audio file. Not unit tested — requires the real
    gated model; verify manually per the README setup steps."""
    from pyannote.audio import Inference

    inference = Inference("pyannote/embedding", window="whole", use_auth_token=hf_token)

    def embed(audio_path: Path, start: float, end: float) -> list[float]:
        from pyannote.core import Segment

        embedding = inference.crop(str(audio_path), Segment(start, end))
        return embedding.tolist()

    return embed


def centroid_for_segments(
    embed_fn: EmbedFn, audio_path: Path, spans: list[tuple[float, float]]
) -> list[float]:
    embeddings = [embed_fn(audio_path, start, end) for start, end in spans]
    return voiceprints.compute_centroid(embeddings)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_embedding_extraction.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add src/meeting_transcribe/embedding_extraction.py tests/test_embedding_extraction.py
git commit -m "feat: add embedding_extraction with injectable pyannote embedder"
```

---

### Task 8: `audio_convert.py` — ffmpeg wrapper

**Files:**
- Create: `src/meeting_transcribe/audio_convert.py`
- Test: `tests/test_audio_convert.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `convert_to_wav16k_mono(source_path: Path, dest_path: Path) -> None`. Consumed by `pipeline.py`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_audio_convert.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_audio_convert.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

```python
# src/meeting_transcribe/audio_convert.py
import subprocess
from pathlib import Path


def convert_to_wav16k_mono(source_path: Path, dest_path: Path) -> None:
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(source_path), "-ar", "16000", "-ac", "1", str(dest_path)],
        check=True,
        capture_output=True,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_audio_convert.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/meeting_transcribe/audio_convert.py tests/test_audio_convert.py
git commit -m "feat: add audio_convert ffmpeg wrapper"
```

---

### Task 9: `vtt_import.py` — Zoom VTT lightweight path

**Files:**
- Create: `src/meeting_transcribe/vtt_import.py`
- Test: `tests/test_vtt_import.py`

**Interfaces:**
- Consumes: `naming.output_basename` (Task 3), `output_writer.merge_cues_into_turns` + `write_output_files` (Task 4), `config.get_paths`/`ensure_directories` (Task 2).
- Produces: `parse_vtt(path: Path) -> list[dict]` (each cue: `{"start", "end", "speaker", "text"}`), `import_vtt(source_path: Path, paths: config.Paths, title: str | None = None) -> tuple[Path, Path]`, CLI `main()`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_vtt_import.py
from pathlib import Path

from meeting_transcribe import config, vtt_import

_SAMPLE_VTT = """WEBVTT

00:00:00.000 --> 00:00:02.000
Alice: Hello there

00:00:02.500 --> 00:00:04.000
Alice: how are you

00:00:04.500 --> 00:00:06.000
Bob: Fine thanks
"""


def test_parse_vtt_extracts_speaker_and_text(tmp_path):
    vtt_path = tmp_path / "zoom_meeting.vtt"
    vtt_path.write_text(_SAMPLE_VTT)

    cues = vtt_import.parse_vtt(vtt_path)

    assert cues == [
        {"start": 0.0, "end": 2.0, "speaker": "Alice", "text": "Hello there"},
        {"start": 2.5, "end": 4.0, "speaker": "Alice", "text": "how are you"},
        {"start": 4.5, "end": 6.0, "speaker": "Bob", "text": "Fine thanks"},
    ]


def test_parse_vtt_defaults_speaker_to_unknown_when_no_colon(tmp_path):
    vtt_path = tmp_path / "no_speaker.vtt"
    vtt_path.write_text("WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nHello there\n")

    cues = vtt_import.parse_vtt(vtt_path)

    assert cues == [{"start": 0.0, "end": 1.0, "speaker": "Unknown", "text": "Hello there"}]


def test_import_vtt_writes_output_and_deletes_source(tmp_path, monkeypatch):
    monkeypatch.setenv("MEETINGS_DIR", str(tmp_path / "meetings"))
    paths = config.get_paths()
    config.ensure_directories(paths)

    source = paths.inbox_dir / "zoom_meeting.vtt"
    source.write_text(_SAMPLE_VTT)

    json_path, txt_path = vtt_import.import_vtt(source, paths)

    assert json_path.exists()
    assert txt_path.exists()
    assert not source.exists()
    assert "Alice: Hello there how are you" in txt_path.read_text()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_vtt_import.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

```python
# src/meeting_transcribe/vtt_import.py
import argparse
import re
from pathlib import Path

import webvtt

from . import config, naming
from .output_writer import merge_cues_into_turns, write_output_files

_SPEAKER_PATTERN = re.compile(r"^\s*([^:\n]{1,60}):\s*(.*)$", re.DOTALL)


def parse_vtt(path: Path) -> list[dict]:
    cues = []
    for caption in webvtt.read(str(path)):
        text = caption.text.strip()
        match = _SPEAKER_PATTERN.match(text)
        if match:
            speaker, spoken = match.group(1).strip(), match.group(2).strip()
        else:
            speaker, spoken = "Unknown", text
        cues.append(
            {
                "start": caption.start_in_seconds,
                "end": caption.end_in_seconds,
                "speaker": speaker,
                "text": spoken,
            }
        )
    return cues


def import_vtt(
    source_path: Path, paths: config.Paths, title: str | None = None
) -> tuple[Path, Path]:
    cues = parse_vtt(source_path)
    turns = merge_cues_into_turns(cues)
    basename = naming.output_basename(source_path, title)
    metadata = {
        "recording_id": basename,
        "source_path": str(source_path),
        "source_type": "zoom_vtt",
    }
    json_path, txt_path = write_output_files(paths.output_dir, basename, turns, metadata)
    source_path.unlink()
    return json_path, txt_path


def main() -> None:
    parser = argparse.ArgumentParser(description="File a Zoom .vtt export as a meeting note.")
    parser.add_argument("vtt_path")
    parser.add_argument("--title", default=None)
    args = parser.parse_args()

    paths = config.get_paths()
    config.ensure_directories(paths)
    json_path, txt_path = import_vtt(Path(args.vtt_path), paths, args.title)
    print(f"Wrote {json_path} and {txt_path}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_vtt_import.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/meeting_transcribe/vtt_import.py tests/test_vtt_import.py
git commit -m "feat: add vtt_import for lightweight Zoom transcript filing"
```

---

### Task 10: `enroll.py` — voiceprint enrollment CLI

**Files:**
- Create: `src/meeting_transcribe/enroll.py`
- Test: `tests/test_enroll.py`

**Interfaces:**
- Consumes: `embedding_extraction.centroid_for_segments`/`EmbedFn`/`load_pyannote_embedder` (Task 7), `voiceprints.save_voiceprint` (Task 5), `config.get_paths`/`ensure_directories`/`HF_TOKEN_ENV_VAR` (Task 2).
- Produces: `enroll_from_audio(embed_fn, audio_path: Path, duration_seconds: float, chunk_seconds: float = 5.0) -> list[float]`, CLI `main()` (real model load, not unit tested).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_enroll.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_enroll.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

```python
# src/meeting_transcribe/enroll.py
import argparse
import os
from pathlib import Path

from . import config, voiceprints
from .embedding_extraction import EmbedFn, centroid_for_segments, load_pyannote_embedder


def enroll_from_audio(
    embed_fn: EmbedFn, audio_path: Path, duration_seconds: float, chunk_seconds: float = 5.0
) -> list[float]:
    spans = []
    start = 0.0
    while start < duration_seconds:
        end = min(start + chunk_seconds, duration_seconds)
        spans.append((start, end))
        start = end
    return centroid_for_segments(embed_fn, audio_path, spans)


def main() -> None:
    parser = argparse.ArgumentParser(description="Enroll a named voiceprint from a clean audio sample.")
    parser.add_argument("--name", required=True)
    parser.add_argument("--audio", required=True)
    args = parser.parse_args()

    hf_token = os.environ.get(config.HF_TOKEN_ENV_VAR)
    if not hf_token:
        raise SystemExit(f"{config.HF_TOKEN_ENV_VAR} environment variable is required")

    import torchaudio

    audio_path = Path(args.audio)
    info = torchaudio.info(str(audio_path))
    duration_seconds = info.num_frames / info.sample_rate

    embed_fn = load_pyannote_embedder(hf_token)
    embedding = enroll_from_audio(embed_fn, audio_path, duration_seconds)

    paths = config.get_paths()
    config.ensure_directories(paths)
    voiceprints.save_voiceprint(paths.voiceprints_path, args.name, embedding, source="enroll")
    print(f"Enrolled '{args.name}' from {audio_path} into {paths.voiceprints_path}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_enroll.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add src/meeting_transcribe/enroll.py tests/test_enroll.py
git commit -m "feat: add enroll CLI for voiceprint enrollment"
```

---

### Task 11: `pipeline.py` — full audio pipeline CLI

**Files:**
- Create: `src/meeting_transcribe/pipeline.py`

**Interfaces:**
- Consumes: `audio_convert.convert_to_wav16k_mono` (Task 8), `staging_builder.build_staging`/`longest_turns_for_speaker` (Task 6), `embedding_extraction.centroid_for_segments`/`load_pyannote_embedder` (Task 7), `voiceprints.load_voiceprints` (Task 5), `naming.build_recording_id` (Task 3), `config.get_paths`/`ensure_directories`/`get_match_threshold`/`HF_TOKEN_ENV_VAR` (Task 2).
- Produces: CLI `main()` that writes `.staging/<recording_id>.json` and prints a summary. This task has no automated tests — it is real-model glue, verified manually in Task 14.

This task is CLI glue with no pure logic of its own, so there is no red/green
test cycle — every piece it calls was already tested in its own task. Write
it directly, then verify manually per Step 3 below.

- [ ] **Step 1: Write the implementation**

```python
# src/meeting_transcribe/pipeline.py
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import whisperx

from . import config, naming, voiceprints
from .audio_convert import convert_to_wav16k_mono
from .embedding_extraction import centroid_for_segments, load_pyannote_embedder
from .staging_builder import build_staging, longest_turns_for_speaker

DEVICE = "cpu"
COMPUTE_TYPE = "int8"
WHISPER_MODEL = "large-v3"
MAX_EMBEDDING_SPANS = 5


def run_pipeline(source_path: Path, paths: config.Paths, hf_token: str, title: str | None = None) -> Path:
    config.ensure_directories(paths)

    wav_path = paths.staging_dir / f"{source_path.stem}.wav"
    convert_to_wav16k_mono(source_path, wav_path)

    model = whisperx.load_model(WHISPER_MODEL, DEVICE, compute_type=COMPUTE_TYPE)
    audio = whisperx.load_audio(str(wav_path))
    transcription = model.transcribe(audio)

    align_model, align_metadata = whisperx.load_align_model(
        language_code=transcription["language"], device=DEVICE
    )
    aligned = whisperx.align(transcription["segments"], align_model, align_metadata, audio, DEVICE)

    diarize_model = whisperx.diarize.DiarizationPipeline(use_auth_token=hf_token, device=DEVICE)
    diarize_segments = diarize_model(str(wav_path))
    result = whisperx.assign_word_speakers(diarize_segments, aligned)

    words = [
        {
            "start": word["start"],
            "end": word["end"],
            "word": word["word"],
            "speaker": word.get("speaker", "SPEAKER_UNKNOWN"),
        }
        for segment in result["segments"]
        for word in segment["words"]
        if "start" in word and "end" in word and "speaker" in word
    ]

    embed_fn = load_pyannote_embedder(hf_token)
    raw_speakers = sorted({word["speaker"] for word in words})
    speaker_embeddings = {}
    for raw_label in raw_speakers:
        spans = [
            (turn["start"], turn["end"])
            for turn in longest_turns_for_speaker(words, raw_label, MAX_EMBEDDING_SPANS)
        ]
        speaker_embeddings[raw_label] = centroid_for_segments(embed_fn, wav_path, spans)

    voiceprint_db = voiceprints.load_voiceprints(paths.voiceprints_path)
    threshold = config.get_match_threshold()

    recording_id = naming.build_recording_id(source_path, title)
    duration_seconds = words[-1]["end"] if words else 0.0
    recorded_at = datetime.now(timezone.utc).isoformat()

    staging = build_staging(
        recording_id=recording_id,
        source_path=str(source_path),
        recorded_at=recorded_at,
        duration_seconds=duration_seconds,
        words=words,
        speaker_embeddings=speaker_embeddings,
        voiceprint_db=voiceprint_db,
        threshold=threshold,
    )

    staging_path = paths.staging_dir / f"{recording_id}.json"
    staging_path.write_text(json.dumps(staging, indent=2))
    wav_path.unlink(missing_ok=True)

    matched = sum(1 for s in staging["speakers"].values() if s["status"] == "matched")
    unmatched = len(staging["speakers"]) - matched
    print(f"Staged {staging_path} — {matched} speaker(s) matched, {unmatched} need disambiguation.")
    print(f"Match threshold in use: {threshold} (unvalidated default unless you've calibrated it).")

    return staging_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Transcribe, diarize, and stage a meeting recording.")
    parser.add_argument("audio_path")
    parser.add_argument("--title", default=None)
    args = parser.parse_args()

    hf_token = os.environ.get(config.HF_TOKEN_ENV_VAR)
    if not hf_token:
        raise SystemExit(f"{config.HF_TOKEN_ENV_VAR} environment variable is required")

    paths = config.get_paths()
    run_pipeline(Path(args.audio_path), paths, hf_token, args.title)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify it imports cleanly**

Run: `uv run python -c "from meeting_transcribe import pipeline; print('ok')"`
Expected: prints `ok` (confirms no syntax/import errors; real execution is
verified against a real recording in Task 14)

- [ ] **Step 3: Commit**

```bash
git add src/meeting_transcribe/pipeline.py
git commit -m "feat: add pipeline CLI wiring whisperx and pyannote to staging_builder"
```

---

### Task 12: `finalize.py` — apply resolutions and write final output

**Files:**
- Create: `src/meeting_transcribe/finalize.py`
- Test: `tests/test_finalize.py`

**Interfaces:**
- Consumes: `output_writer.merge_words_into_turns`/`write_output_files` (Task 4), `voiceprints.save_voiceprint` (Task 5), `naming.output_basename` (Task 3), `config.get_paths` (Task 2).
- Produces: `apply_resolutions(staging: dict, resolutions: dict) -> dict[str, str]`, `finalize(staging_path: Path, resolutions_path: Path, paths: config.Paths) -> tuple[Path, Path]`, CLI `main()`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_finalize.py
import json
from pathlib import Path

import pytest

from meeting_transcribe import config, finalize, voiceprints


def _staging(source_path: Path) -> dict:
    return {
        "recording_id": "team-standup-1799500000",
        "source_path": str(source_path),
        "recorded_at": "2026-09-07T09:00:00+10:00",
        "duration_seconds": 4.0,
        "words": [
            {"start": 0.0, "end": 0.5, "word": "Hi", "speaker": "SPEAKER_00"},
            {"start": 1.0, "end": 1.5, "word": "Hello", "speaker": "SPEAKER_01"},
        ],
        "speakers": {
            "SPEAKER_00": {"status": "matched", "name": "Alice", "score": 0.9},
            "SPEAKER_01": {
                "status": "unmatched",
                "best_guess": None,
                "score": 0.4,
                "centroid_embedding": [0.0, 1.0],
                "snippets": [{"start": 1.0, "end": 1.5, "text": "Hello"}],
            },
        },
    }


def _write_staging_and_resolutions(tmp_path, resolutions):
    source = tmp_path / "inbox" / "Team Standup.m4a"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"fake")

    staging_path = tmp_path / "staging" / "team-standup-1799500000.json"
    staging_path.parent.mkdir(parents=True)
    staging_path.write_text(json.dumps(_staging(source)))

    resolutions_path = tmp_path / "staging" / "team-standup-1799500000.resolutions.json"
    resolutions_path.write_text(json.dumps(resolutions))

    return source, staging_path, resolutions_path


def test_apply_resolutions_uses_matched_name_and_resolution_name():
    staging = _staging(Path("/tmp/x.m4a"))
    labels = finalize.apply_resolutions(staging, {"SPEAKER_01": {"name": "Bob", "enroll": True}})
    assert labels == {"SPEAKER_00": "Alice", "SPEAKER_01": "Bob"}


def test_apply_resolutions_falls_back_to_raw_label_when_unknown():
    staging = _staging(Path("/tmp/x.m4a"))
    labels = finalize.apply_resolutions(staging, {"SPEAKER_01": {"name": None, "enroll": False}})
    assert labels == {"SPEAKER_00": "Alice", "SPEAKER_01": "SPEAKER_01"}


def test_finalize_writes_output_enrolls_and_cleans_up(tmp_path, monkeypatch):
    monkeypatch.setenv("MEETINGS_DIR", str(tmp_path / "meetings"))
    paths = config.get_paths()
    config.ensure_directories(paths)

    source, staging_path, resolutions_path = _write_staging_and_resolutions(
        tmp_path, {"SPEAKER_01": {"name": "Bob", "enroll": True}}
    )
    staging = json.loads(staging_path.read_text())
    staging["source_path"] = str(source)
    staging_path.write_text(json.dumps(staging))

    json_path, txt_path = finalize.finalize(staging_path, resolutions_path, paths)

    assert json_path.parent == paths.output_dir
    assert "Alice: Hi" in txt_path.read_text()
    assert "Bob: Hello" in txt_path.read_text()

    db = voiceprints.load_voiceprints(paths.voiceprints_path)
    assert db["Bob"]["embedding"] == [0.0, 1.0]
    assert db["Bob"]["source"] == "session"

    assert not source.exists()
    assert not staging_path.exists()
    assert not resolutions_path.exists()


def test_finalize_leaves_generic_label_when_resolution_says_dont_know(tmp_path, monkeypatch):
    monkeypatch.setenv("MEETINGS_DIR", str(tmp_path / "meetings"))
    paths = config.get_paths()
    config.ensure_directories(paths)

    source, staging_path, resolutions_path = _write_staging_and_resolutions(
        tmp_path, {"SPEAKER_01": {"name": None, "enroll": False}}
    )
    staging = json.loads(staging_path.read_text())
    staging["source_path"] = str(source)
    staging_path.write_text(json.dumps(staging))

    _, txt_path = finalize.finalize(staging_path, resolutions_path, paths)

    assert "SPEAKER_01: Hello" in txt_path.read_text()
    db = voiceprints.load_voiceprints(paths.voiceprints_path)
    assert "Bob" not in db


def test_finalize_leaves_source_and_staging_in_place_on_write_failure(tmp_path, monkeypatch):
    monkeypatch.setenv("MEETINGS_DIR", str(tmp_path / "meetings"))
    paths = config.get_paths()
    config.ensure_directories(paths)

    source, staging_path, resolutions_path = _write_staging_and_resolutions(
        tmp_path, {"SPEAKER_01": {"name": "Bob", "enroll": True}}
    )
    staging = json.loads(staging_path.read_text())
    staging["source_path"] = str(source)
    staging_path.write_text(json.dumps(staging))

    def boom(*args, **kwargs):
        raise RuntimeError("disk full")

    monkeypatch.setattr(finalize, "write_output_files", boom)

    with pytest.raises(RuntimeError):
        finalize.finalize(staging_path, resolutions_path, paths)

    assert source.exists()
    assert staging_path.exists()
    assert resolutions_path.exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_finalize.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

```python
# src/meeting_transcribe/finalize.py
import argparse
import json
from pathlib import Path

from . import config, naming, voiceprints
from .output_writer import merge_words_into_turns, write_output_files


def apply_resolutions(staging: dict, resolutions: dict) -> dict[str, str]:
    labels: dict[str, str] = {}
    for raw_label, info in staging["speakers"].items():
        if info["status"] == "matched":
            labels[raw_label] = info["name"]
            continue
        resolution = resolutions.get(raw_label)
        name = resolution["name"] if resolution else None
        labels[raw_label] = name if name else raw_label
    return labels


def finalize(staging_path: Path, resolutions_path: Path, paths: config.Paths) -> tuple[Path, Path]:
    staging = json.loads(staging_path.read_text())
    resolutions = json.loads(resolutions_path.read_text()) if resolutions_path.exists() else {}

    labels = apply_resolutions(staging, resolutions)
    turns = merge_words_into_turns(staging["words"], labels)

    source_path = Path(staging["source_path"])
    basename = naming.output_basename(source_path)
    metadata = {
        "recording_id": staging["recording_id"],
        "source_path": staging["source_path"],
        "source_type": "audio",
        "recorded_at": staging["recorded_at"],
        "duration_seconds": staging["duration_seconds"],
    }

    json_path, txt_path = write_output_files(
        paths.output_dir, basename, turns, metadata, words=staging["words"]
    )

    for raw_label, info in staging["speakers"].items():
        if info["status"] != "unmatched":
            continue
        resolution = resolutions.get(raw_label)
        if resolution and resolution.get("name") and resolution.get("enroll"):
            voiceprints.save_voiceprint(
                paths.voiceprints_path,
                resolution["name"],
                info["centroid_embedding"],
                source="session",
            )

    if source_path.exists():
        source_path.unlink()
    staging_path.unlink()
    if resolutions_path.exists():
        resolutions_path.unlink()

    return json_path, txt_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply speaker resolutions and finalize a transcript.")
    parser.add_argument("--staging", required=True)
    parser.add_argument("--resolutions", required=True)
    args = parser.parse_args()

    paths = config.get_paths()
    json_path, txt_path = finalize(Path(args.staging), Path(args.resolutions), paths)
    print(f"Wrote {json_path} and {txt_path}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_finalize.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add src/meeting_transcribe/finalize.py tests/test_finalize.py
git commit -m "feat: add finalize CLI to apply speaker resolutions and clean up sources"
```

---

### Task 13: `SKILL.md`, symlink installation, and data directory bootstrap

**Files:**
- Create: `SKILL.md`
- Modify: `README.md` (add "Skill installation" section)

**Interfaces:**
- Produces: an installed skill discoverable by Claude Code, and the bootstrapped `~/Documents/meetings` directory tree.

- [ ] **Step 1: Write `SKILL.md`**

```markdown
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
   "zoom_3"). If so, ask the user for a short meeting title first and pass
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
```

- [ ] **Step 2: Symlink into `~/.claude/skills/`**

Run:
```bash
ln -s /Users/michael/Projects/skillz/meeting-transcribe /Users/michael/.claude/skills/meeting-transcribe
```
Expected: `ls -la ~/.claude/skills/meeting-transcribe` shows a symlink to the project directory, matching this user's existing skill-installation convention.

- [ ] **Step 3: Bootstrap the data directory**

Run:
```bash
cd /Users/michael/Projects/skillz/meeting-transcribe
uv run python -c "from meeting_transcribe import config; config.ensure_directories(config.get_paths())"
```
Expected: creates `~/Documents/meetings/{inbox,output,data,.staging}` if they
don't already exist.

- [ ] **Step 4: Add a "Skill installation" section to `README.md`**

```markdown
## Skill installation

This project is symlinked into `~/.claude/skills/meeting-transcribe` so
Claude Code picks it up automatically:

```bash
ln -s ~/Projects/skillz/meeting-transcribe ~/.claude/skills/meeting-transcribe
```
```

- [ ] **Step 5: Commit**

```bash
git add SKILL.md README.md
git commit -m "docs: add SKILL.md and skill installation instructions"
```

---

### Task 14: Manual end-to-end verification

**Files:** none (verification only)

This is the acceptance gate the automated tests can't cover — real WhisperX
and pyannote model calls against real audio, and the interactive loop as it
actually feels in a Claude Code session.

- [ ] **Step 1: Verify environment setup**

Confirm `HF_TOKEN` is set and both gated model pages have accepted terms.
Run `uv run python -c "from meeting_transcribe.embedding_extraction import load_pyannote_embedder; import os; load_pyannote_embedder(os.environ['HF_TOKEN']); print('ok')"` from the project directory.
Expected: prints `ok` (model loads without an auth error).

- [ ] **Step 2: Enroll a real voiceprint**

Record or use an existing ~30 second clean clip of one known speaker as
`sample.wav`. Run:
```
uv run python -m meeting_transcribe.enroll --name "<Your Name>" --audio sample.wav
```
Expected: prints an "Enrolled" confirmation; `data/voiceprints.json` contains
the new entry.

- [ ] **Step 3: Run the audio pipeline on a short real recording with at least one enrolled and one unenrolled speaker**

Drop a short (2-5 minute) `.m4a` into `inbox/`. In a Claude Code session,
say "process the inbox" and follow SKILL.md's flow through to the
disambiguation questions.
Expected: the enrolled speaker is labelled automatically; the unenrolled
speaker triggers a one-at-a-time question with real snippets; answering with
a name and "yes" to enrollment adds them to `voiceprints.json`; the source
`.m4a` is deleted after finalize; `output/` contains a correctly labelled
`.json` and `.txt`.

- [ ] **Step 4: Run the VTT path on a real Zoom export**

Drop a `.vtt` from a Zoom recording into `inbox/`. Say "process the inbox"
again.
Expected: no questions asked; `output/` gains a `.json`/`.txt` pair using
Zoom's own speaker labels; the source `.vtt` is deleted.

- [ ] **Step 5: Sanity-check the threshold**

Note, in the README or in conversation, whether the 0.75 default produced
any false match or false non-match during Steps 3-4, and adjust
`MEETING_MATCH_THRESHOLD` if needed. This is expected to take more than one
real recording to calibrate properly — flag it as ongoing, not a one-time
fix.

- [ ] **Step 6: Final commit**

```bash
cd /Users/michael/Projects/skillz/meeting-transcribe
git add -A
git commit -m "chore: note manual verification results" --allow-empty
```
(Only include this commit if verification notes were actually added
somewhere, e.g. the README; otherwise skip — don't create an empty commit
for its own sake.)

---

## Self-Review Notes

- **Spec coverage:** environment/Apple Silicon caveat (Task 1), centroid
  embeddings (Tasks 5-7), enrollment (Task 10), full pipeline (Task 11),
  interactive disambiguation (Task 13's SKILL.md + Task 14 manual
  verification), finalize/cleanup semantics (Task 12), VTT lightweight path
  (Task 9), inbox dispatch (Task 13), SKILL.md packaging (Task 13), testing
  strategy scoped to deterministic logic (all test-bearing tasks) — every
  spec section maps to a task.
- **Naming inconsistency resolved:** the spec's directory tree implied
  `<date>-<slug>` output filenames while its Finalize section said
  `<recording_id>.json` (which includes a timestamp, not a date). Resolved
  in Global Constraints and implemented consistently: `recording_id` is
  staging-only, `output_basename` is what reaches `output/`.
- **Type consistency checked:** `Paths`, `EmbedFn`, staging/turn/cue dict
  shapes, and every function signature are used identically across the
  tasks that produce and consume them.
