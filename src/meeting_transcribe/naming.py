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
