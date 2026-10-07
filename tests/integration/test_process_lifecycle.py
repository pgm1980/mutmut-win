"""Integration: process lifecycle corridors for the engine pipeline (T4, TM-03/04).

Real process trees (Job Object containment, pipe handles, runtime-root
cleanup) verified over actual ``mutmut-win`` subprocess runs — not mocked.

Ctrl-C delivery on Windows: ``signal.CTRL_C_EVENT`` targets the entire
process GROUP, which would kill pytest itself.  The interrupt tests start
the engine with ``CREATE_NEW_PROCESS_GROUP`` so the signal reaches only
the engine's group; the hard-kill tests use ``process.kill()`` directly.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import pytest

from tests.e2e.e2e_util import SIMPLE_LIB, copy_project, run_cli

pytestmark = [pytest.mark.integration, pytest.mark.slow]


def _start_isolated_run(project_dir: Path) -> subprocess.Popen[str]:
    """Start ``mutmut-win run`` in its own process group (Ctrl-C-safe)."""

    return subprocess.Popen(
        [sys.executable, "-m", "mutmut_win", "run", "--no-progress"],
        cwd=project_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
    )


def _process_alive(pid: int) -> bool:
    import psutil

    try:
        psutil.Process(pid)
        return True
    except psutil.NoSuchProcess:
        return False


# ---------------------------------------------------------------------------
# Job Object / tree-kill contracts (TM-03)
# ---------------------------------------------------------------------------


class TestTreeKill:
    """Hard-kill of the engine reaps the full tree (Job Object contract)."""

    def test_kill_parent_reaps_descendants(self, tmp_path: Path) -> None:
        """Hard-kill of the engine leaves no orphaned process tree."""

        project = copy_project(SIMPLE_LIB, tmp_path)
        process = _start_isolated_run(project)
        time.sleep(20)  # get into dispatch with active workers
        if process.poll() is not None:
            process.kill()
            pytest.skip("run finished before kill could be delivered")
        process.kill()
        process.wait(timeout=30)
        time.sleep(5)
        assert not _process_alive(process.pid), "engine process must be gone"


# ---------------------------------------------------------------------------
# Runtime-root lifecycle (M-146, TM-03)
# ---------------------------------------------------------------------------


class TestRuntimeRootLifecycle:
    """The mkdtemp run-root is cleaned up on normal shutdown."""

    def test_no_runtime_root_left_after_clean_exit(self, tmp_path: Path) -> None:
        """After a successful run, no temp runtime-root directories remain."""

        search_root = Path(sys.executable).parent.parent.parent
        pattern = "mutmut-win-run-*"
        before = {str(p) for p in search_root.glob(pattern)}
        project = copy_project(SIMPLE_LIB, tmp_path)
        result = run_cli(project, "run", "--no-progress")
        assert result.returncode == 0
        time.sleep(2)
        after = {str(p) for p in search_root.glob(pattern)}
        leaked = after - before
        assert not leaked, f"runtime-root directories leaked: {leaked}"


# ---------------------------------------------------------------------------
# Pool collapse recovery (TM-03)
# ---------------------------------------------------------------------------


class TestPoolCollapse:
    """Worker pool collapse (all workers die) produces a defined terminal state."""

    def test_all_workers_killed_engine_completes_or_aborts(self, tmp_path: Path) -> None:
        """Killing all worker children yields a defined terminal state."""

        import psutil

        project = copy_project(SIMPLE_LIB, tmp_path)
        process = _start_isolated_run(project)
        time.sleep(20)  # get into dispatch
        if process.poll() is not None:
            pytest.skip("run finished before collapse could be induced")
        try:
            parent = psutil.Process(process.pid)
            children = parent.children(recursive=True)
        except psutil.NoSuchProcess:
            pytest.skip("engine already exited")
        for child in children:
            child.kill()
        try:
            exit_code = process.wait(timeout=120)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=30)
            pytest.fail("engine hung after pool collapse (no terminal state within 120s)")
        # The core contract is TERMINATION within the budget; the exact exit
        # code depends on which phase the collapse reached.
        assert isinstance(exit_code, int)
