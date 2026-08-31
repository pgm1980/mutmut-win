"""Tests for the 'no tests' producer (Issue #106, audit A4-QX-007).

``tests=[]`` on a task used to be AMBIGUOUS: the worker dispatched such a
task without node-id arguments, so pytest ran the FULL suite for that one
mutant — for every unmapped mutant.  That burned the entire suite runtime
per mutant and produced random full-suite kills that inflated the score.

The two meanings are now separated by an explicit authority bit:

* Only an authoritative collector may turn an absent mapping into ``no tests``.
* The current collector cannot observe every import/subprocess/xdist hit, so
  its mapping is non-authoritative and unmapped mutants use the full suite.
"""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

from mutmut_win.config import MutmutConfig
from mutmut_win.db import load_results
from mutmut_win.models import MutationTask, TaskCompleted, TaskStarted
from mutmut_win.orchestrator import (
    MutationOrchestrator,
    _assign_tests_to_tasks,
    _split_no_test_tasks,
)
from mutmut_win.stats import MutmutStats, load_stats, save_stats

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def _task(name: str, tests: list[str] | None = None) -> MutationTask:
    return MutationTask(mutant_name=name, tests=tests or [])


def _stats(
    mapping: dict[str, set[str]] | None = None,
    *,
    authoritative: bool = False,
) -> MutmutStats:
    return MutmutStats(
        tests_by_mangled_function_name=mapping or {},
        duration_by_test={"tests/test_x.py::test_one": 0.5},
        stats_time=1.0,
        mapping_is_authoritative=authoritative,
    )


class TestSplitNoTestTasks:
    def test_mapped_but_empty_mutant_is_split_off(self) -> None:
        tasks = [
            _task("src/a.py::x_f__mutmut_1", tests=["tests/test_x.py::test_one"]),
            _task("src/a.py::x_g__mutmut_1"),  # mapping exists, no entry for g
        ]
        mapping = {"src/a.py::x_f": {"tests/test_x.py::test_one"}}

        dispatchable, no_tests = _split_no_test_tasks(tasks, _stats(mapping, authoritative=True))

        assert [t.mutant_name for t in dispatchable] == ["src/a.py::x_f__mutmut_1"]
        assert no_tests == {"src/a.py::x_g__mutmut_1"}

    def test_empty_mapping_keeps_the_full_suite_fallback(self) -> None:
        # An empty mapping means the stats run failed or recorded nothing —
        # NOT that no tests exist. Everything stays dispatchable.
        tasks = [_task("src/a.py::x_f__mutmut_1"), _task("src/a.py::x_g__mutmut_1")]

        dispatchable, no_tests = _split_no_test_tasks(tasks, _stats(mapping=None))

        assert len(dispatchable) == 2
        assert no_tests == set()

    def test_non_authoritative_mapping_cannot_narrow_even_observed_mutant(self) -> None:
        task = _task("src/a.py::x_f__mutmut_1")
        mapping = {"src/a.py::x_f": {"tests/test_x.py::test_parent_only"}}

        [assigned] = _assign_tests_to_tasks([task], _stats(mapping))

        # An unobserved subprocess/xdist test may be the one that kills this
        # mutant. Empty node IDs select the full pytest suite in the worker.
        assert assigned.tests == []

    def test_authoritative_mapping_may_narrow_observed_mutant(self) -> None:
        task = _task("src/a.py::x_f__mutmut_1")
        mapping = {"src/a.py::x_f": {"tests/test_x.py::test_one"}}

        [assigned] = _assign_tests_to_tasks([task], _stats(mapping, authoritative=True))

        assert assigned.tests == ["tests/test_x.py::test_one"]

    def test_persisted_authority_bit_cannot_activate_selective_testing(
        self, tmp_path: Path
    ) -> None:
        stats_path = tmp_path / "mutmut-stats.json"
        stats_path.write_text(
            json.dumps(
                {
                    "tests_by_mangled_function_name": {
                        "src/a.py::x_f": ["tests/test_x.py::test_one"]
                    },
                    "duration_by_test": {"tests/test_x.py::test_one": 0.5},
                    "stats_time": 1.0,
                    "context_fingerprint": "current-context",
                    "mapping_is_authoritative": True,
                }
            ),
            encoding="utf-8",
        )

        loaded = load_stats(tmp_path)

        assert loaded is not None
        assert loaded.mapping_is_authoritative is False
        tasks = [
            _task("src/a.py::x_f__mutmut_1"),
            _task("src/a.py::x_g__mutmut_1"),
        ]
        assigned = _assign_tests_to_tasks(tasks, loaded)
        dispatchable, no_tests = _split_no_test_tasks(assigned, loaded)
        assert [task.tests for task in dispatchable] == [[], []]
        assert no_tests == set()

    def test_partial_non_authoritative_mapping_keeps_full_suite(self) -> None:
        tasks = [
            _task("src/a.py::x_f__mutmut_1", tests=["tests/test_x.py::test_one"]),
            _task("src/a.py::x_g__mutmut_1"),
        ]
        mapping = {"src/a.py::x_f": {"tests/test_x.py::test_one"}}

        dispatchable, no_tests = _split_no_test_tasks(tasks, _stats(mapping))

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
    def test_all_unmapped_mutants_use_conservative_full_suite(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # A partial mapping cannot prove absence because import/subprocess
        # hits may be invisible. Every mutant is dispatched conservatively.
        monkeypatch.chdir(tmp_path)
        harness = _OrchestratorHarness(tmp_path)
        harness.write_stats({"src/other.py::x_unrelated": {"tests/test_x.py::test_one"}})

        result = harness.run()

        assert harness.executor.start.called
        assert result.no_tests == 0
        assert result.total_mutants > 0
        assert "no covering tests" not in capsys.readouterr().out.lower()

    def test_non_authoritative_unmapped_rows_receive_real_verdicts(
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
        assert {r.status for r in rows} == {"killed"}
        assert {r.exit_code for r in rows} == {1}

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
