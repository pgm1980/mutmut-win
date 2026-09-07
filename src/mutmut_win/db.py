"""SQLite persistence layer for mutation testing results.

Stores and retrieves mutation results in a schema compatible with mutmut's
cache database.  The default database location is
``.mutmut-cache/mutmut-cache.db`` relative to the current working directory.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import math
import os
import sqlite3
import stat as stat_module
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, NoReturn
from uuid import uuid4

from mutmut_win.exceptions import (
    CorruptCacheError,
    MutmutWinError,
    UnsafeWorkspaceStateError,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

    from mutmut_win.models import MutationResult


class RunStateError(MutmutWinError):
    """Raised when a persisted run transition would be ambiguous or unsafe."""


@dataclass(frozen=True, slots=True)
class RunMutationResult:
    """Immutable snapshot of one result attributed to a particular run.

    The fields intentionally mirror :class:`mutmut_win.models.MutationResult`
    without depending on Pydantic.  ``reused`` records whether the orchestrator
    explicitly reused a historical cache verdict rather than executing the
    mutant in this run.
    """

    mutant_name: str
    status: str
    exit_code: int | None
    duration: float | None
    last_output: str | None
    forensics: dict[str, object] | None
    tests_fingerprint: str | None
    reused: bool
    completed_at: str


@dataclass(frozen=True, slots=True)
class MutationRunState:
    """Immutable view of the newest persisted mutation run."""

    run_id: str
    status: str
    started_at: str
    finished_at: str | None
    planned_names: tuple[str, ...]
    completed_results: tuple[RunMutationResult, ...]
    completed_names: tuple[str, ...]
    pending_names: tuple[str, ...]
    plan_finalized: bool = True
    universe_fingerprint: str | None = None
    plan_digest: str | None = None
    basis_fingerprint: str | None = None
    basis_config_json: str | None = None
    evidence_invalidated: bool = False
    is_full_run: bool = False


class RunBasisIncompleteness(StrEnum):
    """Known reasons why persisted run evidence cannot be release authority."""

    MISSING = "missing"
    GENERIC_TYPE_CHECK_COMMAND = "generic-type-check-command"
    MALFORMED = "malformed"


#: A newly-created run always starts in this state.
RUN_STATUS_RUNNING = "running"

#: Terminal states accepted by :func:`finish_run`.
TERMINAL_RUN_STATUSES: frozenset[str] = frozenset({"completed", "interrupted", "aborted", "failed"})

#: Every mutation status that may legitimately occur in a persisted cache.
#:
#: ``check was interrupted by user`` is retained solely for pre-v2.9 cache
#: compatibility. ``not checked`` is likewise a valid legacy/display row, but
#: neither value is a completed verdict in the modern per-run snapshot.
PERSISTED_MUTATION_STATUSES: frozenset[str] = frozenset(
    {
        "survived",
        "killed",
        "no tests",
        "skipped",
        "suspicious",
        "timeout",
        "caught by type check",
        "killed_by_infinite_loop",
        "segfault",
        "not checked",
        "check was interrupted by user",
    }
)
RUN_RESULT_STATUSES: frozenset[str] = PERSISTED_MUTATION_STATUSES - {
    "not checked",
    "check was interrupted by user",
}

type _PreparedResult = tuple[
    str,
    str,
    int | None,
    float | None,
    str | None,
    str | None,
    str | None,
]

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

# Run-state tables deliberately do not reference ``mutant``.  That table is
# the historical verdict-reuse cache and may be overwritten or purged by a
# later run; a run snapshot must remain truthful after either operation.
_CREATE_RUN_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS mutation_run (
    sequence    INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id      TEXT NOT NULL UNIQUE,
    status      TEXT NOT NULL,
    started_at  TEXT NOT NULL,
    finished_at TEXT,
    plan_finalized INTEGER NOT NULL DEFAULT 0 CHECK (plan_finalized IN (0, 1)),
    universe_fingerprint TEXT,
    plan_digest TEXT,
    basis_fingerprint TEXT,
    basis_config_json TEXT,
    evidence_invalidated INTEGER NOT NULL DEFAULT 0
        CHECK (evidence_invalidated IN (0, 1)),
    is_full_run INTEGER NOT NULL DEFAULT 0 CHECK (is_full_run IN (0, 1)),
    CHECK (status IN ('running', 'completed', 'interrupted', 'aborted', 'failed')),
    CHECK (
        (status = 'running' AND finished_at IS NULL)
        OR (status != 'running' AND finished_at IS NOT NULL)
    ),
    CHECK (
        (basis_fingerprint IS NULL AND basis_config_json IS NULL)
        OR (basis_fingerprint IS NOT NULL AND basis_config_json IS NOT NULL)
    )
)
"""

_CREATE_RUN_MUTANT_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS mutation_run_mutant (
    run_id            TEXT NOT NULL,
    ordinal           INTEGER NOT NULL CHECK (ordinal >= 0),
    mutant_name       TEXT NOT NULL,
    completed         INTEGER NOT NULL DEFAULT 0 CHECK (completed IN (0, 1)),
    reused            INTEGER NOT NULL DEFAULT 0 CHECK (reused IN (0, 1)),
    result_status     TEXT,
    exit_code         INTEGER,
    duration          REAL,
    last_output       TEXT,
    forensics         TEXT,
    tests_fingerprint TEXT,
    completed_at      TEXT,
    PRIMARY KEY (run_id, mutant_name),
    UNIQUE (run_id, ordinal),
    FOREIGN KEY (run_id) REFERENCES mutation_run(run_id) ON DELETE CASCADE,
    CHECK (
        (
            completed = 0
            AND reused = 0
            AND result_status IS NULL
            AND exit_code IS NULL
            AND duration IS NULL
            AND last_output IS NULL
            AND forensics IS NULL
            AND tests_fingerprint IS NULL
            AND completed_at IS NULL
        )
        OR (completed = 1 AND result_status IS NOT NULL AND completed_at IS NOT NULL)
    )
)
"""

# The database, not merely a process-local check, enforces the single-active-
# run boundary.  ``start_run`` also takes BEGIN IMMEDIATE so two processes
# cannot both pass the preflight check.
_CREATE_SINGLE_RUNNING_INDEX_SQL = """
CREATE UNIQUE INDEX IF NOT EXISTS mutation_run_single_running
ON mutation_run(status)
WHERE status = 'running'
"""

#: Migration: add last_output column to existing databases.
_MIGRATE_ADD_LAST_OUTPUT = "ALTER TABLE mutant ADD COLUMN last_output TEXT"

#: Migration: add forensics JSON column for IL-detection evidence (Issue #71).
_MIGRATE_ADD_FORENSICS = "ALTER TABLE mutant ADD COLUMN forensics TEXT"

#: Migration: add the result-reuse fingerprint column (issue #119).
_MIGRATE_ADD_TESTS_FINGERPRINT = "ALTER TABLE mutant ADD COLUMN tests_fingerprint TEXT"

# Existing run tables predate the prepare/plan boundary. Their already
# persisted plans are complete, so the migration default is deliberately 1.
_MIGRATE_ADD_PLAN_FINALIZED = (
    "ALTER TABLE mutation_run ADD COLUMN plan_finalized INTEGER NOT NULL DEFAULT 1"
)
_MIGRATE_ADD_UNIVERSE_FINGERPRINT = "ALTER TABLE mutation_run ADD COLUMN universe_fingerprint TEXT"
_MIGRATE_ADD_PLAN_DIGEST = "ALTER TABLE mutation_run ADD COLUMN plan_digest TEXT"
_MIGRATE_ADD_BASIS_FINGERPRINT = "ALTER TABLE mutation_run ADD COLUMN basis_fingerprint TEXT"
_MIGRATE_ADD_BASIS_CONFIG_JSON = "ALTER TABLE mutation_run ADD COLUMN basis_config_json TEXT"
_MIGRATE_ADD_EVIDENCE_INVALIDATED = (
    "ALTER TABLE mutation_run ADD COLUMN evidence_invalidated "
    "INTEGER NOT NULL DEFAULT 0 CHECK (evidence_invalidated IN (0, 1))"
)
# Existing run rows do not carry proof that their plan covered the configured
# mutation universe.  Migrating them as subsets is the only fail-closed
# default: a new full run must establish export authority explicitly.
_MIGRATE_ADD_IS_FULL_RUN = (
    "ALTER TABLE mutation_run ADD COLUMN is_full_run "
    "INTEGER NOT NULL DEFAULT 0 CHECK (is_full_run IN (0, 1))"
)

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

_MARK_RUN_RESULT_SQL = """
UPDATE mutation_run_mutant
SET completed = 1,
    reused = ?,
    result_status = ?,
    exit_code = ?,
    duration = ?,
    last_output = ?,
    forensics = ?,
    tests_fingerprint = ?,
    completed_at = ?
