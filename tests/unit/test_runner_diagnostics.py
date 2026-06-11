"""Tests for runner diagnostics (Issue #99, audit A2-RN-001/002).

All three runner phases piped pytest to DEVNULL: a failing gate showed ZERO
output, and exit codes 2/4/5 were not decoded — everything got the
misleading "Fix tests before mutating".  And ``extra_paths`` (Bug #69) was
missing from the runner's PYTHONPATH, so affected projects failed the clean
gate with an ImportError nobody could see.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest

from mutmut_win.config import MutmutConfig
from mutmut_win.runner import PytestRunner, decode_pytest_exit

if TYPE_CHECKING:
    from pathlib import Path


class TestDecodePytestExit:
    @pytest.mark.parametrize(
        ("code", "needle"),
        [
            (1, "fail"),
            (2, "collection"),
            (3, "internal"),
            (4, "usage"),
            (5, "no tests"),
            (36, "timed out"),
        ],
    )
    def test_known_exit_classes_are_explained(self, code: int, needle: str) -> None:
        assert needle in decode_pytest_exit(code).lower()

    def test_unknown_code_is_still_a_string(self) -> None:
        assert decode_pytest_exit(77)


class TestPhaseOutputCapture:
    def _fail_with_output(self, runner_call: Any, text: bytes) -> tuple[int, str | None]:
        runner = PytestRunner(MutmutConfig())

        def fake_run(cmd: list[str], **kwargs: Any) -> MagicMock:  # noqa: ARG001
            os.write(kwargs["stdout"], text)
            completed = MagicMock()
            completed.returncode = 2
            return completed

        with patch("subprocess.run", side_effect=fake_run):
            exit_code = runner_call(runner)
        return exit_code, runner.last_diagnostic_output

    def test_clean_run_failure_captures_the_tail(self) -> None:
        exit_code, tail = self._fail_with_output(
            lambda r: r.run_clean_test(), b"!!! Interrupted: 1 error during collection !!!\n"
        )
        assert exit_code == 2
        assert tail is not None
        assert "error during collection" in tail

    def test_forced_fail_failure_captures_the_tail(self) -> None:
        _exit_code, tail = self._fail_with_output(
            lambda r: r.run_forced_fail("pkg.mod.x_f__mutmut_1"),
            b"ERROR: usage problem\n",
        )
        assert tail is not None
        assert "usage problem" in tail

    def test_successful_run_leaves_no_diagnostic(self) -> None:
        runner = PytestRunner(MutmutConfig())

        def fake_run(cmd: list[str], **kwargs: Any) -> MagicMock:  # noqa: ARG001
            completed = MagicMock()
            completed.returncode = 0
            return completed

        with patch("subprocess.run", side_effect=fake_run):
            assert runner.run_clean_test() == 0
        assert runner.last_diagnostic_output is None


class TestExtraPathsOnRunnerPythonpath:
    def test_extra_paths_reach_the_clean_gate_env(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # A2-RN-002 (double-verified): only the WORKER had extra_paths on
        # PYTHONPATH — the clean gate failed with an invisible ImportError
        # for every Bug-#69 project.
        monkeypatch.chdir(tmp_path)
        (tmp_path / "mutants" / "src").mkdir(parents=True)
        (tmp_path / "mutants" / "benchmarks").mkdir()

        runner = PytestRunner(MutmutConfig(extra_paths=["benchmarks"]))
        env = runner._mutants_env()

        entries = env["PYTHONPATH"].split(os.pathsep)
        expected = str((tmp_path / "mutants" / "benchmarks").absolute())
        assert expected in entries
