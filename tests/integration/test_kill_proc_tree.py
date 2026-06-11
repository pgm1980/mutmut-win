"""Integration tests for ``_kill_proc_tree`` orphan handling (Issue #82,
audit A2-EW-008) and the startup sweep wiring (A2-EW-007).

The old implementation returned early when the direct child had already
exited — children spawned by pytest (xdist, test subprocesses) survived
until job-object close at the END of the whole run.
"""

from __future__ import annotations

import contextlib
import subprocess
import sys
import textwrap
import time
from typing import TYPE_CHECKING

import psutil
import pytest

from mutmut_win.config import MutmutConfig
from mutmut_win.process.executor import SpawnPoolExecutor
from mutmut_win.process.worker import _create_task_job, _kill_proc_tree

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration

_PARENT_THAT_ORPHANS_A_CHILD = textwrap.dedent(
    """
    import subprocess, sys

    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    print(child.pid, flush=True)
    """
)

_PARENT_THAT_KEEPS_RUNNING = textwrap.dedent(
    """
    import subprocess, sys, time

    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    print(child.pid, flush=True)
    time.sleep(60)
    """
)


def _wait_until_dead(pid: int, timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline and psutil.pid_exists(pid):
        time.sleep(0.1)
    return not psutil.pid_exists(pid)


def _cleanup(pid: int) -> None:
    if psutil.pid_exists(pid):
        with contextlib.suppress(psutil.NoSuchProcess, psutil.AccessDenied):
            psutil.Process(pid).kill()


class TestKillProcTreeOrphans:
    @pytest.mark.skipif(sys.platform != "win32", reason="per-task job objects are win32")
    def test_job_reaps_grandchildren_across_dead_intermediates(self, tmp_path: Path) -> None:
        """Production path (A2-EW-008): the per-task kill-on-close job is the
        only mechanism that bridges DEAD intermediate processes — a live-pid
        ppid sweep cannot (empirically shown: the grandchild's recorded ppid
        points at the dead intermediate, not at our Popen child)."""
        script = tmp_path / "parent.py"
        script.write_text(_PARENT_THAT_ORPHANS_A_CHILD, encoding="utf-8")

        proc = subprocess.Popen(  # noqa: S603 — fully controlled command
            [sys.executable, str(script)],
            stdout=subprocess.PIPE,
            encoding="utf-8",
        )
        job_handle = _create_task_job(proc.pid)  # exactly as _process_task does
        assert proc.stdout is not None
        child_pid = int(proc.stdout.readline().strip())
        proc.wait(timeout=15)  # parent exits, grandchild becomes an orphan
        assert proc.poll() is not None
        assert psutil.pid_exists(child_pid)

        try:
            _kill_proc_tree(proc, job_handle)
            assert _wait_until_dead(child_pid), (
                "orphaned grandchild survived _kill_proc_tree — "
                "A2-EW-008 regression (job-object reaping broken)"
            )
        finally:
            _cleanup(child_pid)

    def test_sweep_kills_live_chain_without_job(self, tmp_path: Path) -> None:
        """Belt-and-suspenders layer: with the chain alive, the ppid sweep
        kills parent and child even without a job handle."""
        script = tmp_path / "parent.py"
        script.write_text(_PARENT_THAT_KEEPS_RUNNING, encoding="utf-8")

        proc = subprocess.Popen(  # noqa: S603 — fully controlled command
            [sys.executable, str(script)],
            stdout=subprocess.PIPE,
            encoding="utf-8",
        )
        assert proc.stdout is not None
        child_pid = int(proc.stdout.readline().strip())
        assert psutil.pid_exists(child_pid)

        try:
            _kill_proc_tree(proc)
            assert proc.poll() is not None or _wait_until_dead(proc.pid)
            assert _wait_until_dead(child_pid), "live-chain child survived the sweep"
        finally:
            _cleanup(child_pid)
            with contextlib.suppress(Exception):
                proc.kill()


class TestStartupSweepWiring:
    def test_start_sweeps_stale_artifacts(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        mutants = tmp_path / "mutants"
        mutants.mkdir()
        stale = mutants / "mutmut_out_stale.log"
        stale.write_text("leftover from an aborted run", encoding="utf-8")

        executor = SpawnPoolExecutor(max_workers=1, config=MutmutConfig())
        try:
            executor.start([])  # no tasks: workers drain their sentinel and exit
            assert not stale.exists()
        finally:
            executor.shutdown(timeout=10.0)
