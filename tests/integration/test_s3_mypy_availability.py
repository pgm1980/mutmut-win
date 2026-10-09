"""Native missing-checker and available-checker controls for S3-073 / S3-082."""

import sys
from typing import TYPE_CHECKING

import pytest

from mutmut_win import type_checking
from mutmut_win.exceptions import TypeCheckCommandError

if TYPE_CHECKING:
    import subprocess
    from pathlib import Path


@pytest.mark.integration
def test_real_missing_mypy_fails_visibly(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The real isolated interpreter cannot import mypy and must fail closed."""
    target = tmp_path / "bad.py"
    target.write_text('value: int = "bad"\n', encoding="utf-8")
    original_run = type_checking._run_type_check_process
    observed: list[subprocess.CompletedProcess[str]] = []

    def observe(command: list[str], *, timeout: float) -> subprocess.CompletedProcess[str]:
        result = original_run(command, timeout=timeout)
        observed.append(result)
        return result

    monkeypatch.setattr(type_checking, "_run_type_check_process", observe)
    with pytest.raises(TypeCheckCommandError, match=r"exit code 1.*No module named mypy"):
        type_checking.run_type_checker(
            [sys.executable, "-I", "-S", "-m", "mypy", "--output=json", str(target)]
        )
    assert len(observed) == 1
    assert observed[0].returncode == 1
    assert observed[0].stdout == ""
    assert "No module named mypy" in observed[0].stderr


@pytest.mark.integration
@pytest.mark.parametrize(
    ("source", "error_count"),
    [("value: int = 1\n", 0), ('value: int = "bad"\n', 1), ("reveal_type(1)\n", 0)],
    ids=["clean", "type-error", "notes-only"],
)
def test_available_mypy_preserves_clean_errors_and_notes(
    tmp_path: Path, source: str, error_count: int
) -> None:
    """The installed checker still distinguishes real errors from valid notes."""
    target = tmp_path / "target.py"
    target.write_text(source, encoding="utf-8")
    errors = type_checking.run_type_checker(
        [sys.executable, "-m", "mypy", "--output=json", "--no-incremental", str(target)]
    )
    assert len(errors) == error_count