WHERE run_id = ? AND mutant_name = ? AND completed = 0
"""


def _utc_now() -> str:
    """Return a stable, timezone-aware timestamp for persisted metadata."""
    return datetime.now(tz=UTC).isoformat(timespec="microseconds")


type _FileIdentity = tuple[int, int]

_SQLITE_SIDECAR_SUFFIXES = ("-journal", "-wal", "-shm")


def _absolute_cache_path(path: Path) -> Path:
    """Return a normalized absolute path without resolving redirects."""
    try:
        # ``resolve`` would follow the very parent/leaf redirects this boundary
        # must inspect lexically before any SQLite access.
        return Path(os.path.abspath(os.fspath(path)))  # noqa: PTH100
    except (OSError, RuntimeError, ValueError) as exc:
        raise UnsafeWorkspaceStateError(
            f"Refusing workspace state access: cannot normalize cache database path {path}."
        ) from exc


def _is_reparse_point(metadata: os.stat_result) -> bool:
    attributes = getattr(metadata, "st_file_attributes", 0)
    reparse_flag = getattr(stat_module, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return bool(reparse_flag and attributes & reparse_flag)


def _is_link_like(path: Path, metadata: os.stat_result) -> bool:
    junction_check = getattr(path, "is_junction", None)
    return bool(
        stat_module.S_ISLNK(metadata.st_mode)
        or _is_reparse_point(metadata)
        or (callable(junction_check) and junction_check())
    )


def _unsafe_cache_path(path: Path, detail: str) -> NoReturn:
    raise UnsafeWorkspaceStateError(f"Refusing workspace state access: {path} {detail}.")


def _validate_parent_components(database: Path) -> None:
    """Reject every existing redirected/non-directory parent component."""
    parent = database.parent
    anchor = Path(parent.anchor)
    current = anchor
    parts = parent.parts[1:] if parent.anchor else parent.parts
    for part in parts:
        current /= part
        try:
            metadata = current.lstat()
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise UnsafeWorkspaceStateError(
                f"Refusing workspace state access: cannot inspect cache parent {current}."
            ) from exc
        if _is_link_like(current, metadata):
            _unsafe_cache_path(current, "is a symlink, junction, or reparse point")
        if not stat_module.S_ISDIR(metadata.st_mode):
            _unsafe_cache_path(current, "is not a directory")
        try:
            resolved = current.resolve(strict=True)
            resolved_metadata = resolved.stat()
        except (OSError, RuntimeError) as exc:
            raise UnsafeWorkspaceStateError(
                f"Refusing workspace state access: cannot resolve cache parent {current}."
            ) from exc
        if _file_identity(metadata) != _file_identity(resolved_metadata):
            _unsafe_cache_path(current, f"has redirected identity at {resolved}")


def _inspect_cache_leaf(
    path: Path,
    *,
    label: str,
    ephemeral: bool = False,
) -> os.stat_result | None:
    """Return one safe regular single-link leaf, or ``None`` if absent."""
    for _attempt in range(3):
        try:
            metadata = path.lstat()
        except FileNotFoundError:
            return None
        except OSError as exc:
            raise UnsafeWorkspaceStateError(
                f"Refusing workspace state access: cannot inspect SQLite {label} {path}."
            ) from exc
        if _is_link_like(path, metadata):
            _unsafe_cache_path(path, f"SQLite {label} is a symlink, junction, or reparse point")
        if not stat_module.S_ISREG(metadata.st_mode):
            _unsafe_cache_path(path, f"SQLite {label} is not a regular file")
        if metadata.st_nlink != 1:
            _unsafe_cache_path(path, f"SQLite {label} is a hardlink ({metadata.st_nlink} links)")
        try:
            resolved = path.resolve(strict=True)
            resolved_metadata = resolved.stat()
            current = path.lstat()
        except FileNotFoundError:
            if ephemeral:
                return None
            _unsafe_cache_path(path, f"SQLite {label} disappeared during validation")
        except (OSError, RuntimeError) as exc:
            raise UnsafeWorkspaceStateError(
                f"Refusing workspace state access: cannot resolve SQLite {label} {path}."
            ) from exc
        if _file_identity(current) != _file_identity(metadata) or _file_identity(
            current
        ) != _file_identity(resolved_metadata):
            if ephemeral:
                continue
            _unsafe_cache_path(path, f"SQLite {label} changed during validation")
        return current
    if ephemeral:
        return None
    _unsafe_cache_path(path, f"SQLite {label} changed repeatedly during validation")


def _file_identity(metadata: os.stat_result) -> _FileIdentity:
    return metadata.st_dev, metadata.st_ino


def _validate_database_tree(path: Path) -> _FileIdentity | None:
    absolute = _absolute_cache_path(path)
    _validate_parent_components(absolute)
    database_metadata = _inspect_cache_leaf(absolute, label="database")
    for suffix in _SQLITE_SIDECAR_SUFFIXES:
        _inspect_cache_leaf(
            Path(f"{absolute}{suffix}"),
            label=f"sidecar {suffix}",
            ephemeral=True,
        )
    return _file_identity(database_metadata) if database_metadata is not None else None


def validate_cache_path(path: Path = DEFAULT_DB_PATH) -> None:
    """Reject redirected parents and unsafe DB/sidecar leaves for every path.

    Python's sqlite3 API accepts only a pathname, not a pre-opened verified
    file descriptor.  This validation is therefore repeated around connect
    and before schema/write access below.  It closes deterministic swaps and
    pre-existing redirects, but cannot make an actively hostile same-user
    pathname namespace transactional; an ABA swap entirely between two checks
    remains an operating-system boundary that stdlib sqlite3 cannot eliminate.
    """
    _validate_database_tree(path)


def _prepare_database_file(path: Path) -> tuple[Path, _FileIdentity]:
    """Safely pre-create a missing DB leaf and return its fixed identity."""
    absolute = _absolute_cache_path(path)
    # Validate before mkdir so an already redirected ancestor cannot turn
    # parent creation into an external write. A same-user swap during mkdir is
    # part of the explicitly documented stdlib pathname race above.
    _validate_parent_components(absolute)
    try:
        absolute.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise UnsafeWorkspaceStateError(
            f"Refusing workspace state access: cannot create cache parent {absolute.parent}."
        ) from exc
    _validate_parent_components(absolute)

    existing = _validate_database_tree(absolute)
    if existing is not None:
        return absolute, existing

    flags = (
        os.O_RDWR
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_BINARY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        descriptor = os.open(absolute, flags, 0o600)
    except FileExistsError:
        identity = _validate_database_tree(absolute)
        if identity is None:  # pragma: no cover - immediate concurrent disappearance
            _unsafe_cache_path(absolute, "changed while the database was being prepared")
        return absolute, identity
    except OSError as exc:
        raise UnsafeWorkspaceStateError(
            f"Refusing workspace state access: cannot exclusively create database {absolute}."
        ) from exc

    try:
        handle_metadata = os.fstat(descriptor)
        if not stat_module.S_ISREG(handle_metadata.st_mode) or handle_metadata.st_nlink != 1:
            _unsafe_cache_path(absolute, "new database handle is not a single-link regular file")
        path_metadata = _inspect_cache_leaf(absolute, label="database")
        if path_metadata is None or _file_identity(path_metadata) != _file_identity(
            handle_metadata
        ):
            _unsafe_cache_path(absolute, "changed during exclusive database creation")
        identity = _file_identity(handle_metadata)
    finally:
        os.close(descriptor)

    _verify_database_identity(absolute, identity)
    return absolute, identity


def _verify_database_identity(path: Path, expected: _FileIdentity) -> None:
    current = _validate_database_tree(path)
    if current != expected:
        _unsafe_cache_path(
            _absolute_cache_path(path),
            "changed identity during SQLite access",
        )


def _corrupt_cache(path: Path, detail: str, exc: BaseException | None = None) -> NoReturn:
    message = (
        f"cache database at '{path}' is corrupt or unreadable, or contains invalid persisted data "
        f"({detail}). Delete the .mutmut-cache/ directory (or the configured custom cache "
        "database) or re-run with --force."
    )
    raise CorruptCacheError(message) from exc


def _raise_database_error(path: Path, exc: sqlite3.DatabaseError) -> NoReturn:
    """Classify transient SQLite contention separately from corrupt bytes."""
    error_code = getattr(exc, "sqlite_errorcode", None)
    base_code = error_code & 0xFF if isinstance(error_code, int) else None
    detail = str(exc).casefold()
    if base_code in {sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED} or (
        isinstance(exc, sqlite3.OperationalError)
        and ("database is locked" in detail or "database table is locked" in detail)
    ):
        raise RunStateError(
            f"cache database at '{path}' is busy or locked by another process; "
            "wait for that mutmut-win operation to finish and retry. The cache "
            "is not known to be corrupt and must not be deleted."
        ) from exc
    _corrupt_cache(path, str(exc), exc)


@contextlib.contextmanager
def _verified_connection(
    path: Path,
    *,
    create: bool,
) -> Iterator[tuple[sqlite3.Connection, _FileIdentity, Path]]:
    """Connect by pathname only while repeatedly pinning its observed identity."""
    if create:
        absolute, identity = _prepare_database_file(path)
    else:
        absolute = _absolute_cache_path(path)
        existing_identity = _validate_database_tree(absolute)
        if existing_identity is None:
            _unsafe_cache_path(absolute, "disappeared before SQLite connect")
        identity = existing_identity
    _verify_database_identity(absolute, identity)
    try:
        connection = sqlite3.connect(absolute)
    except sqlite3.DatabaseError as exc:
        _raise_database_error(absolute, exc)
    try:
        # sqlite3 may open/read the file in connect(). Revalidate immediately,
        # then callers revalidate once more directly before schema/write SQL.
        _verify_database_identity(absolute, identity)
        yield connection, identity, absolute
    except sqlite3.DatabaseError as exc:
        _raise_database_error(absolute, exc)
    else:
        # A read may have completed against the still-open inode after the
        # pathname was permanently replaced.  Validate on every successful
        # context exit so callers cannot return that detached snapshot as
        # current workspace authority.  This narrows, but cannot eliminate,
        # same-user pathname ABA between two identity observations.
        _verify_database_identity(absolute, identity)
    finally:
        connection.close()


@contextlib.contextmanager
def _write_transaction(path: Path) -> Iterator[sqlite3.Connection]:
    """Open one close-safe, rollback-safe immediate write transaction."""
    with _verified_connection(path, create=True) as (conn, identity, absolute):
        conn.execute("PRAGMA foreign_keys = ON")
        _verify_database_identity(absolute, identity)
        conn.execute("BEGIN IMMEDIATE")
        _verify_database_identity(absolute, identity)
        try:
            yield conn
        except BaseException:
            conn.rollback()
            raise
        else:
            _verify_database_identity(absolute, identity)
            conn.commit()
            _verify_database_identity(absolute, identity)


def _active_run_id(conn: sqlite3.Connection) -> str | None:
    """Return the sole active run ID, failing closed on corrupt ambiguity."""
    rows = conn.execute(
        "SELECT run_id FROM mutation_run WHERE status = ? ORDER BY sequence DESC LIMIT 2",
        (RUN_STATUS_RUNNING,),
    ).fetchall()
    if len(rows) > 1:
        raise RunStateError("database contains more than one running mutation run")
    return str(rows[0][0]) if rows else None


def _require_active_run(conn: sqlite3.Connection, run_id: str) -> None:
    """Require *run_id* to be the database's one active run."""
    active_run_id = _active_run_id(conn)
    if active_run_id is None:
        raise RunStateError("no mutation run is currently running")
    if active_run_id != run_id:
        raise RunStateError(
            f"run ID mismatch: active run is {active_run_id!r}, received {run_id!r}"
        )


