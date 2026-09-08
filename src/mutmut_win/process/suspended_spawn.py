"""Windows multiprocessing spawn with containment before interpreter startup.

The standard Windows ``multiprocessing`` spawn backend starts Python normally;
``site``, ``.pth`` files and ``sitecustomize`` therefore run before a Python
target-level handshake can assign the worker to a Job Object.  This module is
the narrow, version-guarded variant of CPython's ``popen_spawn_win32.Popen``
needed by mutmut-win: create the interpreter with ``CREATE_SUSPENDED``, assign
its process handle to the parent-owned kill-on-close Job, then resume the
primary thread.  The private protocol is audited specifically for CPython
3.14.7 on Windows.
"""

from __future__ import annotations

import contextlib
import os
import sys
import tempfile
from multiprocessing.context import SpawnProcess
from typing import TYPE_CHECKING, Any, BinaryIO

from mutmut_win.exceptions import ProcessContainmentError

if TYPE_CHECKING:
    from collections.abc import Callable

_CREATE_SUSPENDED = 0x00000004
_CONTAINMENT_ABORT_EXIT_CODE = 70


def _require_supported_runtime() -> None:
    """Fail closed outside the sole supported runtime and platform."""
    version = tuple(sys.version_info[:3])
    if sys.platform != "win32" or sys.implementation.name != "cpython" or version != (3, 14, 7):
        raise ProcessContainmentError(
            "Race-free Windows worker containment is audited only for "
            "Windows with CPython 3.14.7; refusing to use unsupported private "
            "multiprocessing internals."
        )


def _abort_created_process(api: Any, process_handle: int, thread_handle: int) -> None:
    """Terminate and close a child whose pre-resume containment failed."""
    with contextlib.suppress(BaseException):
        api.TerminateProcess(process_handle, _CONTAINMENT_ABORT_EXIT_CODE)
    with contextlib.suppress(BaseException):
        api.WaitForSingleObject(process_handle, 5_000)
    with contextlib.suppress(BaseException):
        api.CloseHandle(thread_handle)
    with contextlib.suppress(BaseException):
        api.CloseHandle(process_handle)


def _close_spawn_resources(api: Any, process_handle: int, bootstrap_file: BinaryIO) -> None:
    """Close the parent-side resources retained for one spawned worker."""
    with contextlib.suppress(BaseException):
        bootstrap_file.close()
    with contextlib.suppress(BaseException):
        api.CloseHandle(process_handle)


