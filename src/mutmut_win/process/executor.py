"""Spawn-based pool executor for mutation test workers.

``SpawnPoolExecutor`` manages a pool of ``multiprocessing.Process`` workers,
feeds them tasks via a shared task queue, and exposes their output via an
event queue.  On Windows ``spawn`` is the only safe start method — ``fork``
is unavailable.
"""

from __future__ import annotations

import contextlib
import logging
import multiprocessing
import multiprocessing.queues
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from mutmut_win.exceptions import ProcessContainmentError, PytestBoundaryError, WorkerError
from mutmut_win.process.worker import worker_main

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

    from mutmut_win.config import MutmutConfig
    from mutmut_win.models import MutationTask, TaskCompleted, TaskEvent

logger = logging.getLogger(__name__)

#: Poll interval (seconds) for the event loop.  Every idle tick triggers a
#: worker-liveness sweep (issue #80 / A2-EW-002); under load ``get`` returns
#: immediately, so this adds no overhead to a healthy run.
_EVENT_POLL_SECONDS: float = 1.0

#: Exit code for synthesized completions of tasks whose worker died hard.
_EXIT_CODE_SUSPICIOUS: int = 35

#: Wall-clock grace (seconds) for queued work to make progress while no task is
#: in flight.  WRK-001 originally covered only total startup failure.  A mixed
#: pool could still hang forever after one healthy worker completed a task while
#: another worker remained alive but wedged before pulling its first task.  The
#: same generous grace now applies after every real progress event, but only
#: while *no* task is in flight.  This keeps slow, healthy mutants under their
#: own per-task timeout instead of killing them from the executor.  Not a user
#: knob (test-monkeypatchable).
_STARTUP_GRACE_SECONDS: float = 60.0


def _sweep_stale_artifacts(mutants_dir: Path) -> None:
    """Delete leftover worker artifacts from aborted runs (issue #82 / A2-EW-007).

    Kill paths can leak ``mutmut_out_*.log`` / ``mutmut_tests_*.txt`` into the
    ``mutants/`` staging (the audit found four orphaned logs in a real tree);
    every fresh pool start begins with a clean slate instead.
    """
    if not mutants_dir.is_dir():
        return
    for pattern in ("mutmut_out_*.log", "mutmut_tests_*.txt"):
        for stale in mutants_dir.glob(pattern):
            with contextlib.suppress(OSError):
                stale.unlink()


def _idle_grace_expired(*, remaining_tasks: int, in_flight_tasks: int, idle_elapsed: float) -> bool:
    """Return whether queued work is stalled with no task currently running.

    ``in_flight_tasks`` is the safety guard: a long but healthy mutant must be
    governed by its per-task timeout, not by this pool-level progress watchdog.
    """
    return remaining_tasks > 0 and in_flight_tasks == 0 and idle_elapsed > _STARTUP_GRACE_SECONDS


@dataclass
class _EventLoopState:
    """Mutable event-loop accounting shared by the normal and drain paths (M-054).

    Bundling it keeps the idle-tick drain on the exact same counting and
    aborting logic as the normal blocking read: single-counting
    (``finished``), in-flight ownership, synthesized drops, one-time process
    cleanup per dead PID (``handled_dead_pids`` — cleanup only, NOT a
    synthesis gate), the WRK-001 watchdog bookkeeping, and the fatal-abort
    flag the caller checks right after an event was yielded.
    """

    finished: int = 0
    in_flight: dict[str, int] = field(default_factory=dict)
    synthesized: set[str] = field(default_factory=set)
    handled_dead_pids: set[int] = field(default_factory=set)
    progress_observed: bool = False
    last_progress_monotonic: float = field(default_factory=time.monotonic)
    fatal_completion: bool = False


