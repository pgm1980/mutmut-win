"""Windows Job Object wrapper for orphan process protection.

When the parent process dies unexpectedly (crash, Task Manager kill, IDE close),
all worker processes and their subprocess children are automatically terminated
by the OS kernel — preventing CPU overheating from orphaned pytest processes.

Uses ``ctypes.windll.kernel32`` to call the Win32 Job Object API directly.
No external dependencies required.

Graceful degradation: if Job Objects are unavailable (e.g. restricted security
policies), ``create_kill_on_close_job()`` raises ``OSError`` and the caller
should fall back to running without orphan protection.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import logging
import sys

logger = logging.getLogger(__name__)

# Only define the Win32 bindings on Windows.
if sys.platform == "win32":
    _kernel32 = ctypes.windll.kernel32

    # Constants from the Windows SDK.
    _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE: int = 0x2000
    _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION: int = 9
    _PROCESS_ALL_ACCESS: int = 0x1F0FFF

    class _JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):  # noqa: N801
        """Win32 JOBOBJECT_BASIC_LIMIT_INFORMATION structure."""

        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.wintypes.LARGE_INTEGER),
            ("PerJobUserTimeLimit", ctypes.wintypes.LARGE_INTEGER),
            ("LimitFlags", ctypes.wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", ctypes.wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", ctypes.wintypes.DWORD),
            ("SchedulingClass", ctypes.wintypes.DWORD),
        ]

    class _IO_COUNTERS(ctypes.Structure):  # noqa: N801
        """Win32 IO_COUNTERS structure."""

        _fields_ = [
            ("ReadOperationCount", ctypes.c_ulonglong),
            ("WriteOperationCount", ctypes.c_ulonglong),
            ("OtherOperationCount", ctypes.c_ulonglong),
            ("ReadTransferCount", ctypes.c_ulonglong),
            ("WriteTransferCount", ctypes.c_ulonglong),
            ("OtherTransferCount", ctypes.c_ulonglong),
        ]

    class _JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):  # noqa: N801
        """Win32 JOBOBJECT_EXTENDED_LIMIT_INFORMATION structure."""

        _fields_ = [
            ("BasicLimitInformation", _JOBOBJECT_BASIC_LIMIT_INFORMATION),
            ("IoInfo", _IO_COUNTERS),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]


def create_kill_on_close_job() -> int:
    """Create a Windows Job Object that kills all assigned processes on close.

    The ``JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`` flag causes the OS to terminate
    every process in the job when the last handle to the Job Object is closed.
    Since handles are closed automatically when a process exits, this guarantees
    cleanup even on hard kills.

    Returns:
        An opaque handle (integer) to the Job Object.

    Raises:
        OSError: If the Job Object could not be created or configured.
        RuntimeError: If called on a non-Windows platform.
    """
    if sys.platform != "win32":
        msg = "Job Objects are only available on Windows"
        raise RuntimeError(msg)

    handle: int = _kernel32.CreateJobObjectW(None, None)
    if not handle:
        msg = f"CreateJobObjectW failed (error {ctypes.get_last_error()})"
        raise OSError(msg)

    info = _JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
    info.BasicLimitInformation.LimitFlags = _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE

    success: int = _kernel32.SetInformationJobObject(
        handle,
        _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
        ctypes.byref(info),
        ctypes.sizeof(info),
    )
    if not success:
        _kernel32.CloseHandle(handle)
        msg = f"SetInformationJobObject failed (error {ctypes.get_last_error()})"
        raise OSError(msg)

    return handle


def assign_process_to_job(job_handle: int, pid: int) -> None:
    """Add a process (by PID) to the Job Object.

    Opens the process with full access, assigns it to the job, then closes
    the process handle (the job keeps its own reference).

    Args:
        job_handle: Handle returned by ``create_kill_on_close_job()``.
        pid: Process ID of the child to assign.

    Raises:
        OSError: If the process could not be opened or assigned.
    """
    if sys.platform != "win32":
        msg = "Job Objects are only available on Windows"
        raise RuntimeError(msg)

    process_handle: int = _kernel32.OpenProcess(_PROCESS_ALL_ACCESS, False, pid)
    if not process_handle:
        msg = f"OpenProcess({pid}) failed (error {ctypes.get_last_error()})"
        raise OSError(msg)

    try:
        success: int = _kernel32.AssignProcessToJobObject(job_handle, process_handle)
        if not success:
            msg = f"AssignProcessToJobObject failed for PID {pid} (error {ctypes.get_last_error()})"
            raise OSError(msg)
    finally:
        _kernel32.CloseHandle(process_handle)


def close_job(job_handle: int) -> None:
    """Close the Job Object handle.

    If ``JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`` is set and this is the last
    handle, the OS terminates all processes in the job.

    Args:
        job_handle: Handle returned by ``create_kill_on_close_job()``.
    """
    if sys.platform != "win32":
        return
    _kernel32.CloseHandle(job_handle)
