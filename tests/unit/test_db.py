"""Unit tests for mutmut_win.db (SQLite persistence layer)."""

from __future__ import annotations

import contextlib
import sqlite3
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


# ---------------------------------------------------------------------------
# schema migration on the read path (mutation hardening for create_db)
# ---------------------------------------------------------------------------


def _make_old_schema_db(path: Path) -> None:
    """Create a pre-migration cache the way mutmut-win < v2.5 did.

    The ``mutant`` table is created WITHOUT the ``last_output``, ``forensics``
    and ``tests_fingerprint`` columns and seeded with one row, so a later
    ``create_db`` / ``load_results`` has real migrations to perform on the
    read path.

    Args:
        path: Destination database file.
    """
    with contextlib.closing(sqlite3.connect(path)) as conn:
        conn.execute(
            "CREATE TABLE mutant ("
            "mutant_name TEXT PRIMARY KEY, status TEXT NOT NULL, "
            "exit_code INTEGER, duration REAL)"
        )
        conn.execute(
            "INSERT INTO mutant VALUES (?, ?, ?, ?)",
            ("pkg.mod.fn__mutmut_1", "survived", 0, 0.5),
        )
        conn.commit()


def _table_columns(path: Path) -> set[str]:
    """Return the column names of the ``mutant`` table.

    Args:
        path: Database file to inspect.

    Returns:
        Column names as reported by ``PRAGMA table_info``.
    """
    with contextlib.closing(sqlite3.connect(path)) as conn:
        return {row[1] for row in conn.execute("PRAGMA table_info(mutant)").fetchall()}


class TestSchemaMigration:
    """Migration-on-read coverage for the ``create_db`` schema branches.

    These pin the migration guards to >=80% function-wise mutation. The
    residual survivors under ``--profile all --force "*create_db*"`` are all
    EQUIVALENT and cannot be killed: case-only respellings of the
    ``PRAGMA table_info(mutant)`` query (SQLite keywords and identifiers are
    case-insensitive), and ``conn.commit()`` -> ``pass`` (``create_db`` only
    issues DDL, which autocommits — no transaction is ever open for the commit
    to flush; the upsert commit on the DML path IS load-bearing and is pinned
    by :class:`TestWriteDurability`).
    """

    _NEW_COLUMNS = frozenset({"last_output", "forensics", "tests_fingerprint"})

    def test_old_schema_is_migrated_with_new_columns(self, tmp_path: Path) -> None:
        # A pre-v2.5 cache lacks the columns the SELECT in load_results names;
        # create_db must add every one of them on the read path. Pins the
        # "X not in columns -> ALTER" branches against mutants that skip a
        # genuinely needed migration.
        db_path = tmp_path / "old-cache.db"
        _make_old_schema_db(db_path)

        create_db(db_path)

        assert _table_columns(db_path) >= self._NEW_COLUMNS

    def test_migration_preserves_existing_rows(self, tmp_path: Path) -> None:
        # The ALTERs must not drop the pre-existing row, and the brand-new
        # columns read back as NULL for it.
        db_path = tmp_path / "old-cache.db"
        _make_old_schema_db(db_path)

        results = load_results(db_path)

        assert len(results) == 1
        row = results[0]
        assert row.mutant_name == "pkg.mod.fn__mutmut_1"
        assert row.status == "survived"
        assert row.last_output is None
        assert row.forensics is None
        assert row.tests_fingerprint is None

    def test_no_redundant_migration_on_current_schema(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The "X not in columns" guards exist to AVOID firing an ALTER when the
        # schema is already current (issue #100 / A3-FD-007 — migrations are
        # race-tolerant, but must also not run needlessly). On a freshly
        # created DB every column is present, so not one migration may be
        # attempted. _add_column_if_missing swallows duplicate-column errors,
        # so a redundant ALTER is otherwise INVISIBLE — spying on the migration
        # primitive is what pins the contract and kills the always-migrate
        # mutants (if True, case-swapped names, wrong PRAGMA index).
        from mutmut_win import db as db_module

        db_path = tmp_path / "cache.db"
        create_db(db_path)  # fully-current schema, all columns present

        attempted: list[str] = []
        real_add = db_module._add_column_if_missing

        def spy(conn: sqlite3.Connection, ddl: str) -> None:
            attempted.append(ddl)
            real_add(conn, ddl)

        monkeypatch.setattr(db_module, "_add_column_if_missing", spy)

        create_db(db_path)  # second call on an already-current schema

        assert attempted == [], f"create_db ran redundant migrations: {attempted}"


class TestWriteDurability:
    """Persistence guard for the upsert commit path."""

    def test_save_result_is_durable_across_connections(self, tmp_path: Path) -> None:
        # The upsert must be committed: without conn.commit() the INSERT is
        # rolled back when the writer closes its connection, and a later reader
        # on a brand-new connection sees nothing. Reading back through both a
        # fresh load_results AND a raw connection proves the write survived the
        # close.
        db_path = tmp_path / "cache.db"
        save_result(db_path, "mod.fn__mutmut_7", "killed", 1, 0.25, last_output="boom")

        results = load_results(db_path)  # fresh connection
        assert len(results) == 1
        assert results[0].mutant_name == "mod.fn__mutmut_7"
        assert results[0].status == "killed"
        assert results[0].last_output == "boom"

        with contextlib.closing(sqlite3.connect(db_path)) as conn:
            persisted = conn.execute(
                "SELECT status, last_output FROM mutant WHERE mutant_name = ?",
                ("mod.fn__mutmut_7",),
            ).fetchall()
        assert persisted == [("killed", "boom")]
