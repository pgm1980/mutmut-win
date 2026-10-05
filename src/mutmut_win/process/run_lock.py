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


class RunLockUnavailableError(RunLockError):
    """The owner metadata could not be published (environment/OS condition).

    No acquisition took place: the guard was released and the caller may
    retry.  Raised for transient publication failures (disk full, sharing
    violations, fsync failures) that are neither corruption nor a held
    lock — the raw OSError would otherwise escape as a stack trace
    (M-091).
    """


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


def _rollback_published_owner(path: Path, owner: RunLockOwner) -> None:
    """Retract an already-published 'acquired' record after acquire failed (M-092).

    Only the provably own record (token match) is retired: a 'released'
    marker is published first; if that publication fails, the exact inode
    is removed identity-checked as a fallback.  Every error is suppressed
    and logged — this runs inside an exception handler and must never
    mask the original failure.
    """
    try:
        current = _read_owner(path)
        if current is None or current.token != owner.token or current.state != "acquired":
            return
        released = replace(current, state="released")
        released_identity = _write_owner(path, released)
        with contextlib.suppress(OSError, RunLockCorruptError):
            stat = _checked_leaf_lstat(path, label="owner metadata", allow_missing=True)
            if stat is not None and _file_identity(stat) == released_identity:
                path.unlink()
    except (OSError, RunLockError) as exc:
        logger.warning("Could not roll back published run-lock owner metadata at %s: %s", path, exc)


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
            # M-090: a competitor's mandatory byte-range lock on byte 0
            # makes this write fail with a raw OSError that used to escape
            # before acquire's cleanup handler — translate it so the CLI
            # shows the domain error instead of a stack trace.
            try:
                os.lseek(fd, 0, os.SEEK_SET)
                os.write(fd, b"\0")
                os.fsync(fd)
            except OSError as exc:
                raise RunLockHeldError(path, None) from exc
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
    except OSError as exc:
        # M-091: AtomicReplaceError (a PermissionError), ENOSPC, fsync
        # failures and every other publication-level OSError used to escape
        # acquire() as a raw stack trace because only
        # UnsafeAtomicWriteError had a translation.  No acquisition took
        # place; the caller may retry.
        raise RunLockUnavailableError(
            f"cannot publish workspace run-lock owner metadata at {path}: {exc}"
        ) from exc

    try:
        published = _checked_leaf_lstat(path, label="owner metadata", allow_missing=False)
    except FileNotFoundError as exc:
        # M-091/M-092 overlap: the leaf vanished between publication and
        # the post-check — treat as corruption, not as a raw traceback.
        raise RunLockCorruptError(
            f"workspace run-lock owner metadata at {path}: published leaf disappeared"
        ) from exc
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
        owner: RunLockOwner | None = None
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
            # M-092: if our 'acquired' record was already published before
            # the failure, retract it while the guard is still held —
            # otherwise the record blocks every future acquire from this
            # still-living process (RunLockHeldError on our own PID).
            if guard_locked and owner is not None:
                with contextlib.suppress(BaseException):
                    _rollback_published_owner(self.path, owner)
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


_DATABASE_LOCK_FILENAME_PREFIX = ".mutmut-win-db-"


def _validate_database_lock_parent(lexical_parent: Path) -> Path:
    """Return the canonical physical parent of the database lock domain.

    Every existing component of the *lexical* parent is inspected with
    ``lstat`` before ``resolve`` could follow it, so a symlink/junction in
    the database path cannot silently move the colocated lock domain (and
    its owner metadata) into another directory.  The canonical parent must
    exist: creating directories is the db layer's job
    (``ensure_cache_parent``), never the lock layer's.
    """
    anchor = Path(lexical_parent.anchor)
    current = anchor
    parts = lexical_parent.parts[1:] if lexical_parent.anchor else lexical_parent.parts
    for part in parts:
        current = current / part
        try:
            metadata = current.lstat()
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise RunLockError(f"cannot inspect database parent directory: {current}") from exc
        if _is_reparse_point(metadata) or stat_module.S_ISLNK(metadata.st_mode):
            raise RunLockError(
                f"database parent directory is a symlink, junction, or reparse point: {current}"
            )
        if not stat_module.S_ISDIR(metadata.st_mode):
            raise RunLockError(f"database parent is not a directory: {current}")
    try:
        canonical_parent = lexical_parent.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise RunLockError(f"cannot canonicalize database parent: {lexical_parent}") from exc
    if not canonical_parent.is_dir():
        raise RunLockError(f"database parent directory is not a directory: {canonical_parent}")
    return canonical_parent


