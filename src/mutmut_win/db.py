"""SQLite persistence layer for mutation testing results.

Stores and retrieves mutation results in a schema compatible with mutmut's
cache database.  The default database location is
``.mutmut-cache/mutmut-cache.db`` relative to the current working directory.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
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
    forensics   TEXT
)
"""

#: Migration: add last_output column to existing databases.
_MIGRATE_ADD_LAST_OUTPUT = "ALTER TABLE mutant ADD COLUMN last_output TEXT"

#: Migration: add forensics JSON column for IL-detection evidence (Issue #71).
_MIGRATE_ADD_FORENSICS = "ALTER TABLE mutant ADD COLUMN forensics TEXT"

#: INSERT-or-replace statement used by save_result.
_UPSERT_SQL = """
INSERT OR REPLACE INTO mutant
    (mutant_name, status, exit_code, duration, last_output, forensics)
VALUES (?, ?, ?, ?, ?, ?)
"""

#: SELECT statement for load_results.
_SELECT_ALL_SQL = (
    "SELECT mutant_name, status, exit_code, duration, last_output, forensics "
    "FROM mutant"
)


def create_db(path: Path = DEFAULT_DB_PATH) -> None:
    """Create the SQLite database and schema if they do not exist.

    Parent directories are created automatically.  Existing databases
    from older versions are migrated (``last_output`` and ``forensics``
    columns added).

    Args:
        path: Filesystem path to the SQLite database file.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.execute(_CREATE_TABLE_SQL)
        # Migrate existing databases from older schemas.
        columns = {row[1] for row in conn.execute("PRAGMA table_info(mutant)").fetchall()}
        if "last_output" not in columns:
            conn.execute(_MIGRATE_ADD_LAST_OUTPUT)
        if "forensics" not in columns:
            conn.execute(_MIGRATE_ADD_FORENSICS)
        conn.commit()


def save_result(
    path: Path,
    mutant_name: str,
    status: str,
    exit_code: int | None,
    duration: float | None,
    last_output: str | None = None,
    forensics: dict[str, object] | None = None,
) -> None:
    """Persist a single mutation result (upsert semantics).

    Creates the database schema automatically if it does not yet exist.

    Args:
        path: Filesystem path to the SQLite database file.
        mutant_name: Unique mutant identifier.
        status: Mutation status string (e.g. ``"killed"``, ``"survived"``,
            ``"killed_by_infinite_loop"``).
        exit_code: Pytest exit code, or ``None`` if not available.
        duration: Test execution time in seconds, or ``None`` if not measured.
        last_output: Last pytest output lines (captured on timeout/suspicious).
        forensics: Optional IL-detection forensic snapshot, serialised as JSON.
    """
    create_db(path)
    forensics_json = json.dumps(forensics) if forensics is not None else None
    with sqlite3.connect(path) as conn:
        conn.execute(
            _UPSERT_SQL,
            (mutant_name, status, exit_code, duration, last_output, forensics_json),
        )
        conn.commit()


def delete_results_not_in(path: Path, valid_names: set[str]) -> int:
    """Delete rows whose mutant is not in *valid_names* (issue #96).

    Stale rows of mutants that no longer exist (renamed/edited sources)
    used to survive forever, so ``results`` reported the union of all runs
    ever (A3-OS-012).  Called by the orchestrator on FULL runs only — a
    subset run knows just a slice of the valid set and must never purge.

    The orphan set is computed in Python (DB names minus *valid_names*) and
    deleted in chunks of ``IN (...)`` — a ``NOT IN`` per chunk would be
    semantically wrong, and SQLite caps bound parameters.

    Args:
        path: Filesystem path to the SQLite database file.
        valid_names: The complete set of currently generated mutant names.

    Returns:
        Number of deleted rows.
    """
    if not path.exists():
        return 0

    with sqlite3.connect(path) as conn:
        rows = conn.execute("SELECT mutant_name FROM mutant").fetchall()
        orphans = sorted({row[0] for row in rows} - valid_names)
        chunk_size = 500  # comfortably below SQLite's bound-parameter limit
        for i in range(0, len(orphans), chunk_size):
            chunk = orphans[i : i + chunk_size]
            placeholders = ",".join("?" * len(chunk))
            conn.execute(
                f"DELETE FROM mutant WHERE mutant_name IN ({placeholders})",  # noqa: S608 — placeholders are generated '?', values are bound
                chunk,
            )
        conn.commit()
    return len(orphans)


def load_results(path: Path = DEFAULT_DB_PATH) -> list[MutationResult]:
    """Load all mutation results from the database.

    Returns an empty list if the database does not exist.

    Args:
        path: Filesystem path to the SQLite database file.

    Returns:
        List of ``MutationResult`` instances, one per persisted mutant.
    """
    from mutmut_win.models import MutationResult

    if not path.exists():
        return []

    with sqlite3.connect(path) as conn:
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
            )
        )
    return out
