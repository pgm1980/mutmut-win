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
import sys
from queue import Queue
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from mutmut_win.cli import cli
from mutmut_win.config import MutmutConfig, load_config
from mutmut_win.exceptions import ProcessContainmentError
from mutmut_win.models import MutationRunResult, MutationTask, TaskCompleted
from mutmut_win.orchestrator import MutationOrchestrator, _print_summary
from mutmut_win.process.executor import SpawnPoolExecutor
from tests.unit.phase_mock_util import frozen_worker_config

pytestmark = pytest.mark.usefixtures("isolated_cli_workspace")

if TYPE_CHECKING:
    from pathlib import Path


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
        # Verbatim pin (mutation hardening): diagnostics are contract.
        expected = (
            "Error: all 1 workers died; 2 task(s) were never started — "
            "aborting the run. Their mutants remain unchecked."
        )
        assert expected in captured.err.splitlines()
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

    def test_fatal_containment_completion_aborts_remaining_pool(self) -> None:
        executor = SpawnPoolExecutor(max_workers=1, config=_config())
        executor._num_tasks = 2
        executor._event_queue.put(
            TaskCompleted(
                mutant_name="m.x_f__mutmut_1",
                worker_pid=101,
                exit_code=35,
                duration=0.0,
                last_output="ProcessContainmentError: no Job Object",
                fatal=True,
            ).model_dump()
        )

        events = list(executor.get_events())
        executor.shutdown()

        assert len(events) == 1
        assert events[0].fatal is True
        assert executor.aborted is True
        assert executor.abort_reason is not None
        assert "fatal execution-boundary" in executor.abort_reason
        assert "ProcessContainmentError" in executor.abort_reason


@pytest.mark.skipif(sys.platform != "win32", reason="Windows Job Object containment")
class TestWindowsPoolContainmentBootstrap:
    def test_missing_job_fails_before_executor_allocation(self) -> None:
        with (
            patch(
                "mutmut_win.process.job_object.create_kill_on_close_job",
                side_effect=OSError("denied"),
            ),
            pytest.raises(ProcessContainmentError, match="refusing to start"),
        ):
            SpawnPoolExecutor(max_workers=1, config=_config())

    def test_assignment_failure_kills_worker_before_enqueuing_tasks(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / "mutants").mkdir()
        with patch("mutmut_win.process.job_object.create_kill_on_close_job", return_value=77):
            executor = SpawnPoolExecutor(max_workers=1, config=_config())
        boundary_payload = frozen_worker_config(executor._config_data)["_pytest_boundary"]
        assert isinstance(boundary_payload, dict)
        executor.configure_pytest_boundary(boundary_payload)

        fake_process = MagicMock()
        fake_process.start.side_effect = ProcessContainmentError(
            "assignment denied before worker resume"
        )
        task_queue = MagicMock()
        event_queue = MagicMock()
        executor._task_queue = task_queue
        executor._event_queue = event_queue

        try:
            with (
                patch.object(executor, "_make_worker_process", return_value=fake_process),
                pytest.raises(ProcessContainmentError, match="before worker resume"),
            ):
                executor.start([MutationTask(mutant_name="m.x_f__mutmut_1")])
        finally:
            # The handle is synthetic; prevent shutdown from passing it to the
            # real Windows API while still exercising queue cleanup.
            executor._job_handle = None
            executor.shutdown()

        fake_process.start.assert_called_once()
        task_queue.put.assert_not_called()


