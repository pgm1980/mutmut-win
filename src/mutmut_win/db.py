"""SQLite persistence layer for mutation testing results.

Stores and retrieves mutation results in a schema compatible with mutmut's
cache database.  The default database location is
``.mutmut-cache/mutmut-cache.db`` relative to the current working directory.
"""

from __future__ import annotations

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
    last_output TEXT
)
"""

#: Migration: add last_output column to existing databases.
_MIGRATE_ADD_LAST_OUTPUT = (
    "ALTER TABLE mutant ADD COLUMN last_output TEXT"
)

#: INSERT-or-replace statement used by save_result.
_UPSERT_SQL = """
INSERT OR REPLACE INTO mutant (mutant_name, status, exit_code, duration, last_output)
VALUES (?, ?, ?, ?, ?)
"""

#: SELECT statement for load_results.
_SELECT_ALL_SQL = "SELECT mutant_name, status, exit_code, duration, last_output FROM mutant"


def create_db(path: Path = DEFAULT_DB_PATH) -> None:
    """Create the SQLite database and schema if they do not exist.

    Parent directories are created automatically.  Existing databases
    from older versions are migrated (``last_output`` column added).

    Args:
        path: Filesystem path to the SQLite database file.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.execute(_CREATE_TABLE_SQL)
        # Migrate existing databases: add last_output if missing.
        columns = {row[1] for row in conn.execute("PRAGMA table_info(mutant)").fetchall()}
        if "last_output" not in columns:
            conn.execute(_MIGRATE_ADD_LAST_OUTPUT)
        conn.commit()


def save_result(
    path: Path,
    mutant_name: str,
    status: str,
    exit_code: int | None,
    duration: float | None,
    last_output: str | None = None,
) -> None:
    """Persist a single mutation result (upsert semantics).

    Creates the database schema automatically if it does not yet exist.

    Args:
        path: Filesystem path to the SQLite database file.
        mutant_name: Unique mutant identifier.
        status: Mutation status string (e.g. ``"killed"``, ``"survived"``).
        exit_code: Pytest exit code, or ``None`` if not available.
        duration: Test execution time in seconds, or ``None`` if not measured.
        last_output: Last pytest output lines (captured on timeout/suspicious).
    """
    create_db(path)
    with sqlite3.connect(path) as conn:
        conn.execute(_UPSERT_SQL, (mutant_name, status, exit_code, duration, last_output))
        conn.commit()


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

    return [
        MutationResult(
            mutant_name=row[0],
            status=row[1],
            exit_code=row[2],
            duration=row[3],
            last_output=row[4] if len(row) > 4 else None,
        )
        for row in rows
    ]
