"""Issue #119 (external QA RUN-001): the documented result cache, implemented.

The README has long promised "unchanged mutants are not re-run"; until
v2.13.0 the result DB was write-only for ``run``. A prior verdict is now
reused iff the mutant's file took the staging fast path (source
fingerprint unchanged), its currently assigned test set is unchanged
(``tests_fingerprint``: sorted node IDs + per-test-file mtime/size), and
the stored status is reusable. ``--rerun-all`` opts out; reuse is loud.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from mutmut_win.config import MutmutConfig
from mutmut_win.db import create_db, load_results, save_result
from mutmut_win.models import MutationResult, MutationTask
from mutmut_win.orchestrator import (
    REUSABLE_STATUSES,
    MutationOrchestrator,
    _build_tests_fingerprints,
    _split_reusable_tasks,
    _tests_fingerprint,
)
from mutmut_win.stats import MutmutStats

# ---------------------------------------------------------------------------
# The reusable-verdict set is a conscious decision
# ---------------------------------------------------------------------------


class TestReusableStatuses:
    def test_exact_set(self) -> None:
        """timeout/suspicious are environment-sensitive, 'no tests' is
        re-verdicted per run (#106), type-check kills are re-produced by
        the filter, interrupt placeholders carry no verdict."""
        assert {
            "killed",
            "survived",
            "segfault",
            "killed_by_infinite_loop",
        } == REUSABLE_STATUSES


# ---------------------------------------------------------------------------
# tests_fingerprint
# ---------------------------------------------------------------------------


class TestTestsFingerprint:
    @pytest.fixture(autouse=True)
    def _cwd(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_a.py").write_text("def test_x(): pass\n", encoding="utf-8")

    def test_node_order_does_not_matter(self) -> None:
        a = _tests_fingerprint(["tests/test_a.py::test_x", "tests/test_a.py::test_y"])
        b = _tests_fingerprint(["tests/test_a.py::test_y", "tests/test_a.py::test_x"])
        assert a == b

    def test_different_node_sets_differ(self) -> None:
        a = _tests_fingerprint(["tests/test_a.py::test_x"])
        b = _tests_fingerprint(["tests/test_a.py::test_y"])
        assert a != b

    def test_editing_the_test_file_changes_the_fingerprint(self, tmp_path: Path) -> None:
        """The node-ID-only hash would keep cached verdicts after assertions
        were strengthened — the file part must invalidate reuse."""
        before = _tests_fingerprint(["tests/test_a.py::test_x"])
        target = tmp_path / "tests" / "test_a.py"
        stat = target.stat()
        os.utime(target, ns=(stat.st_mtime_ns + 1_000_000_000, stat.st_mtime_ns + 1_000_000_000))
        after = _tests_fingerprint(["tests/test_a.py::test_x"])
        assert before != after

    def test_missing_file_is_deterministic(self) -> None:
        a = _tests_fingerprint(["tests/nope.py::test_x"])
        b = _tests_fingerprint(["tests/nope.py::test_x"])
        assert a == b

    def test_build_skips_tasks_without_tests(self) -> None:
        tasks = [
            MutationTask(mutant_name="m1", tests=["tests/test_a.py::test_x"]),
            MutationTask(mutant_name="m2", tests=[]),
        ]
        fingerprints = _build_tests_fingerprints(tasks)
        assert "m1" in fingerprints
        assert "m2" not in fingerprints  # full-suite fallback: never reusable


# ---------------------------------------------------------------------------
# Condition matrix
# ---------------------------------------------------------------------------


def _row(name: str, status: str, fingerprint: str | None) -> None:
    save_result(
        Path(".mutmut-test.db"),
        name,
        status,
        1,
        0.1,
        tests_fingerprint=fingerprint,
    )


class TestSplitReusableTasks:
    @pytest.fixture(autouse=True)
    def _cwd(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)

    def _split(
        self,
        *,
        status: str = "killed",
        in_fast_path: bool = True,
        stored_fp: str | None = "fp1",
        current_fp: str | None = "fp1",
        with_row: bool = True,
    ) -> tuple[list[MutationResult], list[MutationTask]]:
        db = Path(".mutmut-test.db")
        if with_row:
            _row("m1", status, stored_fp)
        else:
            create_db(db)
        task = MutationTask(mutant_name="m1", tests=["tests/t.py::x"])
        fp_map = {"m1": current_fp} if current_fp is not None else {}
        fast = {"m1"} if in_fast_path else set()
        return _split_reusable_tasks([task], fast, fp_map, db)

    def test_all_conditions_met_reuses(self) -> None:
        reused, remaining = self._split()
        assert [r.mutant_name for r in reused] == ["m1"]
        assert remaining == []

    def test_not_fast_path_dispatches(self) -> None:
        reused, remaining = self._split(in_fast_path=False)
        assert reused == []
        assert len(remaining) == 1

    def test_fingerprint_mismatch_dispatches(self) -> None:
        reused, remaining = self._split(current_fp="fp2")
        assert reused == []
        assert len(remaining) == 1

    def test_null_stored_fingerprint_dispatches(self) -> None:
        """Pre-v2.13 rows carry NULL — conservatively never reused."""
        reused, remaining = self._split(stored_fp=None)
        assert reused == []
        assert len(remaining) == 1

    def test_no_current_fingerprint_dispatches(self) -> None:
        reused, remaining = self._split(current_fp=None)
        assert reused == []
        assert len(remaining) == 1

    @pytest.mark.parametrize("status", ["timeout", "suspicious", "no tests", "not checked"])
    def test_non_reusable_status_dispatches(self, status: str) -> None:
        reused, remaining = self._split(status=status)
        assert reused == []
        assert len(remaining) == 1

    def test_no_row_dispatches(self) -> None:
        reused, remaining = self._split(with_row=False)
        assert reused == []
        assert len(remaining) == 1


# ---------------------------------------------------------------------------
# DB roundtrip + migration
# ---------------------------------------------------------------------------


class TestDbFingerprintColumn:
    def test_fingerprint_roundtrips(self, tmp_path: Path) -> None:
        db = tmp_path / "db.sqlite"
        save_result(db, "m1", "killed", 1, 0.1, tests_fingerprint="abc123")
        rows = load_results(db)
        assert rows[0].tests_fingerprint == "abc123"

    def test_old_schema_is_migrated_on_read(self, tmp_path: Path) -> None:
        """A pre-v2.13 DB (no tests_fingerprint column) stays readable;
        old rows surface with None and are therefore never reused."""
        import sqlite3

        db = tmp_path / "old.sqlite"
        with sqlite3.connect(db) as conn:
            conn.execute(
                "CREATE TABLE mutant (mutant_name TEXT PRIMARY KEY, status TEXT NOT NULL, "
                "exit_code INTEGER, duration REAL, last_output TEXT, forensics TEXT)"
            )
            conn.execute("INSERT INTO mutant VALUES ('m1', 'killed', 1, 0.1, NULL, NULL)")
            conn.commit()
        rows = load_results(db)
        assert rows[0].mutant_name == "m1"
        assert rows[0].tests_fingerprint is None


# ---------------------------------------------------------------------------
# End to end: run B reuses, file/test changes re-run, --rerun-all opts out
# ---------------------------------------------------------------------------


_SRC = "def add(a, b):\n    return a + b\n"


def _project(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "target.py").write_text(_SRC, encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_target.py").write_text("def test_add(): pass\n", encoding="utf-8")


def _stats() -> MutmutStats:
    return MutmutStats(
        tests_by_mangled_function_name={"target.x_add": {"tests/test_target.py::test_add"}},
        duration_by_test={"tests/test_target.py::test_add": 0.05},
        stats_time=0.05,
    )


def _killing_executor() -> MagicMock:
    from mutmut_win.models import TaskCompleted

    executor = MagicMock()
    captured: list[MutationTask] = []

    def fake_start(tasks: list[MutationTask]) -> None:
        captured.clear()
        captured.extend(tasks)

    def fake_events() -> Any:
        return iter(
            TaskCompleted(mutant_name=t.mutant_name, worker_pid=1, exit_code=1, duration=0.05)
            for t in captured
        )

    executor.start.side_effect = fake_start
    executor.get_events.side_effect = fake_events
    executor.captured = captured
    return executor


def _runner() -> MagicMock:
    runner = MagicMock()
    runner.run_clean_test.return_value = 0
    runner.run_stats.return_value = None
    runner.collect_tests.return_value = []
    runner.run_forced_fail.return_value = 1
    runner.last_forced_fail_attributed = True
    return runner


def _orchestrate(tmp_path: Path, *, rerun_all: bool = False) -> tuple[Any, MagicMock]:
    executor = _killing_executor()
    orch = MutationOrchestrator(
        MutmutConfig(paths_to_mutate=["src"], tests_dir=["tests/"], max_children=1),
        runner=_runner(),
        executor=executor,
        db_path=tmp_path / "reuse.sqlite",
        rerun_all=rerun_all,
    )
    summary = orch.run()
    return summary, executor


@pytest.mark.usefixtures("_stats_patch")
class TestReuseEndToEnd:
    @pytest.fixture(autouse=True)
    def _cwd(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        _project(tmp_path)

    @pytest.fixture
    def _stats_patch(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import mutmut_win.orchestrator as orch_mod

        monkeypatch.setattr(orch_mod, "collect_or_load_stats", lambda _runner: _stats())

    def test_unchanged_second_run_dispatches_nothing(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The RUN-001 report repro: back-to-back runs with zero changes."""
        summary_a, executor_a = _orchestrate(tmp_path)
        assert summary_a.killed > 0
        assert executor_a.start.call_count == 1
        dispatched_a = len(executor_a.captured)
        assert dispatched_a > 0

        summary_b, executor_b = _orchestrate(tmp_path)
        assert executor_b.start.call_count == 0  # nothing dispatched
        assert summary_b.killed == summary_a.killed  # identical buckets
        assert summary_b.total_mutants == summary_a.total_mutants
        assert f"Reused {dispatched_a} cached verdicts" in capsys.readouterr().out

    def test_source_change_rerons_only_that_file(self, tmp_path: Path) -> None:
        _orchestrate(tmp_path)
        # Touch the SOURCE: fast path misses, everything re-runs.
        target = tmp_path / "src" / "target.py"
        target.write_text(_SRC + "\n# changed\n", encoding="utf-8")
        _summary, executor = _orchestrate(tmp_path)
        assert executor.start.call_count == 1
        assert len(executor.captured) > 0

    def test_test_change_invalidates_reuse(self, tmp_path: Path) -> None:
        _orchestrate(tmp_path)
        test_file = tmp_path / "tests" / "test_target.py"
        stat = test_file.stat()
        os.utime(
            test_file,
            ns=(stat.st_mtime_ns + 2_000_000_000, stat.st_mtime_ns + 2_000_000_000),
        )
        _summary, executor = _orchestrate(tmp_path)
        assert executor.start.call_count == 1  # fingerprints differ -> re-run

    def test_rerun_all_forces_execution(self, tmp_path: Path) -> None:
        _orchestrate(tmp_path)
        _summary, executor = _orchestrate(tmp_path, rerun_all=True)
        assert executor.start.call_count == 1
        assert len(executor.captured) > 0
