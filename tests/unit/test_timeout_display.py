"""The timeout announcement describes the budgets actually dispatched."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import pytest

from mutmut_win.config import MutmutConfig
from mutmut_win.models import MutationTask, TaskCompleted, TaskStarted
from mutmut_win.orchestrator import MutationOrchestrator, _apply_timeouts, _print_timeout_model
from mutmut_win.stats import RunBasisEvidence

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize(
    ("tests", "authoritative", "stats", "clean_wall", "expected_budget"),
    [
        (["test_fast"], False, {"test_fast": 0.1}, 0.2, 60.0),
        ([], True, {"test_fast": 0.1}, 0.2, 60.0),
        (["test_fast"], True, {}, 0.2, 60.0),
        (["test_fast"], True, {"test_fast": 0.0}, 0.2, 60.0),
        (["test_fast"], False, {"test_fast": 0.1}, 40.0, 80.0),
    ],
)
def test_fallback_reports_actual_budget_without_selected_timing_formula(
    tests: list[str],
    authoritative: bool,
    stats: dict[str, float],
    clean_wall: float,
    expected_budget: float,
    capsys: pytest.CaptureFixture[str],
) -> None:
    task = MutationTask(
        mutant_name="src/calc.py::add__mutmut_1",
        tests=tests,
        test_selection_is_authoritative=authoritative,
    )
    dispatched = _apply_timeouts(
        [task], stats, 2.0, startup_floor=5.0, clean_wall_seconds=clean_wall
    )

    _print_timeout_model(
        dispatched,
        2.0,
        startup_floor=5.0,
        clean_wall_seconds=clean_wall,
        total_test_time=sum(stats.values()),
    )

    assert dispatched[0].timeout_seconds == expected_budget
    out = capsys.readouterr().out
    assert f"Timeout budgets: {expected_budget:.1f}s for 1 dispatched task(s)." in out
    assert "1 task(s) use the fallback: max(60.0s, clean run " in out
    assert "selected test time x" not in out
    assert "authoritative selected-test timings" not in out


def test_authoritative_selection_reports_assigned_budget_range(
    capsys: pytest.CaptureFixture[str],
) -> None:
    tasks = [
        MutationTask(mutant_name=f"src/calc.py::add__mutmut_{index}", tests=[test])
        for index, test in enumerate(["test_fast", "test_slow"], 1)
    ]
    dispatched = _apply_timeouts(
        tasks,
        {"test_fast": 0.5, "test_slow": 2.0},
        2.0,
        startup_floor=5.0,
        clean_wall_seconds=7.5,
    )

    _print_timeout_model(
        dispatched, 2.0, startup_floor=5.0, clean_wall_seconds=7.5, total_test_time=2.5
    )

    assert [task.timeout_seconds for task in dispatched] == [6.0, 9.0]
    out = capsys.readouterr().out
    assert "Timeout budgets: 6.0s to 9.0s for 2 dispatched task(s)." in out
    assert "2 task(s) use authoritative selected-test timings" in out
    assert "max(5.0s, startup floor 5.0s + selected test time x 2.0)" in out
    assert "fallback" not in out


@pytest.mark.parametrize(
    ("test_time", "clean_wall", "budgets", "displayed_budgets"),
    [(0.5, 5.5, [6.0, 60.0], "6.0s to 60.0s"), (27.5, 30.0, [60.0, 60.0], "60.0s")],
)
def test_mixed_dispatch_reports_both_active_models(
    test_time: float,
    clean_wall: float,
    budgets: list[float],
    displayed_budgets: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    tasks = [
        MutationTask(mutant_name="src/calc.py::add__mutmut_1", tests=["test_fast"]),
        MutationTask(
            mutant_name="src/calc.py::add__mutmut_2",
            tests=["test_fast"],
            test_selection_is_authoritative=False,
        ),
    ]
    dispatched = _apply_timeouts(
        tasks, {"test_fast": test_time}, 2.0, startup_floor=5.0, clean_wall_seconds=clean_wall
    )

    _print_timeout_model(
        dispatched,
        2.0,
        startup_floor=5.0,
        clean_wall_seconds=clean_wall,
        total_test_time=test_time,
    )

    assert [task.timeout_seconds for task in dispatched] == budgets
    out = capsys.readouterr().out
    assert f"Timeout budgets: {displayed_budgets} for 2 dispatched task(s)." in out
    assert "1 task(s) use authoritative selected-test timings" in out
    assert "1 task(s) use the fallback" in out


def test_no_dispatch_has_no_timeout_announcement(capsys: pytest.CaptureFixture[str]) -> None:
    _print_timeout_model([], 2.0, startup_floor=5.0, clean_wall_seconds=5.5, total_test_time=0.5)

    assert capsys.readouterr().out == ""


def test_run_announces_the_budget_sent_to_executor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    source = tmp_path / "src"
    source.mkdir()
    (source / "calc.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    monkeypatch.setattr(
        "mutmut_win.orchestrator.build_run_basis_evidence",
        lambda *_args, **_kwargs: RunBasisEvidence("a" * 64, True),
    )

    dispatched: list[MutationTask] = []
    executor = MagicMock()
    executor.start.side_effect = dispatched.extend

    def events() -> Any:
        pid = os.getpid()
        for task in dispatched:
            yield TaskStarted(mutant_name=task.mutant_name, worker_pid=pid)
            yield TaskCompleted(
                mutant_name=task.mutant_name, worker_pid=pid, exit_code=1, duration=0.01
            )

    executor.get_events.side_effect = events
    runner = MagicMock()
    runner.run_clean_test.return_value = 0
    runner.run_forced_fail.return_value = 1
    runner.run_stats.return_value = None
    runner.collect_tests.return_value = []
    orchestrator = MutationOrchestrator(
        MutmutConfig(max_children=1, timeout_multiplier=2.0, paths_to_mutate=["src"]),
        runner=runner,
        executor=executor,
        db_path=tmp_path / "cache.db",
    )

    orchestrator.run()

    assert dispatched
    assert {task.timeout_seconds for task in dispatched} == {60.0}
    out = capsys.readouterr().out
    assert f"Timeout budgets: 60.0s for {len(dispatched)} dispatched task(s)." in out
    assert f"Timeout model: {len(dispatched)} task(s) use the fallback" in out
    assert "selected test time x" not in out
