"""A mypy finding status requires a diagnostic record (S3-073 / S3-082)."""

import subprocess
from unittest.mock import patch

import pytest
from hypothesis import given
from hypothesis import strategies as st

from mutmut_win.exceptions import TypeCheckCommandError
from mutmut_win.type_checking import run_type_checker


@given(stdout=st.text(alphabet=" \t\r\n", max_size=80))
def test_mypy_exit_one_without_diagnostics_is_failure(stdout: str) -> None:
    """Empty JSONL cannot turn a checker startup failure into a clean report."""
    completed = subprocess.CompletedProcess(
        ["python", "-m", "mypy"], 1, stdout=stdout, stderr="No module named mypy"
    )
    with (
        patch("mutmut_win.type_checking._run_type_check_process", return_value=completed),
        pytest.raises(TypeCheckCommandError, match=r"exit code 1.*No module named mypy"),
    ):
        run_type_checker(["python", "-m", "mypy", "--output=json", "."])


@pytest.mark.parametrize("returncode", [0, 1])
def test_mypy_notes_are_not_confused_with_absent_diagnostics(returncode: int) -> None:
    """A real JSON note record remains valid even when there are no errors."""
    completed = subprocess.CompletedProcess(
        ["mypy"],
        returncode,
        stdout='{"severity":"note","message":"Revealed type is int"}\n',
        stderr="",
    )
    with patch("mutmut_win.type_checking._run_type_check_process", return_value=completed):
        assert run_type_checker(["mypy", "--output=json", "."]) == []
