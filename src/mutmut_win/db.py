"""SQLite persistence layer for mutation testing results.

Stores and retrieves mutation results in a schema compatible with mutmut's
cache database.  The default database location is
``.mutmut-cache/mutmut-cache.db`` relative to the current working directory.
"""

from __future__ import annotations

import contextlib
import json
import sqlite3
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

    from mutmut_win.models import MutationResult

#: Default path to the SQLite database file.
DEFAULT_DB_PATH: Path = Path(".mutmut-cache") / "mutmut-cache.db"

#: DDL statement for the results table.
_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS mutant (
    mutant_name TEXT PRIMARY KEY,
    status      TEXT NOT NULL,
    exit_code   INTEGER,
    duration    REAL,
    last_output TEXT,
    forensics   TEXT,
    tests_fingerprint TEXT
)
"""

#: Migration: add last_output column to existing databases.
_MIGRATE_ADD_LAST_OUTPUT = "ALTER TABLE mutant ADD COLUMN last_output TEXT"

#: Migration: add forensics JSON column for IL-detection evidence (Issue #71).
_MIGRATE_ADD_FORENSICS = "ALTER TABLE mutant ADD COLUMN forensics TEXT"

#: Migration: add the result-reuse fingerprint column (issue #119).
_MIGRATE_ADD_TESTS_FINGERPRINT = "ALTER TABLE mutant ADD COLUMN tests_fingerprint TEXT"

#: INSERT-or-replace statement used by save_result.
_UPSERT_SQL = """
INSERT OR REPLACE INTO mutant
    (mutant_name, status, exit_code, duration, last_output, forensics, tests_fingerprint)
