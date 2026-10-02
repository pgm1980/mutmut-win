"""The timeout announcement describes the budgets actually dispatched."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import pytest

from mutmut_win.config import MutmutConfig
from mutmut_win.models import MutationTask, TaskCompleted, TaskStarted
from mutmut_win.orchestrator import (
    MutationOrchestrator,
    _apply_timeouts,
    _assign_tests_to_tasks,
    _print_timeout_model,
)
from mutmut_win.stats import MutmutStats, RunBasisEvidence

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
    assert (
        f"Timeout model: 1 task(s) use the fallback: max(60.0s, clean run {clean_wall:.1f}s x 2.0)."
    ) in out.splitlines()
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
        3.0,
        startup_floor=6.5,
        clean_wall_seconds=9.0,
    )

    _print_timeout_model(
        dispatched, 3.0, startup_floor=6.5, clean_wall_seconds=9.0, total_test_time=2.5
    )

    assert [task.timeout_seconds for task in dispatched] == [8.0, 12.5]
    out = capsys.readouterr().out
    assert "Timeout budgets: 8.0s to 12.5s for 2 dispatched task(s)." in out
    assert (
        "Timeout calibration: startup floor 6.5s (clean run 9.0s - measured test time 2.5s)."
    ) in out.splitlines()
    assert (
        "Timeout model: 2 task(s) use authoritative selected-test timings: "
        "max(5.0s, startup floor 6.5s + selected test time x 3.0)."
    ) in out.splitlines()
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
    assert (
        "Timeout model: 1 task(s) use authoritative selected-test timings: "
        "max(5.0s, startup floor 5.0s + selected test time x 2.0)."
    ) in out.splitlines()
    assert (
        f"Timeout model: 1 task(s) use the fallback: max(60.0s, clean run {clean_wall:.1f}s x 2.0)."
    ) in out.splitlines()


# --- M-102: exactly one truthful diagnosis line per affected run ------------
#
# Tasks WITH timing data still get the full-suite fallback budget when the
# test mapping is not authoritative (the production normal case: the collector
# never sets MutmutStats.mapping_is_authoritative).  The diagnosis explains
# WHY per-test budgets stayed inactive — budgets and verdicts are untouched.


def test_non_authoritative_timing_tasks_report_one_diagnosis_line(
    capsys: pytest.CaptureFixture[str],
) -> None:
    tasks = [
        MutationTask(
            mutant_name="src/calc.py::add__mutmut_1",
            tests=["test_fast"],
            test_selection_is_authoritative=False,
        ),
        MutationTask(
            mutant_name="src/calc.py::add__mutmut_2",
            tests=["test_fast"],
            test_selection_is_authoritative=False,
        ),
        # Authoritative with timing -> selective budget, not affected.
        MutationTask(mutant_name="src/calc.py::add__mutmut_3", tests=["test_fast"]),
        # No test selection -> fallback, but no timing-based selection to explain.
        MutationTask(mutant_name="src/calc.py::add__mutmut_4", tests=[]),
    ]
    dispatched = _apply_timeouts(
        tasks, {"test_fast": 0.5}, 2.0, startup_floor=5.0, clean_wall_seconds=9.0
    )

    _print_timeout_model(
        dispatched, 2.0, startup_floor=5.0, clean_wall_seconds=9.0, total_test_time=0.5
    )

    # Budgets are unchanged: selective for the authoritative task only.
    assert [task.timeout_seconds for task in dispatched] == [60.0, 60.0, 6.0, 60.0]
    out = capsys.readouterr().out
    lines = out.splitlines()
    diagnosis = (
        "Timeout model: 2 task(s) with timing data use the fallback budget "
        "because the test mapping is not authoritative; each such task runs the full suite."
    )
    assert diagnosis in lines
    # Exactly one diagnosis per run — not one per affected task.
    assert out.count("test mapping is not authoritative") == 1
    # It appears after the fallback line it explains.
    assert lines.index(diagnosis) > lines.index(
        "Timeout model: 3 task(s) use the fallback: max(60.0s, clean run 9.0s x 2.0)."
    )


def test_purely_authoritative_dispatch_prints_no_diagnosis_line(
    capsys: pytest.CaptureFixture[str],
) -> None:
    tasks = [
        MutationTask(mutant_name=f"src/calc.py::add__mutmut_{index}", tests=["test_slow"])
        for index in range(1, 3)
    ]
    dispatched = _apply_timeouts(
        tasks, {"test_slow": 2.0}, 3.0, startup_floor=6.5, clean_wall_seconds=9.0
    )

    _print_timeout_model(
        dispatched, 3.0, startup_floor=6.5, clean_wall_seconds=9.0, total_test_time=4.0
    )

    out = capsys.readouterr().out
    assert "test mapping is not authoritative" not in out
    assert "use the fallback budget because" not in out


def test_tasks_without_tests_print_no_diagnosis_line(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Tasks without a test selection have no timing-based selection that the
    # non-authority could suppress — the diagnosis must stay silent for them.
    tasks = [
        MutationTask(mutant_name=f"src/calc.py::add__mutmut_{index}", tests=[])
        for index in range(1, 3)
    ]
    dispatched = _apply_timeouts(
        tasks, {"test_a": 1.0}, 2.0, startup_floor=5.0, clean_wall_seconds=8.0
    )

    _print_timeout_model(
        dispatched, 2.0, startup_floor=5.0, clean_wall_seconds=8.0, total_test_time=1.0
    )

    out = capsys.readouterr().out
    # The fallback path ran (mean timing > 0), yet no diagnosis line appears.
    assert (
        "Timeout model: 2 task(s) use the fallback: max(60.0s, clean run 8.0s x 2.0)."
        in out.splitlines()
    )
    assert "test mapping is not authoritative" not in out


def test_missing_timing_data_prints_no_diagnosis_line(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # M-102 counting rule: the diagnosis speaks about tasks WITH timing data.
    # This task HAS a selection and IS non-authoritative, but its selected
    # test has no recorded duration (estimated == 0) — printing the
    # "with timing data" diagnosis here would be a lie.
    task = MutationTask(
        mutant_name="src/calc.py::add__mutmut_1",
        tests=["test_unknown"],
        test_selection_is_authoritative=False,
    )
    dispatched = _apply_timeouts(
        [task], {"test_other": 3.0}, 2.0, startup_floor=5.0, clean_wall_seconds=8.0
    )

    _print_timeout_model(
        dispatched, 2.0, startup_floor=5.0, clean_wall_seconds=8.0, total_test_time=3.0
    )

    assert dispatched[0].estimated_time == 0.0
    assert dispatched[0].timeout_seconds == 60.0  # the fallback branch ran
    out = capsys.readouterr().out
    assert (
        "Timeout model: 1 task(s) use the fallback: max(60.0s, clean run 8.0s x 2.0)."
        in out.splitlines()
    )
    assert "test mapping is not authoritative" not in out


def test_production_sequence_prints_the_diagnosis_exactly_once(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # The production data flow: _assign_tests_to_tasks overwrites the
    # authority bit with MutmutStats.mapping_is_authoritative (always False
    # with the current collector) while the mapping DOES carry timings —
    # such a run must print exactly one diagnosis, and the budget stays the
    # full-suite fallback.
    assigned = _assign_tests_to_tasks(
        [MutationTask(mutant_name="calc.x_add__mutmut_1")],
        MutmutStats(
            tests_by_mangled_function_name={"calc.x_add": {"tests/test_calc.py::test_add"}},
            duration_by_test={"tests/test_calc.py::test_add": 30.0},
            mapping_is_authoritative=False,
        ),
    )
    dispatched = _apply_timeouts(
        assigned,
        {"tests/test_calc.py::test_add": 30.0},
        2.0,
        startup_floor=5.0,
        clean_wall_seconds=100.0,
    )
    _print_timeout_model(
        dispatched, 2.0, startup_floor=5.0, clean_wall_seconds=100.0, total_test_time=30.0
    )

    assert dispatched[0].timeout_seconds == 200.0  # fallback budget, unchanged
    out = capsys.readouterr().out
    assert (
        out.count(
            "Timeout model: 1 task(s) with timing data use the fallback budget "
            "because the test mapping is not authoritative; each such task runs the full suite."
        )
        == 1
    )


def test_diagnosis_line_follows_the_cli_json_redirect_to_stderr(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # cli.py wraps the whole run (incl. _print_timeout_model) in
    # redirect_stdout(sys.stderr) for --output json; the diagnosis must keep
    # the stdout JSON channel clean through that same mechanism.
    import contextlib
    import sys

    task = MutationTask(
        mutant_name="src/calc.py::add__mutmut_1",
        tests=["test_fast"],
        test_selection_is_authoritative=False,
    )
    dispatched = _apply_timeouts(
        [task], {"test_fast": 0.5}, 2.0, startup_floor=5.0, clean_wall_seconds=9.0
    )

    with contextlib.redirect_stdout(sys.stderr):
        _print_timeout_model(
            dispatched, 2.0, startup_floor=5.0, clean_wall_seconds=9.0, total_test_time=0.5
        )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.count("test mapping is not authoritative") == 1


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
