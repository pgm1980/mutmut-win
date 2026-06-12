"""Tests for the type-check baseline subtraction + JSON-flag hint (issue #131).

360°-B4: a PRE-EXISTING type error inside a function body replicates into
every mutant copy of that function — the checker reports it in every
``x_f__mutmut_N`` range and ALL its mutants were falsely 'caught by type
check' (score inflation). The errors inside the ``__mutmut_orig`` copy ARE
the baseline: a mutant only counts as caught when it carries at least one
error that is NOT (line-offset, text)-identical to an orig-copy error.

360°-A5: the README documented ``type_check_command = ["mypy", "src/"]`` —
guaranteed to abort because the parser requires JSON output. The
orchestrator now warns with the concrete flag BEFORE running the checker.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

from mutmut_win.models import MutationTask
from mutmut_win.orchestrator import _filter_with_type_checker
from mutmut_win.type_checking import TypeCheckingError

if TYPE_CHECKING:
    import pytest

_STAGED = """\
def f():
    return _mutmut_trampoline()


def x_f__mutmut_orig():
    value = "pre-existing"
    return value


def x_f__mutmut_1():
    value = "pre-existing"
    return value


def x_f__mutmut_2():
    value = "pre-existing"
    return value
"""


def _line_of(source: str, needle: str) -> int:
    """1-based line number of the first line containing *needle*."""
    for index, line in enumerate(source.splitlines(), start=1):
        if needle in line:
            return index
    msg = f"needle {needle!r} not found"
    raise AssertionError(msg)


def _staging(tmp_path: Path) -> Path:
    staged = tmp_path / "mutants" / "src" / "mod.py"
    staged.parent.mkdir(parents=True)
    staged.write_text(_STAGED, encoding="utf-8")
    return staged


class TestBaselineSubtraction:
    def test_replicated_baseline_error_does_not_catch_the_mutant(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.chdir(tmp_path)
        _staging(tmp_path)
        # The same error text at the SAME offset inside orig and mutant 1
        # (offset 1 = the 'value =' line of each copy) — replicated baseline.
        orig_line = _line_of(_STAGED, "def x_f__mutmut_orig") + 1
        mutant1_line = _line_of(_STAGED, "def x_f__mutmut_1") + 1
        # Mutant 2 carries a NEW error (different text) at the same offset.
        mutant2_line = _line_of(_STAGED, "def x_f__mutmut_2") + 1
        errors = [
            TypeCheckingError(Path("src/mod.py"), orig_line, "incompatible str"),
            TypeCheckingError(Path("src/mod.py"), mutant1_line, "incompatible str"),
            TypeCheckingError(Path("src/mod.py"), mutant2_line, "mutation broke it"),
        ]
        tasks = [
            MutationTask(mutant_name="mod.x_f__mutmut_1"),
            MutationTask(mutant_name="mod.x_f__mutmut_2"),
        ]
        with patch("mutmut_win.type_checking.run_type_checker", return_value=errors):
            remaining, caught = _filter_with_type_checker(tasks, {}, ["mypy", "--output=json", "."])

        assert caught == {"mod.x_f__mutmut_2"}  # only the NEW error catches
        assert [t.mutant_name for t in remaining] == ["mod.x_f__mutmut_1"]
        err = capsys.readouterr().err
        assert "pre-existing" in err  # the subtraction is announced, not silent

    def test_without_baseline_errors_behavior_is_unchanged(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        _staging(tmp_path)
        mutant1_line = _line_of(_STAGED, "def x_f__mutmut_1") + 1
        errors = [TypeCheckingError(Path("src/mod.py"), mutant1_line, "mutation broke it")]
        tasks = [
            MutationTask(mutant_name="mod.x_f__mutmut_1"),
            MutationTask(mutant_name="mod.x_f__mutmut_2"),
        ]
        with patch("mutmut_win.type_checking.run_type_checker", return_value=errors):
            remaining, caught = _filter_with_type_checker(tasks, {}, ["mypy", "--output=json", "."])
        assert caught == {"mod.x_f__mutmut_1"}
        assert [t.mutant_name for t in remaining] == ["mod.x_f__mutmut_2"]


class TestJsonFlagHint:
    def test_mypy_without_output_flag_warns_with_the_fix(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # 360°-A5: the documented-config failure mode gets a concrete hint
        # BEFORE the parser aborts with 'did not return JSON'.
        monkeypatch.chdir(tmp_path)
        _staging(tmp_path)
        with patch("mutmut_win.type_checking.run_type_checker", return_value=[]):
            _filter_with_type_checker([], {}, ["mypy", "src/"])
        assert "--output=json" in capsys.readouterr().err

    def test_pyright_without_outputjson_warns(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.chdir(tmp_path)
        _staging(tmp_path)
        with patch("mutmut_win.type_checking.run_type_checker", return_value=[]):
            _filter_with_type_checker([], {}, ["pyright", "."])
        assert "--outputjson" in capsys.readouterr().err

    def test_correct_command_stays_silent(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.chdir(tmp_path)
        _staging(tmp_path)
        with patch("mutmut_win.type_checking.run_type_checker", return_value=[]):
            _filter_with_type_checker([], {}, ["mypy", "--output=json", "src/"])
        assert capsys.readouterr().err == ""