def _prepare_result(
    mutant_name: str,
    status: str,
    exit_code: int | None,
    duration: float | None,
    last_output: str | None,
    forensics: dict[str, object] | None,
    tests_fingerprint: str | None,
) -> _PreparedResult:
    """Normalise one result for both cache and run-snapshot persistence."""
    if not isinstance(status, str) or not status:
        raise ValueError("mutation result status must be a non-empty string")
    if status not in PERSISTED_MUTATION_STATUSES:
        raise ValueError(f"unknown mutation result status: {status!r}")
    if last_output is not None:
        # Issue #100 / A3-FD-011: a lone surrogate (undecodable bytes that
        # slipped through as \udcXX/\udXXX) raises UnicodeEncodeError inside
        # sqlite. Diagnostics may be lossy, results may not.
        last_output = last_output.encode("utf-8", errors="replace").decode("utf-8")
    return (
        mutant_name,
        status,
        exit_code,
        duration,
        last_output,
        json.dumps(forensics) if forensics is not None else None,
        tests_fingerprint,
    )


def _mark_planned_result(
    conn: sqlite3.Connection,
    run_id: str,
    result: _PreparedResult,
    *,
    reused: bool,
    require_planned: bool,
) -> bool:
    """Snapshot one result, optionally rejecting unplanned mutant names."""
    mutant_name, status, exit_code, duration, last_output, forensics, fingerprint = result
    if status not in RUN_RESULT_STATUSES:
        raise RunStateError(
            f"status {status!r} is not a completed verdict for active run {run_id!r}"
        )
    planned_row = conn.execute(
        "SELECT completed FROM mutation_run_mutant WHERE run_id = ? AND mutant_name = ?",
        (run_id, mutant_name),
    ).fetchone()
    if planned_row is None:
        if require_planned:
            raise RunStateError(f"mutant {mutant_name!r} was not planned for active run {run_id!r}")
        return False
    if bool(planned_row[0]):
        raise RunStateError(f"mutant {mutant_name!r} is already complete in active run {run_id!r}")

    cursor = conn.execute(
        _MARK_RUN_RESULT_SQL,
        (
            int(reused),
            status,
            exit_code,
            duration,
            last_output,
            forensics,
            fingerprint,
            _utc_now(),
            run_id,
            mutant_name,
        ),
    )
    if cursor.rowcount != 1:
        raise RunStateError(
            f"could not atomically complete mutant {mutant_name!r} in run {run_id!r}"
        )
    return True


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

    Raises:
        CorruptCacheError: if the file exists but is not a valid SQLite
            database (external QA CACHE-001); recover with ``run --force``.
    """
    with _verified_connection(path, create=True) as (conn, identity, absolute):
        conn.execute("PRAGMA foreign_keys = ON")
        # This is the first schema/write boundary. The exclusive pre-created
        # leaf and all sidecars must still name the exact verified namespace.
        _verify_database_identity(absolute, identity)
        conn.execute(_CREATE_TABLE_SQL)
        # Migrate existing databases from older schemas.
        columns = {row[1] for row in conn.execute("PRAGMA table_info(mutant)").fetchall()}
        if "last_output" not in columns:
            _add_column_if_missing(conn, _MIGRATE_ADD_LAST_OUTPUT)
        if "forensics" not in columns:
            _add_column_if_missing(conn, _MIGRATE_ADD_FORENSICS)
        if "tests_fingerprint" not in columns:
            _add_column_if_missing(conn, _MIGRATE_ADD_TESTS_FINGERPRINT)
        # Run identity is additive: old cache rows remain untouched and
        # readable, while every upgraded database gains an independent
        # per-run truth layer.
        conn.execute(_CREATE_RUN_TABLE_SQL)
        run_columns = {row[1] for row in conn.execute("PRAGMA table_info(mutation_run)").fetchall()}
        if "plan_finalized" not in run_columns:
            _add_column_if_missing(conn, _MIGRATE_ADD_PLAN_FINALIZED)
        if "universe_fingerprint" not in run_columns:
            _add_column_if_missing(conn, _MIGRATE_ADD_UNIVERSE_FINGERPRINT)
        if "plan_digest" not in run_columns:
            _add_column_if_missing(conn, _MIGRATE_ADD_PLAN_DIGEST)
        if "basis_fingerprint" not in run_columns:
            _add_column_if_missing(conn, _MIGRATE_ADD_BASIS_FINGERPRINT)
        if "basis_config_json" not in run_columns:
            _add_column_if_missing(conn, _MIGRATE_ADD_BASIS_CONFIG_JSON)
        if "evidence_invalidated" not in run_columns:
            _add_column_if_missing(conn, _MIGRATE_ADD_EVIDENCE_INVALIDATED)
        if "is_full_run" not in run_columns:
            _add_column_if_missing(conn, _MIGRATE_ADD_IS_FULL_RUN)
        conn.execute(_CREATE_RUN_MUTANT_TABLE_SQL)
        conn.execute(_CREATE_SINGLE_RUNNING_INDEX_SQL)
        _verify_database_identity(absolute, identity)
        conn.commit()
        _verify_database_identity(absolute, identity)


def _validated_plan(planned_names: Iterable[str]) -> tuple[str, ...]:
    """Materialize and validate a unique ordered mutation plan."""
    planned = tuple(planned_names)
    seen: set[str] = set()
    for name in planned:
        if not isinstance(name, str) or not name:
            raise ValueError("planned mutant names must be non-empty strings")
        if name in seen:
            raise ValueError(f"duplicate planned mutant name: {name!r}")
        seen.add(name)
    return planned


def _ordered_plan_digest(planned_names: Iterable[str]) -> str:
    """Hash the complete ordered plan independently of generation metadata."""
    payload = json.dumps(tuple(planned_names), ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _validated_run_basis(
    basis_fingerprint: str | None,
    basis_config_json: str | None,
) -> tuple[str | None, str | None]:
    """Require an all-or-nothing, canonical run-evidence basis payload."""
    if (basis_fingerprint is None) != (basis_config_json is None):
        raise ValueError("run basis fingerprint and config must be supplied together")
    if basis_fingerprint is None:
        return None, None
    if basis_config_json is None:  # pragma: no cover - narrowed by the pair check above
        raise ValueError("run basis fingerprint and config must be supplied together")
    if len(basis_fingerprint) != 64 or any(
        char not in "0123456789abcdef" for char in basis_fingerprint
    ):
        raise ValueError("run basis fingerprint must be a lowercase SHA-256 hex digest")
    try:
        parsed_config = json.loads(basis_config_json)
    except json.JSONDecodeError as exc:
        raise ValueError("run basis config must be valid JSON") from exc
    if not isinstance(parsed_config, dict):
        raise ValueError("run basis config must be a JSON object")
    canonical_config = json.dumps(parsed_config, sort_keys=True, separators=(",", ":"))
    if canonical_config != basis_config_json:
        raise ValueError("run basis config must use canonical JSON encoding")
    from pydantic import ValidationError

    from mutmut_win.config import MutmutConfig

    try:
        validated_config = MutmutConfig.model_validate(parsed_config)
    except ValidationError as exc:
        raise ValueError("run basis config is not a valid MutmutConfig") from exc
    complete_config = json.dumps(
        validated_config.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
    )
    if complete_config != basis_config_json:
        raise ValueError("run basis config must contain the complete effective MutmutConfig")
    return basis_fingerprint, complete_config


def known_run_basis_incompleteness(
    current_run: MutationRunState,
) -> RunBasisIncompleteness | None:
    """Return a known fail-closed reason for non-authoritative run evidence.

    Modern incomplete runs persist neither basis field. Older releases could
    persist an apparently complete pair for a generic ``type_check_command``
    even though that argv can reach undeclared executables, scripts, plugins,
    or configuration. Revalidate the complete canonical payload here so direct
    or future callers cannot turn malformed stored data into a positive display
    claim. The database loader normally rejects that corruption earlier; the
    ``MALFORMED`` result is deliberate defence in depth for presentation code.
    """

    fingerprint = current_run.basis_fingerprint
    config_json = current_run.basis_config_json
    if fingerprint is None and config_json is None:
        return RunBasisIncompleteness.MISSING
    if fingerprint is None or config_json is None:
        return RunBasisIncompleteness.MALFORMED

    try:
        _validated_fingerprint, validated_config_json = _validated_run_basis(
            fingerprint,
            config_json,
        )
        if validated_config_json is None:  # pragma: no cover - pair checked above
            return RunBasisIncompleteness.MALFORMED

        from mutmut_win.config import MutmutConfig

        config = MutmutConfig.model_validate_json(validated_config_json)
    # Presentation authority must fail closed for every ordinary parser or
    # validation failure, including backend-specific exceptions.
    except Exception:
        return RunBasisIncompleteness.MALFORMED

    if config.type_check_command:
        return RunBasisIncompleteness.GENERIC_TYPE_CHECK_COMMAND
    return None


def begin_run(
    path: Path,
    *,
    basis_fingerprint: str | None = None,
    basis_config_json: str | None = None,
    is_full_run: bool = False,
) -> str:
    """Persist a running attempt before staging or generation can mutate state."""
    basis_fingerprint, basis_config_json = _validated_run_basis(
        basis_fingerprint,
        basis_config_json,
    )
    create_db(path)
    with _write_transaction(path) as conn:
        active_run_id = _active_run_id(conn)
        if active_run_id is not None:
            raise RunStateError(f"mutation run {active_run_id!r} is already running")
        run_id = str(uuid4())
        conn.execute(
            """
            INSERT INTO mutation_run
                (run_id, status, started_at, basis_fingerprint, basis_config_json, is_full_run)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                RUN_STATUS_RUNNING,
                _utc_now(),
                basis_fingerprint,
                basis_config_json,
                int(is_full_run),
            ),
        )
    return run_id


