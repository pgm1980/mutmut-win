"""Tests for the wave-2 CI-trust fixes (issue #127 / 360°-A6 + A7).

A7: a collapsed worker pool (all workers dead, tasks never started) ended
exactly like a successful run — ``was_interrupted`` stayed False, the CLI
exited 0 and a ``--min-score`` gate judged only the checked remainder:
CI false-green. A6: ``--output json`` stdout was polluted by the
``--force`` echo and the config warnings (both printed BEFORE the redirect
started) and by child-process diagnostics that bypass the Python-level
redirect via OS fd 1. The A9 resolved-name forensics lookup is covered in
test_show_forensics.py.
"""

from __future__ import annotations

import json
from queue import Queue
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from mutmut_win.cli import cli
from mutmut_win.config import MutmutConfig, load_config
from mutmut_win.models import MutationRunResult, TaskCompleted
from mutmut_win.orchestrator import _print_summary
from mutmut_win.process.executor import SpawnPoolExecutor

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def _config() -> MutmutConfig:
    return MutmutConfig(max_children=1, timeout_multiplier=2.0)


# ---------------------------------------------------------------------------
# A7 — executor collapse state
# ---------------------------------------------------------------------------


class TestExecutorPoolCollapse:
    def test_collapse_sets_aborted_state_and_reports_to_stderr(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        executor = SpawnPoolExecutor(max_workers=1, config=_config())
        dead = MagicMock()
        dead.is_alive.return_value = False
        dead.pid = 101
        dead.exitcode = 1
        executor._workers = [dead]
        executor._num_tasks = 2

        events = list(executor.get_events())
        executor.shutdown()

        assert events == []
        assert executor.aborted is True
        assert executor.abort_reason is not None
        assert "2 task(s)" in executor.abort_reason
        captured = capsys.readouterr()
        assert "workers died" in captured.err  # error prose belongs on stderr
        assert "workers died" not in captured.out

    def test_healthy_completion_leaves_aborted_false(self) -> None:
        executor = SpawnPoolExecutor(max_workers=1, config=_config())
        executor._num_tasks = 1
        executor._event_queue.put(
            TaskCompleted(
                mutant_name="m.x_f__mutmut_1", worker_pid=1, exit_code=0, duration=0.0
            ).model_dump()
        )

        events = list(executor.get_events())
        executor.shutdown()

        assert len(events) == 1
        assert executor.aborted is False
        assert executor.abort_reason is None


# ---------------------------------------------------------------------------
# A7 — orchestrator seam (the MagicMock-truthiness hardening)
# ---------------------------------------------------------------------------


class _CollapsedExecutor:
    aborted = True
    abort_reason = "all 1 workers died; 2 task(s) were never started"


class TestExecutorAbortedSeam:
    @staticmethod
    def _seam() -> Any:
        # Late import: in the red phase only these tests fail, not collection.
        from mutmut_win.orchestrator import _executor_aborted

        return _executor_aborted

    def test_real_collapse_reports_true(self) -> None:
        assert self._seam()(_CollapsedExecutor()) is True

    def test_magicmock_executor_reports_false(self) -> None:
        # DI test doubles answer EVERY attribute with a truthy MagicMock —
        # only a literal True may count, or every mocked run turns aborted.
        assert self._seam()(MagicMock()) is False

    def test_attributeless_executor_reports_false(self) -> None:
        assert self._seam()(object()) is False


class TestSummaryAbortedLine:
    def test_print_summary_announces_the_abort(self, capsys: pytest.CaptureFixture[str]) -> None:
        summary = MutationRunResult(total_mutants=5, killed=1, unchecked=4, run_aborted=True)

        _print_summary(summary)

        out = capsys.readouterr().out
        assert "ABORTED" in out
        assert "checked 1 of 5" in out


# ---------------------------------------------------------------------------
# A7 — CLI honesty (mirrors the test_interrupt_honesty patterns)
# ---------------------------------------------------------------------------


def _invoke_run_with(result: MutationRunResult, *args: str) -> Any:
    orchestrator = MagicMock()
    orchestrator.run.return_value = result
    with (
        patch("mutmut_win.cli.MutationOrchestrator", return_value=orchestrator),
        patch("mutmut_win.cli.PytestRunner"),
        patch("mutmut_win.cli.SpawnPoolExecutor"),
        patch("mutmut_win.cli.load_config", return_value=MagicMock(model_copy=MagicMock())),
    ):
        return CliRunner().invoke(cli, ["run", *args])


class TestCliPoolCollapseHonesty:
    def test_aborted_run_exits_1(self) -> None:
        result = MutationRunResult(total_mutants=5, killed=1, unchecked=4, run_aborted=True)
        outcome = _invoke_run_with(result)
        assert outcome.exit_code == 1
        assert "aborted" in outcome.stderr.lower()
        assert "checked 1 of 5" in outcome.stderr

    def test_aborted_run_skips_the_score_gate(self) -> None:
        result = MutationRunResult(total_mutants=5, killed=1, unchecked=4, run_aborted=True)
        outcome = _invoke_run_with(result, "--min-score", "99")
        assert outcome.exit_code == 1
        assert "below threshold" not in outcome.output
        assert "below threshold" not in outcome.stderr

    def test_aborted_json_still_parses_and_carries_the_flag(self) -> None:
        result = MutationRunResult(total_mutants=5, killed=1, unchecked=4, run_aborted=True)
        outcome = _invoke_run_with(result, "--output", "json")
        assert outcome.exit_code == 1
        payload = json.loads(outcome.stdout)  # JSON is echoed BEFORE the exit
        assert payload["run_aborted"] is True

    def test_interrupt_takes_precedence_over_abort(self) -> None:
        result = MutationRunResult(
            total_mutants=5, unchecked=5, was_interrupted=True, run_aborted=True
        )
        outcome = _invoke_run_with(result)
        assert outcome.exit_code == 130


# ---------------------------------------------------------------------------
# A6 — json purity: pre-redirect prose and warning channels
# ---------------------------------------------------------------------------


class TestJsonPurity:
    def test_force_echo_and_config_warning_stay_off_json_stdout(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The deterministic A6 leaks: `--force` echoed 'Removed mutants/'
        # and load_config printed the unknown-key warning to stdout BEFORE
        # the json redirect started — stdout was never parseable.
        monkeypatch.chdir(tmp_path)
        (tmp_path / "mutants").mkdir()
        (tmp_path / ".mutmut-cache").mkdir()
        (tmp_path / "src").mkdir()
        (tmp_path / "pyproject.toml").write_text(
            '[tool.mutmut]\npaths_to_mutat = ["src/"]\n', encoding="utf-8"
        )
        orchestrator = MagicMock()
        orchestrator.run.return_value = MutationRunResult(total_mutants=1, killed=1)
        with (
            patch("mutmut_win.cli.MutationOrchestrator", return_value=orchestrator),
            patch("mutmut_win.cli.PytestRunner"),
            patch("mutmut_win.cli.SpawnPoolExecutor"),
        ):
            outcome = CliRunner().invoke(cli, ["run", "--output", "json", "--force"])

        assert outcome.exit_code == 0, outcome.output
        payload = json.loads(outcome.stdout)  # the WHOLE stdout is the JSON
        assert payload["killed"] == 1
        assert "Removed mutants/" in outcome.stderr
        assert "unknown [tool.mutmut] key" in outcome.stderr

    def test_config_warnings_go_to_stderr(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # Library-level guarantee, independent of any CLI redirect: config
        # warnings are warnings — stderr for every command (show/apply too).
        (tmp_path / "pyproject.toml").write_text(
            "[tool.mutmut]\n"
            'paths_to_mutat = ["src/"]\n'
            'paths-to-mutate = ["src/"]\n'
            'paths_to_mutate = ["src/"]\n',
            encoding="utf-8",
        )

        config = load_config(tmp_path)

        captured = capsys.readouterr()
        assert "unknown [tool.mutmut] key 'paths_to_mutat'" in captured.err
        assert "twins" in captured.err
        assert captured.out == ""
        assert config.paths_to_mutate == ["src/"]


class _SimpleQueue:
    """Thread-safe stand-in duck-typing multiprocessing.Queue for worker_main."""

    def __init__(self) -> None:
        self._q: Queue[Any] = Queue()

    def put(self, item: Any) -> None:
        self._q.put(item)

    def get(self) -> Any:
        return self._q.get()


class TestWorkerDiagnosticsChannel:
    def test_recovery_print_goes_to_stderr(self, capsys: pytest.CaptureFixture[str]) -> None:
        # Child processes inherit OS fd 1 — the parent's json redirect can
        # never catch worker prints. Diagnostics must be born on stderr.
        from mutmut_win.process.worker import worker_main

        task_q = _SimpleQueue()
        event_q = _SimpleQueue()
        task_q.put({"not": "a task"})  # ValidationError → recovery path
        task_q.put(None)

        worker_main(task_q, event_q, {"pytest_add_cli_args": []})  # type: ignore[arg-type]

        captured = capsys.readouterr()
        assert "WORKER RECOVERY" in captured.err
        assert "WORKER RECOVERY" not in captured.out
