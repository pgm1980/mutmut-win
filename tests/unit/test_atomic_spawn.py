"""Regression contracts for atomic Windows Job-list process creation."""

from __future__ import annotations

import contextlib
import ctypes
import subprocess
import sys
from ctypes import wintypes

import pytest

from mutmut_win.process.atomic_spawn import AtomicJobPopen
from mutmut_win.process.job_object import close_job, create_kill_on_close_job


@pytest.mark.skipif(sys.platform != "win32", reason="Windows Job-list creation")
def test_child_is_job_member_at_first_user_mode_observation() -> None:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.IsProcessInJob.argtypes = [
        wintypes.HANDLE,
        wintypes.HANDLE,
        ctypes.POINTER(wintypes.BOOL),
    ]
    kernel32.IsProcessInJob.restype = wintypes.BOOL

    job_handle = create_kill_on_close_job()
    process: subprocess.Popen[bytes] | None = None
    try:
        process = AtomicJobPopen(
            [sys.executable, "-c", "import time; time.sleep(120)"],
            job_handle=job_handle,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        in_job = wintypes.BOOL()
        assert kernel32.IsProcessInJob(
            int(process._handle),  # type: ignore[attr-defined]
            job_handle,
            ctypes.byref(in_job),
        )
        assert bool(in_job.value) is True

        close_job(job_handle)
        job_handle = 0
        process.wait(timeout=5.0)
    finally:
        if job_handle:
            close_job(job_handle)
        if process is not None and process.poll() is None:
            with contextlib.suppress(OSError):
                process.kill()
            with contextlib.suppress(OSError, subprocess.TimeoutExpired):
                process.wait(timeout=2.0)
