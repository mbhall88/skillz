"""Validate inbox sources and bind cleanup to the file that was processed."""

import stat
from pathlib import Path


def source_identity(source: Path, inbox: Path, suffix: str) -> dict:
    try:
        canonical = source.resolve(strict=True)
        info = source.lstat()
        valid = (
            stat.S_ISREG(info.st_mode)
            and canonical.is_relative_to(inbox.resolve(strict=True))
            and canonical.suffix.lower() == suffix
        )
    except (OSError, RuntimeError) as exc:
        raise ValueError(f"Source is unavailable: {source}") from exc
    if not valid:
        raise ValueError(f"Source must be a regular {suffix} file inside {inbox}: {source}")
    return {
        "path": str(canonical),
        **{key: getattr(info, f"st_{key}") for key in
           ("dev", "ino", "size", "mtime_ns", "ctime_ns")},
    }


def verify_source(source: Path, inbox: Path, suffix: str, expected: dict | None) -> None:
    if expected is None or source_identity(source, inbox, suffix) != expected:
        raise ValueError("Source identity is missing or changed; retain source and restage it")


def delete_verified_source(source: Path, inbox: Path, suffix: str, expected: dict) -> None:
    # Revalidate after all output/enrollment I/O, immediately before unlinking.
    verify_source(source, inbox, suffix, expected)
    source.unlink()
