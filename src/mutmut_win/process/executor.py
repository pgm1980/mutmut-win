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
import sys
import time
import warnings
from pathlib import Path
from typing import TYPE_CHECKING, Any

from mutmut_win.process.worker import worker_main

if TYPE_CHECKING:
    from collections.abc import Iterator

    from mutmut_win.config import MutmutConfig
    from mutmut_win.models import MutationTask, TaskCompleted, TaskEvent

logger = logging.getLogger(__name__)

#: Poll interval (seconds) for the event loop.  Every idle tick triggers a
#: worker-liveness sweep (issue #80 / A2-EW-002); under load ``get`` returns
#: immediately, so this adds no overhead to a healthy run.
_EVENT_POLL_SECONDS: float = 1.0

#: Exit code for synthesized completions of tasks whose worker died hard.
_EXIT_CODE_SUSPICIOUS: int = 35


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


class SpawnPoolExecutor:
    """Pool of spawned worker processes for parallel mutation testing.

    Creates *max_workers* child processes using the ``spawn`` start method,
    distributes ``MutationTask`` objects via a task queue, and yields domain
    events (``TaskStarted``, ``TaskCompleted``) from an event queue.

    Args:
        max_workers: Number of worker processes to spawn.
        config: Validated ``MutmutConfig`` instance; converted to a dict
            before being sent to child processes for pickle safety.
    """

    def __init__(self, max_workers: int, config: MutmutConfig) -> None:
        self._max_workers = max_workers
        self._config_data: dict[str, Any] = config.model_dump()
        # Use "spawn" explicitly — required on Windows, safe on all platforms.
        self._mp_ctx = multiprocessing.get_context("spawn")
        self._task_queue: multiprocessing.queues.Queue[dict[str, object] | None] = (
            self._mp_ctx.Queue()
        )
        self._event_queue: multiprocessing.queues.Queue[dict[str, object]] = self._mp_ctx.Queue()
        self._workers: list[multiprocessing.process.BaseProcess] = []
        self._num_tasks: int = 0
        self._shutdown_done: bool = False

        # Orphan protection: Windows Job Object kills all children when parent dies.
        self._job_handle: int | None = None
        if sys.platform == "win32":
            try:
                from mutmut_win.process.job_object import create_kill_on_close_job

                self._job_handle = create_kill_on_close_job()
            except OSError:
                warnings.warn(
                    "Could not create Windows Job Object — orphan process protection "
                    "is disabled. If mutmut-win crashes, worker processes may remain alive.",
                    RuntimeWarning,
                    stacklevel=2,
                )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self, tasks: list[MutationTask]) -> None:
        """Spawn workers and enqueue all tasks.

        Each task is serialised to a ``dict`` before being placed on the
        queue so that Pydantic models do not need to cross the pickle
        boundary.  After all tasks, one ``None`` sentinel per worker is
        enqueued to signal clean shutdown.

        Args:
            tasks: List of mutation tasks to distribute among workers.
        """
        _sweep_stale_artifacts(Path("mutants"))
        self._num_tasks = len(tasks)

        # Enqueue tasks as plain dicts for pickle safety.
        for task in tasks:
            self._task_queue.put(task.model_dump())

        # One sentinel per worker so each worker exits after draining tasks.
        for _ in range(self._max_workers):
            self._task_queue.put(None)

        # Spawn workers after the queue is populated so they can start
        # consuming immediately without a race on the sentinel count.
        for _ in range(self._max_workers):
            proc = self._mp_ctx.Process(
                target=worker_main,
                args=(self._task_queue, self._event_queue, self._config_data),
                daemon=True,
            )
            proc.start()

            # Assign to Job Object for orphan protection (Windows only).
            if self._job_handle is not None and proc.pid is not None:
                try:
                    from mutmut_win.process.job_object import assign_process_to_job

                    assign_process_to_job(self._job_handle, proc.pid)
                except OSError:
                    logger.warning("Could not assign worker PID %d to Job Object", proc.pid)

            self._workers.append(proc)

    def get_events(self) -> Iterator[TaskEvent]:
        """Yield domain events until all tasks have been reported as done.

        ``TaskStarted`` events are yielded immediately as they arrive; the
        loop ends once every task produced a ``TaskCompleted`` (worker-side
        timeouts arrive as completions with exit code 36/38).

        Liveness (issue #80 / A2-EW-002): the queue is polled with a timeout,
        and every idle tick sweeps the workers.  A worker that died hard can
        never deliver a completion for its in-flight task — previously this
        blocked the run forever.  Such tasks are completed synthetically
        (exit code 35 "suspicious" with an explanatory ``last_output``); a
        late-flushed REAL completion for an already-synthesized mutant is
        dropped so every task is counted exactly once.  When the whole pool
        is dead and tasks were never started, the loop aborts loudly instead
        of fabricating results for them.

        Yields:
            ``TaskStarted`` or ``TaskCompleted`` instances.
        """
        import queue as queue_module

        from mutmut_win.models import TaskCompleted, TaskStarted

        finished = 0
        in_flight: dict[str, int] = {}  # mutant_name -> worker pid
        synthesized: set[str] = set()
        handled_dead_pids: set[int] = set()

        while finished < self._num_tasks:
            try:
                raw: dict[str, object] = self._event_queue.get(timeout=_EVENT_POLL_SECONDS)
            except queue_module.Empty:
                # Idle tick: everything flushed so far has been consumed, so
                # the in-flight map is current — sweep worker liveness now
                # (drain-first ordering prevents double counting, JT-008).
                for synthetic_event in self._sweep_dead_workers(in_flight, handled_dead_pids):
                    synthesized.add(synthetic_event.mutant_name)
                    finished += 1
                    yield synthetic_event
                if not any(worker.is_alive() for worker in self._workers):
                    remaining = self._num_tasks - finished
                    if remaining > 0:
                        print(
                            f"Error: all {len(self._workers)} workers died; "
                            f"{remaining} task(s) were never started — aborting the run. "
                            "Their mutants remain unchecked."
                        )
                        break
                continue

            # Discriminate on the keys present in the dict.
            if "exit_code" in raw:
                event: TaskEvent = TaskCompleted.model_validate(raw)
                if event.mutant_name in synthesized:
                    # Late flush from a worker we already declared dead —
                    # drop it to keep the finished-accounting single-counted.
                    synthesized.discard(event.mutant_name)
                    in_flight.pop(event.mutant_name, None)
                    continue
                in_flight.pop(event.mutant_name, None)
                finished += 1
            elif "timestamp" in raw:
                event = TaskStarted.model_validate(raw)
                in_flight[event.mutant_name] = event.worker_pid
            else:
                # Fail fast on unknown shapes instead of misparsing them
                # (issue #81; the #79 finally-shutdown cleans up the pool).
                msg = f"unknown event shape on the event queue: {sorted(raw)!r}"
                raise RuntimeError(msg)

            yield event

    def _sweep_dead_workers(
        self, in_flight: dict[str, int], handled_dead_pids: set[int]
    ) -> list[TaskCompleted]:
        """Synthesize completions for in-flight tasks of newly dead workers."""
        from mutmut_win.models import TaskCompleted

        synthetic: list[TaskCompleted] = []
        for worker in self._workers:
            pid = worker.pid or -1
            if worker.is_alive() or pid in handled_dead_pids:
                continue
            handled_dead_pids.add(pid)
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

        deadline = time.monotonic() + timeout
        for worker in self._workers:
            worker.join(timeout=max(0.0, deadline - time.monotonic()))
        for worker in self._workers:
            if worker.is_alive():
                worker.kill()
                worker.join()

        self._workers.clear()

        for queue in (self._task_queue, self._event_queue):
            queue.cancel_join_thread()
            queue.close()

        # Release the Job Object handle (processes are already dead at this point).
        if self._job_handle is not None:
            from mutmut_win.process.job_object import close_job

            close_job(self._job_handle)
            self._job_handle = None
