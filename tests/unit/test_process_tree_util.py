"""Self-tests for the process-tree helpers (AP-00 / Q-04)."""

from __future__ import annotations

import os
import subprocess
import sys
from typing import TYPE_CHECKING

import psutil
import pytest

from tests.unit.process_tree_util import (
    assert_tree_terminated,
    tree_cpu_seconds,
    tree_handles,
    wait_for_pid_file,
    write_pid_file_snippet,
)

if TYPE_CHECKING:
    from pathlib import Path


def test_wait_for_pid_file_reads_atomically_published_pid(tmp_path: Path) -> None:
    pid_file = tmp_path / "child.pid"
    # The snippet process keeps living after publishing so the PID is
    # observably valid (the venv launcher would otherwise reap it first).
    keep_alive = write_pid_file_snippet() + "import time\ntime.sleep(10)\n"
    proc = subprocess.Popen(  # noqa: S603  # interpreter + generated snippet are fully controlled
        [sys.executable, "-c", keep_alive, str(pid_file)],
    )
    try:
        pid = wait_for_pid_file(pid_file, timeout=10.0)
        # The PID belongs to the direct child (the interpreter that ran the
        # snippet). psutil accepts it as a live process.
        assert psutil.Process(pid).is_running()
    finally:
        proc.kill()
        proc.wait(timeout=10.0)


def test_wait_for_pid_file_fails_with_deadline_not_hang(tmp_path: Path) -> None:
    with pytest.raises(AssertionError, match="did not appear"):
        wait_for_pid_file(tmp_path / "never.pid", timeout=0.2, poll_seconds=0.02)


def test_wait_for_pid_file_rejects_non_integer_content(tmp_path: Path) -> None:
    pid_file = tmp_path / "garbage.pid"
    pid_file.write_text("not-a-pid", encoding="ascii")
    with pytest.raises(AssertionError, match="non-integer"):
        wait_for_pid_file(pid_file, timeout=0.1)


def test_tree_handles_includes_root_and_descendants() -> None:
    handles = tree_handles(os.getpid())
    assert handles[0].pid == os.getpid()
    assert all(isinstance(handle, psutil.Process) for handle in handles)


def test_tree_cpu_seconds_is_nonnegative() -> None:
    handles = tree_handles(os.getpid())
    assert tree_cpu_seconds(handles) >= 0.0


def test_assert_tree_terminated_fails_while_process_lives() -> None:
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        handles = tree_handles(proc.pid)
        with pytest.raises(AssertionError, match="survived"):
            assert_tree_terminated(handles, timeout=0.5)
    finally:
        proc.kill()
        proc.wait(timeout=10.0)


def test_assert_tree_terminated_passes_after_process_ends() -> None:
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    proc.wait(timeout=10.0)
    try:
        handles: list[psutil.Process] = [psutil.Process(proc.pid)]
    except psutil.NoSuchProcess:
        # Already reaped: nothing left to observe, the assertion is trivially
        # satisfied and the helper must not raise on an empty list.
        handles = []
    assert_tree_terminated(handles, timeout=2.0)
