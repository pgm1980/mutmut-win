"""Windows Job Object wrapper for orphan process protection.

When the parent process dies unexpectedly (crash, Task Manager kill, IDE close),
all worker processes and their subprocess children are automatically terminated
by the OS kernel — preventing CPU overheating from orphaned pytest processes.

Uses a private ``ctypes.WinDLL("kernel32", use_last_error=True)`` instance to
call the Win32 Job Object API directly. No external dependencies required.

If Job Objects are unavailable (for example under a restricted security
policy), ``create_kill_on_close_job()`` raises ``OSError``. Production process
launchers treat that as a containment failure and refuse to resume or dispatch
work on Windows.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import logging
import sys
from typing import Any

logger = logging.getLogger(__name__)

# Only define the Win32 bindings on Windows.
if sys.platform == "win32":
    # A private WinDLL instance with use_last_error=True: ctypes then captures
    # GetLastError() into a thread-local copy immediately after every foreign
    # call, so ``ctypes.get_last_error()`` reports the real Win32 error code.
    # The shared ``ctypes.windll.kernel32`` lacks this flag and always reported
    # 0 in our OSError messages (audit finding A2-JT-005).
    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    # Constants from the Windows SDK.
    _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE: int = 0x2000
    _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION: int = 9
    # Least-privilege access mask for AssignProcessToJobObject, which only
    # requires PROCESS_SET_QUOTA (0x0100) | PROCESS_TERMINATE (0x0001). The
    # previous PROCESS_ALL_ACCESS (0x1F0FFF) was over-privileged (A2-JT-017).
    _PROCESS_ASSIGN_ACCESS: int = 0x0100 | 0x0001

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

    # Explicit C signatures (audit finding A2-JT-006). Without argtypes/restype
    # ctypes defaults every parameter and return value to c_int, silently
    # truncating 64-bit HANDLE values on Win64. With HANDLE as restype, a NULL
    # result is returned as ``None`` (hence the ``int | None`` locals below).
    _kernel32.CreateJobObjectW.argtypes = [
        ctypes.wintypes.LPVOID,  # lpJobAttributes (LPSECURITY_ATTRIBUTES)
        ctypes.wintypes.LPCWSTR,  # lpName
    ]
    _kernel32.CreateJobObjectW.restype = ctypes.wintypes.HANDLE

    _kernel32.SetInformationJobObject.argtypes = [
        ctypes.wintypes.HANDLE,  # hJob
        ctypes.c_int,  # JobObjectInformationClass (JOBOBJECTINFOCLASS enum)
        ctypes.wintypes.LPVOID,  # lpJobObjectInformation
        ctypes.wintypes.DWORD,  # cbJobObjectInformationLength
    ]
    _kernel32.SetInformationJobObject.restype = ctypes.wintypes.BOOL

    _kernel32.AssignProcessToJobObject.argtypes = [
        ctypes.wintypes.HANDLE,  # hJob
        ctypes.wintypes.HANDLE,  # hProcess
    ]
    _kernel32.AssignProcessToJobObject.restype = ctypes.wintypes.BOOL

    _kernel32.OpenProcess.argtypes = [
        ctypes.wintypes.DWORD,  # dwDesiredAccess
        ctypes.wintypes.BOOL,  # bInheritHandle
        ctypes.wintypes.DWORD,  # dwProcessId
    ]
    _kernel32.OpenProcess.restype = ctypes.wintypes.HANDLE

    _kernel32.CloseHandle.argtypes = [ctypes.wintypes.HANDLE]  # hObject
    _kernel32.CloseHandle.restype = ctypes.wintypes.BOOL

    _kernel32.ResumeThread.argtypes = [ctypes.wintypes.HANDLE]
    _kernel32.ResumeThread.restype = ctypes.wintypes.DWORD
else:
    # Public functions reject non-Windows callers before using these names.
    # Explicit placeholders retain that runtime contract while allowing the
    # same module to be checked under both Windows and POSIX typeshed views.
    _kernel32: Any = None
    _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0
    _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 0
    _PROCESS_ASSIGN_ACCESS = 0
    _JOBOBJECT_EXTENDED_LIMIT_INFORMATION: Any = None


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

    handle: int | None = _kernel32.CreateJobObjectW(None, None)
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

    Opens the process with the least-privilege access mask required by
    ``AssignProcessToJobObject`` (``PROCESS_SET_QUOTA | PROCESS_TERMINATE``),
    assigns it to the job, then closes the process handle (the job keeps
    its own reference).

    Production callers prevent work during assignment. Direct subprocesses
    start with ``CREATE_SUSPENDED`` and use this PID-based helper before they
    resume. Worker-pool interpreters use ``assign_process_handle_to_job`` on
    the handle returned by ``CreateProcess`` while their primary thread is
    still suspended. Assignment failure is therefore handled before any
    uncontained Python startup or task code can run.

    Args:
        job_handle: Handle returned by ``create_kill_on_close_job()``.
        pid: Process ID of the child to assign.

    Raises:
        OSError: If the process could not be opened or assigned.
        RuntimeError: If called on a non-Windows platform.
    """
    if sys.platform != "win32":
        msg = "Job Objects are only available on Windows"
        raise RuntimeError(msg)

    process_handle: int | None = _kernel32.OpenProcess(_PROCESS_ASSIGN_ACCESS, False, pid)
    if not process_handle:
        msg = f"OpenProcess({pid}) failed (error {ctypes.get_last_error()})"
        raise OSError(msg)

    try:
        assign_process_handle_to_job(job_handle, process_handle)
    finally:
        _kernel32.CloseHandle(process_handle)


def assign_process_handle_to_job(job_handle: int, process_handle: int) -> None:
    """Assign an already-open process handle to a Job Object.

    This is the race-free primitive for ``CREATE_SUSPENDED`` launchers: no
    Python startup code runs before the handle is assigned.
    """
    if sys.platform != "win32":
        msg = "Job Objects are only available on Windows"
        raise RuntimeError(msg)
    success: int = _kernel32.AssignProcessToJobObject(job_handle, process_handle)
    if not success:
        msg = f"AssignProcessToJobObject failed (error {ctypes.get_last_error()})"
        raise OSError(msg)


def resume_thread_handle(thread_handle: int) -> None:
    """Resume a primary thread created with ``CREATE_SUSPENDED``."""
    if sys.platform != "win32":
        msg = "ResumeThread is only available on Windows"
        raise RuntimeError(msg)
    previous_suspend_count: int = _kernel32.ResumeThread(thread_handle)
    if previous_suspend_count == 0xFFFFFFFF:
        msg = f"ResumeThread failed (error {ctypes.get_last_error()})"
        raise OSError(msg)


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
