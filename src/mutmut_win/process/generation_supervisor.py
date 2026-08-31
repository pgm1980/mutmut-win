"""Hard-bounded supervisor for parallel mutant generation.

``ProcessPoolExecutor`` owns a non-daemon management thread.  Killing its
workers and then calling ``shutdown(wait=False)`` is not a hard bound: the
management thread may hold the executor shutdown lock while it joins a broken
worker or queue feeder.  This module therefore keeps the executor in a
dedicated, non-daemon ``multiprocessing`` process.  The caller watches only
that supervisor and can terminate the entire contained process tree without
joining executor internals in the main process.

Containment is established before the supervisor is allowed to create the
executor:

* Windows: the parent creates a kill-on-close Job Object, starts the
  supervisor, assigns it to the job, and only then sends the start command.
  Executor workers and their descendants inherit membership in that job.
* POSIX: the supervisor calls ``setsid()`` before its ready handshake.  The
  resulting process group contains the executor and its descendants and is
  killed with ``killpg`` on abort.

The wire protocol uses a ``multiprocessing.Pipe`` rather than a Queue.  Pipes
have no background feeder thread and their cleanup never calls
``Queue.join_thread()``.
"""

from __future__ import annotations

import contextlib
import math
import multiprocessing
import os
import signal
import sys
import time
import traceback
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from multiprocessing.connection import Connection
    from multiprocessing.process import BaseProcess

    import psutil  # type: ignore[import-untyped]


_READY = "ready"
_START = "start"
_RESULT = "result"
_DONE = "done"
_ERROR = "error"
_SUPERVISOR_NAME = "mutmut-generation-supervisor"
_POLL_FLOOR_SECONDS = 0.0
_PARENT_LIVENESS_POLL_SECONDS = 0.2
# A DONE message is emitted only after ProcessPoolExecutor.shutdown(wait=True),
# but interpreter/resource-tracker teardown can still be slow under host load.
# Keep that healthy teardown distinct from the deliberately short abort bound.
_SUCCESS_JOIN_TIMEOUT_SECONDS = 15.0


@dataclass(frozen=True, slots=True)
class GenerationProgress[ResultT]:
    """One completed file reported by the generation supervisor.

    ``index`` maps the completion back to the corresponding input element.
    Results are returned in input order, while callbacks run in completion
    order.
    """

    index: int
    result: ResultT
    completed: int
    total: int
    supervisor_pid: int


@dataclass(frozen=True, slots=True)
class GenerationCleanupDiagnostics:
    """Bounded-abort outcome attached to supervisor exceptions."""

    supervisor_pid: int | None
    containment: str
    residual_pids: tuple[int, ...]
    join_timed_out: bool


