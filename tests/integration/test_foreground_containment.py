"""Integration: hard TUI death must kill the whole foreground child tree.

M-057 (issue #158): the browser's ``run``/``apply``/``tests-for-mutant``
children run via ``run_foreground_contained`` inside a kill-on-close Job
Object.  The decisive NESTED-jobs scenario: the contained child itself
creates its own kill-on-close job for a grandchild — exactly the pattern
the ``run`` child uses for its executor/worker pools.  Killing the parent
hard (TerminateProcess) must cascade: the parent's job handle closes, the
kernel kills the child; the child's own job handle then closes, the
kernel kills the grandchild.  Without this pin the fix could break every
TUI ``run`` action in the run-child (nested jobs are only available on
Windows 8+ / Server 2016+, the contract platforms).
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from typing import TYPE_CHECKING

import psutil
import pytest

if TYPE_CHECKING:
    from pathlib import Path

_LONG_SLEEP_SECONDS = 300
_STARTUP_DEADLINE_SECONDS = 30.0
_KILL_DEADLINE_SECONDS = 10.0
_POLL_INTERVAL_SECONDS = 0.1
_PARENT_WAIT_SECONDS = 5.0

pytestmark = [
    pytest.mark.integration,
    pytest.mark.slow,
    pytest.mark.skipif(sys.platform != "win32", reason="Job Objects are Windows-only"),
]

_CHILD_SCRIPT = f"""\
import json
import os
import sys
import time
from pathlib import Path

from mutmut_win.process.atomic_spawn import AtomicJobPopen
from mutmut_win.process.job_object import close_job, create_kill_on_close_job

pid_file = Path(sys.argv[1])
job = create_kill_on_close_job()
try:
    grandchild = AtomicJobPopen(
        [sys.executable, "-c", "import time; time.sleep({_LONG_SLEEP_SECONDS})"],
        job_handle=job,
    )
    pid_file.write_text(
        json.dumps({{"child": os.getpid(), "grandchild": grandchild.pid}}),
        encoding="utf-8",
    )
    time.sleep({_LONG_SLEEP_SECONDS})
finally:
    close_job(job)
"""

_PARENT_SCRIPT = """\
import sys

from mutmut_win.process.foreground import run_foreground_contained

run_foreground_contained([sys.executable, sys.argv[1], sys.argv[2]])
"""


def _wait_gone(pids: set[int], deadline_seconds: float) -> set[int]:
    """Poll until all PIDs exited; return the survivors on deadline expiry."""
    deadline = time.monotonic() + deadline_seconds
    while time.monotonic() < deadline:
        alive = {pid for pid in pids if psutil.pid_exists(pid)}
        if not alive:
            return set()
        time.sleep(_POLL_INTERVAL_SECONDS)
    return {pid for pid in pids if psutil.pid_exists(pid)}


def _terminate_if_alive(pid: int) -> None:
    """Belt-and-braces cleanup so a regression never leaks sleepers."""
    try:
        proc = psutil.Process(pid)
        proc.terminate()
        proc.wait(timeout=2.0)
    except (psutil.NoSuchProcess, psutil.AccessDenied):  # fmt: skip
        pass


def test_hard_parent_kill_terminates_child_and_nested_grandchild(tmp_path: Path) -> None:
    """TerminateProcess on the TUI parent must cascade through both job levels."""
    child_script = tmp_path / "contained_child.py"
    child_script.write_text(_CHILD_SCRIPT, encoding="utf-8")
    parent_script = tmp_path / "tui_parent.py"
    parent_script.write_text(_PARENT_SCRIPT, encoding="utf-8")
    pid_file = tmp_path / "pids.json"

    parent = subprocess.Popen(  # noqa: S603 - fixture scripts written to tmp_path above
        [sys.executable, str(parent_script), str(child_script), str(pid_file)]
    )

    deadline = time.monotonic() + _STARTUP_DEADLINE_SECONDS
    while time.monotonic() < deadline and not pid_file.exists():
        if parent.poll() is not None:
            # The launcher failed closed: this host forbids Job Objects.
            pytest.skip("environment could not establish Job Object containment")
        time.sleep(_POLL_INTERVAL_SECONDS)
    assert pid_file.exists(), "contained child never reported its process tree"

    pids = json.loads(pid_file.read_text(encoding="utf-8"))
    child_pid = int(pids["child"])
    grandchild_pid = int(pids["grandchild"])

    assert psutil.pid_exists(child_pid), "contained child must be alive before the kill"
    assert psutil.pid_exists(grandchild_pid), "nested grandchild must be alive before the kill"

    try:
        # Hard kill of the TUI process: TerminateProcess, no cleanup handlers.
        parent.kill()
        parent.wait(timeout=_PARENT_WAIT_SECONDS)

        survivors = _wait_gone({child_pid, grandchild_pid}, _KILL_DEADLINE_SECONDS)
        assert not survivors, (
            f"PIDs {survivors} survived the kill-on-close cascade — "
            "M-057 regression: the TUI child tree is no longer contained"
        )
    finally:
        _terminate_if_alive(parent.pid)
        _terminate_if_alive(child_pid)
        _terminate_if_alive(grandchild_pid)
