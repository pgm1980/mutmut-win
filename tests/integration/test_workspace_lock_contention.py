"""Integration: workspace lock contention — two engines, one workspace (GAP-6)."""

from __future__ import annotations

import subprocess
import sys
import time
from typing import TYPE_CHECKING

import psutil
import pytest
from pydantic import BaseModel

from mutmut_win.process.run_lock import RunLockHeldError, WorkspaceRunLock
from tests.e2e.e2e_util import kill_process_tree

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.integration, pytest.mark.slow]


class _ObservedOwner(BaseModel):
    """Owner identity independently checked against the live engine."""

    pid: int
    process_start_time: float
    state: str


def _setup_project(tmp: Path, *, hold: bool = False) -> Path:
    project = tmp / "proj"
    src = project / "src" / "pkg"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    tests = project / "tests"
    tests.mkdir()
    (tests / "test_f.py").write_text(
        "from pathlib import Path\nimport time\n"
        "def test_f():\n"
        f"    barrier = Path({str(tmp / 'hold-first')!r})\n"
        "    while barrier.exists():\n        time.sleep(0.05)\n"
        "    from pkg import f\n    assert f() == 1\n",
        encoding="utf-8",
    )
    if hold:
        (tmp / "hold-first").touch()
    return project


def _start_engine(project: Path) -> subprocess.Popen[str]:
    with (project.parent / "first-engine.log").open("w", encoding="utf-8") as log:
        return subprocess.Popen(
            [sys.executable, "-m", "mutmut_win", "run", "--no-progress"],
            cwd=project,
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )


def _wait_for_owner(project: Path, first: subprocess.Popen[str]) -> tuple[Path, _ObservedOwner]:
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        assert first.poll() is None, "first engine exited before acquiring the workspace lock"
        for path in project.glob(".mutmut-win-*.run.lock"):
            owner = _ObservedOwner.model_validate_json(path.read_bytes())
            if owner.state == "acquired":
                # CPython's Windows venv launcher may own the Popen PID while
                # its interpreter child owns the lock. Both must be our tree.
                owned_pids = {first.pid} | {
                    child.pid for child in psutil.Process(first.pid).children(recursive=True)
                }
                assert owner.pid in owned_pids
                assert psutil.Process(owner.pid).create_time() == owner.process_start_time
                with pytest.raises(RunLockHeldError) as caught:
                    WorkspaceRunLock(path).acquire()
                assert caught.value.owner is not None
                assert caught.value.owner.pid == owner.pid
                return path, owner
        time.sleep(0.05)
    pytest.fail("live engine did not publish an acquired workspace owner within 60s")


class TestWorkspaceLockContention:
    def test_second_engine_rejected_while_first_holds_lock(self, tmp_path: Path) -> None:
        """Two simultaneous runs: one wins the lock, the other is rejected."""

        project = _setup_project(tmp_path, hold=True)
        first = _start_engine(project)
        try:
            lock_path, owner = _wait_for_owner(project, first)
            second_result = subprocess.run(
                [sys.executable, "-m", "mutmut_win", "run", "--no-progress"],
                cwd=project,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=120,
                check=False,
            )
            assert first.poll() is None, "lock owner must still be active at rejection"
            assert second_result.returncode == 1, second_result.stderr
            assert "workspace run lock is held at" in second_result.stderr
            assert str(lock_path) in second_result.stderr
            assert f"PID {owner.pid}, process started" in second_result.stderr
            (tmp_path / "hold-first").unlink()
            assert first.wait(timeout=600) == 0, (tmp_path / "first-engine.log").read_text(
                encoding="utf-8"
            )
            with WorkspaceRunLock(lock_path) as released:
                assert released.acquired
                assert released.owner is not None
                assert released.owner.pid != owner.pid
        finally:
            (tmp_path / "hold-first").unlink(missing_ok=True)
            if first.poll() is None:
                kill_process_tree(first)

    def test_lock_released_after_engine_exit(self, tmp_path: Path) -> None:
        """After the first engine exits, a second run can acquire the lock."""

        project = _setup_project(tmp_path)

        first = subprocess.run(
            [sys.executable, "-m", "mutmut_win", "run", "--no-progress"],
            cwd=project,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=600,
            check=False,
        )
        assert first.returncode == 0, "First run must complete"

        second = subprocess.run(
            [sys.executable, "-m", "mutmut_win", "run", "--no-progress"],
            cwd=project,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=600,
            check=False,
        )
        # Second run after first completes should succeed (cache reuse from M-147)
        assert second.returncode == 0, (
            f"Second run after first exits should work (lock released).\n"
            f"stdout:\n{second.stdout}\nstderr:\n{second.stderr}"
        )