class GenerationSupervisorError(RuntimeError):
    """Base class for generation-supervisor failures."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.cleanup: GenerationCleanupDiagnostics | None = None


class GenerationNoProgressTimeoutError(GenerationSupervisorError):
    """No source file completed within the configured progress window."""


class GenerationSupervisorCrashedError(GenerationSupervisorError):
    """The dedicated supervisor exited without completing its protocol."""


class GenerationSupervisorRemoteError(GenerationSupervisorError):
    """The supervisor or its executor failed and reported diagnostics."""


class GenerationContainmentError(GenerationSupervisorError):
    """The OS process-tree containment boundary could not be established."""


class GenerationProtocolError(GenerationSupervisorError):
    """The supervisor sent a malformed or inconsistent message."""


@dataclass(slots=True)
class _Containment:
    """Parent-owned containment state; closes every handle at most once."""

    job_handle: int | None = None
    process_group: int | None = None

    @property
    def description(self) -> str:
        if sys.platform == "win32":
            return "windows-job-object"
        if os.name == "posix":
            return "posix-process-group"
        return "direct-process-fallback"

    def close_job(self) -> None:
        handle = self.job_handle
        self.job_handle = None
        if handle is None:
            return
        from mutmut_win.process.job_object import close_job

        close_job(handle)


@dataclass(frozen=True, slots=True)
class _TrackedProcess:
    """A psutil process identity retained across the abort operation."""

    process: object
    pid: int


def _send_message(connection: Connection, message: tuple[object, ...]) -> None:
    """Send a protocol message, allowing pickling failures to reach the caller."""
    connection.send(message)


def _send_remote_error(connection: Connection, exc: BaseException) -> bool:
    """Best-effort error notification; parent death must not mask child exit."""
    message = (
        _ERROR,
        f"{type(exc).__module__}.{type(exc).__qualname__}",
        str(exc),
        "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
    )
    try:
        connection.send(message)
    except BaseException:
        return False
    return True


def _parent_connection_closed(connection: Connection) -> bool:
    """Detect parent death without blocking healthy generation work."""
    try:
        if not connection.poll():
            return False
        unexpected = connection.recv()
    except (EOFError, OSError):
        return True
    msg = f"unexpected parent control message after start: {unexpected!r}"
    raise RuntimeError(msg)


def _hard_exit_own_tree() -> None:
    """Last-resort child-side cleanup when the parent pipe disappeared."""
    if os.name == "posix":
        with contextlib.suppress(BaseException):
            process_group = int(
                os.getpgrp()  # type: ignore[attr-defined,unused-ignore]
            )
            os.killpg(  # type: ignore[attr-defined,unused-ignore]
                process_group,
                signal.SIGKILL,  # type: ignore[attr-defined,unused-ignore]
            )
    os._exit(1)


def _establish_posix_session() -> int | None:
    if os.name != "posix":
        return None
    try:
        os.setsid()  # type: ignore[attr-defined,unused-ignore]
    except PermissionError:
        # SessionContainedSpawnProcess establishes this before exec so even
        # .pth/sitecustomize runs in the killable group. A second setsid from
        # the session leader is expected to fail with EPERM.
        if (
            os.getsid(0)  # type: ignore[attr-defined,unused-ignore]
            != os.getpid()
            or os.getpgrp()  # type: ignore[attr-defined,unused-ignore]
            != os.getpid()
        ):
            raise
    return int(os.getpgrp())  # type: ignore[attr-defined,unused-ignore]


def _as_connection(connection: object) -> Connection:
    """Return a Pipe endpoint with one stable type across platform stubs."""
    return cast("Connection", connection)


def _generation_supervisor_main(
    connection: Connection,
    max_children: int,
) -> None:
    """Child entry point.  No executor worker exists before the start command."""
    try:
        process_group = _establish_posix_session()
        _send_message(
            connection,
            (_READY, os.getpid(), process_group, multiprocessing.current_process().daemon),
        )

        try:
            command = connection.recv()
        except EOFError:
            return
        if not isinstance(command, tuple) or len(command) != 3 or command[0] != _START:
            msg = f"unexpected supervisor command: {command!r}"
            raise RuntimeError(msg)
        file_args = cast("Sequence[object]", command[1])
        worker = cast("Callable[[object], object]", command[2])

        spawn_context = multiprocessing.get_context("spawn")
        pool = ProcessPoolExecutor(max_workers=max_children, mp_context=spawn_context)
        completed = 0
        pending = {pool.submit(worker, argument): index for index, argument in enumerate(file_args)}
        while pending:
            done, _not_done = wait(
                pending,
                timeout=_PARENT_LIVENESS_POLL_SECONDS,
                return_when=FIRST_COMPLETED,
            )
            if not done and _parent_connection_closed(connection):
                _hard_exit_own_tree()
            for future in done:
                index = pending.pop(future)
                result = future.result()
                completed += 1
                _send_message(connection, (_RESULT, index, result, completed))

        # A successful DONE means no executor management thread or worker
        # remains.  On every error the parent tears down the containment
        # boundary instead of asking a potentially wedged PPE to shut down.
        pool.shutdown(wait=True)

        _send_message(connection, (_DONE, completed))
    except BaseException as exc:
        if not _send_remote_error(connection, exc):
            _hard_exit_own_tree()
    finally:
        with contextlib.suppress(BaseException):
            connection.close()


def _wait_for_wire_event(
    connection: Connection,
    process: BaseProcess,
    *,
    deadline: float,
) -> tuple[object, ...] | None:
    """Return the next complete message, ``None`` on deadline, or raise on EOF."""
    from multiprocessing.connection import wait as wait_connections

    remaining = max(_POLL_FLOOR_SECONDS, deadline - time.monotonic())
    ready = wait_connections([connection, process.sentinel], timeout=remaining)
    if not ready:
        return None

    # A process can send its final message and exit before the parent wakes;
    # drain the pipe before interpreting a simultaneously-ready sentinel as a
    # crash.
    if connection in ready:
        try:
            message = connection.recv()
        except EOFError:
            message = None
        if message is not None:
            if not isinstance(message, tuple):
                msg = f"supervisor sent non-tuple message: {message!r}"
                raise GenerationProtocolError(msg)
            return cast("tuple[object, ...]", message)

    if process.sentinel in ready or not process.is_alive():
        process.join(timeout=0)
        msg = f"generation supervisor exited unexpectedly (exit code {process.exitcode})"
        raise GenerationSupervisorCrashedError(msg)

    # A closed pipe is itself a protocol-ending crash even if the process
    # sentinel has not propagated through the OS wait set yet.
    msg = "generation supervisor closed its progress pipe unexpectedly"
    raise GenerationSupervisorCrashedError(msg)


def _snapshot_process_tree(pid: int | None) -> list[_TrackedProcess]:
    if pid is None:
        return []
    try:
        import psutil  # type: ignore[import-untyped,unused-ignore]
    except ImportError:  # pragma: no cover - psutil is a required dependency
        return []
    try:
        root = psutil.Process(pid)
    except BaseException:
        return []
    tracked = [_TrackedProcess(process=root, pid=pid)]
    # The root still gives the fallback kill a useful target if descendant
    # enumeration fails.  Containment remains authoritative for the tree.
    with contextlib.suppress(BaseException):
        tracked[0:0] = [
            _TrackedProcess(process=process, pid=process.pid)
            for process in root.children(recursive=True)
        ]
    return tracked


def _tracked_process_is_running(tracked: _TrackedProcess) -> bool:
    try:
        import psutil  # type: ignore[import-untyped,unused-ignore]
    except ImportError:  # pragma: no cover - psutil is a required dependency
        return True
    process = cast("psutil.Process", tracked.process)
    try:
        return bool(process.is_running() and process.status() != psutil.STATUS_ZOMBIE)
    except psutil.NoSuchProcess:
        return False
    except BaseException:
        # An inaccessible identity is diagnostically residual, never silently
        # reported as successfully reaped.
        return True


def _kill_tracked_processes(processes: Sequence[_TrackedProcess], *, deadline: float) -> None:
    for tracked in processes:
        if time.monotonic() >= deadline:
            break
        process = cast("psutil.Process", tracked.process)
        with contextlib.suppress(BaseException):
            process.kill()


def _safe_process_pid(process: BaseProcess) -> int | None:
    try:
        pid = process.pid
    except BaseException:
        return None
    return pid if isinstance(pid, int) else None


def _safe_process_is_alive(process: BaseProcess) -> bool:
    try:
        return process.is_alive()
    except BaseException:
        # Unknown is not success.  Callers retain a residual diagnostic.
        return True


def _abort_supervisor(
    process: BaseProcess,
    containment: _Containment,
    *,
    join_timeout: float,
) -> GenerationCleanupDiagnostics:
    """Hard-kill containment, bounded-join the root, and report survivors."""
    deadline = time.monotonic() + join_timeout
    supervisor_pid = _safe_process_pid(process)
    tracked = _snapshot_process_tree(supervisor_pid)

    # Kernel containment is the primary tree-kill.  Clearing the handle before
    # CloseHandle prevents a later finally block from closing a recycled Win32
    # handle value a second time.
    if sys.platform == "win32":
        with contextlib.suppress(BaseException):
            containment.close_job()
    elif os.name == "posix" and containment.process_group is not None:
        with contextlib.suppress(BaseException):
            os.killpg(containment.process_group, signal.SIGKILL)

    # Belt-and-suspenders fallback for failed assignment, an unavailable
    # process group, or descendants observed before an OS containment failure.
    _kill_tracked_processes(tracked, deadline=deadline)
    if supervisor_pid is not None and _safe_process_is_alive(process):
        with contextlib.suppress(BaseException):
            process.kill()

    remaining = max(0.0, deadline - time.monotonic())
    with contextlib.suppress(BaseException):
        process.join(timeout=remaining)

    # Poll known identities only until the same absolute deadline.  psutil's
    # Process identity includes create time, avoiding false residuals on PID
    # reuse.
    while time.monotonic() < deadline:
        if not any(_tracked_process_is_running(item) for item in tracked):
            break
        time.sleep(min(0.02, max(0.0, deadline - time.monotonic())))

    residual_set = {item.pid for item in tracked if _tracked_process_is_running(item)}
    join_timed_out = _safe_process_is_alive(process)
    if join_timed_out and supervisor_pid is not None:
        residual_set.add(supervisor_pid)
    return GenerationCleanupDiagnostics(
        supervisor_pid=supervisor_pid,
        containment=containment.description,
        residual_pids=tuple(sorted(residual_set)),
        join_timed_out=join_timed_out,
    )


def _attach_cleanup_diagnostics(
    exc: BaseException, diagnostics: GenerationCleanupDiagnostics
) -> None:
    if isinstance(exc, GenerationSupervisorError):
        exc.cleanup = diagnostics
    residual = ",".join(str(pid) for pid in diagnostics.residual_pids) or "none"
    exc.add_note(
        "generation cleanup: "
        f"supervisor_pid={diagnostics.supervisor_pid}, "
        f"containment={diagnostics.containment}, "
        f"residual_pids={residual}, "
        f"join_timed_out={diagnostics.join_timed_out}"
    )


def _decode_ready(
    message: tuple[object, ...], process: BaseProcess, containment: _Containment
) -> int:
    if len(message) != 4 or message[0] != _READY:
        msg = f"expected supervisor ready handshake, received {message!r}"
        raise GenerationProtocolError(msg)
    pid, process_group, daemon = message[1], message[2], message[3]
    if not isinstance(pid, int) or pid != process.pid:
        msg = f"supervisor ready PID mismatch: expected {process.pid}, received {pid!r}"
        raise GenerationProtocolError(msg)
    if daemon is not False:
        msg = f"generation supervisor must be non-daemon, received daemon={daemon!r}"
        raise GenerationProtocolError(msg)

    if os.name == "posix":
        if not isinstance(process_group, int) or process_group != pid:
            msg = f"supervisor did not establish an isolated POSIX process group: {message!r}"
            raise GenerationContainmentError(msg)
        containment.process_group = process_group
    return pid


def _assign_windows_job(containment: _Containment, pid: int) -> None:
    if sys.platform != "win32":
        return
    if containment.job_handle is None:
        msg = "Windows generation Job Object was not created"
        raise GenerationContainmentError(msg)
    from mutmut_win.process.job_object import assign_process_to_job

    try:
        assign_process_to_job(containment.job_handle, pid)
    except OSError as exc:
        msg = f"could not assign generation supervisor PID {pid} to its Job Object: {exc}"
        raise GenerationContainmentError(msg) from exc


def _decode_result(
    message: tuple[object, ...], *, expected: int, seen: set[int]
) -> tuple[int, object, int]:
    if len(message) != 4 or message[0] != _RESULT:
        msg = f"expected generation result, received {message!r}"
        raise GenerationProtocolError(msg)
    index, result, completed = message[1], message[2], message[3]
    if not isinstance(index, int) or not 0 <= index < expected or index in seen:
        msg = f"invalid or duplicate generation result index: {index!r}"
        raise GenerationProtocolError(msg)
    if not isinstance(completed, int) or completed != len(seen) + 1:
        msg = f"invalid generation progress counter: {completed!r}"
        raise GenerationProtocolError(msg)
    return index, result, completed


def _join_completed_supervisor(process: BaseProcess) -> None:
    """Bound a healthy post-DONE teardown independently from abort cleanup."""
    process.join(timeout=_SUCCESS_JOIN_TIMEOUT_SECONDS)
    if process.is_alive():
        raise GenerationSupervisorCrashedError(
            "generation supervisor did not exit after reporting completion"
        )
    if process.exitcode != 0:
        raise GenerationSupervisorCrashedError(
            f"generation supervisor exited with code {process.exitcode} after completion"
        )


def _remote_error(message: tuple[object, ...]) -> GenerationSupervisorRemoteError:
    if len(message) != 4:
        return GenerationSupervisorRemoteError(f"malformed supervisor error: {message!r}")
    error_type, error_message, remote_traceback = message[1], message[2], message[3]
    return GenerationSupervisorRemoteError(
        f"generation supervisor failed with {error_type}: {error_message}\n{remote_traceback}"
    )


def run_generation_supervised[ArgT, ResultT](
    file_args: Sequence[ArgT],
    *,
    max_children: int,
    no_progress_timeout: float,
    worker: Callable[[ArgT], ResultT],
    on_progress: Callable[[GenerationProgress[ResultT]], None] | None = None,
    abort_join_timeout: float = 2.0,
) -> list[ResultT]:
    """Generate files inside a hard-contained supervisor process.

    The no-progress clock starts before the supervisor is spawned and resets
    only after the parent receives a completed file.  It therefore includes
    supervisor bootstrap, containment handshake, executor construction, worker
    startup, and all ``submit`` calls.

    Args:
        file_args: Picklable per-file worker arguments.
        max_children: PPE worker count.  One still uses a real PPE worker; the
            worker callable is never executed in the main or supervisor process.
        no_progress_timeout: Maximum seconds without a completed file.
        worker: Spawn-picklable single-argument worker callable.
        on_progress: Optional main-process callback invoked in completion order.
        abort_join_timeout: Total bounded cleanup/join budget after an abort.

    Returns:
        Worker results in the same order as ``file_args``.

    Raises:
        GenerationNoProgressTimeoutError: No file completed before the deadline.
        GenerationSupervisorCrashedError: Supervisor exited without a final message.
        GenerationSupervisorRemoteError: Executor/bootstrap/worker failure.
        GenerationContainmentError: Job Object or process group setup failed.
        GenerationProtocolError: The child violated the wire protocol.
        BaseException: Callback exceptions and ``KeyboardInterrupt`` are
            preserved after exception-safe process-tree cleanup.
    """
    if isinstance(max_children, bool) or not isinstance(max_children, int) or max_children < 1:
        msg = "max_children must be an integer greater than zero"
        raise ValueError(msg)
    if not math.isfinite(no_progress_timeout) or no_progress_timeout <= 0.0:
        msg = "no_progress_timeout must be finite and greater than zero"
        raise ValueError(msg)
    if not math.isfinite(abort_join_timeout) or abort_join_timeout <= 0.0:
        msg = "abort_join_timeout must be finite and greater than zero"
        raise ValueError(msg)

    arguments = tuple(file_args)
    context = multiprocessing.get_context("spawn")
    parent_connection, child_connection = context.Pipe(duplex=True)
    containment = _Containment()
    process: BaseProcess | None = None

    # Only the parent owns this non-inheritable handle.  Closing it on abort
    # kills the assigned supervisor and every descendant in the job.
    if sys.platform == "win32":
        from mutmut_win.process.job_object import create_kill_on_close_job

        try:
            containment.job_handle = create_kill_on_close_job()
        except OSError as exc:
            with contextlib.suppress(BaseException):
                parent_connection.close()
            with contextlib.suppress(BaseException):
                child_connection.close()
            msg = f"could not create generation Job Object: {exc}"
            raise GenerationContainmentError(msg) from exc

    try:
        if sys.platform == "win32":
            if containment.job_handle is None:
                raise GenerationContainmentError("Windows generation Job Object was not created")
            from mutmut_win.process.suspended_spawn import JobContainedSpawnProcess

            process = JobContainedSpawnProcess(
                job_handle=containment.job_handle,
                target=_generation_supervisor_main,
                args=(child_connection, max_children),
                daemon=False,
            )
            process.name = _SUPERVISOR_NAME
        elif os.name == "posix":
            from mutmut_win.process.posix_spawn import SessionContainedSpawnProcess

            process = SessionContainedSpawnProcess(
                target=_generation_supervisor_main,
                args=(child_connection, max_children),
                daemon=False,
            )
            process.name = _SUPERVISOR_NAME
        else:
            process = context.Process(
                target=_generation_supervisor_main,
                args=(child_connection, max_children),
                name=_SUPERVISOR_NAME,
                daemon=False,
            )
    except BaseException:
        with contextlib.suppress(BaseException):
            parent_connection.close()
        with contextlib.suppress(BaseException):
            child_connection.close()
        with contextlib.suppress(BaseException):
            containment.close_job()
        raise
    progress_deadline = time.monotonic() + no_progress_timeout
    completed_indices: set[int] = set()
    results: dict[int, ResultT] = {}
    supervisor_pid: int | None = None
    completed_normally = False

    try:
        process.start()
        # The child owns its duplicate after spawn.  Keeping this endpoint in
        # the parent would prevent EOF-based crash detection.
        child_connection.close()

        ready = _wait_for_wire_event(
            _as_connection(parent_connection),
            process,
            deadline=progress_deadline,
        )
        if ready is None:
            raise GenerationNoProgressTimeoutError(
                f"no generation file completed for {no_progress_timeout:g}s "
                "during supervisor startup/submit"
            )
        if ready and ready[0] == _ERROR:
            raise _remote_error(ready)
        supervisor_pid = _decode_ready(ready, process, containment)
        # Windows membership was part of CreateProcess itself.  There is no
        # post-start assignment window and no startup code outside the Job.
        parent_connection.send((_START, arguments, worker))

        while True:
            message = _wait_for_wire_event(
                _as_connection(parent_connection),
                process,
                deadline=progress_deadline,
            )
            if message is None:
                phase = (
                    "during supervisor startup/submit"
                    if not completed_indices
                    else f"after {len(completed_indices)} completed file(s)"
                )
                raise GenerationNoProgressTimeoutError(
                    f"no generation file completed for {no_progress_timeout:g}s {phase}"
                )

            kind = message[0] if message else None
            if kind == _ERROR:
                raise _remote_error(message)
            if kind == _DONE:
                if len(message) != 2 or message[1] != len(arguments):
                    msg = f"invalid generation completion message: {message!r}"
                    raise GenerationProtocolError(msg)
                if len(completed_indices) != len(arguments):
                    msg = (
                        "generation supervisor declared completion with "
                        f"{len(completed_indices)}/{len(arguments)} result(s) received"
                    )
                    raise GenerationProtocolError(msg)
                break
            if kind != _RESULT:
                msg = f"unexpected generation supervisor message: {message!r}"
                raise GenerationProtocolError(msg)

            index, raw_result, completed = _decode_result(
                message,
                expected=len(arguments),
                seen=completed_indices,
            )
            result = cast("ResultT", raw_result)
            completed_indices.add(index)
            results[index] = result
            if on_progress is not None:
                on_progress(
                    GenerationProgress(
                        index=index,
                        result=result,
                        completed=completed,
                        total=len(arguments),
                        supervisor_pid=supervisor_pid,
                    )
                )
            # Caller-side rendering/persistence is not generation idle time.
            progress_deadline = time.monotonic() + no_progress_timeout

        # DONE is sent only after pool.shutdown(wait=True), so this join covers
        # ordinary multiprocessing process teardown rather than executor work.
        _join_completed_supervisor(process)
        completed_normally = True
        return [results[index] for index in range(len(arguments))]
    except BaseException as exc:
        try:
            diagnostics = _abort_supervisor(
                process,
                containment,
                join_timeout=abort_join_timeout,
            )
        except BaseException as cleanup_exc:  # last-resort cause preservation
            diagnostics = GenerationCleanupDiagnostics(
                supervisor_pid=_safe_process_pid(process),
                containment=containment.description,
                residual_pids=(),
                join_timed_out=True,
            )
            exc.add_note(
                f"generation cleanup itself failed: {type(cleanup_exc).__qualname__}: {cleanup_exc}"
            )
        _attach_cleanup_diagnostics(exc, diagnostics)
        raise
    finally:
        with contextlib.suppress(BaseException):
            parent_connection.close()
        with contextlib.suppress(BaseException):
            child_connection.close()
        if completed_normally:
            with contextlib.suppress(BaseException):
                containment.close_job()
        elif containment.job_handle is not None:
            # Covers process.start() failure before the except block can kill
            # anything.  No supervisor has been assigned in that case.
            with contextlib.suppress(BaseException):
                containment.close_job()
        if process is not None and not _safe_process_is_alive(process):
            with contextlib.suppress(BaseException):
                process.close()


__all__ = [
    "GenerationCleanupDiagnostics",
    "GenerationContainmentError",
    "GenerationNoProgressTimeoutError",
    "GenerationProgress",
    "GenerationProtocolError",
    "GenerationSupervisorCrashedError",
    "GenerationSupervisorError",
    "GenerationSupervisorRemoteError",
    "run_generation_supervised",
]