class TestStartupWatchdog:
    """WRK-001: a worker that dies DURING interpreter startup (before the mp
    bootstrap) never pulls a task, and the liveness sweep cannot resolve it to
    a clean ``not any(is_alive())`` abort — the run hung >=50s. A time-based
    watchdog aborts when no task is ever pulled within the startup grace.  It
    now remains armed for the mixed-pool variant, resetting on progress and
    firing only when queued work exists without an in-flight task."""

    def test_watchdog_aborts_when_no_task_is_ever_pulled(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        import mutmut_win.process.executor as executor_module

        # Race simulation: the worker reports alive forever (the unresolved
        # bootstrap state) and never emits a single event.
        monkeypatch.setattr(executor_module, "_STARTUP_GRACE_SECONDS", 0.0)
        monkeypatch.setattr(executor_module, "_EVENT_POLL_SECONDS", 0.01)

        executor = SpawnPoolExecutor(max_workers=1, config=_config())
        alive_silent = MagicMock()
        alive_silent.is_alive.return_value = True
        alive_silent.pid = 202
        executor._workers = [alive_silent]
        executor._num_tasks = 3

        events = list(executor.get_events())
        executor.shutdown()

        assert events == []
        assert executor.aborted is True
        # Verbatim pins (mutation hardening): abort_reason + stderr are contract.
        assert executor.abort_reason == (
            "no worker pulled a task within 0s; 3 task(s) were never started"
        )
        expected_err = (
            "Error: no worker pulled a task within 0s; 3 task(s) were never "
            "started — workers are failing during interpreter startup "
            "(a crashing sitecustomize/.pth/site-packages wedges every spawn). "
            "Aborting the run; their mutants remain unchecked."
        )
        assert expected_err in capsys.readouterr().err.splitlines()

    def test_watchdog_silent_when_last_inflight_task_is_recovered(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import mutmut_win.process.executor as executor_module
        from mutmut_win.models import TaskStarted

        # Grace 0 would fire instantly if the watchdog ignored the fact that
        # recovery finishes the final task and leaves no queued remainder.
        monkeypatch.setattr(executor_module, "_STARTUP_GRACE_SECONDS", 0.0)
        monkeypatch.setattr(executor_module, "_EVENT_POLL_SECONDS", 0.01)

        executor = SpawnPoolExecutor(max_workers=1, config=_config())
        # Worker pulled a task (TaskStarted) then died mid-task: the normal
        # sweep synthesizes a 'suspicious' completion. The watchdog must stay
        # silent because no task remains after that completion.
        dead_after_pull = MagicMock()
        dead_after_pull.is_alive.return_value = False
        dead_after_pull.pid = 303
        dead_after_pull.exitcode = 1
        executor._workers = [dead_after_pull]
        executor._num_tasks = 1
        executor._event_queue.put(
            TaskStarted(mutant_name="m.x_f__mutmut_1", worker_pid=303).model_dump()
        )

        events = list(executor.get_events())
        executor.shutdown()

        assert any(getattr(e, "exit_code", None) == 35 for e in events)
        assert executor.aborted is False

    def test_watchdog_aborts_mixed_pool_after_earlier_progress(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """One healthy completion must not disarm protection for a wedged peer."""
        import mutmut_win.process.executor as executor_module
        from mutmut_win.models import TaskStarted

        monkeypatch.setattr(executor_module, "_STARTUP_GRACE_SECONDS", 0.0)
        monkeypatch.setattr(executor_module, "_EVENT_POLL_SECONDS", 0.01)

        executor = SpawnPoolExecutor(max_workers=2, config=_config())
        completed_worker = MagicMock()
        completed_worker.is_alive.return_value = False
        completed_worker.pid = 401
        completed_worker.exitcode = 0
        alive_but_wedged = MagicMock()
        alive_but_wedged.is_alive.return_value = True
        alive_but_wedged.pid = 402
        executor._workers = [completed_worker, alive_but_wedged]
        executor._num_tasks = 2
        executor._event_queue.put(TaskStarted(mutant_name="m1", worker_pid=401).model_dump())
        executor._event_queue.put(
            TaskCompleted(mutant_name="m1", worker_pid=401, exit_code=0, duration=0.1).model_dump()
        )

        events = list(executor.get_events())
        executor.shutdown()

        assert len(events) == 2
        assert executor.aborted is True
        assert executor.abort_reason == (
            "no worker pulled another task within 0s; 1 task(s) were never started"
        )
        assert "stopped pulling queued tasks" in capsys.readouterr().err

    def test_watchdog_never_aborts_a_long_inflight_task(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Elapsed idle grace is irrelevant while a real task is in flight."""
        import queue

        import mutmut_win.process.executor as executor_module
        from mutmut_win.models import TaskStarted

        monkeypatch.setattr(executor_module, "_STARTUP_GRACE_SECONDS", 0.0)
        monkeypatch.setattr(executor_module, "_EVENT_POLL_SECONDS", 0.0)

        executor = SpawnPoolExecutor(max_workers=1, config=_config())
        alive = MagicMock()
        alive.is_alive.return_value = True
        alive.pid = 501
        executor._workers = [alive]
        executor._num_tasks = 1
        executor._event_queue = MagicMock()
        executor._event_queue.get.side_effect = [
            TaskStarted(mutant_name="slow", worker_pid=501).model_dump(),
            queue.Empty,
            queue.Empty,
            TaskCompleted(
                mutant_name="slow", worker_pid=501, exit_code=0, duration=120.0
            ).model_dump(),
        ]

        events = list(executor.get_events())
        executor.shutdown()

        assert [type(event) for event in events] == [TaskStarted, TaskCompleted]
        assert executor.aborted is False


def test_idle_grace_expired_predicate() -> None:
    """Only queued + idle + overdue work trips the progress watchdog."""
    from mutmut_win.process.executor import _STARTUP_GRACE_SECONDS, _idle_grace_expired

    grace = _STARTUP_GRACE_SECONDS
    assert (
        _idle_grace_expired(remaining_tasks=1, in_flight_tasks=0, idle_elapsed=grace + 1.0) is True
    )
    assert (
        _idle_grace_expired(remaining_tasks=1, in_flight_tasks=0, idle_elapsed=grace - 1.0) is False
    )
    # boundary: strictly greater, not >=
    assert _idle_grace_expired(remaining_tasks=1, in_flight_tasks=0, idle_elapsed=grace) is False
    # A running task stays under its worker timeout, however long it needs.
    assert (
        _idle_grace_expired(remaining_tasks=1, in_flight_tasks=1, idle_elapsed=grace + 100.0)
        is False
    )
    assert (
        _idle_grace_expired(remaining_tasks=0, in_flight_tasks=0, idle_elapsed=grace + 100.0)
        is False
    )


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
    def test_print_summary_announces_the_abort_verbatim(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        summary = MutationRunResult(total_mutants=5, killed=1, unchecked=4, run_aborted=True)

        _print_summary(summary)

        out = capsys.readouterr().out
        # Verbatim pin (mutation hardening): the line is contract.
        assert "ABORTED       : worker pool collapsed — checked 1 of 5 mutants" in out.splitlines()

    def test_no_aborted_line_for_a_normal_run(self, capsys: pytest.CaptureFixture[str]) -> None:
        # Kills the and→or guard mutant: a healthy summary must NOT carry
        # the ABORTED banner.
        _print_summary(MutationRunResult(total_mutants=5, killed=5))
        assert "ABORTED" not in capsys.readouterr().out

    def test_interrupt_banner_wins_over_aborted_line(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # Both flags true → INTERRUPTED banner only (no duplicate header).
        summary = MutationRunResult(
            total_mutants=5, unchecked=5, was_interrupted=True, run_aborted=True
        )
        _print_summary(summary)
        out = capsys.readouterr().out
        assert "INTERRUPTED" in out
        assert "ABORTED" not in out


class _AbortedFakeExecutor:
    """Real object (not MagicMock) — getattr must see LITERAL attribute values."""

    aborted = True
    abort_reason = "all 1 workers died; 1 task(s) were never started"

    def start(self, tasks: Any) -> None:
        self.started = list(tasks)

    def get_events(self) -> Any:
        return iter(())

    def shutdown(self, timeout: float = 10.0) -> None:
        pass


def _make_runner() -> MagicMock:
    runner = MagicMock()
    runner.run_clean_test.return_value = 0
    runner.run_forced_fail.return_value = 1
    runner.run_stats.return_value = 0
    runner.collect_tests.return_value = []
    return runner


class TestRunAbortedWiring:
    """End-to-end seam: run() must read the EXECUTOR's collapse declaration."""

    def _run_with_executor(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, executor: Any
    ) -> MutationRunResult:
        monkeypatch.chdir(tmp_path)
        src = tmp_path / "src"
        src.mkdir()
        (src / "target.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
        orch = MutationOrchestrator(
            _config(),
            runner=_make_runner(),
            executor=executor,
            db_path=tmp_path / "db",
        )
        return orch.run()

    def test_collapsed_executor_sets_run_aborted(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Kills the run() wiring mutants (assignment → None / wrong arg):
        # the literal True of the REAL executor must reach the summary.
        result = self._run_with_executor(tmp_path, monkeypatch, _AbortedFakeExecutor())
        assert result.run_aborted is True
        assert result.unchecked >= 1  # never-started remainder stays unchecked

    def test_executor_without_any_attributable_completions_aborts(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # A falsey/missing ``aborted`` attribute is not enough to claim
        # success: if planned tasks produce no attributable completions the
        # run is incomplete and must fail closed.
        executor = MagicMock()
        executor.get_events.return_value = iter(())
        result = self._run_with_executor(tmp_path, monkeypatch, executor)
        assert result.run_aborted is True
        assert result.unchecked == result.total_mutants


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
    def test_recovery_print_goes_to_stderr(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # Child processes inherit OS fd 1 — the parent's json redirect can
        # never catch worker prints. Diagnostics must be born on stderr.
        from mutmut_win.process.worker import worker_main

        monkeypatch.chdir(tmp_path)
        (tmp_path / "mutants").mkdir()

        task_q = _SimpleQueue()
        event_q = _SimpleQueue()
        task_q.put({"not": "a task"})  # ValidationError → recovery path
        task_q.put(None)

        worker_main(
            task_q,
            event_q,
            frozen_worker_config({"pytest_add_cli_args": []}),
        )  # type: ignore[arg-type]

        captured = capsys.readouterr()
        assert "WORKER RECOVERY" in captured.err
        assert "WORKER RECOVERY" not in captured.out

    def test_worker_error_print_is_verbatim_on_stderr(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # The OSError diagnostic of _process_task — verbatim pin + channel.
        from mutmut_win.process.worker import worker_main

        monkeypatch.chdir(tmp_path)
        (tmp_path / "mutants").mkdir()  # _process_task creates its log here
        task_q = _SimpleQueue()
        event_q = _SimpleQueue()
        task_q.put(MutationTask(mutant_name="m.x_f__mutmut_1").model_dump())
        task_q.put(None)

        with patch("mutmut_win.process.worker.subprocess.Popen", side_effect=OSError("boom")):
            worker_main(
                task_q,
                event_q,
                frozen_worker_config({"pytest_add_cli_args": []}),
            )  # type: ignore[arg-type]

        captured = capsys.readouterr()
        assert "WORKER ERROR for m.x_f__mutmut_1: boom" in captured.err.splitlines()
        assert "WORKER ERROR" not in captured.out
        # A subprocess that never started must not publish TaskStarted and
        # thereby disarm the executor's startup watchdog.  The worker still
        # returns one terminal suspicious result for the claimed queue item.
        completed = TaskCompleted.model_validate(event_q.get())
        assert completed.exit_code == 35

    def test_monitor_start_failure_print_is_verbatim_on_stderr(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from mutmut_win.process.worker import _maybe_start_loop_monitor

        with patch(
            "mutmut_win.process.loop_monitor.ProcessMonitor",
            side_effect=RuntimeError("boom"),
        ):
            monitor = _maybe_start_loop_monitor(True, 1234, tmp_path / "x.log")

        assert monitor is None  # graceful degradation, never poison the worker
        captured = capsys.readouterr()
        assert "WORKER MONITOR start failed: boom" in captured.err.splitlines()
        assert "MONITOR" not in captured.out