def database_lock_paths_for_db(db_path: Path) -> tuple[Path, ...]:
    """Return path- and file-identity lock domains for one SQLite database.

    Both keys are colocated in the canonical physical parent directory of
    the database (M-036), so every process that can name and open the
    database shares one lock domain — regardless of the process's TMP/TEMP
    environment, user profile, or machine-wide temp redirections.  There is
    deliberately no fallback to a temporary-directory domain.

    The canonical path key serializes callers that name the same database
    before it exists.  Once the file exists, the device/inode key pins the
    observable database identity so deleting and recreating the file cannot
    open a same-path coordination gap.  A database with more than one
    directory entry (hardlink alias) cannot converge on a colocated
    identity key and is rejected fail-closed as corrupt — as is a database
    whose link count could not be observed at all, because an unobservable
    link count is not proof of a safe single-link file.
    """
    lexical = db_path.absolute()
    lock_root = _validate_database_lock_parent(lexical.parent)
    canonical_path = lock_root / lexical.name

    path_key = f"path:{str(canonical_path).casefold()}"
    path_digest = hashlib.sha256(path_key.encode("utf-8")).hexdigest()
    paths = [lock_root / f"{_DATABASE_LOCK_FILENAME_PREFIX}0-path-{path_digest}.run.lock"]

    try:
        database_stat = canonical_path.lstat()
    except FileNotFoundError:
        return tuple(paths)
    except OSError as exc:
        raise RunLockError(f"cannot inspect database identity: {canonical_path}") from exc

    if _is_reparse_point(database_stat) or stat_module.S_ISLNK(database_stat.st_mode):
        raise RunLockCorruptError(
            f"unsafe database lock identity at {canonical_path}: "
            "database is a symlink, junction, or reparse point"
        )
    if not stat_module.S_ISREG(database_stat.st_mode):
        raise RunLockCorruptError(
            f"unsafe database lock identity at {canonical_path}: database is not a regular file"
        )
    if database_stat.st_nlink == 0:
        # A zero link count means lstat could not read the metadata (the
        # CPython fallback for an unopenable regular file, cf. M-095); the
        # degenerate identity (0, 0) must never be hashed as a lock key, and
        # the refusal must not claim a hardlink that was not observed.
        raise RunLockCorruptError(
            f"unsafe database lock identity at {canonical_path}: database link "
            "count could not be observed (0); its metadata could not be read "
            "reliably, so it cannot be verified as a single-link file"
        )
    if database_stat.st_nlink != 1:
        raise RunLockCorruptError(
            f"unsafe database lock identity at {canonical_path}: "
            f"database has {database_stat.st_nlink} hard links"
        )

    identity_key = f"file:{database_stat.st_dev}:{database_stat.st_ino}"
    identity_digest = hashlib.sha256(identity_key.encode("ascii")).hexdigest()
    paths.append(lock_root / f"{_DATABASE_LOCK_FILENAME_PREFIX}1-file-{identity_digest}.run.lock")
    return tuple(paths)


class DatabaseRunLocks:
    """Non-blocking path plus inode lock set for one SQLite database.

    Both lock keys live in the canonical physical parent directory of the
    database (M-036), so the lock domain is shared by every process that
    can open that directory, independent of TMP/TEMP; the parent directory
    must already exist (``db.ensure_cache_parent`` creates it for run
    commands).  Locks are always acquired in the same order: canonical path
    first, then file identity.  Acquisition is non-blocking and partial
    acquisition is rolled back.  Hardlink-aliased databases are rejected as
    corrupt before any lock is taken instead of converging on a shared
    identity key.
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
            lock: WorkspaceRunLock | None = None
            try:
                lock = WorkspaceRunLock(path)
                lock.acquire()
                self._locks[path] = lock
            except BaseException:
                # Roll back completely, even under interruption: an acquired
                # but unregistered lock has no other owner and is released
                # here (try/finally so an interrupt cannot skip the rest of
                # the rollback), then every registered partial lock follows.
                try:
                    if lock is not None and lock.acquired and path not in self._locks:
                        lock.release()
                finally:
                    self.release()
                raise

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
        """Release every partial lock, completing even under interruption.

        Callbacks run in LIFO order (identity lock before path lock, the map
        cleared last) and every stage runs even when a previous one raised;
        the propagating exception carries the others as chained context
        (M-093).
        """
        with contextlib.ExitStack() as stack:
            stack.callback(self._locks.clear)
            for lock in tuple(self._locks.values()):
                stack.callback(lock.release)

    def __enter__(self) -> Self:
        return self.acquire()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.release()
