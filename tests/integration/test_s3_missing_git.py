"""Real Git prerequisite diagnostics and healthy incremental selection."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from typing import TYPE_CHECKING

import pytest
from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from pathlib import Path


class _ErrorReport(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    error: str
    exit_code: int


class _DryRunReport(BaseModel):
    total_mutants: int


def _project(path: Path) -> None:
    (path / "src/pkg").mkdir(parents=True)
    (path / "tests").mkdir()
    (path / "src/pkg/__init__.py").write_text("", encoding="utf-8")
    (path / "src/pkg/changed.py").write_text("def value():\n    return 1\n", encoding="utf-8")
    (path / "src/pkg/unchanged.py").write_text("def value():\n    return 3\n", encoding="utf-8")
    (path / "tests/test_value.py").write_text(
        "from pkg.changed import value\ndef test_value():\n    assert value() == 2\n",
        encoding="utf-8",
    )
    (path / "pyproject.toml").write_text(
        '[tool.mutmut]\npaths_to_mutate=["src/pkg"]\ntests_dir=["tests"]\n'
        '[tool.pytest.ini_options]\npythonpath=["src"]\n',
        encoding="utf-8",
    )


@pytest.mark.parametrize("output", ["text", "json"])
def test_missing_git_uses_usage_error_channel(tmp_path: Path, output: str) -> None:
    """An actual missing executable yields exit2 and the promised channels."""
    _project(tmp_path)
    environment = os.environ.copy()
    environment["PATH"] = str(tmp_path)
    assert shutil.which("git", path=environment["PATH"]) is None
    # Fixed interpreter and CLI arguments; only the test-owned PATH is changed.
    result = subprocess.run(  # noqa: S603
        [
            sys.executable,
            "-m",
            "mutmut_win",
            "run",
            "--since-commit",
            "HEAD",
            "--dry-run",
            "--output",
            output,
        ],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
        check=False,
    )
    assert result.returncode == 2, result.stdout + result.stderr
    assert "Traceback" not in result.stderr
    assert "git" in result.stderr.lower()
    if output == "json":
        error = _ErrorReport.model_validate_json(result.stdout)
        assert error.exit_code == 2
        assert "git" in error.error.lower()
    else:
        assert result.stdout == ""
    assert not (tmp_path / "mutants").exists()


def test_available_git_selects_only_changed_source(tmp_path: Path) -> None:
    """The real CLI retains ordinary Git selection and a nonempty population."""
    _project(tmp_path)
    git = shutil.which("git")
    assert git is not None, "Git is a required test prerequisite"
    for arguments in [
        ["init", "--quiet"],
        ["add", "src", "tests", "pyproject.toml"],
        [
            "-c",
            "user.name=S3 fixture",
            "-c",
            "user.email=s3@example.invalid",
            "commit",
            "--quiet",
            "-m",
            "baseline",
        ],
    ]:
        # Git is resolved by the host; all arguments are literal fixture setup.
        subprocess.run(  # noqa: S603
            [git, *arguments], cwd=tmp_path, check=True, capture_output=True
        )
    (tmp_path / "src/pkg/changed.py").write_text("def value():\n    return 2\n", encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "mutmut_win",
            "run",
            "--since-commit",
            "HEAD",
            "--dry-run",
            "--output",
            "json",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    report = _DryRunReport.model_validate_json(result.stdout)
    assert report.total_mutants == 5
    complete = subprocess.run(
        [sys.executable, "-m", "mutmut_win", "run", "--dry-run", "--output", "json"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
        check=False,
    )
    assert complete.returncode == 0, complete.stdout + complete.stderr
    assert _DryRunReport.model_validate_json(complete.stdout).total_mutants == 10
