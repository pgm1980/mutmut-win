"""Windows filesystem state helpers for remediation tests (AP-00 / Q-02).

Factories and context managers that put a file or directory into a specific
Windows filesystem state:

- a read-only leaf (``stat.S_IREAD``),
- a directory junction (``_winapi.CreateJunction``) where available,
- an exclusive ``msvcrt.locking`` byte-range lock,
- a sharing-violation holder (``CreateFileW`` with ``dwShareMode=0``),
- file names near the 255 UTF-16 unit limit,
- a file name containing a lone (unpaired) UTF-16 surrogate.

Every helper either restores the previous state in ``finally`` or leaves the
created artefacts inside a caller-owned temporary directory, so nothing leaks
outside ``tmp_path``. Helpers raise or let the caller skip when a state is
unavailable on the host (e.g. junction creation); they never silently
pretend the state was created.

Consumers are the regression tests for M-010, M-020, M-027, M-030, M-062,
M-068, M-089 and M-090.
"""

from __future__ import annotations

import _winapi
import contextlib
import ctypes
import msvcrt
import os
import stat
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

__all__ = [
    "JunctionUnavailableError",
    "byte_range_locked_file",
    "lone_surrogate_name",
    "make_junction",
    "near_max_length_path",
    "readonly_leaf",
    "sharing_violation_holder",
]

# Windows-only stdlib extensions, grouped with the other stdlib imports so
# isort stays silent (contract: win32 only).
_GENERIC_READ = 0x80000000
_OPEN_EXISTING = 3
_SHARE_MODE_NONE = 0
_INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
#: NTFS caps path components at 255 UTF-16 code units.
_MAX_COMPONENT_UTF16_UNITS = 255


class JunctionUnavailableError(RuntimeError):
    """Raised when the host cannot create a directory junction."""


@contextlib.contextmanager
def readonly_leaf(path: Path) -> Iterator[Path]:
    """Make an existing file read-only for the duration of the block.

    Args:
        path: Existing file (created by the caller if absent).

    Yields:
        The same path, now carrying the read-only attribute.

    Raises:
        OSError: If the file does not exist or the attribute cannot be set.
    """

    if not path.is_file():
        msg = f"readonly_leaf requires an existing file, got {path}"
        raise OSError(msg)
    original_mode = path.stat().st_mode
    path.chmod(stat.S_IREAD)
    try:
        yield path
    finally:
        with contextlib.suppress(OSError):
            path.chmod(original_mode | stat.S_IWRITE)


def make_junction(link: Path, target: Path) -> None:
    """Create a directory junction at ``link`` pointing to ``target``.

    Args:
        link: Junction location (must not exist).
        target: Existing directory the junction points to.

    Raises:
        JunctionUnavailableError: If junction creation is not supported here.
        OSError: If the underlying API call fails.
    """

    if os.name != "nt":
        msg = "junctions require Windows"
        raise JunctionUnavailableError(msg)
    if not target.is_dir():
        msg = f"junction target must be an existing directory, got {target}"
        raise OSError(msg)
    if link.exists() or link.is_symlink():
        msg = f"junction location already exists: {link}"
        raise OSError(msg)
    try:
        _winapi.CreateJunction(str(target), str(link))
    except (AttributeError, OSError) as exc:
        raise JunctionUnavailableError(f"CreateJunction failed: {exc}") from exc
    if not link.exists():
        raise JunctionUnavailableError("CreateJunction returned but the link is not usable")


@contextlib.contextmanager
def byte_range_locked_file(path: Path, *, offset: int = 0, length: int = 1) -> Iterator[Path]:
    """Hold an exclusive lock on ``length`` bytes of ``path``.

    Args:
        path: Existing file to lock.
        offset: Byte offset where the lock starts.
        length: Number of bytes to lock.

    Yields:
        The same path while the lock is held.
    """

    if not path.is_file():
        msg = f"byte_range_locked_file requires an existing file, got {path}"
        raise OSError(msg)
    with path.open("r+b") as handle:
        # msvcrt.locking locks at the current file position; seek first.
        handle.seek(offset)
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, length)
        try:
            yield path
        finally:
            with contextlib.suppress(OSError):
                handle.seek(offset)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, length)


@contextlib.contextmanager
def sharing_violation_holder(path: Path) -> Iterator[Path]:
    """Open ``path`` with ``dwShareMode=0`` so other opens get winerror 32/33.

    Args:
        path: Existing file to hold open exclusively.

    Yields:
        The same path while the sharing-violation handle is open.
    """

    if not path.is_file():
        msg = f"sharing_violation_holder requires an existing file, got {path}"
        raise OSError(msg)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    handle = kernel32.CreateFileW(
        str(path),
        _GENERIC_READ,
        _SHARE_MODE_NONE,
        None,
        _OPEN_EXISTING,
        0,
        None,
    )
    if handle == _INVALID_HANDLE_VALUE:
        msg = f"CreateFileW failed for sharing violation holder (error {ctypes.get_last_error()})"
        raise OSError(msg)
    try:
        yield path
    finally:
        kernel32.CloseHandle(handle)


def near_max_length_path(directory: Path, suffix: str = ".txt") -> Path:
    """Return a file path whose stem fills the component length limit.

    The full name (stem + suffix) is padded to exactly
    ``_MAX_COMPONENT_UTF16_UNITS`` UTF-16 code units, or one below when the
    suffix length makes exact fill impossible.

    Args:
        directory: Directory the name lives in (not verified to exist).
        suffix: File extension including the dot.

    Returns:
        A path whose final component is at the 255 UTF-16 unit boundary.
    """

    stem_units = _MAX_COMPONENT_UTF16_UNITS - len(suffix)
    stem = "x" * stem_units
    return directory / f"{stem}{suffix}"


def lone_surrogate_name(base: str = "surrogate") -> str:
    """Return a file name containing one unpaired UTF-16 low surrogate.

    Creating a file with this name may raise ``OSError`` on some filesystems;
    callers must treat that as an unavailable state (skip with reason), never
    as success.
    """

    return f"{base}-\udc80.txt"
