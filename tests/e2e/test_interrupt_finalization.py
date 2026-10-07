"""E2E: interrupt during the run — Ctrl-C yields exit 130, interrupted status (GAP-7).

Delivery note (Windows): ``CTRL_C_EVENT`` is a CONSOLE event.  A test runner
with captured output has no console, which makes ``send_signal(CTRL_C_EVENT)``
a silent no-op — the engine never sees anything and completes normally
(exit 0).  To test the real interrupt contract the engine gets its own
console (``CREATE_NEW_CONSOLE``) and process group
(``CREATE_NEW_PROCESS_GROUP``); the test attaches to that console, delivers
the event, and detaches immediately so pytest itself never receives it.
"""

from __future__ import annotations

import ctypes
import sqlite3
import subprocess
import sys
import time
from contextlib import closing
from typing import TYPE_CHECKING

import pytest

from tests.e2e.e2e_util import SIMPLE_LIB, copy_project

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.e2e, pytest.mark.slow]

_KERNEL32 = ctypes.windll.kernel32

_ENGINE_CREATIONFLAGS = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NEW_CONSOLE


def _start_engine(project: Path) -> subprocess.Popen[str]:
    """Start ``mutmut-win run`` with its own console + process group."""

    return subprocess.Popen(
        [sys.executable, "-m", "mutmut_win", "run", "--no-progress"],
        cwd=project,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=_ENGINE_CREATIONFLAGS,
    )


def _send_ctrl_c(proc: subprocess.Popen[str]) -> bool:
    """Deliver a genuine console Ctrl+C to the engine's group.

    Returns True when the event could be delivered.  Delivery runs in a
    short-lived helper subprocess that attaches to the engine's console and
    fires the event: the test runner itself never attaches to or detaches
    from any console (a runner that touched console state could disturb
    unrelated processes on the same machine — seen once as a stray
    STATUS_CONTROL_C_EXIT in an unrelated later test).
    """

    helper_code = (
        "import ctypes, sys\n"
        "kernel32 = ctypes.windll.kernel32\n"
        "pid = int(sys.argv[1])\n"
        "kernel32.FreeConsole()\n"
        "ok = kernel32.AttachConsole(pid)\n"
        "if ok:\n"
        "    kernel32.GenerateConsoleCtrlEvent(0, pid)\n"
        "sys.exit(0 if ok else 3)\n"
    )
    helper = subprocess.run(  # noqa: S603 - helper source is a literal above
        [sys.executable, "-c", helper_code, str(proc.pid)],
        capture_output=True,
        timeout=15,
        check=False,
    )
    return helper.returncode == 0


def _wait_for_staging(project: Path, proc: subprocess.Popen[str], timeout: float = 120.0) -> bool:
    """Wait until the run is underway (staging directory exists)."""

    deadline = time.time() + timeout
    while time.time() < deadline:
        if (project / "mutants").is_dir():
            return True
        if proc.poll() is not None:
            return False
        time.sleep(1)
    return (project / "mutants").is_dir()


def _run_status(project: Path) -> str:
    db = project / ".mutmut-cache" / "mutmut-cache.db"
    if not db.exists():
        return "no-db"
    with closing(sqlite3.connect(f"file:{db}?mode=ro", uri=True)) as conn:
        row = conn.execute(
            "SELECT status FROM mutation_run ORDER BY sequence DESC LIMIT 1"
        ).fetchone()
        return row[0] if row else "no-run"


class TestInterruptFinalization:
    def test_ctrl_c_produces_exit_130_and_interrupted_status(self, tmp_path: Path) -> None:
        """A delivered Ctrl-C must yield exit 130 and an interrupted run status."""

        project = copy_project(SIMPLE_LIB, tmp_path)
        proc = _start_engine(project)

        if not _wait_for_staging(project, proc):
            pytest.skip("run finished before interrupt could be delivered")

        time.sleep(5)  # land inside a live phase (fingerprinting / clean run)
        if proc.poll() is not None:
            pytest.skip("run finished before interrupt could be delivered")
        if not _send_ctrl_c(proc):
            proc.kill()
            proc.wait(timeout=30)
            pytest.fail("could not deliver CTRL_C_EVENT (AttachConsole failed)")

        try:
            exit_code = proc.wait(timeout=180)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=30)
            pytest.fail("engine did not exit after Ctrl-C within 180s")

        # AR-24 / M-076: EVERY Ctrl-C during the run honors exit 130.
        assert exit_code == 130, f"expected exit 130, got {exit_code}"

        # The cache DB stays readable (no lock deadlock) and the orchestrator
        # marked the run 'interrupted' before re-raising.
        status = _run_status(project)
        assert status == "interrupted", f"run status must be interrupted, got {status!r}"

    def test_restart_after_interrupt_works(self, tmp_path: Path) -> None:
        """After an interrupted run, a new run recovers and completes."""

        project = copy_project(SIMPLE_LIB, tmp_path)
        proc = _start_engine(project)

        if _wait_for_staging(project, proc):
            time.sleep(5)
            if proc.poll() is None:
                delivered = _send_ctrl_c(proc)
                if not delivered:
                    pytest.skip("could not deliver CTRL_C_EVENT (AttachConsole failed)")
                try:
                    proc.wait(timeout=180)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=30)
                    pytest.fail("engine did not exit after Ctrl-C within 180s")
        else:
            pytest.skip("first run finished before interrupt could be delivered")

        # Restart: recovery from 'interrupted' must allow a fresh completed run.
        result = subprocess.run(
            [sys.executable, "-m", "mutmut_win", "run", "--no-progress"],
            cwd=project,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=600,
            check=False,
        )
        assert result.returncode == 0, (
            f"Restart after interrupt should work.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
        assert _run_status(project) == "completed"
