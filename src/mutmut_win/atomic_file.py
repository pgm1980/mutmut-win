"""Safe atomic publication of byte payloads to workspace files.

The destination is never opened for writing.  Payloads are written to a
random, exclusively-created sibling and then published with ``os.replace``.
This is important for workspace paths: a predictable temporary or backup
name may already be a hardlink or symlink to a file outside the workspace.
"""

from __future__ import annotations

import contextlib
import os
import secrets
import stat
from pathlib import Path


class UnsafeAtomicWriteError(OSError):
    """Raised when a publication path changes or contains unsafe indirection."""


class AtomicReplaceError(PermissionError):
    """The destination entry could not be replaced during atomic publication."""


class AtomicPublicationRaceError(UnsafeAtomicWriteError):
    """A competing publisher replaced the destination before post-validation."""


FileIdentity = tuple[int, int]


def _identity(file_stat: os.stat_result) -> FileIdentity:
    return file_stat.st_dev, file_stat.st_ino


def _is_reparse_point(file_stat: os.stat_result) -> bool:
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    attributes = getattr(file_stat, "st_file_attributes", 0)
    return bool(reparse_flag and attributes & reparse_flag)


def _checked_parent(path: Path, expected: FileIdentity | None = None) -> FileIdentity:
    """Return a stable parent identity, rejecting symlink/reparse indirection."""
    parent = path.parent.absolute()
    try:
        parent_stat = parent.lstat()
    except OSError as exc:
        raise UnsafeAtomicWriteError(f"cannot inspect atomic-write parent {parent}") from exc

    if (
        not stat.S_ISDIR(parent_stat.st_mode)
        or stat.S_ISLNK(parent_stat.st_mode)
        or _is_reparse_point(parent_stat)
    ):
        raise UnsafeAtomicWriteError(
            f"atomic-write parent must be a real directory, not a link or reparse point: {parent}"
        )

    # Reject indirection in every existing component.  A textual comparison
    # between ``absolute()`` and ``resolve()`` is not a link test on Windows:
    # an ordinary NTFS directory can be addressed through its legitimate 8.3
    # alias while resolving to the long spelling.  Component metadata plus
    # final directory identity distinguishes that alias from a redirect.
    for component in reversed((parent, *parent.parents)):
        try:
            component_stat = component.lstat()
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise UnsafeAtomicWriteError(
                f"cannot inspect atomic-write parent component {component}"
            ) from exc
        if stat.S_ISLNK(component_stat.st_mode) or _is_reparse_point(component_stat):
            raise UnsafeAtomicWriteError(
                f"atomic-write parent contains link indirection or reparse point: {component}"
            )
        if not stat.S_ISDIR(component_stat.st_mode):
            raise UnsafeAtomicWriteError(
                f"atomic-write parent component is not a directory: {component}"
            )

    try:
        resolved_parent = parent.resolve(strict=True)
        resolved_stat = resolved_parent.stat()
    except OSError as exc:
        raise UnsafeAtomicWriteError(f"cannot resolve atomic-write parent {parent}") from exc
    if _identity(parent_stat) != _identity(resolved_stat):
        raise UnsafeAtomicWriteError(f"atomic-write parent changed or was redirected: {parent}")

    identity = _identity(parent_stat)
    if expected is not None and identity != expected:
        raise UnsafeAtomicWriteError(f"atomic-write parent changed during publication: {parent}")
    return identity


def _open_random_sibling(path: Path) -> tuple[int, Path, FileIdentity]:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_BINARY", 0)
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)

    for _attempt in range(32):
        token = secrets.token_hex(16)
        temp_path = path.with_name(f".{path.name}.mutmut-atomic-{token}.tmp")
        try:
            fd = os.open(temp_path, flags, 0o600)
        except FileExistsError:
            continue

        try:
            opened_stat = os.fstat(fd)
            leaf_stat = temp_path.lstat()
            opened_identity = _identity(opened_stat)
            if (
                not stat.S_ISREG(opened_stat.st_mode)
                or stat.S_ISLNK(leaf_stat.st_mode)
                or _is_reparse_point(leaf_stat)
                or opened_identity != _identity(leaf_stat)
                or opened_stat.st_nlink != 1
                or leaf_stat.st_nlink != 1
            ):
                raise UnsafeAtomicWriteError(
                    f"exclusive atomic-write sibling is not a private regular file: {temp_path}"
                )
            return fd, temp_path, opened_identity
        except BaseException:
            os.close(fd)
            with contextlib.suppress(OSError):
                temp_path.unlink()
            raise

    raise FileExistsError(f"could not allocate a unique atomic-write sibling for {path}")


def _checked_temp(path: Path, expected: FileIdentity) -> None:
    try:
        current = path.lstat()
    except OSError as exc:
        raise UnsafeAtomicWriteError(f"atomic-write sibling disappeared: {path}") from exc
    if (
        not stat.S_ISREG(current.st_mode)
        or stat.S_ISLNK(current.st_mode)
        or _is_reparse_point(current)
        or _identity(current) != expected
        or current.st_nlink != 1
    ):
        raise UnsafeAtomicWriteError(f"atomic-write sibling changed before publication: {path}")


