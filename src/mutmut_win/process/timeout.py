"""Wall-clock timeout monitor for mutation worker processes.

The ``WallClockTimeout`` class runs a background thread that checks all
registered mutant deadlines every second.  When a deadline is exceeded the
worker process is killed and a ``TaskTimedOut`` event is placed in the
event queue.
"""

from __future__ import annotations

import contextlib
import os
import signal
import threading
import time
from typing import TYPE_CHECKING

from mutmut_win.models import TaskTimedOut

if TYPE_CHECKING:
    import multiprocessing
    import multiprocessing.queues

#: How often (in seconds) the monitor thread wakes up to check deadlines.
_POLL_INTERVAL: float = 1.0


class WallClockTimeout:
    """Background deadline monitor for spawned mutation workers.

    Register a ``(mutant_name, worker_pid, deadline)`` entry when a task
    starts, and unregister it when the task completes normally.  If the
    monitor thread finds an entry whose deadline has passed it kills the
    worker and emits a ``TaskTimedOut`` event.

    Args:
        event_queue: The shared queue into which ``TaskTimedOut`` events are
            placed.
    """

    def __init__(self, event_queue: multiprocessing.Queue) -> None:  # type: ignore[type-arg]
        self._event_queue: multiprocessing.Queue = event_queue  # type: ignore[type-arg]
        # _entries maps mutant_name -> (worker_pid, deadline_monotonic)
        self._entries: dict[str, tuple[int, float]] = {}
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def register(self, mutant_name: str, worker_pid: int, deadline: float) -> None:
        """Register a mutant with its worker PID and monotonic deadline.

        Args:
            mutant_name: Unique mutant identifier matching the task.
            worker_pid: OS PID of the worker process running the task.
            deadline: Absolute monotonic time (``time.monotonic()``) after
                which the task is considered timed out.
        """
        with self._lock:
            self._entries[mutant_name] = (worker_pid, deadline)

    def unregister(self, mutant_name: str) -> None:
        """Remove a mutant from deadline tracking (task completed normally).

        Silently ignored if *mutant_name* is not currently registered.

        Args:
            mutant_name: Identifier that was previously passed to
                :meth:`register`.
        """
        with self._lock:
            self._entries.pop(mutant_name, None)

    def start(self) -> None:
        """Start the background monitor thread.

        Must be called before any workers are started.  Safe to call only once
        per instance — subsequent calls are no-ops.
        """
        if self._thread is not None:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._monitor_loop,
            name="WallClockTimeoutMonitor",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        """Stop the background monitor thread and wait for it to exit.

        After this call the instance must not be reused.
        """
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join()
            self._thread = None

    # ------------------------------------------------------------------
    # Internal implementation
    # ------------------------------------------------------------------

    def _monitor_loop(self) -> None:
        """Poll registered deadlines every ``_POLL_INTERVAL`` seconds."""
        while not self._stop_event.wait(timeout=_POLL_INTERVAL):
            self._check_deadlines()
        # One final check before exiting so short-lived tests don't miss it.
        self._check_deadlines()

    def _check_deadlines(self) -> None:
        """Kill any workers whose deadline has passed and emit events."""
        now = time.monotonic()
        timed_out: list[tuple[str, int]] = []

        with self._lock:
            for mutant_name, (pid, deadline) in list(self._entries.items()):
                if now >= deadline:
                    timed_out.append((mutant_name, pid))
                    del self._entries[mutant_name]

        for mutant_name, pid in timed_out:
            _kill_process(pid)
            self._event_queue.put(
                TaskTimedOut(mutant_name=mutant_name, worker_pid=pid).model_dump()
            )


def _kill_process(pid: int) -> None:
    """Attempt to forcefully terminate the process with the given PID.

    Uses ``os.kill`` with ``SIGTERM`` (Unix) or ``signal.CTRL_C_EVENT``
    (Windows).  On Windows, ``SIGTERM`` maps to ``TerminateProcess``, so it
    effectively hard-kills the process.  Silently swallows errors for already
    dead or inaccessible processes.

    Args:
        pid: OS process identifier to kill.
    """
    with contextlib.suppress(ProcessLookupError, PermissionError, OSError):
        os.kill(pid, signal.SIGTERM)
