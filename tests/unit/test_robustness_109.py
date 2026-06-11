"""Tests for the browser/CLI robustness batch (Issue #109).

Four findings from the audit remainder:

* UI-010: browser actions crashed on an EMPTY mutants table —
  ``cursor_row`` is 0 even with zero rows, so ``get_row_at(0)`` raised
  ``RowDoesNotExist``; the ``None`` guard was dead code.
* UI-011: a corrupted pyproject.toml surfaced as a RAW traceback in
  ``show``/``apply`` (``run`` got the clean path in #102) — ConfigError
  now exits 2 with the message, matching the #102 convention.  In the
  browser the diff thread renders exceptions inline by design.
* UI-013: empty-DB exit codes were undefined convention: ``results`` 0,
  ``export-cicd-stats`` 1, ``time-estimates`` 0.  The DOCUMENTED
  convention now: human-informational queries exit 0 with an explicit
  notice; the CI export exits 1 because an empty result set in a gate
  context means the pipeline ran nothing.
* UI-016: ``--no-progress`` also suppressed the END summary — a quiet
  run ended with no result at all (seen live in the Sprint 33 dogfooding
  mid-gate).  The summary always prints; only live progress is optional.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner

from mutmut_win.browser import ResultBrowser
from mutmut_win.cli import cli
from mutmut_win.config import MutmutConfig
from mutmut_win.models import MutationTask, TaskCompleted, TaskStarted
from mutmut_win.orchestrator import MutationOrchestrator
from mutmut_win.stats import MutmutStats, save_stats

if TYPE_CHECKING:
    from pathlib import Path


class TestEmptyMutantsTableDoesNotCrashActions:
    @pytest.mark.asyncio
    async def test_selection_on_empty_table_returns_none(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # UI-010: no mutants/, no DB -> both tables stay empty. cursor_row
        # is 0 even then — get_row_at(0) raised RowDoesNotExist before.
        monkeypatch.chdir(tmp_path)
        app = ResultBrowser(db_path=tmp_path / "absent.sqlite")
        async with app.run_test():
            assert app._get_selected_mutant_name() is None


class TestConfigErrorIsCleanInShowAndApply:
    def _corrupt_project(self, tmp_path: Path) -> None:
        (tmp_path / "mutants").mkdir()
        (tmp_path / "pyproject.toml").write_text("[tool.mutmut\nbroken", encoding="utf-8")

    @pytest.mark.parametrize("command", ["show", "apply"])
    def test_corrupt_pyproject_exits_2_without_traceback(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, command: str
    ) -> None:
        # UI-011: the #102 convention — config errors are exit 2 plus the
        # message, never a raw traceback.
        monkeypatch.chdir(tmp_path)
        self._corrupt_project(tmp_path)

        result = CliRunner().invoke(cli, [command, "src.mod.x_f__mutmut_1"])

        assert result.exit_code == 2
        assert "pyproject.toml" in result.output + str(result.stderr)
        assert result.exception is None or isinstance(result.exception, SystemExit)


class TestEmptyDbExitCodeConvention:
    """UI-013: one documented convention, pinned for all three commands."""

    def test_results_is_informational_exit_0(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        result = CliRunner().invoke(cli, ["results"])
        assert result.exit_code == 0
        assert "No results" in result.output

    def test_time_estimates_is_informational_exit_0(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        mutants_dir = tmp_path / "mutants"
        mutants_dir.mkdir()
        save_stats(
            MutmutStats(
                tests_by_mangled_function_name={},
                duration_by_test={"tests/test_x.py::test_one": 0.5},
                stats_time=1.0,
            ),
            mutants_dir,
        )
        result = CliRunner().invoke(cli, ["time-estimates"])
        assert result.exit_code == 0
        assert "No results" in result.output

    def test_export_cicd_is_a_gate_exit_1(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # A CI gate fed zero data must fail loudly — silence would read as
        # "pipeline green" when the pipeline ran nothing.
        monkeypatch.chdir(tmp_path)
        result = CliRunner().invoke(cli, ["export-cicd-stats"])
        assert result.exit_code == 1


class TestSummaryAlwaysPrints:
    def _run(self, tmp_path: Path, *, no_progress: bool) -> Any:
        src = tmp_path / "src"
        src.mkdir()
        (src / "target.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")

        captured_tasks: list[MutationTask] = []
        executor = MagicMock()
        executor.start.side_effect = captured_tasks.extend

        def fake_get_events() -> Any:
            pid = os.getpid()
            for task in captured_tasks:
                yield TaskStarted(mutant_name=task.mutant_name, worker_pid=pid)
                yield TaskCompleted(
                    mutant_name=task.mutant_name, worker_pid=pid, exit_code=1, duration=0.01
                )

        executor.get_events.side_effect = fake_get_events

        runner = MagicMock()
        runner.run_clean_test.return_value = 0
        runner.run_forced_fail.return_value = 1
        runner.collect_tests.return_value = []

        orch = MutationOrchestrator(
            MutmutConfig(max_children=1, timeout_multiplier=2.0, paths_to_mutate=["src"]),
            runner=runner,
            executor=executor,
            db_path=tmp_path / "db",
            no_progress=no_progress,
        )
        return orch.run()

    def test_no_progress_still_prints_the_summary(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # UI-016: the mid-gate pilot ended with NO result output at all.
        monkeypatch.chdir(tmp_path)
        self._run(tmp_path, no_progress=True)
        out = capsys.readouterr().out
        assert "Mutation Testing Summary" in out
        assert "Score" in out

    def test_no_progress_suppresses_only_live_lines(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.chdir(tmp_path)
        self._run(tmp_path, no_progress=True)
        out = capsys.readouterr().out
        assert "⏰" not in out  # the live progress line's bucket strip
