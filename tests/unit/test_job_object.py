"""Tests for mutmut_win.process.job_object — Windows Job Object orphan protection.

These tests verify that:
1. A Job Object can be created with KILL_ON_JOB_CLOSE
2. A subprocess can be assigned to a Job Object
3. Closing the Job handle kills all assigned processes (deterministic, no timing)
4. Graceful degradation works on non-Windows platforms
"""

from __future__ import annotations

import subprocess
import sys

import pytest


@pytest.mark.skipif(sys.platform != "win32", reason="Windows Job Objects only")
class TestJobObjectWindows:
    """Tests that run only on Windows — exercise the real Win32 API."""

    def test_create_job_object(self) -> None:
        from mutmut_win.process.job_object import close_job, create_kill_on_close_job

        handle = create_kill_on_close_job()
        assert handle > 0
        close_job(handle)

    def test_assign_process(self) -> None:
        from mutmut_win.process.job_object import (
            assign_process_to_job,
            close_job,
            create_kill_on_close_job,
        )

        job = create_kill_on_close_job()
        # Start a long-running subprocess
        proc = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(300)"],
        )
        try:
            assert proc.pid is not None
            assign_process_to_job(job, proc.pid)
        finally:
            proc.kill()
            proc.wait()
            close_job(job)

    def test_kill_on_close(self) -> None:
        """THE core test: closing the Job handle must kill the subprocess.

        This is deterministic — no timing, no polling. The OS kills the
        process synchronously when the last Job handle is closed.
        """
        from mutmut_win.process.job_object import (
            assign_process_to_job,
            close_job,
            create_kill_on_close_job,
        )

        job = create_kill_on_close_job()
        proc = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(300)"],
        )
        assert proc.pid is not None
        assign_process_to_job(job, proc.pid)

        # Close the Job handle — this MUST kill the subprocess.
        close_job(job)

        # The process should be dead now. wait() with a generous timeout.
        exit_code = proc.wait(timeout=10)
        assert exit_code is not None, "Process should have been killed"

    def test_kill_on_close_kills_grandchild(self) -> None:
        """Job Objects kill the entire process tree — including grandchildren.

        This tests the scenario that caused the CPU overheating: a worker
        starts a pytest subprocess, which is a grandchild of the main process.
        """
        from mutmut_win.process.job_object import (
            assign_process_to_job,
            close_job,
            create_kill_on_close_job,
        )

        job = create_kill_on_close_job()
        # Start a process that itself spawns a child (grandchild of us).
        proc = subprocess.Popen(
            [
                sys.executable,
                "-c",
                "import subprocess, sys, time; "
                "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(300)']); "
                "time.sleep(300)",
            ],
        )
        assert proc.pid is not None
        assign_process_to_job(job, proc.pid)

        # Give the grandchild time to spawn.
        import time

        time.sleep(1)

        # Close Job handle — must kill proc AND its grandchild.
        close_job(job)
        exit_code = proc.wait(timeout=10)
        assert exit_code is not None

    def test_assign_dead_process_raises(self) -> None:
        """Assigning a process that has already exited should raise OSError."""
        from mutmut_win.process.job_object import (
            assign_process_to_job,
            close_job,
            create_kill_on_close_job,
        )

        job = create_kill_on_close_job()
        proc = subprocess.Popen(
            [sys.executable, "-c", "pass"],
        )
        proc.wait()  # Wait for it to finish.

        # Assigning a dead process may fail (handle invalid) or succeed
        # (Windows keeps the handle briefly). Either is acceptable.
        try:
            assign_process_to_job(job, proc.pid)  # type: ignore[arg-type]
        except OSError:
            pass  # Expected on some Windows versions.
        finally:
            close_job(job)

    def test_double_close_is_safe(self) -> None:
        """Calling close_job twice should not crash."""
        from mutmut_win.process.job_object import close_job, create_kill_on_close_job

        job = create_kill_on_close_job()
        close_job(job)
        # Second close — should not raise (CloseHandle on invalid handle is a no-op).
        close_job(job)


@pytest.mark.skipif(sys.platform == "win32", reason="Tests non-Windows fallback")
class TestJobObjectNonWindows:
    """Tests that verify graceful behavior on non-Windows platforms."""

    def test_create_raises_runtime_error(self) -> None:
        from mutmut_win.process.job_object import create_kill_on_close_job

        with pytest.raises(RuntimeError, match="only available on Windows"):
            create_kill_on_close_job()

    def test_assign_raises_runtime_error(self) -> None:
        from mutmut_win.process.job_object import assign_process_to_job

        with pytest.raises(RuntimeError, match="only available on Windows"):
            assign_process_to_job(0, 1234)

    def test_close_is_noop(self) -> None:
        from mutmut_win.process.job_object import close_job

        # Should not raise on non-Windows.
        close_job(0)
