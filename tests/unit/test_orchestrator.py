"""Unit tests for mutmut_win.orchestrator (MutationOrchestrator)."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import pytest

from mutmut_win.config import MutmutConfig
from mutmut_win.exceptions import CleanTestFailedError, ForcedFailError
from mutmut_win.models import (
    MutationRunResult,
    MutationTask,
    TaskCompleted,
    TaskStarted,
    TaskTimedOut,
)
from mutmut_win.orchestrator import (
    MutationOrchestrator,
    _apply_timeouts,
    _increment_summary,
    _update_source_data,
    _update_summary_and_persist,
)

if TYPE_CHECKING:
    from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _config(**overrides: Any) -> MutmutConfig:
    defaults: dict[str, Any] = {"max_children": 1, "timeout_multiplier": 2.0}
    defaults.update(overrides)
    return MutmutConfig(**defaults)


def _task(name: str = "src/foo.py::bar__mutmut_1", **kwargs: Any) -> MutationTask:
    return MutationTask(mutant_name=name, **kwargs)


def _make_runner(
    clean_exit: int = 0,
    forced_fail_exit: int = 1,
    tests: list[str] | None = None,
) -> MagicMock:
    runner = MagicMock()
    runner.run_clean_test.return_value = clean_exit
    runner.run_forced_fail.return_value = forced_fail_exit
    # run_stats returns None (side-effect: populates _state globals)
    runner.run_stats.return_value = None
    runner.collect_tests.return_value = tests or []
    return runner


def _make_executor(events: list[Any] | None = None) -> MagicMock:
    executor = MagicMock()
    executor.get_events.return_value = iter(events or [])
    return executor


# ---------------------------------------------------------------------------
# _apply_timeouts (pure helper)
# ---------------------------------------------------------------------------


class TestApplyTimeouts:
    def test_uses_fallback_when_no_stats(self) -> None:
        tasks = [_task()]
        result = _apply_timeouts(tasks, {}, 10.0)
        assert result[0].timeout_seconds == 60.0  # _FALLBACK_TIMEOUT

    def test_uses_multiplier_with_known_stats(self) -> None:
        tasks = [_task(tests=["tests/test_foo.py::test_x"])]
        stats = {"tests/test_foo.py::test_x": 2.0}
        result = _apply_timeouts(tasks, stats, 5.0)
        # 2.0 * 5.0 = 10.0 — above _MIN_TIMEOUT
        assert result[0].timeout_seconds == pytest.approx(10.0)

    def test_min_timeout_enforced(self) -> None:
        tasks = [_task(tests=["tests/test_foo.py::test_x"])]
        stats = {"tests/test_foo.py::test_x": 0.001}
        result = _apply_timeouts(tasks, stats, 1.0)
        assert result[0].timeout_seconds >= 5.0  # _MIN_TIMEOUT

    def test_uses_mean_when_no_test_assignment(self) -> None:
        tasks = [_task()]  # no tests assigned
        stats = {"tests/test_a.py::test_x": 2.0, "tests/test_b.py::test_y": 4.0}
        result = _apply_timeouts(tasks, stats, 2.0)
        # mean = 3.0, * 2.0 = 6.0
        assert result[0].timeout_seconds == pytest.approx(6.0)

    def test_does_not_mutate_original_tasks(self) -> None:
        original = _task()
        original_timeout = original.timeout_seconds
        _apply_timeouts([original], {}, 10.0)
        assert original.timeout_seconds == original_timeout  # unchanged

    def test_preserves_task_count(self) -> None:
        tasks = [_task(f"m{i}") for i in range(5)]
        result = _apply_timeouts(tasks, {}, 2.0)
        assert len(result) == 5


# ---------------------------------------------------------------------------
# _increment_summary (pure helper)
# ---------------------------------------------------------------------------


class TestIncrementSummary:
    def test_killed_increments_killed(self) -> None:
        s = MutationRunResult()
        _increment_summary(s, "killed")
        assert s.killed == 1

    def test_caught_by_type_check_increments_killed(self) -> None:
        s = MutationRunResult()
        _increment_summary(s, "caught by type check")
        assert s.killed == 1

    def test_survived(self) -> None:
        s = MutationRunResult()
        _increment_summary(s, "survived")
        assert s.survived == 1

    def test_timeout(self) -> None:
        s = MutationRunResult()
        _increment_summary(s, "timeout")
        assert s.timeout == 1

    def test_suspicious(self) -> None:
        s = MutationRunResult()
        _increment_summary(s, "suspicious")
        assert s.suspicious == 1

    def test_skipped(self) -> None:
        s = MutationRunResult()
        _increment_summary(s, "skipped")
        assert s.skipped == 1

    def test_no_tests(self) -> None:
        s = MutationRunResult()
        _increment_summary(s, "no tests")
        assert s.no_tests == 1

    def test_unknown_status_does_not_raise(self) -> None:
        s = MutationRunResult()
        # Should not raise; unknown statuses are silently ignored.
        _increment_summary(s, "totally_unknown_status")
        assert s.killed == 0


# ---------------------------------------------------------------------------
# _update_source_data (pure helper)
# ---------------------------------------------------------------------------


class TestUpdateSourceData:
    def test_updates_matching_file(self) -> None:
        from mutmut_win.models import SourceFileMutationData

        sfd = SourceFileMutationData(path="src/foo.py")
        source_data = {"src/foo.py": sfd}
        _update_source_data("src.foo.bar__mutmut_1", 1, 0.5, source_data)
        assert "src.foo.bar__mutmut_1" in sfd.exit_code_by_key

    def test_skips_when_no_match(self) -> None:
        from mutmut_win.models import SourceFileMutationData

        sfd = SourceFileMutationData(path="src/baz.py")
        source_data = {"src/baz.py": sfd}
        # mutant_name belongs to a different module
        _update_source_data("src.foo.bar__mutmut_1", 1, 0.5, source_data)
        assert sfd.exit_code_by_key == {}

    def test_duration_none_not_stored(self) -> None:
        from mutmut_win.models import SourceFileMutationData

        sfd = SourceFileMutationData(path="src/foo.py")
        source_data = {"src/foo.py": sfd}
        _update_source_data("src.foo.bar__mutmut_1", 1, None, source_data)
        assert "src.foo.bar__mutmut_1" not in sfd.durations_by_key


# ---------------------------------------------------------------------------
# MutationOrchestrator — init
# ---------------------------------------------------------------------------


class TestMutationOrchestratorInit:
    def test_accepts_config(self) -> None:
        cfg = _config()
        orch = MutationOrchestrator(cfg)
        assert orch._config is cfg

    def test_accepts_injected_runner(self) -> None:
        runner = _make_runner()
        orch = MutationOrchestrator(_config(), runner=runner)
        assert orch._runner is runner

    def test_accepts_injected_executor(self) -> None:
        executor = _make_executor()
        orch = MutationOrchestrator(_config(), executor=executor)
        assert orch._executor_override is executor

    def test_custom_db_path(self, tmp_path: Path) -> None:
        db = tmp_path / "custom.db"
        orch = MutationOrchestrator(_config(), db_path=db)
        assert orch._db_path == db


# ---------------------------------------------------------------------------
# MutationOrchestrator.run — early-exit cases
# ---------------------------------------------------------------------------


class TestMutationOrchestratorRunNoMutants:
    def test_returns_empty_result_when_no_mutants(self, tmp_path: Path) -> None:
        runner = _make_runner()
        executor = _make_executor()
        cfg = _config(paths_to_mutate=[str(tmp_path)])
        orch = MutationOrchestrator(cfg, runner=runner, executor=executor, db_path=tmp_path / "db")
        result = orch.run()
        assert result.total_mutants == 0
        # Clean test and forced-fail should NOT be called when there are no mutants.
        runner.run_clean_test.assert_not_called()


# ---------------------------------------------------------------------------
# MutationOrchestrator.run — clean-test failure
# ---------------------------------------------------------------------------


class TestMutationOrchestratorRunCleanTestFail:
    def test_raises_clean_test_failed_error(self, tmp_path: Path) -> None:
        # Create a real Python file that produces at least one mutant.
        src = tmp_path / "src"
        src.mkdir()
        (src / "target.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")

        runner = _make_runner(clean_exit=1)
        executor = _make_executor()
        cfg = _config(paths_to_mutate=[str(src)])
        orch = MutationOrchestrator(cfg, runner=runner, executor=executor, db_path=tmp_path / "db")
        with pytest.raises(CleanTestFailedError):
            orch.run()


# ---------------------------------------------------------------------------
# MutationOrchestrator.run — forced-fail check failure
# ---------------------------------------------------------------------------


class TestMutationOrchestratorRunForcedFailCheck:
    def test_raises_forced_fail_error_when_exit_0(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        src.mkdir()
        (src / "target.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")

        runner = _make_runner(clean_exit=0, forced_fail_exit=0)
        executor = _make_executor()
        cfg = _config(paths_to_mutate=[str(src)])
        orch = MutationOrchestrator(cfg, runner=runner, executor=executor, db_path=tmp_path / "db")
        with pytest.raises(ForcedFailError):
            orch.run()


# ---------------------------------------------------------------------------
# MutationOrchestrator.run — full happy-path with mock executor
# ---------------------------------------------------------------------------


class TestMutationOrchestratorRunHappyPath:
    def test_returns_correct_total_mutants(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        src.mkdir()
        (src / "target.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")

        runner = _make_runner(clean_exit=0, forced_fail_exit=1)
        cfg = _config(paths_to_mutate=[str(src)])

        # Capture tasks passed to executor.start so we can build matching events.
        captured_tasks: list[MutationTask] = []

        def fake_start(tasks: list[MutationTask]) -> None:
            captured_tasks.extend(tasks)

        executor = MagicMock()
        executor.start.side_effect = fake_start

        def fake_get_events() -> Any:
            pid = os.getpid()
            for task in captured_tasks:
                yield TaskStarted(mutant_name=task.mutant_name, worker_pid=pid)
                yield TaskCompleted(
                    mutant_name=task.mutant_name, worker_pid=pid, exit_code=1, duration=0.05
                )

        executor.get_events.side_effect = fake_get_events

        orch = MutationOrchestrator(cfg, runner=runner, executor=executor, db_path=tmp_path / "db")
        result = orch.run()
        assert result.total_mutants > 0
        assert result.killed == result.total_mutants

    def test_timeout_events_counted(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        src.mkdir()
        (src / "target.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")

        runner = _make_runner(clean_exit=0, forced_fail_exit=1)
        cfg = _config(paths_to_mutate=[str(src)])

        captured_tasks: list[MutationTask] = []

        def fake_start(tasks: list[MutationTask]) -> None:
            captured_tasks.extend(tasks)

        executor = MagicMock()
        executor.start.side_effect = fake_start

        def fake_get_events() -> Any:
            pid = os.getpid()
            for task in captured_tasks:
                yield TaskStarted(mutant_name=task.mutant_name, worker_pid=pid)
                yield TaskTimedOut(mutant_name=task.mutant_name, worker_pid=pid)

        executor.get_events.side_effect = fake_get_events

        orch = MutationOrchestrator(cfg, runner=runner, executor=executor, db_path=tmp_path / "db")
        result = orch.run()
        assert result.timeout == result.total_mutants

    def test_results_persisted_to_db(self, tmp_path: Path) -> None:
        from mutmut_win.db import load_results

        src = tmp_path / "src"
        src.mkdir()
        (src / "target.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")

        runner = _make_runner(clean_exit=0, forced_fail_exit=1)
        cfg = _config(paths_to_mutate=[str(src)])
        db_path = tmp_path / "cache.db"

        captured_tasks: list[MutationTask] = []

        def fake_start(tasks: list[MutationTask]) -> None:
            captured_tasks.extend(tasks)

        executor = MagicMock()
        executor.start.side_effect = fake_start

        def fake_get_events() -> Any:
            pid = os.getpid()
            for task in captured_tasks:
                yield TaskStarted(mutant_name=task.mutant_name, worker_pid=pid)
                yield TaskCompleted(
                    mutant_name=task.mutant_name, worker_pid=pid, exit_code=1, duration=0.01
                )

        executor.get_events.side_effect = fake_get_events

        orch = MutationOrchestrator(cfg, runner=runner, executor=executor, db_path=db_path)
        result = orch.run()
        db_results = load_results(db_path)
        assert len(db_results) == result.total_mutants


# ---------------------------------------------------------------------------
# MutationOrchestrator.run — keyboard interrupt
# ---------------------------------------------------------------------------


class TestMutationOrchestratorKeyboardInterrupt:
    def test_shutdown_called_on_keyboard_interrupt(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        src.mkdir()
        (src / "target.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")

        runner = _make_runner(clean_exit=0, forced_fail_exit=1)
        executor = MagicMock()
        executor.start.return_value = None
        executor.get_events.side_effect = KeyboardInterrupt

        cfg = _config(paths_to_mutate=[str(src)])
        orch = MutationOrchestrator(cfg, runner=runner, executor=executor, db_path=tmp_path / "db")
        # KeyboardInterrupt is caught internally; run() should return a result.
        result = orch.run()
        executor.shutdown.assert_called_once()
        assert isinstance(result, MutationRunResult)


# ---------------------------------------------------------------------------
# _update_summary_and_persist — event routing
# ---------------------------------------------------------------------------


class TestUpdateSummaryAndPersist:
    def test_task_started_is_ignored(self, tmp_path: Path) -> None:
        db = tmp_path / "db.sqlite"
        summary = MutationRunResult(total_mutants=1)
        event = TaskStarted(mutant_name="m1", worker_pid=1)
        _update_summary_and_persist(event, summary, db, {})
        # No DB file created, no counters changed.
        assert not db.exists()
        assert summary.killed == 0

    def test_task_completed_killed(self, tmp_path: Path) -> None:
        from mutmut_win.db import load_results

        db = tmp_path / "db.sqlite"
        summary = MutationRunResult(total_mutants=1)
        event = TaskCompleted(mutant_name="m1", worker_pid=1, exit_code=1, duration=0.5)
        _update_summary_and_persist(event, summary, db, {})
        assert summary.killed == 1
        results = load_results(db)
        assert results[0].status == "killed"

    def test_task_timed_out(self, tmp_path: Path) -> None:
        from mutmut_win.db import load_results

        db = tmp_path / "db.sqlite"
        summary = MutationRunResult(total_mutants=1)
        event = TaskTimedOut(mutant_name="m1", worker_pid=1)
        _update_summary_and_persist(event, summary, db, {})
        assert summary.timeout == 1
        results = load_results(db)
        assert results[0].status == "timeout"
