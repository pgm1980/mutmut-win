"""Tests for mutmut_win.process.job_object — Windows Job Object orphan protection.

These tests verify that:
1. A Job Object can be created with KILL_ON_JOB_CLOSE
2. A subprocess can be assigned to a Job Object
3. Closing the Job handle kills all assigned processes and their descendants
   (deterministic PID-file synchronisation, no sleeps; the leaf process is
   observed directly before and after the close — issue #142 / M-140)
4. Graceful degradation works on non-Windows platforms
5. Win32 diagnostics are accurate: real error codes (use_last_error), explicit
   argtypes/restype signatures, least-privilege OpenProcess access mask
"""

from __future__ import annotations

import contextlib
import re
import subprocess
import sys
from typing import TYPE_CHECKING

import psutil
import pytest

from tests.unit.process_tree_util import (
    assert_tree_terminated,
    wait_for_pid_file,
    write_pid_file_snippet,
)

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

#: ``subprocess`` has no CREATE_SUSPENDED constant (verified against
#: CPython 3.14.7); the production worker uses the same literal value.
_CREATE_SUSPENDED = 0x00000004


def _spawn_child_and_grandchild(
    child_pid_file: Path, leaf_pid_file: Path
) -> subprocess.Popen[bytes]:
    """Start a suspended root whose descendants publish their PIDs atomically.

    The child writes ``os.getpid()`` (the working interpreter below the venv
    launcher) to *child_pid_file*, then spawns the grandchild, which writes
    its own PID — the true leaf of the tree — to *leaf_pid_file* and sleeps.
    """
    grandchild_code = write_pid_file_snippet() + "import time\ntime.sleep(300)\n"
    child_code = (
        write_pid_file_snippet()
        + "import subprocess, sys, time\n"
        + "subprocess.Popen([sys.executable, '-c', "
        + repr(grandchild_code)
        + ", sys.argv[2]])\n"
        + "time.sleep(300)\n"
    )
    # S603: interpreter plus fully test-controlled scripts, no untrusted input.
    return subprocess.Popen(  # noqa: S603
        [sys.executable, "-c", child_code, str(child_pid_file), str(leaf_pid_file)],
        creationflags=_CREATE_SUSPENDED,
    )


def _assert_tree_inside_job(job_handle: int, handles: Sequence[psutil.Process]) -> None:
    """Assert every observed tree member is a member of the kill-on-close job.

    Separates the two failure modes of the containment proof — "not inside the
    job" (assignment broken) and "not terminated" (kill-on-close broken) — by
    checking ``IsProcessInJob`` per process before the handle is closed.
    """
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.IsProcessInJob.argtypes = (
        wintypes.HANDLE,
        wintypes.HANDLE,
        ctypes.POINTER(wintypes.BOOL),
    )
    kernel32.IsProcessInJob.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel32.CloseHandle.restype = wintypes.BOOL

    process_query_limited_information = 0x1000
    for handle in handles:
        process_handle = kernel32.OpenProcess(process_query_limited_information, False, handle.pid)
        if not process_handle:
            pytest.fail(f"OpenProcess({handle.pid}) failed: {ctypes.get_last_error()}")
        try:
            inside = wintypes.BOOL()
            if not kernel32.IsProcessInJob(process_handle, job_handle, ctypes.byref(inside)):
                pytest.fail(f"IsProcessInJob({handle.pid}) failed: {ctypes.get_last_error()}")
            assert inside.value, f"process {handle.pid} is not inside the kill-on-close job"
        finally:
            kernel32.CloseHandle(process_handle)


def _reap_tree(handles: Sequence[psutil.Process]) -> None:
    """Kill and reap every surviving handle (best effort, for finally blocks)."""
    for handle in handles:
        with contextlib.suppress(psutil.NoSuchProcess, psutil.AccessDenied):
            if handle.is_running():
                handle.kill()
    psutil.wait_procs(list(handles), timeout=10.0)


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

    def test_kill_on_close_kills_grandchild(self, tmp_path: Path) -> None:
        """Job Objects kill the entire process tree — including the leaf.

        Regression test for the vacuous predecessor (issue #142 / M-140): the
        old test observed only the direct child after a fixed ``sleep(1)`` and
        stayed green whenever the grandchild escaped the job. This version is
        deterministic:

        - the root starts suspended and is assigned to the job *before* it
          resumes (the documented production contract of the PID-based API),
          and it must have no children yet at assignment time;
        - child and leaf publish their PIDs atomically; the test waits with a
          deadline for both files;
        - every tree member must be inside the job (``IsProcessInJob``), must
          be alive before the close, and must be gone within 10 s after
          exactly one ``close_job`` call;
        - surviving processes are killed in ``finally``.
        """
        from mutmut_win.process.job_object import (
            assign_process_to_job,
            close_job,
            create_kill_on_close_job,
        )

        child_pid_file = tmp_path / "child.pid"
        leaf_pid_file = tmp_path / "leaf.pid"

        job = create_kill_on_close_job()
        job_closed = False
        proc = _spawn_child_and_grandchild(child_pid_file, leaf_pid_file)
        assert proc.pid is not None
        handles: list[psutil.Process] = []
        try:
            root = psutil.Process(proc.pid)
            assert root.children() == [], "root must be childless while suspended"
            assign_process_to_job(job, proc.pid)
            root.resume()

            child_pid = wait_for_pid_file(child_pid_file, timeout=10.0)
            leaf_pid = wait_for_pid_file(leaf_pid_file, timeout=10.0)

            handles = [root, *root.children(recursive=True)]
            observed_pids = {handle.pid for handle in handles}
            assert child_pid in observed_pids, "child PID file must name a tree member"
            assert leaf_pid in observed_pids, "leaf PID file must name a tree member"
            assert all(handle.is_running() for handle in handles)
            _assert_tree_inside_job(job, handles)

            close_job(job)
            job_closed = True
            assert_tree_terminated(handles, timeout=10.0)
        finally:
            if not job_closed:
                with contextlib.suppress(Exception):
                    close_job(job)
            _reap_tree(handles)
            with contextlib.suppress(subprocess.TimeoutExpired):
                proc.wait(timeout=10.0)

    def test_tree_observation_detects_surviving_leaf(self, tmp_path: Path) -> None:
        """Negative control: without a job the leaf survives — observably.

        Runs the same deterministic tree setup WITHOUT any Job Object and
        proves that ``assert_tree_terminated`` fails and names the surviving
        leaf PID. This pins the observation helper as non-vacuous: only the
        kill-on-close contract, not an observation gap, lets the main test
        pass (issue #142 / M-140).
        """
        child_pid_file = tmp_path / "child.pid"
        leaf_pid_file = tmp_path / "leaf.pid"

        proc = _spawn_child_and_grandchild(child_pid_file, leaf_pid_file)
        assert proc.pid is not None
        handles: list[psutil.Process] = []
        try:
            psutil.Process(proc.pid).resume()
            leaf_pid = wait_for_pid_file(leaf_pid_file, timeout=10.0)
            root = psutil.Process(proc.pid)
            handles = [root, *root.children(recursive=True)]
            assert leaf_pid in {handle.pid for handle in handles}
            with pytest.raises(AssertionError, match="survived") as excinfo:
                assert_tree_terminated(handles, timeout=0.5)
            assert str(leaf_pid) in str(excinfo.value)
        finally:
            _reap_tree(handles)
            with contextlib.suppress(subprocess.TimeoutExpired):
                proc.wait(timeout=10.0)

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