def set_run_plan(
    path: Path,
    run_id: str,
    planned_names: Iterable[str],
    *,
    generation_fingerprint: str | None = None,
) -> None:
    """Atomically attach the one exact plan to a preparing run."""
    planned = _validated_plan(planned_names)
    payload = json.dumps(
        {
            "generation_fingerprint": generation_fingerprint,
            "planned_names": planned,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    universe_fingerprint = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    plan_digest = _ordered_plan_digest(planned)

    create_db(path)
    with _write_transaction(path) as conn:
        _require_active_run(conn, run_id)
        row = conn.execute(
            "SELECT plan_finalized FROM mutation_run WHERE run_id = ?", (run_id,)
        ).fetchone()
        if row is None or bool(row[0]):
            raise RunStateError(f"mutation run {run_id!r} already has a finalized plan")
        conn.executemany(
            "INSERT INTO mutation_run_mutant (run_id, ordinal, mutant_name) VALUES (?, ?, ?)",
            ((run_id, ordinal, name) for ordinal, name in enumerate(planned)),
        )
        cursor = conn.execute(
            """
            UPDATE mutation_run
            SET plan_finalized = 1, universe_fingerprint = ?, plan_digest = ?
            WHERE run_id = ? AND status = ? AND plan_finalized = 0
            """,
            (universe_fingerprint, plan_digest, run_id, RUN_STATUS_RUNNING),
        )
        if cursor.rowcount != 1:
            raise RunStateError(f"could not atomically finalize plan for run {run_id!r}")


def start_run(
    path: Path,
    planned_names: Iterable[str],
    *,
    basis_fingerprint: str | None = None,
    basis_config_json: str | None = None,
    is_full_run: bool = False,
) -> str:
    """Atomically persist a new running mutation plan and return its UUID.

    Only one run may be active per database.  A prior crashed run therefore
    remains visible as ``running``/pending and blocks a new run until the
    caller explicitly finishes it.  Duplicate or empty names are rejected so
    completion cardinality cannot become ambiguous.

    Args:
        path: Filesystem path to the SQLite database file.
        planned_names: Complete mutant-name plan for this run, in display
            order. An empty plan is valid.

    Returns:
        UUID4 string identifying the new run.

    Raises:
        ValueError: if a planned name is invalid or duplicated.
        RunStateError: if another run is already active.
    """
    planned = _validated_plan(planned_names)
    basis_fingerprint, basis_config_json = _validated_run_basis(
        basis_fingerprint,
        basis_config_json,
    )

    create_db(path)
    with _write_transaction(path) as conn:
        active_run_id = _active_run_id(conn)
        if active_run_id is not None:
            raise RunStateError(f"mutation run {active_run_id!r} is already running")

        run_id = str(uuid4())
        conn.execute(
            """
            INSERT INTO mutation_run
                (run_id, status, started_at, plan_finalized, universe_fingerprint,
                 plan_digest, basis_fingerprint, basis_config_json, is_full_run)
            VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                RUN_STATUS_RUNNING,
                _utc_now(),
                hashlib.sha256(
                    json.dumps(planned, separators=(",", ":")).encode("utf-8")
                ).hexdigest(),
                _ordered_plan_digest(planned),
                basis_fingerprint,
                basis_config_json,
                int(is_full_run),
            ),
        )
        conn.executemany(
            "INSERT INTO mutation_run_mutant (run_id, ordinal, mutant_name) VALUES (?, ?, ?)",
            ((run_id, ordinal, name) for ordinal, name in enumerate(planned)),
        )
    return run_id


def mark_reused_results(
    path: Path,
    run_id: str,
    results: Iterable[MutationResult],
) -> None:
    """Atomically attribute explicitly reused cache verdicts to an active run.

    This is intentionally separate from :func:`load_results`: loading history
    never makes it current.  Every supplied result must be planned, incomplete
    and belong to exactly the active ``run_id``; otherwise none are marked.

    Args:
        path: Filesystem path to the SQLite database file.
        run_id: ID returned by :func:`start_run`.
        results: Historical ``MutationResult`` objects the orchestrator has
            independently determined are safe to reuse.

    Raises:
        ValueError: if a duplicate result name is supplied.
        RunStateError: if the run ID or any planned/completion invariant does
            not match.
    """
    prepared: list[_PreparedResult] = []
    seen: set[str] = set()
    for result in results:
        if result.mutant_name in seen:
            raise ValueError(f"duplicate reused mutant name: {result.mutant_name!r}")
        seen.add(result.mutant_name)
        prepared.append(
            _prepare_result(
                result.mutant_name,
                result.status,
                result.exit_code,
                result.duration,
                result.last_output,
                result.forensics,
                result.tests_fingerprint,
            )
        )

    create_db(path)
    with _write_transaction(path) as conn:
        _require_active_run(conn, run_id)
        for prepared_result in prepared:
            _mark_planned_result(
                conn,
                run_id,
                prepared_result,
                reused=True,
                require_planned=True,
            )


def finish_run(path: Path, run_id: str, status: str) -> None:
    """Atomically transition the active run to a validated terminal state.

    ``completed`` is accepted only when no planned mutant remains pending.
    The other terminal statuses preserve pending names as explicit unchecked
    work. Re-finishing, finishing a stale ID, or finishing while another ID is
    active fails closed.

    Args:
        path: Filesystem path to the SQLite database file.
        run_id: ID returned by :func:`start_run`.
        status: One of :data:`TERMINAL_RUN_STATUSES`.

    Raises:
        ValueError: if *status* is not a valid terminal status.
        RunStateError: if the active run does not match, or ``completed`` has
            pending mutants.
    """
    if status not in TERMINAL_RUN_STATUSES:
        valid = ", ".join(sorted(TERMINAL_RUN_STATUSES))
        raise ValueError(f"invalid terminal run status {status!r}; expected one of: {valid}")

    create_db(path)
    with _write_transaction(path) as conn:
        _require_active_run(conn, run_id)
        if status == "completed":
            finalized = conn.execute(
                """
                SELECT plan_finalized, universe_fingerprint, plan_digest
                FROM mutation_run
                WHERE run_id = ?
                """,
                (run_id,),
            ).fetchone()
            if finalized is None or not bool(finalized[0]):
                raise RunStateError(f"run {run_id!r} has no finalized mutation plan")
            if finalized[1] is None or finalized[2] is None:
                raise RunStateError(f"run {run_id!r} has no verifiable mutation-plan fingerprint")
            plan_rows = conn.execute(
                """
                SELECT ordinal, mutant_name
                FROM mutation_run_mutant
                WHERE run_id = ?
                ORDER BY ordinal
                """,
                (run_id,),
            ).fetchall()
            if any(
                not isinstance(ordinal, int)
                or isinstance(ordinal, bool)
                or ordinal != expected
                or not isinstance(mutant_name, str)
                or not mutant_name
                for expected, (ordinal, mutant_name) in enumerate(plan_rows)
            ):
                raise RunStateError(f"run {run_id!r} has a corrupt ordered mutation plan")
            stored_plan_digest = finalized[2]
            if (
                not isinstance(stored_plan_digest, str)
                or _ordered_plan_digest(row[1] for row in plan_rows) != stored_plan_digest
            ):
                raise RunStateError(f"run {run_id!r} mutation plan no longer matches its digest")
            pending = conn.execute(
                "SELECT COUNT(*) FROM mutation_run_mutant WHERE run_id = ? AND completed = 0",
                (run_id,),
            ).fetchone()
            if pending is None or int(pending[0]) != 0:
                pending_count = int(pending[0]) if pending is not None else -1
                raise RunStateError(f"run {run_id!r} still has {pending_count} pending mutant(s)")

        cursor = conn.execute(
            """
            UPDATE mutation_run
            SET status = ?, finished_at = ?
            WHERE run_id = ? AND status = ?
            """,
            (status, _utc_now(), run_id, RUN_STATUS_RUNNING),
        )
        if cursor.rowcount != 1:
            raise RunStateError(f"could not atomically finish active run {run_id!r}")


def invalidate_latest_run_evidence(path: Path = DEFAULT_DB_PATH) -> bool:
    """Mark the newest run snapshot unusable after source mutation.

    Applying a mutant changes the source tree after the latest run measured
    it.  When a run snapshot exists, historical result rows remain useful for
    diagnostics while the additive invalidation flag prevents them from
    authorizing a CI/CD export.  A legacy database has no run snapshot to
    carry that flag, so its unscoped result rows are deleted instead.  That
    conservative fallback prevents the legacy export path from resurrecting
    pre-apply evidence.

    Returns:
        ``True`` when a run existed and is now marked invalidated, otherwise
        ``False``.  A missing database is left missing.
    """
    validate_cache_path(path)
    if not path.exists():
        return False

    create_db(path)
    with _write_transaction(path) as conn:
        latest = conn.execute(
            "SELECT run_id FROM mutation_run ORDER BY sequence DESC LIMIT 1"
        ).fetchone()
        if latest is None:
            # Pre-run-identity databases fall back to ``mutant`` rows for
            # display and CI/CD export.  There is no durable snapshot metadata
            # on which to record invalidation, so retaining those rows would
            # let an export after ``apply`` report the pre-change tree as
            # green.  Purging only this legacy authority keeps modern run
            # snapshots and their diagnostic cache untouched.
            conn.execute("DELETE FROM mutant")
            return False
        conn.execute(
            "UPDATE mutation_run SET evidence_invalidated = 1 WHERE run_id = ?",
            (latest[0],),
        )
    return True


def _required_text(path: Path, value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        _corrupt_cache(path, f"{label} must be a non-empty string")
    return value


def _stored_result_status(
    path: Path,
    value: object,
    label: str,
    *,
    allow_legacy_incomplete: bool,
) -> str:
    """Validate one persisted mutation verdict at the SQLite trust boundary."""
    status = _required_text(path, value, label)
    allowed = PERSISTED_MUTATION_STATUSES if allow_legacy_incomplete else RUN_RESULT_STATUSES
    if status not in allowed:
        _corrupt_cache(path, f"{label} has unknown persisted mutation status {status!r}")
    return status


def _optional_text(path: Path, value: object, label: str) -> str | None:
    if value is None:
        return None
    return _required_text(path, value, label)


def _stored_flag(path: Path, value: object, label: str) -> bool:
    if type(value) is not int or value not in {0, 1}:
        _corrupt_cache(path, f"{label} must be stored as 0 or 1")
    return bool(value)


def _stored_positive_integer(path: Path, value: object, label: str) -> int:
    if type(value) is not int or value <= 0:
        _corrupt_cache(path, f"{label} must be a positive integer")
    return value


def _stored_nonnegative_integer(path: Path, value: object, label: str) -> int:
    if type(value) is not int or value < 0:
        _corrupt_cache(path, f"{label} must be a non-negative integer")
    return value


def _optional_exit_code(path: Path, value: object, label: str) -> int | None:
    if value is None:
        return None
    if type(value) is not int:
        _corrupt_cache(path, f"{label} must be an integer or null")
    return value


def _optional_duration(path: Path, value: object, label: str) -> float | None:
    if value is None:
        return None
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        _corrupt_cache(path, f"{label} must be a finite non-negative number or null")
    duration = float(value)
    if not math.isfinite(duration) or duration < 0:
        _corrupt_cache(path, f"{label} must be a finite non-negative number or null")
    return duration


def _stored_timestamp(path: Path, value: object, label: str) -> str:
    text = _required_text(path, value, label)
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        _corrupt_cache(path, f"{label} is not an ISO-8601 timestamp", exc)
    if parsed.tzinfo is None:
        _corrupt_cache(path, f"{label} must include a timezone")
    return text


def _stored_digest(path: Path, value: object, label: str) -> str | None:
    if value is None:
        return None
    digest = _required_text(path, value, label)
    if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
        _corrupt_cache(path, f"{label} is not a lowercase SHA-256 digest")
    return digest


def _stored_forensics(
    path: Path,
    value: object,
    label: str,
) -> dict[str, object] | None:
    if value is None:
        return None
    raw = _required_text(path, value, label)
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        _corrupt_cache(path, f"{label} is not valid JSON", exc)
    if not isinstance(parsed, dict):
        _corrupt_cache(path, f"{label} must decode to a JSON object")
    return parsed


def load_current_run(path: Path = DEFAULT_DB_PATH) -> MutationRunState | None:
    """Load the newest run and only the results explicitly attributed to it.

    The historical ``mutant`` table is never consulted.  Consequently a
    planned mutant with only an old cache verdict remains pending until
    :func:`mark_reused_results` or :func:`save_result`/:func:`save_results`
    explicitly completes it for this run.

    Args:
        path: Filesystem path to the SQLite database file.

    Returns:
        Immutable current-run state, or ``None`` for no persisted run.
    """
    validate_cache_path(path)
    if not path.exists():
        return None
    create_db(path)

    with _verified_connection(path, create=False) as (conn, identity, absolute):
        # One read transaction keeps the run header and its plan/results on
        # the same SQLite snapshot while workers stream completions.
        _verify_database_identity(absolute, identity)
        conn.execute("BEGIN")
        run_row = conn.execute(
            """
            SELECT sequence, run_id, status, started_at, finished_at,
                   plan_finalized, universe_fingerprint, plan_digest,
                   basis_fingerprint, basis_config_json, evidence_invalidated,
                   is_full_run
            FROM mutation_run
            ORDER BY sequence DESC
            LIMIT 1
            """
        ).fetchone()
        high_water_row = conn.execute(
            "SELECT seq FROM sqlite_sequence WHERE name = 'mutation_run'"
        ).fetchone()
        orphan_row = conn.execute(
            """
            SELECT 1
            FROM mutation_run_mutant AS planned
            LEFT JOIN mutation_run AS run ON run.run_id = planned.run_id
            WHERE run.run_id IS NULL
            LIMIT 1
            """
        ).fetchone()
        plan_rows: list[tuple[object, ...]] = []
        if run_row is not None:
            plan_rows = conn.execute(
                """
                SELECT ordinal, mutant_name, completed, reused, result_status, exit_code,
                       duration, last_output, forensics, tests_fingerprint, completed_at
                FROM mutation_run_mutant
                WHERE run_id = ?
                ORDER BY ordinal
                """,
                (run_row[1],),
            ).fetchall()
        _verify_database_identity(absolute, identity)

    # Parsing is deliberately outside the connection lifetime, but the
    # pathname must still identify the file whose snapshot was read.
    _verify_database_identity(absolute, identity)
    if orphan_row is not None:
        _corrupt_cache(path, "mutation plan contains rows without a matching run header")
    if run_row is None:
        if high_water_row is not None:
            high_water = _stored_positive_integer(
                path,
                high_water_row[0],
                "mutation_run sequence high-water mark",
            )
            _corrupt_cache(
                path,
                f"mutation run headers were removed below sequence high-water mark {high_water}",
            )
        _verify_database_identity(absolute, identity)
        return None

    latest_sequence = _stored_positive_integer(path, run_row[0], "latest run sequence")
    if high_water_row is None:
        _corrupt_cache(path, "mutation_run sequence high-water mark is missing")
    high_water = _stored_positive_integer(
        path,
        high_water_row[0],
        "mutation_run sequence high-water mark",
    )
    if latest_sequence != high_water:
        _corrupt_cache(
            path,
            f"latest run sequence {latest_sequence} disagrees with high-water mark {high_water}",
        )

    run_id = _required_text(path, run_row[1], "run_id")
    run_status = _required_text(path, run_row[2], "run status")
    if run_status not in {RUN_STATUS_RUNNING, *TERMINAL_RUN_STATUSES}:
        _corrupt_cache(path, f"unknown run status {run_status!r}")
    started_at = _stored_timestamp(path, run_row[3], "run started_at")
    finished_at = (
        None if run_row[4] is None else _stored_timestamp(path, run_row[4], "run finished_at")
    )
    if (run_status == RUN_STATUS_RUNNING) != (finished_at is None):
        _corrupt_cache(path, "run status and finished_at disagree")
    plan_finalized = _stored_flag(path, run_row[5], "plan_finalized")
    universe_fingerprint = _stored_digest(path, run_row[6], "universe_fingerprint")
    plan_digest = _stored_digest(path, run_row[7], "plan_digest")
    basis_fingerprint = _stored_digest(path, run_row[8], "basis_fingerprint")
    basis_config_json = _optional_text(path, run_row[9], "basis_config_json")
    try:
        basis_fingerprint, basis_config_json = _validated_run_basis(
            basis_fingerprint,
            basis_config_json,
        )
    except (TypeError, ValueError) as exc:
        _corrupt_cache(path, f"invalid run basis: {exc}", exc)
    evidence_invalidated = _stored_flag(path, run_row[10], "evidence_invalidated")
    is_full_run = _stored_flag(path, run_row[11], "is_full_run")

    planned_names: list[str] = []
    planned_name_set: set[str] = set()
    completed_names: list[str] = []
    pending_names: list[str] = []
    completed_results: list[RunMutationResult] = []
    for expected_ordinal, row in enumerate(plan_rows):
        ordinal = _stored_nonnegative_integer(path, row[0], "stored plan ordinal")
        if ordinal != expected_ordinal:
            _corrupt_cache(
                path,
                f"stored plan ordinal {ordinal} does not match expected {expected_ordinal}",
            )
        mutant_name = _required_text(path, row[1], "planned mutant name")
        if mutant_name in planned_name_set:
            _corrupt_cache(path, f"duplicate planned mutant name {mutant_name!r}")
        planned_names.append(mutant_name)
        planned_name_set.add(mutant_name)
        completed = _stored_flag(path, row[2], f"completed flag for {mutant_name!r}")
        reused = _stored_flag(path, row[3], f"reused flag for {mutant_name!r}")
        if not completed:
            if reused or any(value is not None for value in row[4:]):
                _corrupt_cache(
                    path,
                    f"pending mutant {mutant_name!r} contains completed-result data",
                )
            pending_names.append(mutant_name)
            continue

        status = _stored_result_status(
            path,
            row[4],
            f"result status for {mutant_name!r}",
            allow_legacy_incomplete=False,
        )
        exit_code = _optional_exit_code(path, row[5], f"exit_code for {mutant_name!r}")
        duration = _optional_duration(path, row[6], f"duration for {mutant_name!r}")
        if row[7] is not None and not isinstance(row[7], str):
            _corrupt_cache(path, f"last_output for {mutant_name!r} must be text or null")
        last_output = row[7]
        forensics = _stored_forensics(path, row[8], f"forensics for {mutant_name!r}")
        tests_fingerprint = _optional_text(
            path,
            row[9],
            f"tests_fingerprint for {mutant_name!r}",
        )
        completed_at = _stored_timestamp(
            path,
            row[10],
            f"completed_at for {mutant_name!r}",
        )
        completed_names.append(mutant_name)
        completed_results.append(
            RunMutationResult(
                mutant_name=mutant_name,
                status=status,
                exit_code=exit_code,
                duration=duration,
                last_output=last_output,
                forensics=forensics,
                tests_fingerprint=tests_fingerprint,
                reused=reused,
                completed_at=completed_at,
            )
        )

    loaded_plan = tuple(planned_names)
    if run_status == "completed":
        if not plan_finalized:
            _corrupt_cache(path, "a completed run must have a finalized mutation plan")
        if pending_names:
            _corrupt_cache(path, "a completed run contains pending mutants")
    if not plan_finalized:
        if planned_names:
            _corrupt_cache(path, "an unfinalized run contains planned mutants")
        if universe_fingerprint is not None or plan_digest is not None:
            _corrupt_cache(path, "an unfinalized run contains finalized-plan fingerprints")
    elif plan_digest is not None and _ordered_plan_digest(loaded_plan) != plan_digest:
        _corrupt_cache(path, "ordered mutation plan does not match its persisted digest")

    current = MutationRunState(
        run_id=run_id,
        status=run_status,
        started_at=started_at,
        finished_at=finished_at,
        planned_names=loaded_plan,
        completed_results=tuple(completed_results),
        completed_names=tuple(completed_names),
        pending_names=tuple(pending_names),
        plan_finalized=plan_finalized,
        universe_fingerprint=universe_fingerprint,
        plan_digest=plan_digest,
        basis_fingerprint=basis_fingerprint,
        basis_config_json=basis_config_json,
        evidence_invalidated=evidence_invalidated,
        is_full_run=is_full_run,
    )
    # Close the permanent post-read replacement window. A same-user attacker
    # can still perform a complete ABA between identity checks without native
    # handle-relative SQLite opens; ordinary permanent swaps fail closed.
    _verify_database_identity(absolute, identity)
    return current


def load_latest_run_results(
    path: Path = DEFAULT_DB_PATH,
) -> tuple[MutationRunState | None, list[MutationResult]]:
    """Load the newest run's exact population, or legacy history as fallback.

    Once a run snapshot exists, the mutable historical ``mutant`` cache is no
    longer a display authority. Completed rows are reconstructed from the
    immutable run snapshot and every still-planned name is represented as
    ``not checked``. Old databases with no run records retain their historical
    display behaviour.
    """
    from pydantic import ValidationError

    from mutmut_win.models import MutationResult

    current = load_current_run(path)
    if current is None:
        return None, load_results(path)

    completed_by_name = {result.mutant_name: result for result in current.completed_results}
    results: list[MutationResult] = []
    try:
        for mutant_name in current.planned_names:
            completed = completed_by_name.get(mutant_name)
            if completed is None:
                results.append(MutationResult(mutant_name=mutant_name, status="not checked"))
                continue
            results.append(
                MutationResult(
                    mutant_name=completed.mutant_name,
                    status=completed.status,
                    exit_code=completed.exit_code,
                    duration=completed.duration,
                    last_output=completed.last_output,
                    forensics=completed.forensics,
                    tests_fingerprint=completed.tests_fingerprint,
                )
            )
    except (TypeError, ValueError, ValidationError) as exc:
        _corrupt_cache(path, f"current run result failed validation: {exc}", exc)
    return current, results


def save_result(
    path: Path,
    mutant_name: str,
    status: str,
    exit_code: int | None,
    duration: float | None,
    last_output: str | None = None,
    forensics: dict[str, object] | None = None,
    tests_fingerprint: str | None = None,
    *,
    require_planned: bool = False,
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
        require_planned=require_planned,
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
    *,
    require_planned: bool = False,
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
    prepared: list[_PreparedResult] = []
    for mutant_name, status, exit_code, duration, last_output, forensics, fingerprint in rows:
        prepared.append(
            _prepare_result(
                mutant_name,
                status,
                exit_code,
                duration,
                last_output,
                forensics,
                fingerprint,
            )
        )
    if not prepared:
        return
    create_db(path)
    with _write_transaction(path) as conn:
        active_run_id = _active_run_id(conn)
        if require_planned and active_run_id is None:
            raise RunStateError("cannot persist a required planned result without an active run")
        if active_run_id is not None and require_planned:
            for result in prepared:
                _mark_planned_result(
                    conn,
                    active_run_id,
                    result,
                    reused=False,
                    require_planned=True,
                )
        conn.executemany(_UPSERT_SQL, prepared)
        if active_run_id is not None and not require_planned:
            for result in prepared:
                _mark_planned_result(
                    conn,
                    active_run_id,
                    result,
                    reused=False,
                    require_planned=False,
                )


def invalidate_cached_reuse_for_run(path: Path, run_id: str) -> int:
    """Remove reuse capability from every historical row touched by *run_id*.

    Worker verdicts stream into both the immutable run snapshot and the
    historical ``mutant`` cache before the final staging/live-basis checks.
    If the run later fails, retaining their test fingerprints would let the
    next run reuse results whose execution basis was never authorized.
    Display history is preserved; only the capability-bearing fingerprint is
    cleared.

    Returns:
        Number of historical rows whose reuse fingerprint was invalidated.
    """

    create_db(path)
    with _write_transaction(path) as conn:
        known = conn.execute(
            "SELECT 1 FROM mutation_run WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        if known is None:
            raise RunStateError(f"cannot invalidate reuse for unknown run {run_id!r}")
        cursor = conn.execute(
            """
            UPDATE mutant
            SET tests_fingerprint = NULL
            WHERE tests_fingerprint IS NOT NULL
              AND mutant_name IN (
                  SELECT mutant_name
                  FROM mutation_run_mutant
                  WHERE run_id = ?
              )
            """,
            (run_id,),
        )
        return max(0, cursor.rowcount)


def deauthorize_active_run_evidence(path: Path, run_id: str) -> int:
    """Atomically preserve diagnostics while revoking every evidence capability.

    Used when the project core stayed stable but the ambient interpreter,
    dependency or environment basis changed during a completed run.  The
    result rows remain visible, while the run basis, export authority and both
    current-run and historical verdict-reuse fingerprints are removed in one
    transaction.  Requiring the exact active run prevents a stale caller from
    deauthorizing a newer attempt.

    Returns:
        Number of historical cache rows whose reuse fingerprint was cleared.
    """

    create_db(path)
    with _write_transaction(path) as conn:
        _require_active_run(conn, run_id)
        conn.execute(
            """
            UPDATE mutation_run
            SET basis_fingerprint = NULL,
                basis_config_json = NULL,
                evidence_invalidated = 1
            WHERE run_id = ? AND status = ?
            """,
            (run_id, RUN_STATUS_RUNNING),
        )
        conn.execute(
            """
            UPDATE mutation_run_mutant
            SET tests_fingerprint = NULL
            WHERE run_id = ? AND tests_fingerprint IS NOT NULL
            """,
            (run_id,),
        )
        cursor = conn.execute(
            """
            UPDATE mutant
            SET tests_fingerprint = NULL
            WHERE tests_fingerprint IS NOT NULL
              AND mutant_name IN (
                  SELECT mutant_name
                  FROM mutation_run_mutant
                  WHERE run_id = ?
              )
            """,
            (run_id,),
        )
        return max(0, cursor.rowcount)


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
    validate_cache_path(path)
    if not path.exists():
        return 0

    with _write_transaction(path) as conn:
        rows = conn.execute("SELECT mutant_name FROM mutant").fetchall()
        persisted_names = {_required_text(path, row[0], "legacy mutant name") for row in rows}
        orphans = sorted(persisted_names - valid_names)
        conn.executemany(
            "DELETE FROM mutant WHERE mutant_name = ?",
            [(name,) for name in orphans],
        )
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
    from pydantic import ValidationError

    from mutmut_win.models import MutationResult

    validate_cache_path(path)
    if not path.exists():
        return []
    create_db(path)  # idempotent; migrates old schemas on the READ path

    with _verified_connection(path, create=False) as (conn, identity, absolute):
        _verify_database_identity(absolute, identity)
        cursor = conn.execute(_SELECT_ALL_SQL)
        rows = cursor.fetchall()

    out: list[MutationResult] = []
    try:
        for row in rows:
            mutant_name = _required_text(path, row[0], "legacy mutant name")
            status = _stored_result_status(
                path,
                row[1],
                f"status for {mutant_name!r}",
                allow_legacy_incomplete=True,
            )
            exit_code = _optional_exit_code(path, row[2], f"exit_code for {mutant_name!r}")
            duration = _optional_duration(path, row[3], f"duration for {mutant_name!r}")
            if row[4] is not None and not isinstance(row[4], str):
                _corrupt_cache(path, f"last_output for {mutant_name!r} must be text or null")
            forensics = _stored_forensics(path, row[5], f"forensics for {mutant_name!r}")
            tests_fingerprint = _optional_text(
                path,
                row[6],
                f"tests_fingerprint for {mutant_name!r}",
            )
            out.append(
                MutationResult(
                    mutant_name=mutant_name,
                    status=status,
                    exit_code=exit_code,
                    duration=duration,
                    last_output=row[4],
                    forensics=forensics,
                    tests_fingerprint=tests_fingerprint,
                )
            )
    except (TypeError, ValueError, ValidationError) as exc:
        _corrupt_cache(path, f"legacy result failed validation: {exc}", exc)
    return out
