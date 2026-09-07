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
