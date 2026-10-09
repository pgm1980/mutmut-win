"""E2E: native Ctrl-C at an acknowledged test phase and verified restart."""

from __future__ import annotations

import sqlite3
import subprocess
import sys
import time
from contextlib import closing

# Pydantic resolves the Path field when constructing _InterruptEvidence.
from pathlib import Path  # noqa: TC003

import psutil
import pytest
from pydantic import BaseModel

from tests.e2e.e2e_util import SIMPLE_LIB, copy_project, kill_process_tree

pytestmark = [pytest.mark.e2e, pytest.mark.slow]
_ENGINE_CREATIONFLAGS = subprocess.CREATE_NEW_CONSOLE


class _RunSnapshot(BaseModel):
    """Persisted identity and status for one observed run."""

    run_id: str
    sequence: int
    status: str


class _InterruptEvidence(BaseModel):
    """Observed native interruption, bound to a live pytest phase and run."""

    project: Path
    engine_pid: int
    phase_pid: int
    before: _RunSnapshot
    after: _RunSnapshot
    signal_helper_succeeded: bool
    exit_code: int


def _start_engine(project: Path) -> subprocess.Popen[str]:
    """Start the real CLI in its own hidden console with file-backed output."""
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = subprocess.SW_HIDE
    with (project.parent / "interrupt-engine.log").open("w", encoding="utf-8") as log:
        return subprocess.Popen(
            [sys.executable, "-m", "mutmut_win", "run", "--no-progress"],
            cwd=project,
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=_ENGINE_CREATIONFLAGS,
            startupinfo=startup,
        )


def _send_ctrl_c(proc: subprocess.Popen[str]) -> bool:
    """Request Ctrl-C in the isolated engine console and check every BOOL.

    CTRL_C_EVENT cannot target a nonzero process group. Only the helper
    attaches; pytest never changes console state. The helper ignores its
    own broadcast, and exit/status assertions verify delivery to the engine.
    """
    helper_code = (
        "import ctypes, sys\n"
        "kernel32 = ctypes.windll.kernel32\n"
        "kernel32.FreeConsole()\n"
        "attached = kernel32.AttachConsole(int(sys.argv[1]))\n"
        "if not attached:\n    sys.exit(3)\n"
        "ignored = kernel32.SetConsoleCtrlHandler(None, True)\n"
        "if not ignored:\n    sys.exit(4)\n"
        "sent = kernel32.GenerateConsoleCtrlEvent(0, 0)\n"
        "sys.exit(0 if sent else 5)\n"
    )
    # The helper source is a fixed literal; its sole argument is our child PID.
    helper = subprocess.run(  # noqa: S603
        [sys.executable, "-c", helper_code, str(proc.pid)],
        capture_output=True,
        timeout=15,
        check=False,
    )
    return helper.returncode == 0


def _wait_for_staging(project: Path, proc: subprocess.Popen[str], timeout: float = 180.0) -> bool:
    """Wait for an acknowledged running pytest body, not mere staging creation."""
    deadline = time.monotonic() + timeout
    marker = project.parent / "pytest-phase.pid"
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            return False
        if marker.is_file():
            return True
        time.sleep(0.05)
    return False


def _run_snapshot(project: Path, run_id: str | None = None) -> _RunSnapshot:
    db = project / ".mutmut-cache" / "mutmut-cache.db"
    with closing(sqlite3.connect(f"file:{db}?mode=ro", uri=True)) as conn:
        if run_id is None:
            row = conn.execute(
                "SELECT run_id, sequence, status FROM mutation_run ORDER BY sequence DESC LIMIT 1"
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT run_id, sequence, status FROM mutation_run WHERE run_id = ?", (run_id,)
            ).fetchone()
    assert row is not None, "the acknowledged phase must belong to a persisted run"
    return _RunSnapshot(run_id=row[0], sequence=row[1], status=row[2])


def _run_status(project: Path) -> str:
    return _run_snapshot(project).status


def _interrupt_in_test_phase(tmp_path: Path) -> _InterruptEvidence:
    project = copy_project(SIMPLE_LIB, tmp_path)
    hold = tmp_path / "hold-pytest-phase"
    marker = tmp_path / "pytest-phase.pid"
    hold.touch()
    tests = project / "tests"
    tests.mkdir(exist_ok=True)
    (tests / "test_interrupt_barrier.py").write_text(
        "import os\nimport time\nfrom pathlib import Path\n"
        "def test_interrupt_barrier():\n"
        f"    hold = Path({str(hold)!r})\n"
        "    if hold.exists():\n"
        f"        marker = Path({str(marker)!r})\n"
        "        temporary = marker.with_suffix('.tmp')\n"
        "        temporary.write_text(str(os.getpid()), encoding='ascii')\n"
        "        temporary.replace(marker)\n"
        "        while hold.exists():\n            time.sleep(0.05)\n",
        encoding="utf-8",
    )
    proc = _start_engine(project)
    try:
        assert _wait_for_staging(project, proc), "no live pytest-phase acknowledgement"
        assert _run_status(project) == "running", "first run must still be running before Ctrl-C"
        before = _run_snapshot(project)
        phase_pid = int(marker.read_text(encoding="ascii"))
        assert phase_pid in {
            child.pid for child in psutil.Process(proc.pid).children(recursive=True)
        }
        assert proc.poll() is None
        delivered = _send_ctrl_c(proc)
        assert delivered, "AttachConsole/SetConsoleCtrlHandler/GenerateConsoleCtrlEvent failed"
        exit_code = proc.wait(timeout=180)
        assert exit_code == 130, f"expected exit 130, got {exit_code}"
        assert _run_status(project) == "interrupted"
        after = _run_snapshot(project)
        assert after.run_id == before.run_id
        assert after.sequence == before.sequence
        evidence = _InterruptEvidence(
            project=project,
            engine_pid=proc.pid,
            phase_pid=phase_pid,
            before=before,
            after=after,
            signal_helper_succeeded=delivered,
            exit_code=exit_code,
        )
        (tmp_path / "native-interrupt.json").write_text(
            evidence.model_dump_json(), encoding="utf-8"
        )
        return evidence
    finally:
        hold.unlink(missing_ok=True)
        if proc.poll() is None:
            kill_process_tree(proc)


class TestInterruptFinalization:
    def test_ctrl_c_produces_exit_130_and_interrupted_status(self, tmp_path: Path) -> None:
        """A native Ctrl-C in a live test phase yields 130 and an interrupted row."""
        _interrupt_in_test_phase(tmp_path)

    def test_restart_after_interrupt_works(self, tmp_path: Path) -> None:
        """Restart follows a proved interruption and preserves its previous row."""
        evidence = _interrupt_in_test_phase(tmp_path)
        project = evidence.project
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
        assert result.returncode == 0, result.stdout + result.stderr
        current = _run_snapshot(project)
        assert current.status == "completed"
        assert current.run_id != evidence.before.run_id
        assert current.sequence > evidence.before.sequence
        assert _run_snapshot(project, evidence.before.run_id).status == "interrupted"
        (tmp_path / "restart-completed.json").write_text(
            current.model_dump_json(), encoding="utf-8"
        )
