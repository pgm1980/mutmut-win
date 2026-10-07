"""Integration: workspace lock contention — two engines, one workspace (GAP-6)."""

from __future__ import annotations

import subprocess
import sys
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.integration, pytest.mark.slow]


def _setup_project(tmp: Path) -> Path:
    project = tmp / "proj"
    src = project / "src" / "pkg"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    tests = project / "tests"
    tests.mkdir()
    (tests / "test_f.py").write_text(
        "def test_f():\n    from pkg import f\n    assert f() == 1\n", encoding="utf-8"
    )
    return project


def _start_engine(project: Path) -> subprocess.Popen[str]:
    return subprocess.Popen(
        [sys.executable, "-m", "mutmut_win", "run", "--no-progress"],
        cwd=project,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


class TestWorkspaceLockContention:
    def test_second_engine_rejected_while_first_holds_lock(self, tmp_path: Path) -> None:
        """Two simultaneous runs: one wins the lock, the other is rejected."""

        project = _setup_project(tmp_path)

        first = _start_engine(project)
        # Give the first a moment to acquire the lock
        import time

        time.sleep(5)

        second_result = subprocess.run(
            [sys.executable, "-m", "mutmut_win", "run", "--no-progress"],
            cwd=project,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=120,
            check=False,
        )

        # Clean up first
        first.kill()
        first.wait(timeout=30)

        # The second should have failed (lock held)
        # It might exit with 1 (domain error) or another defined code
        assert second_result.returncode != 0, (
            f"Second engine should be rejected while first holds lock.\n"
            f"stdout:\n{second_result.stdout}\nstderr:\n{second_result.stderr}"
        )

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