def _write_all(fd: int, payload: bytes) -> None:
    view = memoryview(payload)
    offset = 0
    while offset < len(view):
        written = os.write(fd, view[offset:])
        if written <= 0:
            raise OSError("short write while publishing atomic byte payload")
        offset += written


def _fsync_parent(path: Path, expected: FileIdentity) -> None:
    """Durably publish the directory entry where the platform supports it."""
    if os.name == "nt":
        # Windows does not expose a portable directory handle through os.open.
        _checked_parent(path, expected)
        return

    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path.parent, flags)
    try:
        if _identity(os.fstat(fd)) != expected:
            raise UnsafeAtomicWriteError(
                f"atomic-write parent changed before directory fsync: {path.parent}"
            )
        os.fsync(fd)
    finally:
        os.close(fd)


def _cleanup_owned_temp(path: Path | None, identity: FileIdentity | None) -> None:
    if path is None or identity is None:
        return
    try:
        current = path.lstat()
    except FileNotFoundError:
        return
    except OSError:
        return
    if _identity(current) == identity:
        with contextlib.suppress(OSError):
            path.unlink()


def _regular_file_matches_bytes(path: Path, payload: bytes) -> bool:
    """Return whether *path* is one safe, stable regular file with *payload*.

    The comparison never follows a link/reparse leaf and never accepts a
    hardlink.  Revalidating both the open handle and directory entry before
    returning makes this suitable for confirming that a competing publisher
    won an idempotent, same-payload race.
    """
    parent_identity = _checked_parent(path)
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
    except FileNotFoundError:
        return False
    except OSError:
        # An unreadable/busy leaf cannot prove that the requested bytes are
        # already published.  The strict writer (or its original error) must
        # decide the operation instead.
        return False

    try:
        before = os.fstat(fd)
        try:
            leaf_before = path.lstat()
        except OSError:
            return False
        before_identity = _identity(before)
        if (
            not stat.S_ISREG(before.st_mode)
            or not stat.S_ISREG(leaf_before.st_mode)
            or stat.S_ISLNK(leaf_before.st_mode)
            or _is_reparse_point(leaf_before)
            or before_identity != _identity(leaf_before)
            or before.st_nlink != 1
            or leaf_before.st_nlink != 1
            or before.st_size != len(payload)
        ):
            return False

        received = bytearray()
        while len(received) <= len(payload):
            chunk = os.read(fd, min(64 * 1024, len(payload) + 1 - len(received)))
            if not chunk:
                break
            received.extend(chunk)
        after = os.fstat(fd)
        try:
            leaf_after = path.lstat()
        except OSError:
            return False
        _checked_parent(path, parent_identity)
        return (
            bytes(received) == payload
            and _identity(after) == before_identity
            and after.st_size == before.st_size
            and after.st_mtime_ns == before.st_mtime_ns
            and stat.S_ISREG(leaf_after.st_mode)
            and not stat.S_ISLNK(leaf_after.st_mode)
            and not _is_reparse_point(leaf_after)
            and _identity(leaf_after) == before_identity
            and leaf_after.st_nlink == 1
            and leaf_after.st_size == before.st_size
            and leaf_after.st_mtime_ns == before.st_mtime_ns
        )
    finally:
        os.close(fd)


def atomic_write_bytes(
    path: Path,
    payload: bytes,
    *,
    mode: int | None = None,
    timestamps_ns: tuple[int, int] | None = None,
) -> None:
    """Atomically write bytes without ever opening an existing leaf for writing.

    The immediate parent must already exist and must not contain symlink or
    reparse-point indirection.  ``mode`` and ``timestamps_ns`` are applied to
    the private sibling before publication, which lets atomic copies preserve
    the stat fields used by staging freshness checks.
    """
    path = Path(path)
    parent_identity = _checked_parent(path)
    fd: int | None = None
    temp_path: Path | None = None
    temp_identity: FileIdentity | None = None
    try:
        fd, temp_path, temp_identity = _open_random_sibling(path)
        _checked_parent(path, parent_identity)
        if mode is not None:
            temp_path.chmod(mode, follow_symlinks=False)
            _checked_temp(temp_path, temp_identity)
        _write_all(fd, payload)
        if timestamps_ns is not None:
            if os.utime in os.supports_follow_symlinks:
                os.utime(temp_path, ns=timestamps_ns, follow_symlinks=False)
            else:
                # Windows exposes neither fd-relative utime nor the
                # follow_symlinks switch. The leaf is random, exclusively
                # created and still open; the identity check below remains
                # the portable substitution guard.
                os.utime(temp_path, ns=timestamps_ns)
            _checked_temp(temp_path, temp_identity)
        os.fsync(fd)
        os.close(fd)
        fd = None

        _checked_parent(path, parent_identity)
        _checked_temp(temp_path, temp_identity)
        try:
            temp_path.replace(path)
        except PermissionError as exc:
            raise AtomicReplaceError(f"could not replace atomic-write leaf {path}: {exc}") from exc
        temp_path = None

        try:
            published = path.lstat()
        except OSError as exc:
            raise UnsafeAtomicWriteError(
                f"published atomic-write leaf disappeared: {path}"
            ) from exc
        if _identity(published) != temp_identity:
            raise AtomicPublicationRaceError(f"published atomic-write identity mismatch: {path}")
        _fsync_parent(path, parent_identity)
    finally:
        if fd is not None:
            with contextlib.suppress(OSError):
                os.close(fd)
        _cleanup_owned_temp(temp_path, temp_identity)


