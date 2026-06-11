"""Tests for the 'no tests' producer (Issue #106, audit A4-QX-007).

``tests=[]`` on a task used to be AMBIGUOUS: the worker dispatched such a
task without node-id arguments, so pytest ran the FULL suite for that one
mutant — for every unmapped mutant.  That burned the entire suite runtime
per mutant and produced random full-suite kills that inflated the score.

The two meanings are now separated at assignment time:

* Mapping EXISTS, mutant has no entry -> the honest verdict is ``no tests``
  (exit 33): persisted directly, never dispatched — the same pattern that
  issue #93 established for type-check kills.
* No mapping at all (stats collection failed or recorded nothing — possibly
  the hit-recording bugs QX-017/018) -> the full-suite fallback REMAINS the
  safe choice (loud since #99): deciding "no tests for everything" on an
  empty mapping would misreport a broken stats run as untested code.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

from mutmut_win.config import MutmutConfig
from mutmut_win.constants import EXIT_CODE_NO_TESTS
from mutmut_win.db import load_results
from mutmut_win.models import MutationTask, TaskCompleted, TaskStarted
from mutmut_win.orchestrator import MutationOrchestrator, _split_no_test_tasks
from mutmut_win.stats import MutmutStats, save_stats

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def _task(name: str, tests: list[str] | None = None) -> MutationTask:
    return MutationTask(mutant_name=name, tests=tests or [])


def _stats(mapping: dict[str, set[str]] | None = None) -> MutmutStats:
    return MutmutStats(
        tests_by_mangled_function_name=mapping or {},
        duration_by_test={"tests/test_x.py::test_one": 0.5},
        stats_time=1.0,
    )


class TestSplitNoTestTasks:
    def test_mapped_but_empty_mutant_is_split_off(self) -> None:
        tasks = [
            _task("src/a.py::x_f__mutmut_1", tests=["tests/test_x.py::test_one"]),
            _task("src/a.py::x_g__mutmut_1"),  # mapping exists, no entry for g
        ]
        mapping = {"src/a.py::x_f": {"tests/test_x.py::test_one"}}

        dispatchable, no_tests = _split_no_test_tasks(tasks, _stats(mapping))

        assert [t.mutant_name for t in dispatchable] == ["src/a.py::x_f__mutmut_1"]
        assert no_tests == {"src/a.py::x_g__mutmut_1"}

    def test_empty_mapping_keeps_the_full_suite_fallback(self) -> None:
        # An empty mapping means the stats run failed or recorded nothing —
        # NOT that no tests exist. Everything stays dispatchable.
        tasks = [_task("src/a.py::x_f__mutmut_1"), _task("src/a.py::x_g__mutmut_1")]

        dispatchable, no_tests = _split_no_test_tasks(tasks, _stats(mapping=None))

        assert len(dispatchable) == 2
        assert no_tests == set()


class _OrchestratorHarness:
    """Mini project + mocked runner/executor for full-run tests."""

    def __init__(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        src.mkdir()
        (src / "target.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")

        self.captured_tasks: list[MutationTask] = []
        self.executor = MagicMock()
        self.executor.start.side_effect = self.captured_tasks.extend

        def fake_get_events() -> Any:
            pid = os.getpid()
            for task in self.captured_tasks:
                yield TaskStarted(mutant_name=task.mutant_name, worker_pid=pid)
                yield TaskCompleted(
                    mutant_name=task.mutant_name, worker_pid=pid, exit_code=1, duration=0.01
                )

        self.executor.get_events.side_effect = fake_get_events

        self.runner = MagicMock()
        self.runner.run_clean_test.return_value = 0
        self.runner.run_forced_fail.return_value = 1
        # collect_tests matches the cached stats below -> no stats re-run.
        self.runner.collect_tests.return_value = ["tests/test_x.py::test_one"]

        self.db_path = tmp_path / "db"

    def write_stats(self, mapping: dict[str, set[str]]) -> None:
        from pathlib import Path

        mutants_dir = Path("mutants")
        mutants_dir.mkdir(exist_ok=True)
        save_stats(
            MutmutStats(
                tests_by_mangled_function_name=mapping,
                duration_by_test={"tests/test_x.py::test_one": 0.5},
                stats_time=1.0,
            ),
            mutants_dir,
        )

    def run(self) -> Any:
        orch = MutationOrchestrator(
            MutmutConfig(max_children=1, timeout_multiplier=2.0, paths_to_mutate=["src"]),
            runner=self.runner,
            executor=self.executor,
            db_path=self.db_path,
        )
        return orch.run()


class TestNoTestsAreRecordedNotDispatched:
    def test_all_unmapped_mutants_never_reach_the_executor(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # A mapping exists but covers none of the generated mutants: every
        # mutant is honestly 'no tests' — nothing may be dispatched (each
        # dispatch would have been a full-suite run, QX-007).
        monkeypatch.chdir(tmp_path)
        harness = _OrchestratorHarness(tmp_path)
        harness.write_stats({"src/other.py::x_unrelated": {"tests/test_x.py::test_one"}})

        result = harness.run()

        harness.executor.start.assert_not_called()
        assert result.no_tests == result.total_mutants
        assert result.total_mutants > 0
        assert "no tests" in capsys.readouterr().out.lower()

    def test_no_tests_rows_are_persisted_with_exit_33(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Three-channel consistency (#91/#93): `results` and the CICD export
        # read the DB — the verdict must exist there, not only in the
        # in-memory summary.
        monkeypatch.chdir(tmp_path)
        harness = _OrchestratorHarness(tmp_path)
        harness.write_stats({"src/other.py::x_unrelated": {"tests/test_x.py::test_one"}})

        harness.run()

        rows = load_results(harness.db_path)
        assert rows, "expected persisted result rows"
        assert {r.status for r in rows} == {"no tests"}
        assert {r.exit_code for r in rows} == {EXIT_CODE_NO_TESTS}

    def test_empty_mapping_dispatches_everything(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # No mapping at all -> the full-suite fallback stays: all mutants
        # are dispatched, none is verdicted 'no tests'.
        monkeypatch.chdir(tmp_path)
        harness = _OrchestratorHarness(tmp_path)
        harness.write_stats({})

        result = harness.run()

        assert harness.executor.start.called
        assert result.no_tests == 0
        assert result.unchecked == 0
        assert result.total_mutants == len(harness.captured_tasks)

    def test_sum_invariant_holds_with_no_tests_bucket(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Issue #91: every mutant lands in exactly one bucket.
        monkeypatch.chdir(tmp_path)
        harness = _OrchestratorHarness(tmp_path)
        harness.write_stats({"src/other.py::x_unrelated": {"tests/test_x.py::test_one"}})

        result = harness.run()

        buckets = (
            result.killed
            + result.survived
            + result.timeout
            + result.suspicious
            + result.skipped
            + result.no_tests
            + result.segfault
            + result.type_check_caught
            + result.unchecked
        )
        assert buckets == result.total_mutants
