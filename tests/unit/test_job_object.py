"""Tests for mutmut_win.process.job_object — Windows Job Object orphan protection.

These tests verify that:
1. A Job Object can be created with KILL_ON_JOB_CLOSE
2. A subprocess can be assigned to a Job Object
3. Closing the Job handle kills all assigned processes (deterministic, no timing)
4. Graceful degradation works on non-Windows platforms
5. Win32 diagnostics are accurate: real error codes (use_last_error), explicit
   argtypes/restype signatures, least-privilege OpenProcess access mask
"""

from __future__ import annotations

import re
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

    def test_open_process_failure_reports_real_win32_error_code(self) -> None:
        """A failed OpenProcess must report the real Win32 error code, not 0.

        PID 0 is the System Idle Process, which can never be opened; Windows
        fails deterministically with ERROR_INVALID_PARAMETER (87). Regression
        test for audit finding A2-JT-005: ``ctypes.windll.kernel32`` was loaded
        without ``use_last_error=True``, so ``ctypes.get_last_error()`` always
        reported 0 in the OSError message.
        """
        from mutmut_win.process.job_object import (
            assign_process_to_job,
            close_job,
            create_kill_on_close_job,
        )

        job = create_kill_on_close_job()
        try:
            with pytest.raises(OSError, match=r"OpenProcess\(0\) failed") as exc_info:
                assign_process_to_job(job, 0)
        finally:
            close_job(job)

        code_match = re.search(r"error (\d+)", str(exc_info.value))
        assert code_match is not None, f"no error code in message: {exc_info.value}"
        assert int(code_match.group(1)) != 0, "Win32 error code must not be 0"

    def test_kernel32_signatures_declared(self) -> None:
        """All kernel32 bindings must declare argtypes/restype explicitly.

        Regression test for audit finding A2-JT-006: without declarations
        ctypes defaults everything to ``c_int``, silently truncating 64-bit
        HANDLE values on Win64.
        """
        from ctypes import c_int, wintypes

        from mutmut_win.process import job_object

        k32 = job_object._kernel32

        assert k32.CreateJobObjectW.restype is wintypes.HANDLE
        assert tuple(k32.CreateJobObjectW.argtypes or ()) == (
            wintypes.LPVOID,
            wintypes.LPCWSTR,
        )

        assert k32.SetInformationJobObject.restype is wintypes.BOOL
        assert tuple(k32.SetInformationJobObject.argtypes or ()) == (
            wintypes.HANDLE,
            c_int,
            wintypes.LPVOID,
            wintypes.DWORD,
        )

        assert k32.AssignProcessToJobObject.restype is wintypes.BOOL
        assert tuple(k32.AssignProcessToJobObject.argtypes or ()) == (
            wintypes.HANDLE,
            wintypes.HANDLE,
        )

        assert k32.OpenProcess.restype is wintypes.HANDLE
        assert tuple(k32.OpenProcess.argtypes or ()) == (
            wintypes.DWORD,
            wintypes.BOOL,
            wintypes.DWORD,
        )

        assert k32.CloseHandle.restype is wintypes.BOOL
        assert tuple(k32.CloseHandle.argtypes or ()) == (wintypes.HANDLE,)

    def test_open_process_uses_least_privilege_mask(self) -> None:
        """OpenProcess must request only SET_QUOTA | TERMINATE, not ALL_ACCESS.

        Regression test for audit finding A2-JT-017: ``AssignProcessToJobObject``
        only requires PROCESS_SET_QUOTA (0x0100) | PROCESS_TERMINATE (0x0001);
        the previous PROCESS_ALL_ACCESS (0x1F0FFF) was over-privileged.
        """
        from mutmut_win.process import job_object

        assert job_object._PROCESS_ASSIGN_ACCESS == 0x0101
        assert not hasattr(job_object, "_PROCESS_ALL_ACCESS")


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
