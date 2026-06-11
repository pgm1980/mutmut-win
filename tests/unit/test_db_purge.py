"""Tests for stale-row purging (Issue #96, audit A3-OS-012 orphan part).

The DB only ever UPSERTed: rows of mutants that no longer exist (renamed or
edited sources produce different mutant names) survived forever, so
``results`` reported the union of all runs ever — ghost totals, ghost
survivors nobody can reproduce.  A full run now purges rows whose mutant is
not in the freshly generated set.  Destructive operation — the guards are
the point of these tests.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

from mutmut_win.db import create_db, delete_results_not_in, load_results, save_result

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def _seed(db_path: Path, names: list[str]) -> None:
    create_db(db_path)
    for name in names:
        save_result(db_path, name, "killed", 1, 0.1)


class TestDeleteResultsNotIn:
    def test_purges_exactly_the_orphans(self, tmp_path: Path) -> None:
        db = tmp_path / "db.sqlite"
        _seed(db, ["pkg.a.x_f__mutmut_1", "pkg.a.x_f__mutmut_2", "pkg.gone.x_g__mutmut_1"])

        deleted = delete_results_not_in(db, {"pkg.a.x_f__mutmut_1", "pkg.a.x_f__mutmut_2"})

        assert deleted == 1
        remaining = {r.mutant_name for r in load_results(db)}
        assert remaining == {"pkg.a.x_f__mutmut_1", "pkg.a.x_f__mutmut_2"}

    def test_idempotent_when_nothing_is_stale(self, tmp_path: Path) -> None:
        db = tmp_path / "db.sqlite"
        _seed(db, ["pkg.a.x_f__mutmut_1"])
        assert delete_results_not_in(db, {"pkg.a.x_f__mutmut_1"}) == 0
        assert delete_results_not_in(db, {"pkg.a.x_f__mutmut_1"}) == 0
        assert len(load_results(db)) == 1

    def test_empty_db_deletes_nothing(self, tmp_path: Path) -> None:
        db = tmp_path / "db.sqlite"
        create_db(db)
        assert delete_results_not_in(db, {"anything"}) == 0

    def test_chunking_beyond_sqlite_parameter_limit(self, tmp_path: Path) -> None:
        # SQLite caps bound parameters (999 historically) — the orphan
        # delete must chunk.
        db = tmp_path / "db.sqlite"
        names = [f"pkg.m.x_f__mutmut_{i}" for i in range(1500)]
        _seed(db, names)

        keep = set(names[:100])
        deleted = delete_results_not_in(db, keep)

        assert deleted == 1400
        assert {r.mutant_name for r in load_results(db)} == keep


class TestOrchestratorPurgeWiring:
    def _run_with_ghost(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, purge: bool
    ) -> set[str]:
        import os

        from mutmut_win.models import MutationTask, TaskCompleted, TaskStarted
        from mutmut_win.orchestrator import MutationOrchestrator

        monkeypatch.chdir(tmp_path)
        src = tmp_path / "src"
        src.mkdir()
        (src / "target.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")

        db_path = tmp_path / "cache.db"
        _seed(db_path, ["pkg.gone.x_g__mutmut_1"])  # ghost from a previous epoch

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

        from mutmut_win.config import MutmutConfig

        runner = MagicMock()
        runner.run_clean_test.return_value = 0
        runner.run_forced_fail.return_value = 1
        runner.collect_tests.return_value = []

        orch = MutationOrchestrator(
            MutmutConfig(max_children=1, timeout_multiplier=2.0, paths_to_mutate=["src"]),
            runner=runner,
            executor=executor,
            db_path=db_path,
            purge_stale_results=purge,
        )
        orch.run()
        return {r.mutant_name for r in load_results(db_path)}

    def test_full_run_purges_the_ghost(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        remaining = self._run_with_ghost(tmp_path, monkeypatch, purge=True)
        assert "pkg.gone.x_g__mutmut_1" not in remaining
        assert remaining  # current mutants persisted

    def test_default_is_the_safe_polarity_no_purge(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        remaining = self._run_with_ghost(tmp_path, monkeypatch, purge=False)
        assert "pkg.gone.x_g__mutmut_1" in remaining


class TestCliPurgeWiring:
    def _captured_kwargs(self, *args: str) -> dict[str, Any]:
        from mutmut_win.cli import cli
        from mutmut_win.models import MutationRunResult

        captured: dict[str, Any] = {}

        def fake_orchestrator(*_a: Any, **kwargs: Any) -> MagicMock:
            captured.update(kwargs)
            instance = MagicMock()
            instance.run.return_value = MutationRunResult(total_mutants=1, killed=1)
            return instance

        from click.testing import CliRunner

        with (
            patch("mutmut_win.cli.MutationOrchestrator", side_effect=fake_orchestrator),
            patch("mutmut_win.cli.PytestRunner"),
            patch("mutmut_win.cli.SpawnPoolExecutor"),
            patch("mutmut_win.cli.load_config", return_value=MagicMock(model_copy=MagicMock())),
        ):
            CliRunner().invoke(cli, ["run", *args])
        return captured

    def test_unfiltered_run_purges(self) -> None:
        assert self._captured_kwargs()["purge_stale_results"] is True

    def test_mutant_names_run_never_purges(self) -> None:
        # A subset run only knows a slice of the valid set — purging from it
        # would delete healthy history.
        assert self._captured_kwargs("pkg.a.x_f__mutmut_1")["purge_stale_results"] is False
