"""Deterministic test for Bug #54 — Job Object kill-on-close behaviour.

The Hardening Sprint 13 added a Windows Job Object to ``SpawnPoolExecutor``
so that orphaned worker processes die when the parent dies. The behaviour
was demonstrated in interactive testing but never pinned down by an
automated test, leaving #54 open.

This test creates a long-running child subprocess, assigns it to a Job
Object with the ``KILL_ON_JOB_CLOSE`` flag, then closes the Job Object
handle. The OS must terminate the child within a bounded time window.

Test is Windows-only (graceful skip elsewhere) and marked ``slow`` because
it spins up a subprocess. The assigned child sleeps for 30 s by default —
if the Job Object fix regresses, the test fails fast (2 s deadline) rather
than waiting out the child's natural lifetime.
"""

from __future__ import annotations

import subprocess
import sys
import time

import pytest

_LONG_SLEEP_SECONDS = 30
_KILL_DEADLINE_SECONDS = 2.0
_POLL_INTERVAL_SECONDS = 0.05


pytestmark = [
    pytest.mark.integration,
    pytest.mark.slow,
    pytest.mark.skipif(sys.platform != "win32", reason="Job Objects are Windows-only"),
]


def test_close_job_terminates_assigned_child() -> None:
    """Closing the Job Object handle must kill the assigned child within 2 s."""
    from mutmut_win.process.job_object import (
        assign_process_to_job,
        close_job,
        create_kill_on_close_job,
    )

    # Long-running child — without the Job Object kill it would live for 30 s.
    child = subprocess.Popen(  # noqa: S603 - we control the executable + args
        [sys.executable, "-c", f"import time; time.sleep({_LONG_SLEEP_SECONDS})"],
    )

    try:
        job = create_kill_on_close_job()
        try:
            try:
                assign_process_to_job(job, child.pid)
            except OSError as exc:
                # Some host environments place pytest itself in a Job Object that
                # forbids the child from joining a new one. In that case the
                # behaviour can't be tested deterministically — skip.
                pytest.skip(f"AssignProcessToJobObject not permitted in this env: {exc}")

            assert child.poll() is None, "Child should still be alive immediately after assignment"
        finally:
            # Close the only handle — OS terminates every process in the job.
            close_job(job)

        deadline = time.monotonic() + _KILL_DEADLINE_SECONDS
        while time.monotonic() < deadline:
            if child.poll() is not None:
                break
            time.sleep(_POLL_INTERVAL_SECONDS)

        assert child.poll() is not None, (
            f"Child PID {child.pid} should have been killed by Job Object close, "
            f"but is still alive after {_KILL_DEADLINE_SECONDS} s. "
            "Bug #54: Job Object kill-on-close regression."
        )
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=2.0)


def test_close_job_does_not_kill_unassigned_processes() -> None:
    """A second subprocess that was NOT assigned to the job must survive the close."""
    from mutmut_win.process.job_object import (
        assign_process_to_job,
        close_job,
        create_kill_on_close_job,
    )

    assigned = subprocess.Popen(  # noqa: S603
        [sys.executable, "-c", f"import time; time.sleep({_LONG_SLEEP_SECONDS})"],
    )
    unassigned = subprocess.Popen(  # noqa: S603
        [sys.executable, "-c", f"import time; time.sleep({_LONG_SLEEP_SECONDS})"],
    )

    try:
        job = create_kill_on_close_job()
        try:
            try:
                assign_process_to_job(job, assigned.pid)
            except OSError as exc:
                pytest.skip(f"AssignProcessToJobObject not permitted in this env: {exc}")
        finally:
            close_job(job)

        # assigned should die, unassigned should still be alive
        deadline = time.monotonic() + _KILL_DEADLINE_SECONDS
        while time.monotonic() < deadline:
            if assigned.poll() is not None:
                break
            time.sleep(_POLL_INTERVAL_SECONDS)

        assert assigned.poll() is not None, "Assigned child should have been killed"
        assert unassigned.poll() is None, (
            "Unassigned child must survive — Job Object scope is per-process, not global"
        )
    finally:
        for child in (assigned, unassigned):
            if child.poll() is None:
                child.kill()
                child.wait(timeout=2.0)
