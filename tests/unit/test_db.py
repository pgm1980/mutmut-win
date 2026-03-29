"""Unit tests for mutmut_win.db (SQLite persistence layer)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from mutmut_win.db import create_db, load_results, save_result
from mutmut_win.models import MutationResult

if TYPE_CHECKING:
    from pathlib import Path


# ---------------------------------------------------------------------------
# create_db
# ---------------------------------------------------------------------------


class TestCreateDb:
    def test_creates_file(self, tmp_path: Path) -> None:
        db_path = tmp_path / ".mutmut-cache" / "test-cache.db"
        create_db(db_path)
        assert db_path.exists()

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        nested = tmp_path / "a" / "b" / "c" / "cache.db"
        create_db(nested)
        assert nested.exists()

    def test_idempotent(self, tmp_path: Path) -> None:
        """Calling create_db twice must not raise."""
        db_path = tmp_path / "cache.db"
        create_db(db_path)
        create_db(db_path)  # second call — should not fail
        assert db_path.exists()

    def test_creates_mutant_table(self, tmp_path: Path) -> None:
        import sqlite3

        db_path = tmp_path / "cache.db"
        create_db(db_path)
        with sqlite3.connect(db_path) as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='mutant'"
            )
            rows = cursor.fetchall()
        assert len(rows) == 1


# ---------------------------------------------------------------------------
# save_result
# ---------------------------------------------------------------------------


class TestSaveResult:
    def test_saves_killed_mutant(self, tmp_path: Path) -> None:
        db_path = tmp_path / "cache.db"
        save_result(db_path, "mod.foo__mutmut_1", "killed", 1, 0.42)
        results = load_results(db_path)
        assert len(results) == 1
        assert results[0].mutant_name == "mod.foo__mutmut_1"
        assert results[0].status == "killed"
        assert results[0].exit_code == 1
        assert results[0].duration == pytest.approx(0.42)

    def test_saves_survived_mutant(self, tmp_path: Path) -> None:
        db_path = tmp_path / "cache.db"
        save_result(db_path, "mod.bar__mutmut_2", "survived", 0, 1.0)
        results = load_results(db_path)
        assert results[0].status == "survived"

    def test_saves_none_exit_code(self, tmp_path: Path) -> None:
        db_path = tmp_path / "cache.db"
        save_result(db_path, "mod.baz__mutmut_3", "not checked", None, None)
        results = load_results(db_path)
        assert results[0].exit_code is None
        assert results[0].duration is None

    def test_upsert_replaces_existing(self, tmp_path: Path) -> None:
        db_path = tmp_path / "cache.db"
        save_result(db_path, "mod.foo__mutmut_1", "survived", 0, 0.1)
        save_result(db_path, "mod.foo__mutmut_1", "killed", 1, 0.2)
        results = load_results(db_path)
        assert len(results) == 1
        assert results[0].status == "killed"

    def test_multiple_mutants_saved(self, tmp_path: Path) -> None:
        db_path = tmp_path / "cache.db"
        for i in range(5):
            save_result(db_path, f"mod.fn__mutmut_{i}", "killed", 1, float(i))
        results = load_results(db_path)
        assert len(results) == 5

    def test_creates_db_if_not_exists(self, tmp_path: Path) -> None:
        fresh_path = tmp_path / "new" / "cache.db"
        assert not fresh_path.exists()
        save_result(fresh_path, "m1", "killed", 1, 0.1)
        assert fresh_path.exists()


# ---------------------------------------------------------------------------
# load_results
# ---------------------------------------------------------------------------


class TestLoadResults:
    def test_returns_empty_list_when_db_missing(self, tmp_path: Path) -> None:
        missing = tmp_path / "nonexistent.db"
        results = load_results(missing)
        assert results == []

    def test_returns_mutation_result_instances(self, tmp_path: Path) -> None:
        db_path = tmp_path / "cache.db"
        save_result(db_path, "m1", "killed", 1, 0.5)
        results = load_results(db_path)
        assert all(isinstance(r, MutationResult) for r in results)

    def test_round_trip_all_statuses(self, tmp_path: Path) -> None:
        db_path = tmp_path / "cache.db"
        statuses = ["killed", "survived", "timeout", "suspicious", "skipped", "no tests"]
        for i, status in enumerate(statuses):
            save_result(db_path, f"mod.fn__mutmut_{i}", status, i, float(i))
        results = load_results(db_path)
        loaded_statuses = {r.status for r in results}
        assert loaded_statuses == set(statuses)

    def test_loads_after_create_and_save(self, tmp_path: Path) -> None:
        db_path = tmp_path / "cache.db"
        create_db(db_path)
        save_result(db_path, "x.y__mutmut_1", "survived", 0, 2.0)
        results = load_results(db_path)
        assert len(results) == 1
        assert results[0].mutant_name == "x.y__mutmut_1"