def ensure_atomic_bytes(path: Path, payload: bytes) -> None:
    """Idempotently publish *payload*, accepting only an identical safe winner.

    :func:`atomic_write_bytes` deliberately detects when another writer
    replaces its just-published inode.  That is the correct default for
    independent writers, but deterministic generated files can have many
    concurrent publishers with byte-identical payloads.  This helper first
    avoids a redundant replacement and, if a strict publication loses a race,
    treats the operation as successful only when the winning leaf is a safe,
    stable regular file containing the exact requested bytes.  A different or
    unverifiable winner preserves the original failure.
    """
    path = Path(path)
    if _regular_file_matches_bytes(path, payload):
        return
    try:
        atomic_write_bytes(path, payload)
    except (
        AtomicPublicationRaceError,
        AtomicReplaceError,
    ):
        if _regular_file_matches_bytes(path, payload):
            return
        raise


def create_exclusive_random_bytes(
    directory: Path,
    payload: bytes,
    *,
    prefix: str,
    suffix: str,
) -> tuple[Path, FileIdentity]:
    """Create and publish one randomly named file without replacing any leaf.

    The returned path and identity describe a private, regular file created
    with ``O_EXCL`` in a real, identity-checked directory. Unlike
    :func:`atomic_write_bytes`, this helper never calls ``replace``: a
    pre-existing user path is therefore never an eligible publication target.
    """
    if not prefix or Path(prefix).name != prefix or Path(suffix).name != suffix:
        raise ValueError("exclusive random file prefix/suffix must be plain names")

    directory = Path(directory)
    probe = directory / f"{prefix}probe{suffix}"
    parent_identity = _checked_parent(probe)
    if parent_identity[0] < 0 or parent_identity[1] <= 0:
        raise UnsafeAtomicWriteError(
            f"exclusive random-file parent has no stable device/inode identity: {directory}"
        )
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_BINARY", 0)
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)

    for _attempt in range(32):
        path = directory / f"{prefix}{secrets.token_hex(16)}{suffix}"
        fd: int | None = None
        identity: FileIdentity | None = None
        keep = False
        try:
            try:
                fd = os.open(path, flags, 0o600)
            except FileExistsError:
                continue

            opened = os.fstat(fd)
            identity = _identity(opened)
            leaf = path.lstat()
            if (
                not stat.S_ISREG(opened.st_mode)
                or stat.S_ISLNK(leaf.st_mode)
                or _is_reparse_point(leaf)
                or identity[0] < 0
                or identity[1] <= 0
                or identity != _identity(leaf)
                or opened.st_nlink != 1
                or leaf.st_nlink != 1
            ):
                raise UnsafeAtomicWriteError(
                    f"exclusive random file is not a private regular file: {path}"
                )

            _checked_parent(path, parent_identity)
            _write_all(fd, payload)
            os.fsync(fd)
            os.close(fd)
            fd = None
            _checked_parent(path, parent_identity)
            _checked_temp(path, identity)
            _fsync_parent(path, parent_identity)
            keep = True
            return path, identity
        finally:
            if fd is not None:
                with contextlib.suppress(OSError):
                    os.close(fd)
            if not keep:
                _cleanup_owned_temp(path, identity)

    raise FileExistsError(f"could not allocate a unique exclusive file in {directory}")


def atomic_copy_file(source: Path, destination: Path) -> None:
    """Copy a regular file through the safe atomic publication path.

    The source is read through one open handle and checked for identity/size/
    mtime changes before its bytes are published.  Mode and timestamps are
    applied to the private sibling, never to an existing destination leaf.
    """
    source = Path(source)
    with source.open("rb") as source_file:
        before = os.fstat(source_file.fileno())
        if not stat.S_ISREG(before.st_mode):
            raise OSError(f"atomic copy source is not a regular file: {source}")
        payload = source_file.read()
        after = os.fstat(source_file.fileno())

    if (
        _identity(before) != _identity(after)
        or before.st_size != after.st_size
        or before.st_mtime_ns != after.st_mtime_ns
        or len(payload) != after.st_size
    ):
        raise OSError(f"atomic copy source changed while it was being read: {source}")

    atomic_write_bytes(
        destination,
        payload,
        mode=stat.S_IMODE(after.st_mode),
        timestamps_ns=(after.st_atime_ns, after.st_mtime_ns),
    )