def _windows_suspended_popen(process_obj: Any, job_handle: int) -> Any:
    """Return a CPython-compatible Popen after assign-before-resume."""
    if sys.platform != "win32":
        raise ProcessContainmentError("suspended Windows spawn requested off Windows")
    _require_supported_runtime()

    import msvcrt
    from multiprocessing import popen_spawn_win32 as backend_module

    from mutmut_win.process.atomic_spawn import atomic_create_process_in_job
    from mutmut_win.process.job_object import resume_thread_handle

    # Typeshed intentionally exposes only the public multiprocessing surface;
    # every attribute used below is part of the audited private CPython backend.
    backend: Any = backend_module

    class SuspendedJobPopen(backend.Popen):  # type: ignore[misc]
        """CPython spawn Popen with one additional pre-resume safety step."""

        def __init__(self, child_process: Any) -> None:
            preparation = backend.spawn.get_preparation_data(child_process._name)
            # A regular temporary file deliberately replaces CPython's anonymous
            # bootstrap pipe.  With a pipe, a large pickled config can fill the
            # kernel buffer while site/.pth/sitecustomize is wedged and has not
            # started reading, causing Process.start() itself to hang before the
            # executor watchdog exists.  The secure delete-on-close file can be
            # populated completely while the child is still suspended; the child
            # later duplicates the handle exactly as spawn_main() duplicates the
            # standard pipe handle.
            bootstrap_file = tempfile.TemporaryFile(mode="w+b")  # noqa: SIM115 - retained by Popen until child exit
            bootstrap_handle = msvcrt.get_osfhandle(bootstrap_file.fileno())
            command = backend.spawn.get_command_line(
                parent_pid=os.getpid(),
                pipe_handle=bootstrap_handle,
            )

            python_executable = backend.spawn.get_executable()
            if backend.WINENV and backend._path_eq(python_executable, sys.executable):
                command[0] = python_executable = getattr(sys, "_base_executable", sys.executable)
                environment = os.environ.copy()
                environment["__PYVENV_LAUNCHER__"] = sys.executable
            else:
                environment = None

            command_line = " ".join(f'"{part}"' for part in command)
            startup_info_factory = getattr(backend, "STARTUPINFO", None)
            startup_info = (
                startup_info_factory(dwFlags=backend.STARTF_FORCEOFFFEEDBACK)
                if startup_info_factory is not None
                else None
            )

            process_handle: int | None = None
            thread_handle: int | None = None
            try:
                process_handle, thread_handle, pid, _tid = atomic_create_process_in_job(
                    python_executable,
                    command_line,
                    job_handle=job_handle,
                    inherit_handles=False,
                    creationflags=_CREATE_SUSPENDED,
                    environment=environment,
                    current_directory=None,
                    startupinfo=startup_info,
                )
                self.pid = pid
                self.returncode = None
                self._handle = process_handle
                self.sentinel = int(process_handle)

                # Queue handles embedded in child_process can be duplicated only
                # after CreateProcess gives us the target process handle.  Dump
                # them to seekable storage before ResumeThread so the parent's
                # start path never depends on child bootstrap progress.
                backend.set_spawning_popen(self)
                try:
                    backend.reduction.dump(preparation, bootstrap_file)
                    backend.reduction.dump(child_process, bootstrap_file)
                finally:
                    backend.set_spawning_popen(None)
                bootstrap_file.flush()
                bootstrap_file.seek(0)

                resume_thread_handle(thread_handle)
                backend._winapi.CloseHandle(thread_handle)
                thread_handle = None

                # Retain the readable file until spawn_main() has duplicated and
                # consumed its handle.  Closing the Process/Popen later removes
                # the delete-on-close file and the process handle together.
                self._bootstrap_file = bootstrap_file
                self.finalizer = backend.util.Finalize(
                    self,
                    _close_spawn_resources,
                    (backend._winapi, self.sentinel, bootstrap_file),
                )
            except BaseException:
                if process_handle is not None and thread_handle is not None:
                    _abort_created_process(
                        backend._winapi,
                        process_handle,
                        thread_handle,
                    )
                elif process_handle is not None:
                    with contextlib.suppress(BaseException):
                        backend._winapi.TerminateProcess(
                            process_handle,
                            _CONTAINMENT_ABORT_EXIT_CODE,
                        )
                    with contextlib.suppress(BaseException):
                        backend._winapi.CloseHandle(process_handle)
                bootstrap_file.close()
                raise

    try:
        return SuspendedJobPopen(process_obj)
    except ProcessContainmentError:
        raise
    except BaseException as exc:
        raise ProcessContainmentError(
            "Could not create, assign, and resume a contained Windows worker process."
        ) from exc


class JobContainedSpawnProcess(SpawnProcess):
    """SpawnProcess whose interpreter is inside the Job before it runs."""

    def __init__(
        self,
        *,
        job_handle: int,
        target: Callable[..., object],
        args: tuple[object, ...],
        daemon: bool,
    ) -> None:
        self._containment_job_handle = job_handle
        super().__init__(target=target, args=args, daemon=daemon)

    @staticmethod
    def _Popen(process_obj: Any) -> Any:  # noqa: N802 - multiprocessing hook
        job_handle = getattr(process_obj, "_containment_job_handle", None)
        if not isinstance(job_handle, int) or job_handle <= 0:
            raise ProcessContainmentError(
                "Windows worker process has no valid parent-owned Job handle."
            )
        return _windows_suspended_popen(process_obj, job_handle)