VALUES (?, ?, ?, ?, ?, ?, ?)
"""

#: SELECT statement for load_results.
_SELECT_ALL_SQL = (
    "SELECT mutant_name, status, exit_code, duration, last_output, forensics, "
    "tests_fingerprint FROM mutant"
)


def _add_column_if_missing(conn: sqlite3.Connection, ddl: str) -> None:
    """Run an ``ALTER TABLE ... ADD COLUMN`` tolerating a concurrent winner.

    A parallel migrator may add the column between our PRAGMA check and our
    ALTER (issue #100 / A3-FD-007 — the interleaving was confirmed live);
    "duplicate column" is then success, not failure.

    Args:
        conn: Open connection.
        ddl: The ``ALTER TABLE`` statement.
    """
    try:
        conn.execute(ddl)
    except sqlite3.OperationalError as exc:
        if "duplicate column" not in str(exc).lower():
            raise


def create_db(path: Path = DEFAULT_DB_PATH) -> None:
    """Create the SQLite database and schema if they do not exist.

    Parent directories are created automatically.  Existing databases
    from older versions are migrated (``last_output`` and ``forensics``
    columns added); migrations tolerate concurrent runners.

    Args:
        path: Filesystem path to the SQLite database file.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with contextlib.closing(sqlite3.connect(path)) as conn:
        conn.execute(_CREATE_TABLE_SQL)
        # Migrate existing databases from older schemas.
        columns = {row[1] for row in conn.execute("PRAGMA table_info(mutant)").fetchall()}
        if "last_output" not in columns:
            _add_column_if_missing(conn, _MIGRATE_ADD_LAST_OUTPUT)
        if "forensics" not in columns:
            _add_column_if_missing(conn, _MIGRATE_ADD_FORENSICS)
        if "tests_fingerprint" not in columns:
            _add_column_if_missing(conn, _MIGRATE_ADD_TESTS_FINGERPRINT)
        conn.commit()


def save_result(
    path: Path,
    mutant_name: str,
    status: str,
    exit_code: int | None,
    duration: float | None,
    last_output: str | None = None,
    forensics: dict[str, object] | None = None,
    tests_fingerprint: str | None = None,
) -> None:
    """Persist a single mutation result (upsert semantics).

    Creates the database schema automatically if it does not yet exist.
    Thin wrapper over :func:`save_results` — the streaming event loop writes
    one verdict at a time; mass paths pass their whole batch instead
    (issue #132 / 360°-C1).

    Args:
        path: Filesystem path to the SQLite database file.
        mutant_name: Unique mutant identifier.
        status: Mutation status string (e.g. ``"killed"``, ``"survived"``,
            ``"killed_by_infinite_loop"``).
        exit_code: Pytest exit code, or ``None`` if not available.
        duration: Test execution time in seconds, or ``None`` if not measured.
        last_output: Last pytest output lines (captured on timeout/suspicious).
        forensics: Optional IL-detection forensic snapshot, serialised as JSON.
        tests_fingerprint: Fingerprint of the test basis behind this verdict
            (issue #119 result reuse); ``None`` for never-reused verdicts.
    """
    save_results(
        path,
        [
            (
                mutant_name,
                status,
                exit_code,
                duration,
                last_output,
                forensics,
                tests_fingerprint,
            )
        ],
    )


def save_results(
    path: Path,
    rows: Iterable[
        tuple[
            str,
            str,
            int | None,
            float | None,
            str | None,
            dict[str, object] | None,
            str | None,
        ]
    ],
) -> None:
    """Persist many mutation results over ONE connection (issue #132 / C1).

    The mass paths (skipped exclusions, no-test verdicts, type-check kills)
    used to open connect+create+commit per mutant — thousands of redundant
    file operations per run. Row layout matches :func:`save_result`'s
    parameters: ``(mutant_name, status, exit_code, duration, last_output,
    forensics, tests_fingerprint)``.

    Args:
        path: Filesystem path to the SQLite database file.
        rows: Result tuples; ``forensics`` is serialised to JSON here.
    """
    prepared: list[
        tuple[str, str, int | None, float | None, str | None, str | None, str | None]
    ] = []
    for mutant_name, status, exit_code, duration, last_output, forensics, fingerprint in rows:
        if last_output is not None:
            # Issue #100 / A3-FD-011: a lone surrogate (undecodable bytes that
            # slipped through as \udcXX/\udXXX) raised UnicodeEncodeError inside
            # the driver and LOST the upsert. Diagnostics may be lossy, results
            # may not.
            last_output = last_output.encode("utf-8", errors="replace").decode("utf-8")
        prepared.append(
            (
                mutant_name,
                status,
                exit_code,
                duration,
                last_output,
                json.dumps(forensics) if forensics is not None else None,
                fingerprint,
            )
        )
    if not prepared:
        return
    create_db(path)
    with contextlib.closing(sqlite3.connect(path)) as conn:
        conn.executemany(_UPSERT_SQL, prepared)
        conn.commit()


def delete_results_not_in(path: Path, valid_names: set[str]) -> int:
    """Delete rows whose mutant is not in *valid_names* (issue #96).

    Stale rows of mutants that no longer exist (renamed/edited sources)
    used to survive forever, so ``results`` reported the union of all runs
    ever (A3-OS-012).  Called by the orchestrator on FULL runs only — a
    subset run knows just a slice of the valid set and must never purge.

    The orphan set is computed in Python (DB names minus *valid_names*) and
    deleted via ``executemany`` with a fixed one-parameter statement — no
    dynamic SQL, no SQLite bound-parameter limit, one transaction.

    Args:
        path: Filesystem path to the SQLite database file.
        valid_names: The complete set of currently generated mutant names.

    Returns:
        Number of deleted rows.
    """
    if not path.exists():
        return 0

    with contextlib.closing(sqlite3.connect(path)) as conn:
        rows = conn.execute("SELECT mutant_name FROM mutant").fetchall()
        orphans = sorted({row[0] for row in rows} - valid_names)
        conn.executemany(
            "DELETE FROM mutant WHERE mutant_name = ?",
            [(name,) for name in orphans],
        )
        conn.commit()
    return len(orphans)


def load_results(path: Path = DEFAULT_DB_PATH) -> list[MutationResult]:
    """Load all mutation results from the database.

    Returns an empty list if the database does not exist. Existing caches
    from older versions are migrated first (issue #100 / A3-FD-001: the
    SELECT names columns that only ``create_db`` adds — pre-v2.5 caches
    raised OperationalError in every reader after an upgrade).

    Args:
        path: Filesystem path to the SQLite database file.

    Returns:
        List of ``MutationResult`` instances, one per persisted mutant.
    """
    from mutmut_win.models import MutationResult

    if not path.exists():
        return []
    create_db(path)  # idempotent; migrates old schemas on the READ path

    with contextlib.closing(sqlite3.connect(path)) as conn:
        cursor = conn.execute(_SELECT_ALL_SQL)
        rows = cursor.fetchall()

    out: list[MutationResult] = []
    for row in rows:
        forensics_raw = row[5] if len(row) > 5 else None
        forensics: dict[str, object] | None = None
        if forensics_raw:
            try:
                parsed = json.loads(forensics_raw)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, dict):
                forensics = parsed
        out.append(
            MutationResult(
                mutant_name=row[0],
                status=row[1],
                exit_code=row[2],
                duration=row[3],
                last_output=row[4] if len(row) > 4 else None,
                forensics=forensics,
                tests_fingerprint=row[6] if len(row) > 6 else None,
            )
        )
    return out