class SpawnPoolExecutor:
    """Pool of spawned worker processes for parallel mutation testing.

    Creates *max_workers* child processes using the ``spawn`` start method,
    distributes ``MutationTask`` objects via a task queue, and yields domain
    events (``TaskStarted``, ``TaskCompleted``) from an event queue.

    Args:
        max_workers: Number of worker processes to spawn.
        config: Validated ``MutmutConfig`` instance; converted to a dict
            before being sent to child processes for pickle safety.

    Raises:
        ProcessContainmentError: On Windows, when the kill-on-close Job Object
            cannot be created.  This stays fail-closed and happens before any
            other allocation.
        OSError: When the multiprocessing queues cannot be constructed after
            the Job Object exists (handle/memory exhaustion).  In that case the
            Job handle and every queue built so far are released and the
            original exception is re-raised — a failed construction must not
            leak kernel handles until process exit (M-108/M-104).
    """

    def __init__(self, max_workers: int, config: MutmutConfig) -> None:
        self._max_workers = max_workers
        self._config_data: dict[str, Any] = config.model_dump()
        # On Windows the pool is a safety boundary, not an optional
        # optimisation.  Fail before allocating/spawning anything if the
        # kernel boundary cannot be established.
        self._job_handle: int | None = None
        if sys.platform == "win32":
            try:
                from mutmut_win.process.job_object import create_kill_on_close_job

                self._job_handle = create_kill_on_close_job()
            except (OSError, RuntimeError) as exc:
                raise ProcessContainmentError(
                    "Could not create a Windows Job Object for the worker pool; "
                    "refusing to start uncontained workers."
                ) from exc

        # Everything below can still fail (e.g. queue construction under
        # handle/memory exhaustion) while the Job handle is already
        # allocated.  Wrap the remaining initialisation in a rollback
        # (M-108/M-104): on ANY failure release the Job and the queues
        # built so far, then re-raise the original exception.  An
        # ``ExitStack`` is deliberately NOT used here — a raising callback
        # would replace the original exception.
        queues: list[Any] = []
        try:
            # Use "spawn" explicitly — required on Windows, safe on all platforms.
            self._mp_ctx = multiprocessing.get_context("spawn")
            self._task_queue: multiprocessing.queues.Queue[dict[str, object] | None] = (
                self._mp_ctx.Queue()
            )
            queues.append(self._task_queue)
            self._event_queue: multiprocessing.queues.Queue[dict[str, object]] = (
                self._mp_ctx.Queue()
            )
            queues.append(self._event_queue)
            # POSIX task subprocesses publish their process group synchronously
            # here while blocked behind an EOF-safe pre-exec gate. Unlike
            # Queue.put(), SimpleQueue.put() has no feeder thread; the gate releases
            # only after the complete PGID record is visible.
            self._containment_queue: Any = self._mp_ctx.SimpleQueue()
            queues.append(self._containment_queue)
            self._workers: list[multiprocessing.process.BaseProcess] = []
            self._posix_groups_by_worker: dict[int, set[int]] = {}
            self._posix_group_by_task: dict[str, int] = {}
            self._num_tasks: int = 0
            self._shutdown_done: bool = False
            # Pool-collapse declaration (issue #127 / 360°-A7): set by
            # ``get_events`` when every worker died while tasks were never
            # started. The orchestrator maps it onto ``run_aborted`` so the run
            # cannot end like a success (exit 0 / gate over the remainder).
            self.aborted: bool = False
            self.abort_reason: str | None = None
        except BaseException:
            self._release_partial_construction(queues)
            raise

    def _release_partial_construction(self, queues: list[Any]) -> None:
        """Best-effort rollback of a partially constructed executor.

        Closes the queues built so far and releases the Job Object handle.
        ``_job_handle`` is cleared BEFORE ``close_job`` so a failure in this
        method can never trigger a second close of the same kernel handle
        (``close_job`` is not idempotent).  Every cleanup error is suppressed
        and logged: the original constructor exception must propagate
        unchanged.  Only ``close_job`` deterministically releases the kernel
        handle — ``Queue.close()`` without a started feeder thread is
        best-effort and must not be relied upon as pipe cleanup.
        """
        for queue in queues:
            close = getattr(queue, "close", None)
            if not callable(close):
                continue
            try:
                close()
            except Exception as exc:
                logger.warning("constructor rollback: closing partial queue failed: %s", exc)
        handle, self._job_handle = self._job_handle, None
        if handle is None:
            return
        from mutmut_win.process.job_object import close_job

        try:
            close_job(handle)
        except Exception as exc:
            logger.warning("constructor rollback: closing worker-pool Job Object failed: %s", exc)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def configure_pytest_boundary(self, boundary: dict[str, object]) -> None:
        """Freeze the parent-validated pytest boundary before worker spawn."""

        from mutmut_win.pytest_boundary import PytestBoundary

        if self._workers:
            raise RuntimeError("pytest boundary cannot change after worker spawn")
        validated = PytestBoundary.from_dict(boundary)
        validated.arguments()
        existing_payload = self._config_data.get("_pytest_boundary")
        if existing_payload is not None:
            existing = PytestBoundary.from_dict(existing_payload)
            existing.arguments()
            if existing.to_dict() != validated.to_dict():
                raise PytestBoundaryError("pytest boundary is already frozen for this pool")
            return
        self._config_data["_pytest_boundary"] = validated.to_dict()

    def start(self, tasks: list[MutationTask]) -> None:
        """Spawn workers and enqueue all tasks.

        Each task is serialised to a ``dict`` before being placed on the
        queue so that Pydantic models do not need to cross the pickle
        boundary.  After all tasks, one ``None`` sentinel per worker is
        enqueued to signal clean shutdown.

        Args:
            tasks: List of mutation tasks to distribute among workers.
        """
        raw_boundary = self._config_data.get("_pytest_boundary")
        if raw_boundary is None:
            raise PytestBoundaryError(
                "Worker pool start refused: configure_pytest_boundary() was not called."
            )
        from mutmut_win.pytest_boundary import PytestBoundary

        # Revalidate at the last parent-side moment before spawning workers.
        # The workers repeat this check at startup and before every task.
        PytestBoundary.from_dict(raw_boundary).arguments()

        _sweep_stale_artifacts(Path("mutants"))
        self._num_tasks = len(tasks)

        try:
            # Workers are spawned against an empty queue. On Windows the
            # custom spawn backend creates the interpreter suspended, assigns
            # its process handle to the Job, and resumes only afterwards — so
            # even site/.pth/sitecustomize startup is already contained.
            for _ in range(self._max_workers):
                proc = self._make_worker_process()
                proc.start()
                self._workers.append(proc)
            # Queue publication happens only after every Windows worker is
            # contained.  This also makes assignment failure all-or-nothing.
            for task in tasks:
                self._task_queue.put(task.model_dump())
            for _ in range(self._max_workers):
                self._task_queue.put(None)
        except BaseException:
            for worker in self._workers:
                pid = getattr(worker, "pid", None)
                if isinstance(pid, int):
                    self._kill_posix_worker_group(pid)
                with contextlib.suppress(Exception):
                    worker.kill()
                with contextlib.suppress(Exception):
                    worker.join(timeout=5.0)
            self._workers.clear()
            raise

    def _make_worker_process(self) -> multiprocessing.process.BaseProcess:
        """Build one spawn worker with the platform containment contract."""
        args = (
            self._task_queue,
            self._event_queue,
            self._config_data,
            self._containment_queue,
        )
        if sys.platform == "win32":
            if self._job_handle is None:
                raise ProcessContainmentError("Windows worker pool has no usable Job Object.")
            from mutmut_win.process.suspended_spawn import JobContainedSpawnProcess

            return JobContainedSpawnProcess(
                job_handle=self._job_handle,
                target=worker_main,
                args=args,
                daemon=True,
            )
        if os.name == "posix":
            from mutmut_win.process.posix_spawn import SessionContainedSpawnProcess

            # The seekable bootstrap returns from Process.start() even when
            # sitecustomize wedges before spawn_main.  A dedicated session also
            # lets shutdown reap startup-time descendants that never reached
            # worker_main.
            return SessionContainedSpawnProcess(
                target=worker_main,
                args=args,
                daemon=True,
            )
        return self._mp_ctx.Process(target=worker_main, args=args, daemon=True)

    def _apply_event(self, raw: dict[str, object], state: _EventLoopState) -> Iterator[TaskEvent]:
        """Validate, account for, and yield a single event-queue item.

        Shared by the normal blocking read and the idle-tick drain (M-054) so
        both paths count identically. ``state.fatal_completion`` is set
        BEFORE the yield so the caller can break the loop immediately after
        the consumer has received the event. A late real completion for an
        already-synthesized mutant is dropped (with a warning) and yields
        nothing — the single-count guarantee.
        """
        from mutmut_win.models import TaskCompleted, TaskStarted

        if "exit_code" in raw:
            completed = TaskCompleted.model_validate(raw)
            if completed.mutant_name in state.synthesized:
                # Late flush from a worker we already declared dead — drop it
                # to keep the finished-accounting single-counted (M-054: the
                # drop is now logged; it used to vanish silently).
                logger.warning(
                    "dropping late real completion for %s from worker pid %s — "
                    "a synthetic result was already delivered",
                    completed.mutant_name,
                    completed.worker_pid,
                )
                state.synthesized.discard(completed.mutant_name)
                state.in_flight.pop(completed.mutant_name, None)
                return
            event: TaskEvent = completed
            state.in_flight.pop(completed.mutant_name, None)
            self._forget_posix_group(completed.mutant_name, completed.worker_pid)
            state.finished += 1
            if completed.fatal:
                self.aborted = True
                self.abort_reason = (
                    f"worker PID {completed.worker_pid} reported a fatal execution-boundary "
                    f"failure: {completed.last_output or 'no diagnostic'}"
                )
                state.fatal_completion = True
        elif "timestamp" in raw:
            event = TaskStarted.model_validate(raw)
            state.in_flight[event.mutant_name] = event.worker_pid
        else:
            # Fail fast on unknown shapes instead of misparsing them
            # (issue #81; the #79 finally-shutdown cleans up the pool).
            msg = f"unknown event shape on the event queue: {sorted(raw)!r}"
            raise WorkerError(msg)

        state.progress_observed = True
        state.last_progress_monotonic = time.monotonic()
        yield event

    def get_events(self) -> Iterator[TaskEvent]:
        """Yield domain events until all tasks have been reported as done.

        ``TaskStarted`` events are yielded immediately as they arrive; the
        loop ends once every task produced a ``TaskCompleted`` (worker-side
        timeouts arrive as completions with exit code 36/38).

        Liveness (issue #80 / A2-EW-002) with M-054 verdict integrity: the
        queue is polled with a timeout, and every idle tick (1) takes a
        liveness snapshot of the pool, then (2) drains the event queue
        completely via non-blocking reads through the same event-application
        path as normal events. A worker process joins its queue feeder
        thread at interpreter exit, so once a worker is observed dead every
        byte it ever wrote is already in the pipe — after the drain, a
        missing completion is genuinely missing. Only then (3) are the
        snapshot's dead workers swept: their in-flight tasks receive a
        synthetic completion (exit code 35 "suspicious" with an explanatory
        ``last_output``). A late-flushed REAL completion for an
        already-synthesized mutant is dropped (with a warning) so every task
        is counted exactly once, and a ``TaskStarted`` arriving after its
        owner was observed dead is completed on the NEXT idle tick — its
        real completion may still be ahead in the pipe and wins the drain.
        When the whole pool was already dead in the snapshot and tasks were
        never started, the loop aborts loudly instead of fabricating results
        for them. A progress watchdog also bounds a mixed pool where at
        least one task completed but another worker stays alive and never
        pulls queued work; it is active only while no task is in flight.

        Yields:
            ``TaskStarted`` or ``TaskCompleted`` instances.
        """
        import queue as queue_module

        state = _EventLoopState()

        while state.finished < self._num_tasks:
            self._drain_containment_events(state.in_flight)
            try:
                raw: dict[str, object] = self._event_queue.get(timeout=_EVENT_POLL_SECONDS)
            except queue_module.Empty:
                # Idle tick. Ordering (M-054): liveness snapshot FIRST, then
                # a complete non-blocking drain, then sweep and all-dead
                # checks — each against the snapshot. Observing death before
                # draining is what makes "no completion in the drain" proof
                # that none is coming; the reverse order let the sweep
                # replace a real verdict whose bytes were still in flight
                # (the drain-first intent JT-008 documented but the old code
                # never implemented).
                dead_snapshot = [worker for worker in self._workers if not worker.is_alive()]
                any_worker_alive = any(worker.is_alive() for worker in self._workers)

                while state.finished < self._num_tasks:
                    try:
                        drained: dict[str, object] = self._event_queue.get_nowait()
                    except queue_module.Empty:
                        break
                    yield from self._apply_event(drained, state)
                    if state.fatal_completion:
                        break
                if state.fatal_completion:
                    # A fatal completion surfaced during the drain: abort
                    # before any sweep could fabricate further results.
                    break

                if state.finished < self._num_tasks:
                    synthetic_events = self._sweep_dead_workers(
                        state.in_flight, state.handled_dead_pids, dead_snapshot
                    )
                    for synthetic_event in synthetic_events:
                        state.synthesized.add(synthetic_event.mutant_name)
                        state.finished += 1
                        yield synthetic_event
                    if synthetic_events:
                        state.progress_observed = True
                        state.last_progress_monotonic = time.monotonic()

                    remaining = self._num_tasks - state.finished
                    if remaining > 0 and not any_worker_alive:
                        # Issue #127 / 360°-A7: declare the collapse as run
                        # state — the silent break used to read as success.
                        # M-054: judged against the pre-drain snapshot — a
                        # pool that was dead before the drain and still has
                        # unstarted tasks has genuinely lost them.
                        self.aborted = True
                        self.abort_reason = (
                            f"all {len(self._workers)} workers died; "
                            f"{remaining} task(s) were never started"
                        )
                        print(
                            f"Error: {self.abort_reason} — aborting the run. "
                            "Their mutants remain unchecked.",
                            file=sys.stderr,
                        )
                        break
                    # Bound both total startup failure and the mixed-pool variant:
                    # queued tasks, no in-flight task, and no progress for a full
                    # grace interval.  An in-flight task always disables this check
                    # and remains protected by its own worker-side timeout.
                    if _idle_grace_expired(
                        remaining_tasks=remaining,
                        in_flight_tasks=len(state.in_flight),
                        idle_elapsed=time.monotonic() - state.last_progress_monotonic,
                    ):
                        if state.progress_observed:
                            self._declare_idle_collapse(remaining)
                        else:
                            self._declare_startup_collapse()
                        break
                continue

            yield from self._apply_event(raw, state)
            if state.fatal_completion:
                break

    def _sweep_dead_workers(
        self,
        in_flight: dict[str, int],
        handled_dead_pids: set[int],
        dead_workers: Sequence[multiprocessing.process.BaseProcess],
    ) -> list[TaskCompleted]:
        """Synthesize completions for in-flight tasks of dead workers.

        M-054: ``dead_workers`` is the liveness snapshot taken BEFORE the
        idle-tick drain; only those workers are swept, always after that
        drain of the same tick. ``handled_dead_pids`` guards only the
        ONE-TIME process cleanup (POSIX group kills) — synthesis itself runs
        for every dead worker that still owns in-flight entries, so a
        ``TaskStarted`` arriving after its owner was observed dead is
        completed on a later tick instead of stranding in ``in_flight``
        forever, while never being overwritten before its real completion
        had a chance to arrive through the drain.
        """
        from mutmut_win.models import TaskCompleted

        synthetic: list[TaskCompleted] = []
        for worker in dead_workers:
            pid = worker.pid or -1
            if worker.is_alive():
                continue
            if pid not in handled_dead_pids:
                handled_dead_pids.add(pid)
                self._kill_posix_worker_group(pid)
                self._kill_posix_groups_for_worker(pid)
            orphaned = [name for name, owner in in_flight.items() if owner == pid]
            for name in orphaned:
                in_flight.pop(name, None)
                logger.warning(
                    "worker pid %d died (exitcode %s) while running %s — "
                    "synthesizing a 'suspicious' result",
                    pid,
                    worker.exitcode,
                    name,
                )
                synthetic.append(
                    TaskCompleted(
                        mutant_name=name,
                        worker_pid=pid,
                        exit_code=_EXIT_CODE_SUSPICIOUS,
                        duration=0.0,
                        last_output=(
                            f"worker process {pid} died unexpectedly "
                            f"(exitcode {worker.exitcode}) while running this "
                            "mutant — result synthesized by the executor "
                            "(issue #80)"
                        ),
                    )
                )
        return synthetic

    def _drain_containment_events(self, in_flight: dict[str, int]) -> None:
        """Consume synchronously-published POSIX task PGID evidence."""
        if sys.platform == "win32":
            return
        reader = getattr(self._containment_queue, "_reader", None)
        if reader is None:
            return
        while reader.poll():
            raw = self._containment_queue.get()
            if not isinstance(raw, dict):
                raise WorkerError(f"invalid containment event: {raw!r}")
            name = raw.get("mutant_name")
            worker_pid = raw.get("worker_pid")
            process_group = raw.get("process_group")
            if (
                not isinstance(name, str)
                or not name
                or not isinstance(worker_pid, int)
                or worker_pid <= 0
                or not isinstance(process_group, int)
                or process_group <= 0
            ):
                raise WorkerError(f"invalid containment event: {raw!r}")
            in_flight[name] = worker_pid
            self._posix_group_by_task[name] = process_group
            self._posix_groups_by_worker.setdefault(worker_pid, set()).add(process_group)

    def _forget_posix_group(self, mutant_name: str, worker_pid: int) -> None:
        process_group = self._posix_group_by_task.pop(mutant_name, None)
        if process_group is None:
            return
        worker_groups = self._posix_groups_by_worker.get(worker_pid)
        if worker_groups is None:
            return
        worker_groups.discard(process_group)
        if not worker_groups:
            self._posix_groups_by_worker.pop(worker_pid, None)

    def _kill_posix_groups_for_worker(self, worker_pid: int) -> None:
        if sys.platform == "win32":
            return
        import os
        import signal

        for process_group in self._posix_groups_by_worker.pop(worker_pid, set()):
            with contextlib.suppress(ProcessLookupError, PermissionError):
                os.killpg(process_group, signal.SIGKILL)
            for name, group in tuple(self._posix_group_by_task.items()):
                if group == process_group:
                    self._posix_group_by_task.pop(name, None)

    @staticmethod
    def _kill_posix_worker_group(worker_pid: int) -> None:
        """Reap one worker session, including pre-worker_main descendants."""
        if os.name != "posix" or worker_pid <= 0:
            return
        import signal

        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(  # type: ignore[attr-defined,unused-ignore]
                worker_pid,
                signal.SIGKILL,  # type: ignore[attr-defined,unused-ignore]
            )

    def _declare_startup_collapse(self) -> None:
        """Mark the pool collapsed at worker startup and report it (WRK-001)."""
        self.aborted = True
        self.abort_reason = (
            f"no worker pulled a task within {_STARTUP_GRACE_SECONDS:.0f}s; "
            f"{self._num_tasks} task(s) were never started"
        )
        print(
            f"Error: {self.abort_reason} — workers are failing during "
            "interpreter startup (a crashing sitecustomize/.pth/"
            "site-packages wedges every spawn). Aborting the run; "
            "their mutants remain unchecked.",
            file=sys.stderr,
        )

    def _declare_idle_collapse(self, remaining: int) -> None:
        """Mark a mixed pool stalled after earlier progress as collapsed."""
        self.aborted = True
        self.abort_reason = (
            f"no worker pulled another task within {_STARTUP_GRACE_SECONDS:.0f}s; "
            f"{remaining} task(s) were never started"
        )
        print(
            f"Error: {self.abort_reason} — workers stopped pulling queued "
            "tasks after earlier progress. Aborting the run; their mutants "
            "remain unchecked.",
            file=sys.stderr,
        )

    def shutdown(self, timeout: float = 10.0) -> None:
        """Terminate all worker processes and release resources.

        Joins workers gracefully within one shared *timeout* deadline (on the
        normal path they are already draining their sentinels and exit within
        milliseconds), kills whatever is still alive, then severs both queues
        via ``cancel_join_thread()`` + ``close()``: with buffered items and
        dead readers, multiprocessing would otherwise join the feeder thread
        at interpreter exit forever (issue #79 / A2-EW-001).  Losing the
        buffered task data is intended at shutdown.  Safe to call repeatedly.

        Args:
            timeout: Shared deadline in seconds for the graceful join of all
                workers before resorting to ``kill()``.
        """
        if self._shutdown_done:
            return
        self._shutdown_done = True

        cleanup_errors: list[tuple[str, BaseException]] = []

        def attempt(label: str, operation: Any) -> None:
            try:
                operation()
            except BaseException as exc:
                cleanup_errors.append((label, exc))

        # Capture every synchronously-published PGID before workers are
        # touched.  A hard-killed worker cannot retract these records.
        attempt("drain POSIX containment events", lambda: self._drain_containment_events({}))

        deadline = time.monotonic() + max(0.0, timeout)
        for worker in tuple(self._workers):
            attempt(
                f"join worker {getattr(worker, 'pid', None)}",
                lambda worker=worker: worker.join(timeout=max(0.0, deadline - time.monotonic())),
            )

        for worker in tuple(self._workers):
            pid = getattr(worker, "pid", None)
            if isinstance(pid, int):
                attempt(
                    f"kill POSIX groups for worker {pid}",
                    lambda pid=pid: self._kill_posix_groups_for_worker(pid),
                )
                attempt(
                    f"kill POSIX worker session {pid}",
                    lambda pid=pid: self._kill_posix_worker_group(pid),
                )
            alive = True
            try:
                alive = bool(worker.is_alive())
            except BaseException as exc:
                cleanup_errors.append((f"inspect worker {pid}", exc))
            if alive:
                attempt(f"kill worker {pid}", worker.kill)

        # The post-kill reap is independently bounded.  A failed/denied kill
        # cannot block queue and Job cleanup indefinitely.
        reap_deadline = time.monotonic() + min(2.0, max(0.1, max(0.0, timeout)))
        for worker in tuple(self._workers):
            attempt(
                f"reap worker {getattr(worker, 'pid', None)}",
                lambda worker=worker: worker.join(
                    timeout=max(0.0, reap_deadline - time.monotonic())
                ),
            )

        workers = tuple(self._workers)
        self._workers.clear()

        # Each resource is an independent cleanup stage.  Never let one broken
        # queue mask the original run error or prevent the Job from closing.
        for name, queue in (("task queue", self._task_queue), ("event queue", self._event_queue)):
            attempt(f"cancel {name} feeder join", queue.cancel_join_thread)
            attempt(f"close {name}", queue.close)
        attempt("close containment queue", self._containment_queue.close)

        handle = self._job_handle
        self._job_handle = None
        if handle is not None:

            def close_pool_job() -> None:
                from mutmut_win.process.job_object import close_job

                close_job(handle)

            attempt("close worker-pool Job Object", close_pool_job)

        for worker in workers:
            try:
                if not worker.is_alive():
                    attempt(
                        f"close worker {getattr(worker, 'pid', None)}",
                        lambda worker=worker: worker.close(),
                    )
            except BaseException as exc:
                cleanup_errors.append(("inspect worker before close", exc))

        for label, cleanup_exc in cleanup_errors:
            logger.error("executor shutdown cleanup failed (%s): %s", label, cleanup_exc)
