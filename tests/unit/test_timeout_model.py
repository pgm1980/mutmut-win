"""Tests for the additive startup floor in the timeout model (Issue #105).

DOG-001, proven forensically by the first dogfooding run: the task budget
was ``max(5s, estimated_test_time x multiplier)`` — it scaled TEST time
only.  The constant per-process overhead (interpreter start, suite imports,
pytest collection: 16.5s wall for 0.86s of tests in the pilot) had no
additive term, so the 5s floor cut finished runs into 'timeout' rows —
175 of 244 pilot mutants were such pseudo-timeouts with COMPLETE pytest
summaries in their tails.

The budget is now ``startup_floor + estimated x multiplier`` where the
floor is MEASURED, not guessed: the orchestrator already times the clean
run over the full suite in the same trampolined environment, and the stats
plugin knows the pure test time — their difference is the project-specific
process overhead, clamped to [5s, 60s] against degenerate measurements.
The full-suite fallback (empty stats) is budgeted against the measured
clean-run wall time for the same reason: a 60s constant would pseudo-
timeout any suite that takes longer than a minute.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import pytest

from mutmut_win.config import MutmutConfig
from mutmut_win.models import MutationTask, TaskCompleted, TaskStarted
from mutmut_win.orchestrator import (
    _FALLBACK_TIMEOUT,
    _MIN_TIMEOUT,
    MutationOrchestrator,
    _apply_timeouts,
    _compute_startup_floor,
)

if TYPE_CHECKING:
    from pathlib import Path


def _task(name: str = "src/foo.py::bar__mutmut_1", **kwargs: Any) -> MutationTask:
    return MutationTask(mutant_name=name, **kwargs)


class TestComputeStartupFloor:
    def test_floor_is_wall_minus_test_time(self) -> None:
        # The pilot measurement: 16.5s wall, 0.86s of tests -> ~15.6s of
        # process overhead. That is the floor.
        floor = _compute_startup_floor(16.5, {"t1": 0.5, "t2": 0.36})
        assert floor == pytest.approx(15.64)

    def test_negative_difference_clamps_to_min(self) -> None:
        # Stale cached durations can exceed a fresh (faster) clean run.
        floor = _compute_startup_floor(3.0, {"t1": 10.0})
        assert floor == _MIN_TIMEOUT

    def test_huge_difference_clamps_to_max(self) -> None:
        # A pathological clean run (one-off compilation, cold caches) must
        # not inflate EVERY task budget without bound.
        floor = _compute_startup_floor(900.0, {"t1": 1.0})
        assert floor == _FALLBACK_TIMEOUT

    def test_empty_stats_clamp_to_max(self) -> None:
        # No durations at all: the difference degenerates to the full wall
        # time — the clamp bounds it (the fallback path budgets such tasks
        # against clean_wall directly, see TestApplyTimeoutsFallback).
        floor = _compute_startup_floor(300.0, {})
        assert floor == _FALLBACK_TIMEOUT


class TestApplyTimeoutsWithFloor:
    def test_budget_is_floor_plus_scaled_test_time(self) -> None:
        # The pilot scenario that produced 175 pseudo-timeouts: 0.86s of
        # tests, multiplier 2 -> old budget max(5, 1.72) = 5s against a
        # 16.5s wall. New: floor + 1.72.
        task = _task(tests=["t1"])
        [result] = _apply_timeouts(
            [task],
            {"t1": 0.86},
            2.0,
            startup_floor=15.64,
            clean_wall_seconds=16.5,
        )
        assert result.timeout_seconds == pytest.approx(15.64 + 0.86 * 2.0)

    def test_min_timeout_still_holds(self) -> None:
        # The absolute lower bound survives the rework.
        task = _task(tests=["t1"])
        [result] = _apply_timeouts(
            [task],
            {"t1": 0.001},
            1.0,
            startup_floor=_MIN_TIMEOUT,
            clean_wall_seconds=1.0,
        )
        assert result.timeout_seconds >= _MIN_TIMEOUT

    def test_estimated_time_stays_free_of_the_floor(self) -> None:
        # estimated_time feeds the fast-first sort and means "estimated
        # TEST runtime" — adding the constant floor would not break the
        # ordering but would corrupt the field's meaning.
        task = _task(tests=["t1"])
        [result] = _apply_timeouts(
            [task],
            {"t1": 2.0},
            3.0,
            startup_floor=42.0,
            clean_wall_seconds=50.0,
        )
        assert result.estimated_time == pytest.approx(2.0)

    def test_mean_path_budget_is_the_full_suite_fallback(self) -> None:
        # Issue #130 / 360°-B3: tests=[] with nonempty stats still runs the
        # FULL suite (no node-id args) — the mean only feeds the fast-first
        # sort; budgeting it like a single average test was a guaranteed
        # timeout flood.
        task = _task()
        [result] = _apply_timeouts(
            [task],
            {"t1": 2.0, "t2": 4.0},
            2.0,
            startup_floor=10.0,
            clean_wall_seconds=20.0,
        )
        assert result.estimated_time == pytest.approx(3.0)  # mean keeps sorting
        assert result.timeout_seconds == pytest.approx(60.0)  # max(FALLBACK, 20*2)


class TestApplyTimeoutsFallback:
    def test_fallback_scales_with_the_measured_clean_run(self) -> None:
        # Empty stats -> the task runs the FULL suite. Our own suite takes
        # 5-7 minutes; the old flat 60s was a guaranteed pseudo-timeout.
        # clean_wall IS the measured wall time of exactly such a run.
        task = _task(tests=[])
        [result] = _apply_timeouts(
            [task],
            {},
            2.0,
            startup_floor=_FALLBACK_TIMEOUT,
            clean_wall_seconds=300.0,
        )
        assert result.timeout_seconds == pytest.approx(600.0)

    def test_fallback_keeps_sixty_seconds_as_lower_bound(self) -> None:
        # Tiny suites keep the old generous constant.
        task = _task(tests=[])
        [result] = _apply_timeouts(
            [task],
            {},
            2.0,
            startup_floor=_MIN_TIMEOUT,
            clean_wall_seconds=1.0,
        )
        assert result.timeout_seconds == _FALLBACK_TIMEOUT


class TestRunAnnouncesTheTimeoutModel:
    def test_run_prints_the_measured_floor(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # The chosen floor must be visible — a silent timeout model is not
        # diagnosable (the audit lesson behind DOG-001 forensics).
        monkeypatch.chdir(tmp_path)
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
        runner.run_stats.return_value = None
        runner.collect_tests.return_value = []

        orch = MutationOrchestrator(
            MutmutConfig(max_children=1, timeout_multiplier=2.0, paths_to_mutate=["src"]),
            runner=runner,
            executor=executor,
            db_path=tmp_path / "db",
        )
        orch.run()

        out = capsys.readouterr().out
        assert "startup floor" in out
        # The mocked clean run returns instantly -> the floor clamps to the
        # minimum; the line shows the actual number used.
        assert f"{_MIN_TIMEOUT:.1f}s" in out
