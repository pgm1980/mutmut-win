"""Spawn-based pool executor for mutation test workers.

``SpawnPoolExecutor`` manages a pool of ``multiprocessing.Process`` workers,
feeds them tasks via a shared task queue, and exposes their output via an
event queue.  On Windows ``spawn`` is the only safe start method — ``fork``
is unavailable.
"""

from __future__ import annotations

import logging
import multiprocessing
import multiprocessing.queues
import sys
import warnings
from typing import TYPE_CHECKING, Any

from mutmut_win.process.worker import worker_main

if TYPE_CHECKING:
    from collections.abc import Iterator

    from mutmut_win.config import MutmutConfig
    from mutmut_win.models import MutationTask, TaskEvent

logger = logging.getLogger(__name__)


class SpawnPoolExecutor:
    """Pool of spawned worker processes for parallel mutation testing.

    Creates *max_workers* child processes using the ``spawn`` start method,
    distributes ``MutationTask`` objects via a task queue, and yields domain
    events (``TaskStarted``, ``TaskCompleted``, ``TaskTimedOut``) from an
    event queue.

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

        Blocks until each task produces either a ``TaskCompleted`` or
        ``TaskTimedOut`` event.  ``TaskStarted`` events are yielded
        immediately as they arrive.

        Yields:
            ``TaskStarted``, ``TaskCompleted``, or ``TaskTimedOut`` instances.
        """
        from mutmut_win.models import TaskCompleted, TaskStarted, TaskTimedOut

        finished = 0
        while finished < self._num_tasks:
            raw: dict[str, object] = self._event_queue.get()

            # Discriminate on the keys present in the dict.
            if "exit_code" in raw:
                event: TaskEvent = TaskCompleted.model_validate(raw)
                finished += 1
            elif "timestamp" in raw:
                event = TaskStarted.model_validate(raw)
            else:
                event = TaskTimedOut.model_validate(raw)
                finished += 1

            yield event

    def shutdown(self, timeout: float = 10.0) -> None:
        """Terminate all worker processes and release resources.

        Attempts a graceful join first, then kills any remaining workers.

        Args:
            timeout: Maximum seconds to wait for each worker to exit cleanly
                before resorting to ``kill()``.
        """
        for worker in self._workers:
            if worker.is_alive():
                worker.kill()

        for worker in self._workers:
            worker.join(timeout=timeout)
            if worker.is_alive():
                worker.kill()
                worker.join()

        self._workers.clear()

        # Release the Job Object handle (processes are already dead at this point).
        if self._job_handle is not None:
            from mutmut_win.process.job_object import close_job

            close_job(self._job_handle)
            self._job_handle = None
