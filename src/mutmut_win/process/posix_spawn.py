"""Spawn multiprocessing children in POSIX sessions before interpreter startup.

CPython's regular POSIX ``spawn`` backend serialises the process into memory,
starts the new interpreter, and then writes the complete payload through a
bounded pipe. If ``site``/``.pth``/``sitecustomize`` wedges before
``spawn_main()`` starts reading, a sufficiently large payload blocks
``Process.start()`` itself and no caller-side watchdog can run.

This audited backend writes the payload completely to an anonymous seekable
temporary file *before* the child exists. The child inherits that read handle
plus a separate parent-liveness pipe and enters its own session in the
``fork_exec`` boundary. Once this module's child entry point runs, a sentinel
watchdog kills the complete session if the parent disappears. Linux also arms
``PR_SET_PDEATHSIG`` as the first operation in this module's private child
entry point. Running Python callbacks between ``fork`` and ``exec`` would add
an unbounded deadlock risk in multithreaded parents, so interpreter/module
startup before that entry remains an explicit boundary on every POSIX system;
all post-entry work is covered by the kernel signal and EOF watchdog.
"""

from __future__ import annotations

import contextlib
import ctypes
import os
import signal
import sys
import tempfile
import threading
import time
from multiprocessing.context import SpawnProcess
from typing import TYPE_CHECKING, Any

from mutmut_win.exceptions import ProcessContainmentError

if TYPE_CHECKING:
    from collections.abc import Callable

_SPAWN_ABORT_REAP_SECONDS = 2.0
_CONTAINMENT_ABORT_EXIT_CODE = 70
_PR_SET_PDEATHSIG = 1
_PARENT_DEATH_SIGNAL = getattr(signal, "SIGUSR1", signal.SIGTERM)
_KILL_SIGNAL: int = getattr(signal, "SIGKILL", 9)

_linux_prctl: Any | None = None
if sys.platform.startswith("linux"):
    _linux_libc = ctypes.CDLL(None, use_errno=True)
    _linux_prctl = _linux_libc.prctl
    _linux_prctl.argtypes = [
        ctypes.c_int,
        ctypes.c_ulong,
        ctypes.c_ulong,
        ctypes.c_ulong,
        ctypes.c_ulong,
    ]
    _linux_prctl.restype = ctypes.c_int


def _require_supported_runtime() -> None:
    version = sys.version_info[:2]
    if sys.implementation.name != "cpython" or not (3, 12) <= version < (3, 15):
        raise ProcessContainmentError(
            "Pre-interpreter POSIX session containment is audited only for CPython 3.12-3.14."
        )


def _arm_linux_parent_death_signal(expected_parent_pid: int) -> None:
    """Arm Linux parent death at the earliest private child-entry boundary."""
    if _linux_prctl is None:
        return
    result = _linux_prctl(_PR_SET_PDEATHSIG, _PARENT_DEATH_SIGNAL, 0, 0, 0)
    if result != 0:
        error_number = ctypes.get_errno()
        raise OSError(error_number, "prctl(PR_SET_PDEATHSIG) failed")
    # PR_SET_PDEATHSIG is armed only for future parent death. Close the race in
    # which the original parent exited immediately before the prctl call.
    if os.getppid() != expected_parent_pid:
        os.kill(os.getpid(), _KILL_SIGNAL)
        os._exit(_CONTAINMENT_ABORT_EXIT_CODE)


def _kill_own_process_group(process_group: int) -> None:
    """Kill the complete contained session, then fail closed if killpg failed."""
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.killpg(  # type: ignore[attr-defined,unused-ignore]
            process_group,
            _KILL_SIGNAL,
        )
    os._exit(_CONTAINMENT_ABORT_EXIT_CODE)


def _watch_parent_sentinel(parent_sentinel_fd: int, process_group: int) -> None:
    """Block on the liveness pipe and kill the session when its writer closes."""
    while True:
        try:
            chunk = os.read(parent_sentinel_fd, 1)
        except InterruptedError:
            continue
        except OSError:
            break
        if not chunk:
            break
    _kill_own_process_group(process_group)


