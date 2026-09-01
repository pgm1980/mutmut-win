"""Atomic Windows process creation inside a kill-on-close Job Object.

``CREATE_SUSPENDED`` prevents child code from running before a later
``AssignProcessToJobObject`` call, but it cannot make the two kernel calls
atomic: a hard parent exit between them leaves a stopped orphan.  Windows 10
and Server 2016 introduced ``PROC_THREAD_ATTRIBUTE_JOB_LIST`` specifically for
this boundary.  Passing the Job in ``STARTUPINFOEX`` makes membership part of
``CreateProcessW`` itself -- the child is never observable outside the Job.

The module also provides a narrow ``subprocess.Popen`` adapter.  It mirrors the
CPython 3.12-3.14 Windows handle plumbing and replaces only the final process
creation call.  Unknown runtimes and unsupported startup attributes fail
closed rather than silently falling back to post-start assignment.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import os
import subprocess
import sys
import warnings
from pathlib import Path
from typing import TYPE_CHECKING, Any

from mutmut_win.exceptions import ProcessContainmentError

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

_CREATE_UNICODE_ENVIRONMENT = 0x00000400
_EXTENDED_STARTUPINFO_PRESENT = 0x00080000
_PROC_THREAD_ATTRIBUTE_HANDLE_LIST = 0x00020002
_PROC_THREAD_ATTRIBUTE_JOB_LIST = 0x0002000D
_ERROR_INSUFFICIENT_BUFFER = 122


def require_atomic_spawn_runtime() -> None:
    """Fail closed outside the CPython versions audited by this adapter."""
    version = sys.version_info[:2]
    if sys.implementation.name != "cpython" or not (3, 12) <= version < (3, 15):
        raise ProcessContainmentError(
            "Atomic Windows process containment is audited only for "
            "CPython 3.12-3.14; refusing unknown process internals."
        )


if sys.platform == "win32":
    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    class _STARTUPINFOW(ctypes.Structure):
        _fields_ = [
            ("cb", ctypes.wintypes.DWORD),
            ("lpReserved", ctypes.wintypes.LPWSTR),
            ("lpDesktop", ctypes.wintypes.LPWSTR),
            ("lpTitle", ctypes.wintypes.LPWSTR),
            ("dwX", ctypes.wintypes.DWORD),
            ("dwY", ctypes.wintypes.DWORD),
            ("dwXSize", ctypes.wintypes.DWORD),
            ("dwYSize", ctypes.wintypes.DWORD),
            ("dwXCountChars", ctypes.wintypes.DWORD),
            ("dwYCountChars", ctypes.wintypes.DWORD),
            ("dwFillAttribute", ctypes.wintypes.DWORD),
            ("dwFlags", ctypes.wintypes.DWORD),
            ("wShowWindow", ctypes.wintypes.WORD),
            ("cbReserved2", ctypes.wintypes.WORD),
            ("lpReserved2", ctypes.POINTER(ctypes.wintypes.BYTE)),
            ("hStdInput", ctypes.wintypes.HANDLE),
            ("hStdOutput", ctypes.wintypes.HANDLE),
            ("hStdError", ctypes.wintypes.HANDLE),
        ]

    class _STARTUPINFOEXW(ctypes.Structure):
        _fields_ = [
            ("StartupInfo", _STARTUPINFOW),
            ("lpAttributeList", ctypes.wintypes.LPVOID),
        ]

    class _PROCESS_INFORMATION(ctypes.Structure):  # noqa: N801
        _fields_ = [
            ("hProcess", ctypes.wintypes.HANDLE),
            ("hThread", ctypes.wintypes.HANDLE),
            ("dwProcessId", ctypes.wintypes.DWORD),
            ("dwThreadId", ctypes.wintypes.DWORD),
        ]

    _kernel32.InitializeProcThreadAttributeList.argtypes = [
        ctypes.wintypes.LPVOID,
        ctypes.wintypes.DWORD,
        ctypes.wintypes.DWORD,
        ctypes.POINTER(ctypes.c_size_t),
    ]
    _kernel32.InitializeProcThreadAttributeList.restype = ctypes.wintypes.BOOL
    _kernel32.UpdateProcThreadAttribute.argtypes = [
        ctypes.wintypes.LPVOID,
        ctypes.wintypes.DWORD,
        ctypes.c_size_t,
        ctypes.wintypes.LPVOID,
        ctypes.c_size_t,
        ctypes.wintypes.LPVOID,
        ctypes.POINTER(ctypes.c_size_t),
    ]
    _kernel32.UpdateProcThreadAttribute.restype = ctypes.wintypes.BOOL
    _kernel32.DeleteProcThreadAttributeList.argtypes = [ctypes.wintypes.LPVOID]
    _kernel32.DeleteProcThreadAttributeList.restype = None
    _kernel32.CreateProcessW.argtypes = [
        ctypes.wintypes.LPCWSTR,
        ctypes.wintypes.LPWSTR,
        ctypes.wintypes.LPVOID,
        ctypes.wintypes.LPVOID,
        ctypes.wintypes.BOOL,
        ctypes.wintypes.DWORD,
        ctypes.wintypes.LPVOID,
        ctypes.wintypes.LPCWSTR,
        ctypes.POINTER(_STARTUPINFOW),
        ctypes.POINTER(_PROCESS_INFORMATION),
    ]
    _kernel32.CreateProcessW.restype = ctypes.wintypes.BOOL
else:
    # These bindings intentionally do not exist at runtime off Windows.  The
    # public helpers reject that platform before dereferencing them, while the
    # declarations keep cross-platform static analysis aware of those names.
    _kernel32: Any = None
    _STARTUPINFOEXW: Any = None
    _PROCESS_INFORMATION: Any = None


def _winerror(operation: str) -> OSError:
    # ``ctypes`` exposes these helpers only on Windows in typeshed.  Runtime
    # behavior remains the direct Win32 implementation; the targeted ignores
    # cover only the opposite platform's typeshed view.
    code = ctypes.get_last_error()  # type: ignore[attr-defined,unused-ignore]
    error: OSError = ctypes.WinError(code)  # type: ignore[attr-defined,unused-ignore]
    error.add_note(operation)
    return error


def _environment_block(environment: Mapping[str, str] | None) -> Any:
    if environment is None:
        return None
    # CreateProcessW requires a sorted, double-NUL-terminated Unicode block.
    entries = [f"{key}={value}" for key, value in environment.items()]
    entries.sort(key=str.casefold)
    return ctypes.create_unicode_buffer("\0".join(entries) + "\0\0")


def atomic_create_process_in_job(
    application_name: str | None,
    command_line: str,
    *,
    job_handle: int,
    inherit_handles: bool,
    creationflags: int,
    environment: Mapping[str, str] | None,
    current_directory: str | None,
    startupinfo: Any,
    handle_list: Sequence[int] = (),
) -> tuple[int, int, int, int]:
    """Create a process atomically inside *job_handle*.

    Returns ``(process_handle, thread_handle, pid, tid)`` like
    ``_winapi.CreateProcess``.  The caller owns both returned handles.
    """
    if sys.platform != "win32":
        raise ProcessContainmentError("atomic Windows spawn requested off Windows")
    require_atomic_spawn_runtime()
    if not isinstance(job_handle, int) or job_handle <= 0:
        raise ProcessContainmentError("atomic Windows spawn requires a valid Job handle")

    startup_ex = _STARTUPINFOEXW()
    startup_ex.StartupInfo.cb = ctypes.sizeof(_STARTUPINFOEXW)
    for field in (
        "lpReserved",
        "lpDesktop",
        "lpTitle",
        "dwX",
        "dwY",
        "dwXSize",
        "dwYSize",
        "dwXCountChars",
        "dwYCountChars",
        "dwFillAttribute",
        "dwFlags",
        "wShowWindow",
        "cbReserved2",
        "lpReserved2",
        "hStdInput",
        "hStdOutput",
        "hStdError",
    ):
        value = getattr(startupinfo, field, None)
        if value is not None:
            setattr(startup_ex.StartupInfo, field, value)

    handles = tuple(dict.fromkeys(int(handle) for handle in handle_list))
    attribute_count = 1 + bool(handles)
    attribute_size = ctypes.c_size_t()
    ctypes.set_last_error(0)
    _kernel32.InitializeProcThreadAttributeList(
        None,
        attribute_count,
        0,
        ctypes.byref(attribute_size),
    )
    if attribute_size.value == 0 or ctypes.get_last_error() != _ERROR_INSUFFICIENT_BUFFER:
        raise _winerror("InitializeProcThreadAttributeList(size)")

    attribute_buffer = ctypes.create_string_buffer(attribute_size.value)
    attribute_list = ctypes.cast(attribute_buffer, ctypes.wintypes.LPVOID)
    if not _kernel32.InitializeProcThreadAttributeList(
        attribute_list,
        attribute_count,
        0,
        ctypes.byref(attribute_size),
    ):
        raise _winerror("InitializeProcThreadAttributeList")

    job_array = (ctypes.wintypes.HANDLE * 1)(job_handle)
    handle_array: Any = None
    try:
        if not _kernel32.UpdateProcThreadAttribute(
            attribute_list,
            0,
            _PROC_THREAD_ATTRIBUTE_JOB_LIST,
            ctypes.cast(job_array, ctypes.wintypes.LPVOID),
            ctypes.sizeof(job_array),
            None,
            None,
        ):
            raise _winerror("UpdateProcThreadAttribute(JOB_LIST)")

        if handles:
            handle_array = (ctypes.wintypes.HANDLE * len(handles))(*handles)
            if not _kernel32.UpdateProcThreadAttribute(
                attribute_list,
                0,
                _PROC_THREAD_ATTRIBUTE_HANDLE_LIST,
                ctypes.cast(handle_array, ctypes.wintypes.LPVOID),
                ctypes.sizeof(handle_array),
                None,
                None,
            ):
                raise _winerror("UpdateProcThreadAttribute(HANDLE_LIST)")

        startup_ex.lpAttributeList = attribute_list
        command_buffer = ctypes.create_unicode_buffer(command_line)
        environment_buffer = _environment_block(environment)
        environment_pointer = (
            ctypes.cast(environment_buffer, ctypes.wintypes.LPVOID)
            if environment_buffer is not None
            else None
        )
        flags = creationflags | _EXTENDED_STARTUPINFO_PRESENT
        if environment is not None:
            flags |= _CREATE_UNICODE_ENVIRONMENT
        process_info = _PROCESS_INFORMATION()
        if not _kernel32.CreateProcessW(
            application_name,
            command_buffer,
            None,
            None,
            bool(inherit_handles),
            flags,
            environment_pointer,
            current_directory,
            ctypes.byref(startup_ex.StartupInfo),
            ctypes.byref(process_info),
        ):
            raise _winerror("CreateProcessW(PROC_THREAD_ATTRIBUTE_JOB_LIST)")
        return (
            int(process_info.hProcess),
            int(process_info.hThread),
            int(process_info.dwProcessId),
            int(process_info.dwThreadId),
        )
    finally:
        _kernel32.DeleteProcThreadAttributeList(attribute_list)


class AtomicJobPopen(subprocess.Popen[bytes]):
    """``Popen`` whose Windows child is born inside a Job Object."""

    def __init__(self, *args: Any, job_handle: int, **kwargs: Any) -> None:
        self._atomic_job_handle = job_handle
        super().__init__(*args, **kwargs)

    # This is the CPython 3.12-3.14 Windows implementation with only the final
    # CreateProcess call replaced.  Keeping it local avoids a process-global
    # monkeypatch of ``_winapi.CreateProcess`` that would race unrelated threads.
    def _execute_child(
        self,
        args: Any,
        executable: Any,
        preexec_fn: Any,
        close_fds: bool,
        pass_fds: tuple[int, ...],
        cwd: Any,
        env: Mapping[str, str] | None,
        startupinfo: Any,
        creationflags: int,
        shell: bool,
        p2cread: int,
        p2cwrite: int,
        c2pread: int,
        c2pwrite: int,
        errread: int,
        errwrite: int,
        unused_restore_signals: bool,
        unused_gid: Any,
        unused_gids: Any,
        unused_uid: Any,
        unused_umask: int,
        unused_start_new_session: bool,
        unused_process_group: int,
    ) -> None:
        del (
            preexec_fn,
            unused_restore_signals,
            unused_gid,
            unused_gids,
            unused_uid,
            unused_umask,
            unused_start_new_session,
            unused_process_group,
        )
        require_atomic_spawn_runtime()
        if pass_fds:
            raise ProcessContainmentError("pass_fds is unsupported on Windows")

        if isinstance(args, str):
            command_line = args
        elif isinstance(args, bytes):
            if shell:
                raise TypeError("bytes args is not allowed when shell is true")
            command_line = subprocess.list2cmdline([args])
        elif isinstance(args, os.PathLike):
            if shell:
                raise TypeError("path-like args is not allowed when shell is true")
            command_line = subprocess.list2cmdline([args])
        else:
            command_line = subprocess.list2cmdline(args)

        if executable is not None:
            executable = os.fsdecode(executable)
        startupinfo = (
            subprocess.STARTUPINFO()  # type: ignore[attr-defined,unused-ignore]
            if startupinfo is None
            else startupinfo.copy()
        )

        use_std_handles = -1 not in (p2cread, c2pwrite, errwrite)
        if use_std_handles:
            import _winapi

            startupinfo.dwFlags |= _winapi.STARTF_USESTDHANDLES  # type: ignore[attr-defined,unused-ignore]
            startupinfo.hStdInput = p2cread
            startupinfo.hStdOutput = c2pwrite
            startupinfo.hStdError = errwrite

        attribute_list = startupinfo.lpAttributeList
        unknown_attributes = set(attribute_list or ()) - {"handle_list"}
        if unknown_attributes:
            raise ProcessContainmentError(
                f"unsupported Windows startup attributes: {sorted(unknown_attributes)!r}"
            )
        have_handle_list = bool(
            attribute_list and "handle_list" in attribute_list and attribute_list["handle_list"]
        )
        if have_handle_list or (use_std_handles and close_fds):
            if attribute_list is None:
                attribute_list = startupinfo.lpAttributeList = {}
            handle_list = attribute_list["handle_list"] = list(
                attribute_list.get("handle_list", [])
            )
            if use_std_handles:
                handle_list += [int(p2cread), int(c2pwrite), int(errwrite)]
            handle_list[:] = self._filter_handle_list(handle_list)  # type: ignore[attr-defined]
            if handle_list:
                if not close_fds:
                    warnings.warn(
                        "startupinfo.lpAttributeList['handle_list'] overriding close_fds",
                        RuntimeWarning,
                        stacklevel=2,
                    )
                close_fds = False
        else:
            handle_list = []

        if shell:
            import _winapi

            startupinfo.dwFlags |= _winapi.STARTF_USESHOWWINDOW  # type: ignore[attr-defined,unused-ignore]
            startupinfo.wShowWindow = _winapi.SW_HIDE  # type: ignore[attr-defined,unused-ignore]
            if not executable:
                comspec = os.environ.get("COMSPEC")
                if not comspec:
                    system_root = os.environ.get("SYSTEMROOT", "")
                    comspec = str(Path(system_root) / "System32" / "cmd.exe")
                    if not Path(comspec).is_absolute():
                        raise FileNotFoundError(
                            "shell not found: neither %ComSpec% nor %SystemRoot% is set"
                        )
                if Path(comspec).is_absolute():
                    executable = comspec
            else:
                comspec = executable
            command_line = f'{comspec} /c "{command_line}"'

        if cwd is not None:
            cwd = os.fsdecode(cwd)
        sys.audit("subprocess.Popen", executable, command_line, cwd, env)
        try:
            process_handle, thread_handle, pid, _tid = atomic_create_process_in_job(
                executable,
                command_line,
                job_handle=self._atomic_job_handle,
                inherit_handles=not close_fds,
                creationflags=creationflags,
                environment=env,
                current_directory=cwd,
                startupinfo=startupinfo,
                handle_list=handle_list,
            )
        finally:
            self._close_pipe_fds(  # type: ignore[attr-defined]
                p2cread,
                p2cwrite,
                c2pread,
                c2pwrite,
                errread,
                errwrite,
            )

        import _winapi

        self._child_created = True
        self._handle = subprocess.Handle(process_handle)  # type: ignore[attr-defined,unused-ignore]
        self.pid = pid
        _winapi.CloseHandle(thread_handle)  # type: ignore[attr-defined,unused-ignore]


__all__ = [
    "AtomicJobPopen",
    "atomic_create_process_in_job",
    "require_atomic_spawn_runtime",
]
