"""Cross-platform exclusive lock for one mutmut-win run per workspace.

The stable ``*.guard`` file carries the operating-system lock.  The requested
lock path contains an atomically replaced JSON owner record and is removed on a
clean release.  Keeping the guard inode stable avoids the unlink/recreate race
that makes existence-only lock files unsafe: two contenders can never lock two
different inodes bearing the same pathname.

Crash recovery is deliberately conservative.  A contender may replace an
``acquired`` owner record only after PID plus process-start-time inspection
proves that the recorded process identity is gone.  Corrupt or uninspectable
metadata is never guessed stale.
"""

from __future__ import annotations

import contextlib
import errno
import hashlib
import json
import logging
import math
import os
import socket
import stat as stat_module
import sys
import tempfile
import time
import uuid
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, Self

import psutil  # type: ignore[import-untyped,unused-ignore]

from mutmut_win.atomic_file import UnsafeAtomicWriteError, atomic_write_bytes
from mutmut_win.exceptions import MutmutWinError

if TYPE_CHECKING:
    from types import TracebackType

logger = logging.getLogger(__name__)

_LOCK_SCHEMA_VERSION = 1
_MAX_OWNER_BYTES = 16 * 1024
_START_TIME_TOLERANCE_SECONDS = 0.01
#: Windows may report a byte-range lock as busy for a few scheduler ticks even
#: after ``wait()`` confirms the owning process was terminated.  Retry only
#: after PID/start-time proof says the recorded identity is dead; live or
#: ambiguous owners still fail immediately.
_STALE_GUARD_RETRY_SECONDS = 0.5
_STALE_GUARD_RETRY_INTERVAL_SECONDS = 0.02


def run_lock_path_for_db(db_path: Path) -> Path:
    """Return the one lock domain for the current mutation workspace.

    ``db_path`` remains part of the public API for compatibility, but a
    database is not the complete mutation boundary: every run in a workspace
    also writes the shared ``mutants`` staging tree.  Keying the lock by the
    database path would therefore let two runs with different (or hardlink-
    aliased) custom databases mutate the same staging tree concurrently.

    Bind the lock to the canonical current workspace instead.  The lock lives
    directly in that workspace so destructive cache cleanup cannot remove it.
    Workspace canonicalisation is strict and fails closed when the current
    directory cannot be resolved.
    """
    _ = db_path
    try:
        workspace = Path.cwd().resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise RunLockError("cannot canonicalize current mutation workspace") from exc
    if not workspace.is_dir():
        raise RunLockError(f"current mutation workspace is not a directory: {workspace}")
    digest = hashlib.sha256(str(workspace).casefold().encode("utf-8")).hexdigest()[:16]
    return workspace / f".mutmut-win-{digest}.run.lock"


class RunLockError(MutmutWinError):
    """Base class for workspace run-lock failures."""


class RunLockHeldError(RunLockError):
    """Another process currently owns the workspace run lock."""

    def __init__(self, path: Path, owner: RunLockOwner | None) -> None:
        self.path = path
        self.owner = owner
        detail = owner.describe() if owner is not None else "owner metadata unavailable"
        super().__init__(f"workspace run lock is held at {path}: {detail}")


class RunLockCorruptError(RunLockError):
    """Owner metadata is corrupt, so automatic stale takeover is unsafe."""


class RunLockUnverifiableError(RunLockError):
    """The recorded owner cannot be proven alive or dead safely."""

    def __init__(self, path: Path, owner: RunLockOwner) -> None:
        self.path = path
        self.owner = owner
        super().__init__(
            f"cannot verify whether the workspace run-lock owner is dead at {path}: "
            f"{owner.describe()}"
        )


@dataclass(frozen=True)
class RunLockOwner:
    """Serializable identity and diagnostics for one lock owner."""

    version: int
    state: Literal["acquired", "released"]
    pid: int
    process_start_time: float
    acquired_at: str
    hostname: str
    token: str

    def describe(self) -> str:
        """Return stable human-readable PID/start-time diagnostics."""
        try:
            started = datetime.fromtimestamp(self.process_start_time, tz=UTC).isoformat()
        except (
            OSError,
            OverflowError,
            ValueError,
        ):
            started = f"unix:{self.process_start_time:.6f}"
        return (
            f"PID {self.pid}, process started {started}, "
            f"lock acquired {self.acquired_at}, host {self.hostname}"
        )


class _OwnerStatus(Enum):
    ACTIVE = "active"
    DEAD = "dead"
    UNKNOWN = "unknown"


