"""Integration coverage for bounded type-checker process-tree timeouts."""

from __future__ import annotations

import contextlib
import sys
import time
from typing import TYPE_CHECKING

import psutil
import pytest

import mutmut_win.type_checking as type_checking
from mutmut_win.exceptions import ProcessContainmentError, TypeCheckCommandError

if TYPE_CHECKING:
    from pathlib import Path


def _wait_until_dead(pid: int, timeout: float = 3.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            process = psutil.Process(pid)
            if not process.is_running() or process.status() == psutil.STATUS_ZOMBIE:
                return True
        except psutil.NoSuchProcess:
            return True
        time.sleep(0.05)
    return False


@pytest.mark.integration
@pytest.mark.parametrize(
    "job_object_available",
    [True, False],
    ids=["windows-job-object", "explicit-tree-fallback"],
)
def test_timeout_kills_grandchild_without_waiting_for_inherited_output_handles(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    job_object_available: bool,
) -> None:
    """A grandchild inheriting stdout/stderr cannot extend the root timeout."""
    pid_file = tmp_path / "type-checker-pids.txt"
    checker = tmp_path / "hanging_checker.py"
    checker.write_text(
        "import os\n"
        "import pathlib\n"
        "import subprocess\n"
        "import sys\n"
        "import time\n"
        "child = subprocess.Popen([sys.executable, '-c', "
        "'import time; time.sleep(8)'])\n"
        "pathlib.Path(sys.argv[1]).write_text("
        "f'{os.getpid()} {child.pid}', encoding='ascii')\n"
        "time.sleep(8)\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(type_checking, "TYPE_CHECK_TIMEOUT_SECONDS", 2)
    if not job_object_available:
        monkeypatch.setattr(type_checking, "_create_type_checker_job", lambda: None)

    started = time.monotonic()
    pids: list[int] = []
    try:
        if sys.platform == "win32" and not job_object_available:
            with pytest.raises(ProcessContainmentError, match="Job Object"):
                type_checking.run_type_checker([sys.executable, str(checker), str(pid_file)])
            assert time.monotonic() - started < 3.0
            assert not pid_file.exists(), "uncontained checker was allowed to start"
            return
        with pytest.raises(TypeCheckCommandError, match="timed out"):
            type_checking.run_type_checker([sys.executable, str(checker), str(pid_file)])
        elapsed = time.monotonic() - started

        assert elapsed < 6.0, (
            f"timeout waited for the grandchild's inherited output handles ({elapsed:.2f}s)"
        )
        assert pid_file.is_file(), "checker did not reach its grandchild-spawn point"
        pids = [int(value) for value in pid_file.read_text(encoding="ascii").split()]
        assert len(pids) == 2
        assert all(_wait_until_dead(pid) for pid in pids)
    finally:
        # Test-failure hygiene: never leave the deliberate sleeper behind.
        for pid in pids:
            with contextlib.suppress(psutil.AccessDenied, psutil.NoSuchProcess):
                psutil.Process(pid).kill()