def _install_parent_liveness_guard(parent_sentinel_fd: int) -> None:
    """Arm post-entry signal/EOF guards for this dedicated POSIX session."""
    get_process_group = getattr(os, "getpgrp", None)
    if not callable(get_process_group):
        raise ProcessContainmentError("POSIX process-group inspection is unavailable")
    process_group = int(get_process_group())
    if process_group != os.getpid():
        raise ProcessContainmentError(
            "POSIX multiprocessing child did not enter its dedicated process session"
        )

    if sys.platform.startswith("linux"):

        def parent_death_signal(_signum: int, _frame: object) -> None:
            _kill_own_process_group(process_group)

        signal.signal(_PARENT_DEATH_SIGNAL, parent_death_signal)

    watchdog = threading.Thread(
        target=_watch_parent_sentinel,
        args=(parent_sentinel_fd, process_group),
        name="mutmut-parent-liveness",
        daemon=True,
    )
    watchdog.start()


def _spawnv_passfds_setsid(
    path: bytes,
    args: list[bytes | str],
    passfds: list[int],
) -> int:
    """CPython ``spawnv_passfds`` with ``call_setsid=True``."""
    _require_supported_runtime()
    if os.name != "posix":
        raise ProcessContainmentError("POSIX session spawn requested off POSIX")
    import _posixsubprocess

    posix_backend: Any = _posixsubprocess
    sorted_fds = tuple(sorted(map(int, passfds)))
    errpipe_read, errpipe_write = os.pipe()
    try:
        return int(
            posix_backend.fork_exec(
                args,
                [path],
                True,
                sorted_fds,
                None,
                None,
                -1,
                -1,
                -1,
                -1,
                -1,
                -1,
                errpipe_read,
                errpipe_write,
                False,
                True,
                -1,
                None,
                None,
                None,
                -1,
                None,
            )
        )
    finally:
        os.close(errpipe_read)
        os.close(errpipe_write)


def _seekable_spawn_main(
    *,
    bootstrap_fd: int,
    parent_sentinel_fd: int,
    tracker_fd: int,
    expected_parent_pid: int,
) -> None:
    """Child entry point matching ``multiprocessing.spawn.spawn_main``.

    ``spawn_main`` overloads its bootstrap pipe as the child-side
    parent-liveness sentinel. A regular file cannot provide EOF-on-parent-
    death, so the custom command supplies the two descriptors separately.
    """
    # Keep this before imports, validation, and all other private bootstrap
    # work. The ppid check inside closes the race where the parent died after
    # composing the command but before the kernel binding was armed.
    _arm_linux_parent_death_signal(expected_parent_pid)
    _require_supported_runtime()
    if os.name != "posix":
        raise ProcessContainmentError("seekable POSIX bootstrap requested off POSIX")

    from multiprocessing import resource_tracker, spawn

    if not spawn.is_forking(sys.argv):
        raise ProcessContainmentError("invalid seekable POSIX multiprocessing bootstrap")
    _install_parent_liveness_guard(parent_sentinel_fd)
    resource_tracker._resource_tracker._fd = tracker_fd  # type: ignore[attr-defined]
    exit_code = spawn._main(bootstrap_fd, parent_sentinel_fd)
    raise SystemExit(exit_code)


def _seekable_command_line(
    *,
    bootstrap_fd: int,
    parent_sentinel_fd: int,
    tracker_fd: int,
    expected_parent_pid: int,
) -> list[bytes | str]:
    """Build the private spawn command for the seekable bootstrap entry point."""
    from multiprocessing import spawn, util

    if getattr(sys, "frozen", False):
        raise ProcessContainmentError(
            "seekable POSIX multiprocessing bootstrap is unavailable in frozen executables"
        )
    program = (
        "from mutmut_win.process.posix_spawn import _seekable_spawn_main; "
        "_seekable_spawn_main("
        f"bootstrap_fd={bootstrap_fd!r}, "
        f"parent_sentinel_fd={parent_sentinel_fd!r}, "
        f"tracker_fd={tracker_fd!r}, "
        f"expected_parent_pid={expected_parent_pid!r})"
    )
    return [
        spawn.get_executable(),
        *util._args_from_interpreter_flags(),  # type: ignore[attr-defined]
        "-c",
        program,
        "--multiprocessing-fork",
    ]


def _close_fd(fd: int | None) -> None:
    if fd is not None:
        with contextlib.suppress(OSError):
            os.close(fd)