def _guard_path_for(lock_path: Path) -> Path:
    return lock_path.with_name(f"{lock_path.name}.guard")


def _file_identity(file_stat: os.stat_result) -> tuple[int, int]:
    """Return the stable filesystem identity used for anti-swap checks."""
    return file_stat.st_dev, file_stat.st_ino


def _is_reparse_point(file_stat: os.stat_result) -> bool:
    """Detect Windows reparse leaves without following them."""
    attributes = getattr(file_stat, "st_file_attributes", 0)
    reparse_flag = getattr(stat_module, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return bool(reparse_flag and attributes & reparse_flag)


def _validate_leaf_stat(path: Path, file_stat: os.stat_result, *, label: str) -> None:
    """Require one ordinary, single-link file at a canonical leaf path."""
    unsafe_reason: str | None = None
    if _is_reparse_point(file_stat) or stat_module.S_ISLNK(file_stat.st_mode):
        unsafe_reason = "is a symlink, junction, or reparse point"
    elif not stat_module.S_ISREG(file_stat.st_mode):
        unsafe_reason = "is not a regular file"
    elif file_stat.st_nlink > 1:
        unsafe_reason = f"has {file_stat.st_nlink} hard links"

    # Do not resolve a leaf already proven to be a reparse point, non-file, or
    # hardlink.  Resolving it would reintroduce the exact leaf-following
    # boundary this validation exists to prevent.
    if unsafe_reason is not None:
        raise RunLockCorruptError(f"unsafe workspace run-lock {label} at {path}: {unsafe_reason}")

    try:
        resolved = path.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise RunLockCorruptError(
            f"unsafe workspace run-lock {label} at {path}: cannot resolve leaf"
        ) from exc
    if resolved != path:
        raise RunLockCorruptError(
            f"unsafe workspace run-lock {label} at {path}: "
            f"resolves to {resolved} instead of its canonical leaf"
        )


def _checked_leaf_lstat(
    path: Path,
    *,
    label: str,
    allow_missing: bool,
) -> os.stat_result | None:
    """Inspect a lock leaf without following it and validate its type."""
    try:
        file_stat = path.lstat()
    except FileNotFoundError:
        if allow_missing:
            try:
                resolved = path.resolve(strict=False)
            except (OSError, RuntimeError) as exc:
                raise RunLockCorruptError(
                    f"unsafe workspace run-lock {label} at {path}: cannot resolve leaf"
                ) from exc
            if resolved != path:
                raise RunLockCorruptError(
                    f"unsafe workspace run-lock {label} at {path}: "
                    f"resolves to {resolved} instead of its canonical leaf"
                ) from None
            return None
        raise
    except OSError as exc:
        raise RunLockCorruptError(
            f"unsafe workspace run-lock {label} at {path}: cannot inspect leaf"
        ) from exc

    _validate_leaf_stat(path, file_stat, label=label)
    return file_stat


def _verify_open_leaf(fd: int, path: Path, *, label: str) -> os.stat_result:
    """Verify an opened handle still names the checked single-link leaf."""
    try:
        handle_stat = os.fstat(fd)
    except OSError as exc:
        raise RunLockCorruptError(
            f"unsafe workspace run-lock {label} at {path}: cannot inspect open handle"
        ) from exc
    if not stat_module.S_ISREG(handle_stat.st_mode) or handle_stat.st_nlink > 1:
        raise RunLockCorruptError(
            f"unsafe workspace run-lock {label} at {path}: "
            "open handle is not a single-link regular file"
        )

    path_stat = _checked_leaf_lstat(path, label=label, allow_missing=False)
    if path_stat is None or _file_identity(handle_stat) != _file_identity(path_stat):
        raise RunLockCorruptError(
            f"unsafe workspace run-lock {label} at {path}: leaf changed during open"
        )
    return handle_stat


def _nofollow_flag() -> int:
    """Use kernel no-follow semantics where the platform exposes them."""
    return getattr(os, "O_NOFOLLOW", 0) if os.name == "posix" else 0


def _open_guard(path: Path) -> int:
    _checked_leaf_lstat(path, label="guard", allow_missing=True)
    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_BINARY", 0) | _nofollow_flag()
    try:
        fd = os.open(path, flags, 0o600)
    except OSError as exc:
        raise RunLockCorruptError(
            f"unsafe workspace run-lock guard at {path}: cannot open leaf safely"
        ) from exc
    try:
        handle_stat = _verify_open_leaf(fd, path, label="guard")
        if handle_stat.st_size == 0:
            # ``msvcrt.locking`` needs a concrete byte range.  Identity and
            # link-count checks happen before this first write so an attacker-
            # controlled leaf can never receive the initial byte.
            os.lseek(fd, 0, os.SEEK_SET)
            os.write(fd, b"\0")
            os.fsync(fd)
        return fd
    except BaseException:
        os.close(fd)
        raise


def _try_lock_guard(fd: int) -> bool:
    os.lseek(fd, 0, os.SEEK_SET)
    if sys.platform == "win32":
        import msvcrt

        try:
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            if exc.errno in {errno.EACCES, errno.EAGAIN, errno.EDEADLK}:
                return False
            raise
        return True

    import fcntl

    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        if exc.errno in {errno.EACCES, errno.EAGAIN}:
            return False
        raise
    return True


def _unlock_guard(fd: int) -> None:
    os.lseek(fd, 0, os.SEEK_SET)
    if sys.platform == "win32":
        import msvcrt

        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        return

    import fcntl

    fcntl.flock(fd, fcntl.LOCK_UN)


def _owner_from_json(raw: bytes, path: Path) -> RunLockOwner:
    try:
        payload: Any = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RunLockCorruptError(
            f"workspace run-lock metadata at {path} is not valid UTF-8 JSON; "
            "automatic takeover refused"
        ) from exc

    if not isinstance(payload, dict):
        raise RunLockCorruptError(
            f"workspace run-lock metadata at {path} is not a JSON object; "
            "automatic takeover refused"
        )

    expected = {
        "version",
        "state",
        "pid",
        "process_start_time",
        "acquired_at",
        "hostname",
        "token",
    }
    if set(payload) != expected:
        raise RunLockCorruptError(
            f"workspace run-lock metadata at {path} has unexpected fields; "
            "automatic takeover refused"
        )

    version = payload["version"]
    state = payload["state"]
    pid = payload["pid"]
    process_start_time = payload["process_start_time"]
    acquired_at = payload["acquired_at"]
    hostname = payload["hostname"]
    token = payload["token"]
    valid = (
        type(version) is int
        and version == _LOCK_SCHEMA_VERSION
        and isinstance(state, str)
        and state in {"acquired", "released"}
        and type(pid) is int
        and pid > 0
        and type(process_start_time) in {int, float}
        and math.isfinite(float(process_start_time))
        and float(process_start_time) > 0
        and isinstance(acquired_at, str)
        and bool(acquired_at)
        and isinstance(hostname, str)
        and bool(hostname)
        and isinstance(token, str)
        and bool(token)
    )
    if not valid:
        raise RunLockCorruptError(
            f"workspace run-lock metadata at {path} has invalid values; automatic takeover refused"
        )

    return RunLockOwner(
        version=version,
        state=state,
        pid=pid,
        process_start_time=float(process_start_time),
        acquired_at=acquired_at,
        hostname=hostname,
        token=token,
    )


def _read_owner(path: Path) -> RunLockOwner | None:
    existing = _checked_leaf_lstat(path, label="owner metadata", allow_missing=True)
    if existing is None:
        return None

    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | _nofollow_flag()
    try:
        fd = os.open(path, flags)
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise RunLockCorruptError(
            f"workspace run-lock metadata at {path} cannot be read; automatic takeover refused"
        ) from exc
    try:
        _verify_open_leaf(fd, path, label="owner metadata")
        chunks: list[bytes] = []
        remaining = _MAX_OWNER_BYTES + 1
        while remaining > 0:
            chunk = os.read(fd, remaining)
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        raw = b"".join(chunks)
    except OSError as exc:
        raise RunLockCorruptError(
            f"workspace run-lock metadata at {path} cannot be read; automatic takeover refused"
        ) from exc
    finally:
        os.close(fd)

    if not raw or len(raw) > _MAX_OWNER_BYTES:
        raise RunLockCorruptError(
            f"workspace run-lock metadata at {path} is empty or oversized; "
            "automatic takeover refused"
        )
    return _owner_from_json(raw, path)


def _read_owner_for_diagnostics(path: Path) -> RunLockOwner | None:
    with contextlib.suppress(RunLockCorruptError):
        return _read_owner(path)
    return None


def _owner_status(owner: RunLockOwner) -> _OwnerStatus:
    if owner.hostname != socket.gethostname():
        # A PID is meaningful only on the host that issued it.  A released
        # kernel guard on a shared filesystem is not enough to assert that a
        # remote process identity is dead, so refuse automatic takeover.
        return _OwnerStatus.UNKNOWN
    try:
        process = psutil.Process(owner.pid)
        actual_start_time = process.create_time()
        if not process.is_running():
            return _OwnerStatus.DEAD
        with contextlib.suppress(psutil.AccessDenied, psutil.NoSuchProcess):
            if process.status() == psutil.STATUS_ZOMBIE:
                return _OwnerStatus.DEAD
    except psutil.NoSuchProcess:
        return _OwnerStatus.DEAD
    except (
        psutil.AccessDenied,
        psutil.Error,
    ):
        return _OwnerStatus.UNKNOWN

    # A reused PID names a different process.  The identity that wrote the
    # record is therefore proven dead even though the numeric PID is alive.
    if not math.isclose(
        actual_start_time,
        owner.process_start_time,
        rel_tol=0.0,
        abs_tol=_START_TIME_TOLERANCE_SECONDS,
    ):
        return _OwnerStatus.DEAD
    return _OwnerStatus.ACTIVE


def _current_owner() -> RunLockOwner:
    try:
        process_start_time = psutil.Process(os.getpid()).create_time()
    except psutil.Error as exc:
        raise RunLockError("cannot determine this process's start time for the run lock") from exc

    return RunLockOwner(
        version=_LOCK_SCHEMA_VERSION,
        state="acquired",
        pid=os.getpid(),
        process_start_time=process_start_time,
        acquired_at=datetime.now(UTC).isoformat(),
        hostname=socket.gethostname(),
        token=uuid.uuid4().hex,
    )


def _write_owner(path: Path, owner: RunLockOwner) -> tuple[int, int]:
    payload = (json.dumps(asdict(owner), sort_keys=True) + "\n").encode("utf-8")
    # Preserve the run-lock contract that an already unsafe owner leaf is
    # corruption, even though replacing such a leaf would not follow it.
    _checked_leaf_lstat(path, label="owner metadata", allow_missing=True)
    try:
        atomic_write_bytes(path, payload)
    except UnsafeAtomicWriteError as exc:
        raise RunLockCorruptError(
            f"unsafe workspace run-lock owner metadata publication at {path}: {exc}"
        ) from exc

    published = _checked_leaf_lstat(path, label="owner metadata", allow_missing=False)
    if published is None:  # pragma: no cover - allow_missing=False is exhaustive
        raise RunLockCorruptError(
            f"unsafe workspace run-lock owner metadata at {path}: published leaf disappeared"
        )
    return _file_identity(published)


class WorkspaceRunLock:
    """Exclusive, crash-recoverable lock for a workspace mutation run.

    Args:
        path: Owner-metadata path.  Its parent must already exist.  A stable
            sibling named ``<path>.guard`` is retained intentionally as the OS
            locking inode; only the exact owner/temp paths are ever removed.
    """

    def __init__(self, path: Path) -> None:
        # Run orchestration may temporarily change cwd; bind cleanup and
        # diagnostics to one immutable absolute workspace path at construction.
        # Canonicalise the parent only: resolving the complete path would
        # silently follow an attacker-provided owner symlink at the leaf.
        lexical_path = path.absolute()
        try:
            canonical_parent = lexical_path.parent.resolve(strict=False)
        except (OSError, RuntimeError) as exc:
            raise RunLockError(
                f"cannot canonicalize run-lock parent directory: {lexical_path.parent}"
            ) from exc
        self.path = canonical_parent / lexical_path.name
        self.guard_path = _guard_path_for(self.path)
        self._guard_fd: int | None = None
        self._owner: RunLockOwner | None = None
        self._owner_identity: tuple[int, int] | None = None

    @property
    def acquired(self) -> bool:
        """Whether this object currently owns the OS guard lock."""
        return self._guard_fd is not None

    @property
    def owner(self) -> RunLockOwner | None:
        """Return this object's owner record after successful acquisition."""
        return self._owner

    def acquire(self) -> Self:
        """Acquire the lock non-blockingly or raise a diagnostic domain error."""
        if self.acquired:
            return self
        if not self.path.parent.is_dir():
            raise RunLockError(f"run-lock parent directory does not exist: {self.path.parent}")

        # Validate both fixed leaves before creating/opening either one.
        _checked_leaf_lstat(self.path, label="owner metadata", allow_missing=True)
        _checked_leaf_lstat(self.guard_path, label="guard", allow_missing=True)

        fd = _open_guard(self.guard_path)
        guard_locked = False
        try:
            guard_locked = _try_lock_guard(fd)
            if guard_locked:
                # Close the final pre-lock pathname-swap window.  The guard
                # pathname must still name this exact open inode while the OS
                # lock is held, before any owner metadata is read or written.
                _verify_open_leaf(fd, self.guard_path, label="guard")
            if not guard_locked:
                diagnostic_owner = _read_owner_for_diagnostics(self.path)
                if (
                    diagnostic_owner is not None
                    and diagnostic_owner.state == "acquired"
                    and _owner_status(diagnostic_owner) is _OwnerStatus.DEAD
                ):
                    deadline = time.monotonic() + _STALE_GUARD_RETRY_SECONDS
                    while not guard_locked and time.monotonic() < deadline:
                        # Windows CRT byte-range locks need a fresh file
                        # descriptor after a failed non-blocking attempt; retry
                        # on the original descriptor can remain spuriously busy
                        # even after the dead process's kernel handle is gone.
                        os.close(fd)
                        fd = -1
                        time.sleep(_STALE_GUARD_RETRY_INTERVAL_SECONDS)
                        fd = _open_guard(self.guard_path)
                        guard_locked = _try_lock_guard(fd)
                        if guard_locked:
                            _verify_open_leaf(fd, self.guard_path, label="guard")
                if not guard_locked:
                    raise RunLockHeldError(
                        self.path,
                        _read_owner_for_diagnostics(self.path),
                    )

            previous_owner = _read_owner(self.path)
            if previous_owner is not None and previous_owner.state == "acquired":
                status = _owner_status(previous_owner)
                if status is _OwnerStatus.ACTIVE:
                    raise RunLockHeldError(self.path, previous_owner)
                if status is _OwnerStatus.UNKNOWN:
                    raise RunLockUnverifiableError(self.path, previous_owner)

            owner = _current_owner()
            owner_identity = _write_owner(self.path, owner)
            self._guard_fd = fd
            self._owner = owner
            self._owner_identity = owner_identity
            return self
        except BaseException:
            if guard_locked and fd >= 0:
                with contextlib.suppress(OSError):
                    _unlock_guard(fd)
            if fd >= 0:
                os.close(fd)
            raise

    def release(self) -> None:
        """Release this lock; safe to call repeatedly and from exception paths."""
        fd = self._guard_fd
        if fd is None:
            return

        owner = self._owner
        owner_identity = self._owner_identity
        try:
            if owner is not None and owner_identity is not None:
                try:
                    current_stat = _checked_leaf_lstat(
                        self.path,
                        label="owner metadata",
                        allow_missing=True,
                    )
                    current_identity = (
                        _file_identity(current_stat) if current_stat is not None else None
                    )
                except FileNotFoundError:
                    current_identity = None
                except RunLockCorruptError:
                    current_identity = None
                    logger.warning(
                        "Run-lock metadata at %s became unsafe; refusing to access it",
                        self.path,
                    )

                if current_identity == owner_identity:
                    # Publish a clean-release marker atomically first.  If an
                    # antivirus/file-indexer prevents unlink, the next holder
                    # can still distinguish this from a crashed active owner.
                    released_owner = replace(owner, state="released")
                    try:
                        released_identity = _write_owner(self.path, released_owner)
                    except (
                        OSError,
                        RunLockError,
                    ):
                        logger.warning(
                            "Could not publish released run-lock metadata at %s", self.path
                        )
                        # The original owner inode is still ours if atomic
                        # replacement never happened; remove only that exact
                        # file as a safe cleanup fallback.
                        with contextlib.suppress(OSError, RunLockCorruptError):
                            current_stat = _checked_leaf_lstat(
                                self.path,
                                label="owner metadata",
                                allow_missing=True,
                            )
                            if (
                                current_stat is not None
                                and _file_identity(current_stat) == owner_identity
                            ):
                                self.path.unlink()
                    else:
                        try:
                            current_stat = _checked_leaf_lstat(
                                self.path,
                                label="owner metadata",
                                allow_missing=True,
                            )
                            if (
                                current_stat is not None
                                and _file_identity(current_stat) == released_identity
                            ):
                                self.path.unlink()
                        except (
                            OSError,
                            RunLockCorruptError,
                        ):
                            logger.warning(
                                "Could not remove released run-lock metadata at %s", self.path
                            )
                elif current_identity is not None:
                    logger.warning(
                        "Run-lock metadata at %s was replaced externally; refusing to remove it",
                        self.path,
                    )
        finally:
            try:
                try:
                    _unlock_guard(fd)
                except OSError:
                    # Closing the descriptor below is the kernel-level release
                    # fallback and must still happen on every exception path.
                    logger.warning("Could not explicitly unlock run-lock guard %s", self.guard_path)
            finally:
                with contextlib.suppress(OSError):
                    os.close(fd)
                self._guard_fd = None
                self._owner = None
                self._owner_identity = None

    def __enter__(self) -> Self:
        return self.acquire()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.release()


_DATABASE_LOCK_DIRNAME = "mutmut-win-database-locks-v1"


def _database_lock_root() -> Path:
    """Return one process-independent directory for database lock records."""
    try:
        temp_root = Path(tempfile.gettempdir()).resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise RunLockError("cannot canonicalize the system temporary directory") from exc

    lock_root = temp_root / _DATABASE_LOCK_DIRNAME
    try:
        junction_check = getattr(lock_root, "is_junction", None)
        redirected = lock_root.is_symlink() or (callable(junction_check) and junction_check())
        if redirected:
            raise RunLockError(f"database run-lock directory is redirected: {lock_root}")
        lock_root.mkdir(mode=0o700, exist_ok=True)
        if not lock_root.is_dir() or lock_root.resolve(strict=True) != lock_root:
            raise RunLockError(f"database run-lock directory is unsafe: {lock_root}")
    except RunLockError:
        raise
    except (OSError, RuntimeError) as exc:
        raise RunLockError(f"cannot prepare database run-lock directory: {lock_root}") from exc
    return lock_root


def database_lock_paths_for_db(db_path: Path) -> tuple[Path, ...]:
    """Return path- and file-identity lock domains for one SQLite database.

    The canonical path key serializes callers that name the same database
    before it exists.  Once a file exists, the device/inode key additionally
    unifies hardlink aliases, including aliases reached from different
    workspaces.  Both keys are retained: deleting and recreating a database
    changes its inode but must not open a same-path coordination gap.
    """
    lexical = db_path.absolute()
    try:
        canonical_parent = lexical.parent.resolve(strict=False)
    except (OSError, RuntimeError) as exc:
        raise RunLockError(f"cannot canonicalize database parent: {lexical.parent}") from exc
    canonical_path = canonical_parent / lexical.name
    lock_root = _database_lock_root()

    path_key = f"path:{str(canonical_path).casefold()}"
    path_digest = hashlib.sha256(path_key.encode("utf-8")).hexdigest()
    paths = [lock_root / f"0-path-{path_digest}.run.lock"]

    try:
        database_stat = canonical_path.stat()
    except FileNotFoundError:
        return tuple(paths)
    except OSError as exc:
        raise RunLockError(f"cannot inspect database identity: {canonical_path}") from exc

    identity_key = f"file:{database_stat.st_dev}:{database_stat.st_ino}"
    identity_digest = hashlib.sha256(identity_key.encode("ascii")).hexdigest()
    paths.append(lock_root / f"1-file-{identity_digest}.run.lock")
    return tuple(paths)


class DatabaseRunLocks:
    """Non-blocking path plus inode lock set for one SQLite database.

    Locks are always acquired in the same order: canonical path first, then
    file identity.  Acquisition is non-blocking and partial acquisition is
    rolled back, so two hardlink aliases cannot deadlock while converging on
    their shared identity lock.
    """

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path.absolute()
        self._locks: dict[Path, WorkspaceRunLock] = {}

    @property
    def acquired(self) -> bool:
        return bool(self._locks) and all(lock.acquired for lock in self._locks.values())

    @property
    def paths(self) -> tuple[Path, ...]:
        return tuple(self._locks)

    def _acquire_current_paths(self) -> None:
        for path in database_lock_paths_for_db(self.db_path):
            if path in self._locks:
                continue
            lock = WorkspaceRunLock(path)
            try:
                lock.acquire()
            except BaseException:
                self.release()
                raise
            self._locks[path] = lock

    def acquire(self) -> Self:
        if not self.acquired:
            self._acquire_current_paths()
        return self

    def refresh_identity(self) -> None:
        """Acquire the inode key after a previously missing DB was created."""
        if not self.acquired:
            raise RunLockError("database lock identity cannot refresh before acquisition")
        self._acquire_current_paths()

    def release(self) -> None:
        for lock in reversed(tuple(self._locks.values())):
            lock.release()
        self._locks.clear()

    def __enter__(self) -> Self:
        return self.acquire()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.release()
