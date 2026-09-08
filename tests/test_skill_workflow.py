"""Check the executable filename example without a shell or ML dependencies."""

from pathlib import Path
import shlex
import subprocess
import sys

import pytest


@pytest.mark.parametrize("stem, expected", [
    ("Recording", "True"),
    ("O'Brien planning", "False"),
    ("x')); print('INJECTED'); #", "False"),
    ("budget $(printf injected) `printf injected`", "False"),
])
def test_documented_filename_check_treats_stem_as_data(stem, expected):
    skill = (Path(__file__).resolve().parents[1] / "SKILL.md").read_text()
    line = next(line for line in skill.splitlines() if "uv run python -c" in line)
    args = shlex.split(line.split("uv run python ", 1)[1])
    supplied = [arg.replace("<filename-without-extension>", stem).replace("$stem", stem) for arg in args]
    result = subprocess.run([sys.executable, *supplied], text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == expected