def _abort_spawned_session(pid: int) -> None:
    """Kill and bounded-reap a partially constructed session child."""
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.killpg(  # type: ignore[attr-defined,unused-ignore]
            pid,
            signal.SIGKILL,  # type: ignore[attr-defined,unused-ignore]
        )
    # fork_exec may have returned immediately before the child completed
    # setsid().  Direct PID kill closes that tiny cleanup-only race without
    # weakening the process-group sweep for already-started descendants.
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.kill(  # type: ignore[attr-defined,unused-ignore]
            pid,
            signal.SIGKILL,  # type: ignore[attr-defined,unused-ignore]
        )

    deadline = time.monotonic() + _SPAWN_ABORT_REAP_SECONDS
    while time.monotonic() < deadline:
        try:
            waited_pid, _status = os.waitpid(  # type: ignore[attr-defined,unused-ignore]
                pid,
                os.WNOHANG,  # type: ignore[attr-defined,unused-ignore]
            )
        except ChildProcessError:
            return
        except OSError:
            break
        if waited_pid == pid:
            return
        time.sleep(min(0.01, max(0.0, deadline - time.monotonic())))


def _posix_session_popen(process_obj: Any) -> Any:
    from multiprocessing import popen_spawn_posix as backend_module

    backend: Any = backend_module

    class SessionPopen(backend.Popen):  # type: ignore[misc]
        def _launch(self, child_process: Any) -> None:
            from multiprocessing import resource_tracker

            tracker_fd = resource_tracker.getfd()
            if not isinstance(tracker_fd, int) or tracker_fd < 0:
                raise ProcessContainmentError("POSIX resource tracker has no valid descriptor")
            self._fds.append(tracker_fd)
            preparation = backend.spawn.get_preparation_data(child_process._name)

            # POSIX reductions only need ``duplicate_for_child`` to collect the
            # descriptors that fork_exec must preserve, so the complete pickle
            # can be written before the child exists.
            bootstrap_file = tempfile.TemporaryFile(mode="w+b")  # noqa: SIM115
            try:
                backend.set_spawning_popen(self)
                try:
                    backend.reduction.dump(preparation, bootstrap_file)
                    backend.reduction.dump(child_process, bootstrap_file)
                finally:
                    backend.set_spawning_popen(None)
                bootstrap_file.flush()
                bootstrap_file.seek(0)

                parent_read = child_write = child_parent_read = parent_write = None
                spawned_pid: int | None = None
                try:
                    # First pipe: parent observes child exit through parent_read.
                    parent_read, child_write = os.pipe()
                    # Second pipe: child observes parent death through
                    # child_parent_read. It is deliberately distinct from the
                    # seekable bootstrap descriptor.
                    child_parent_read, parent_write = os.pipe()
                    bootstrap_fd = bootstrap_file.fileno()
                    self._fds.extend([bootstrap_fd, child_parent_read, child_write])
                    command = _seekable_command_line(
                        bootstrap_fd=bootstrap_fd,
                        parent_sentinel_fd=child_parent_read,
                        tracker_fd=tracker_fd,
                        expected_parent_pid=os.getpid(),
                    )
                    self.pid = _spawnv_passfds_setsid(
                        backend.spawn.get_executable(),
                        command,
                        self._fds,
                    )
                    spawned_pid = self.pid

                    _close_fd(child_parent_read)
                    child_parent_read = None
                    _close_fd(child_write)
                    child_write = None
                    self.sentinel = parent_read
                    self.finalizer = backend.util.Finalize(
                        self,
                        backend.util.close_fds,
                        [parent_read, parent_write],
                    )
                    # Ownership moved to the finalizer.
                    parent_read = None
                    parent_write = None
                except BaseException:
                    if spawned_pid is not None:
                        _abort_spawned_session(spawned_pid)
                    raise
                finally:
                    for fd in (parent_read, child_write, child_parent_read, parent_write):
                        _close_fd(fd)
            finally:
                # The forked child owns an independent descriptor referring to
                # the same anonymous file; the parent never needs to retain it.
                bootstrap_file.close()

    try:
        return SessionPopen(process_obj)
    except ProcessContainmentError:
        raise
    except BaseException as exc:
        raise ProcessContainmentError(
            "Could not create a multiprocessing child in a pre-interpreter POSIX session."
        ) from exc


class SessionContainedSpawnProcess(SpawnProcess):
    """SpawnProcess whose session and bootstrap are safe before Python startup."""

    def __init__(
        self,
        *,
        target: Callable[..., object],
        args: tuple[object, ...],
        daemon: bool,
    ) -> None:
        super().__init__(target=target, args=args, daemon=daemon)

    @staticmethod
    def _Popen(process_obj: Any) -> Any:  # noqa: N802
        return _posix_session_popen(process_obj)


__all__ = ["SessionContainedSpawnProcess"]
