"""Tests for DB hardening (Issue #100, audit A3-FD-001/006/007/011).

Pre-v2.5 caches crashed every reader after an upgrade (the SELECT names
columns that only ``create_db`` adds — and the read path never ran it);
connections were never closed (``with sqlite3.connect`` only commits), so
an exception could hold the handle and lock the file (WinError 32, observed
live); parallel migrations raced into "duplicate column"; and a lone
surrogate crashed ``save_result``, losing the upsert.
"""

from __future__ import annotations

import sqlite3
import threading
from typing import TYPE_CHECKING

from mutmut_win.db import (
    create_db,
    delete_results_not_in,
    load_results,
    save_result,
)

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def _make_pre_v25_db(path: Path) -> None:
    """Create a cache the way mutmut-win < v2.5 did: no last_output, no forensics."""
    with sqlite3.connect(path) as conn:
        conn.execute(
            "CREATE TABLE mutant ("
            "mutant_name TEXT PRIMARY KEY, status TEXT NOT NULL, "
            "exit_code INTEGER, duration REAL)"
        )
        conn.execute(
            "INSERT INTO mutant VALUES (?, ?, ?, ?)",
            ("pkg.mod.x_f__mutmut_1", "survived", 0, 0.5),
        )
        conn.commit()


class TestReadPathMigration:
    def test_pre_v25_cache_is_readable_after_upgrade(self, tmp_path: Path) -> None:
        # A3-FD-001 (double-verified): load_results selected the forensics
        # column without ever migrating on the READ path — every pre-v2.5
        # cache raised OperationalError in results/browse/export.
        db = tmp_path / "old-cache.db"
        _make_pre_v25_db(db)

        rows = load_results(db)

        assert len(rows) == 1
        assert rows[0].mutant_name == "pkg.mod.x_f__mutmut_1"
        assert rows[0].status == "survived"
        assert rows[0].last_output is None
        assert rows[0].forensics is None

    def test_purge_works_on_a_pre_v25_cache(self, tmp_path: Path) -> None:
        db = tmp_path / "old-cache.db"
        _make_pre_v25_db(db)
        deleted = delete_results_not_in(db, set())
        assert deleted == 1


class TestConnectionsAreClosed:
    def test_every_connect_is_paired_with_a_close(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # A3-FD-006 (double-verified, WinError 32 observed live): `with
        # sqlite3.connect(...)` only commits — it does NOT close. An
        # exception anywhere kept the handle alive and locked the file.
        opened: list[object] = []
        closed: list[object] = []
        real_connect = sqlite3.connect

        class _TrackingConnection:
            """Proxy — sqlite3.Connection attributes are read-only C slots."""

            def __init__(self, conn: sqlite3.Connection) -> None:
                self._conn = conn

            def close(self) -> None:
                closed.append(self)
                self._conn.close()

            def __getattr__(self, name: str) -> object:
                return getattr(self._conn, name)

            def __enter__(self) -> _TrackingConnection:
                self._conn.__enter__()
                return self

            def __exit__(self, *args: object) -> bool:
                return bool(self._conn.__exit__(*args))

        def tracking_connect(*args: object, **kwargs: object) -> _TrackingConnection:
            proxy = _TrackingConnection(real_connect(*args, **kwargs))  # type: ignore[arg-type]
            opened.append(proxy)
            return proxy

        monkeypatch.setattr(sqlite3, "connect", tracking_connect)

        db = tmp_path / "cache.db"
        create_db(db)
        save_result(db, "m1", "killed", 1, 0.1)
        load_results(db)
        delete_results_not_in(db, {"m1"})

        assert opened, "sanity: the tracking wrapper must have been used"
        assert len(closed) == len(opened), (
            f"{len(opened) - len(closed)} connection(s) were never closed"
        )


class TestMigrationRace:
    def test_parallel_create_db_never_raises(self, tmp_path: Path) -> None:
        # A3-FD-007: the PRAGMA-check + ALTER pair raced between processes
        # ("duplicate column" OperationalError, interleaving confirmed).
        db = tmp_path / "cache.db"
        errors: list[Exception] = []

        def worker() -> None:
            try:
                for _ in range(5):
                    create_db(db)
            except Exception as exc:  # pragma: no cover - the failure path
                errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"parallel create_db raised: {errors[0]!r}"

    def test_duplicate_column_is_tolerated(self, tmp_path: Path) -> None:
        # Direct pin for the tolerance: a concurrent migrator may have added
        # the column between our PRAGMA check and our ALTER.
        from mutmut_win.db import _add_column_if_missing

        db = tmp_path / "cache.db"
        create_db(db)
        with sqlite3.connect(db) as conn:
            # Second ALTER for an existing column must not raise.
            _add_column_if_missing(conn, "ALTER TABLE mutant ADD COLUMN forensics TEXT")
            _add_column_if_missing(conn, "ALTER TABLE mutant ADD COLUMN forensics TEXT")


class TestSurrogateSafety:
    def test_lone_surrogate_does_not_lose_the_upsert(self, tmp_path: Path) -> None:
        # A3-FD-011: a lone surrogate in last_output raised
        # UnicodeEncodeError inside save_result — the row was lost.
        db = tmp_path / "cache.db"
        create_db(db)

        save_result(db, "m1", "suspicious", 35, 0.1, last_output="boom \ud800 tail")

        [row] = load_results(db)
        assert row.mutant_name == "m1"
        assert row.last_output is not None
        assert "boom" in row.last_output
        assert "tail" in row.last_output
