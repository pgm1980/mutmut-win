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
import ctypes.wintypes
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

# A private WinDLL instance with use_last_error=True (same contract as the
# production ``mutmut_win.process.job_object`` bindings): ctypes captures the
# thread-local Win32 error immediately after every foreign call, so
# ``ctypes.get_last_error()`` reports the real error code.
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

# Explicit C signatures (AR-13 / PERF-005 / TQ-004; same pattern as
# job_object._kernel32, audit A2-JT-006). Without argtypes/restype ctypes
# defaults every binding to c_int: INVALID_HANDLE_VALUE then arrives as
# signed -1 instead of the unsigned pointer value stored above, and 64-bit
# HANDLE arguments are truncated before CloseHandle on Win64. With HANDLE as
# restype, a NULL result is returned as ``None``.
_kernel32.CreateFileW.argtypes = [
    ctypes.wintypes.LPCWSTR,  # lpFileName
    ctypes.wintypes.DWORD,  # dwDesiredAccess
    ctypes.wintypes.DWORD,  # dwShareMode
    ctypes.wintypes.LPVOID,  # lpSecurityAttributes (LPSECURITY_ATTRIBUTES; always None here)
    ctypes.wintypes.DWORD,  # dwCreationDisposition
    ctypes.wintypes.DWORD,  # dwFlagsAndAttributes
    ctypes.wintypes.HANDLE,  # hTemplateFile
]
_kernel32.CreateFileW.restype = ctypes.wintypes.HANDLE
_kernel32.CloseHandle.argtypes = [ctypes.wintypes.HANDLE]  # hObject
_kernel32.CloseHandle.restype = ctypes.wintypes.BOOL


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

    Raises:
        OSError: Carrying the native ``winerror`` when CreateFileW fails —
            for example 32 (``ERROR_SHARING_VIOLATION``) when another holder
            already owns the file. The context body is never entered and no
            handle is closed in that case.
    """

    if not path.is_file():
        msg = f"sharing_violation_holder requires an existing file, got {path}"
        raise OSError(msg)
    handle = _kernel32.CreateFileW(
        str(path),
        _GENERIC_READ,
        _SHARE_MODE_NONE,
        None,
        _OPEN_EXISTING,
        0,
        None,
    )
    # Capture the Win32 error before any further call can replace it, and
    # never yield — or close — a handle that was not acquired (AR-13).
    if handle is None or handle == _INVALID_HANDLE_VALUE:
        error_code = ctypes.get_last_error()
        msg = f"CreateFileW failed for sharing violation holder (error {error_code})"
        raise OSError(error_code, msg, str(path), error_code)
    try:
        yield path
    finally:
        _kernel32.CloseHandle(handle)


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
