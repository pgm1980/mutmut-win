"""Cross-process integration tests for the workspace run lock."""

from __future__ import annotations

import contextlib
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import psutil
import pytest

from mutmut_win.process.run_lock import (
    DatabaseRunLocks,
    RunLockHeldError,
    WorkspaceRunLock,
    database_lock_paths_for_db,
)

_CHILD_HOLDER = """
import os
import pathlib
import sys
import time
from mutmut_win.process.run_lock import WorkspaceRunLock

lock_path = pathlib.Path(sys.argv[1])
ready_path = pathlib.Path(sys.argv[2])
lock = WorkspaceRunLock(lock_path).acquire()
ready_tmp = ready_path.with_name(f".{ready_path.name}.{os.getpid()}.tmp")
ready_tmp.write_text(str(os.getpid()), encoding="ascii")
os.replace(ready_tmp, ready_path)
while True:
    time.sleep(1)
"""

_DATABASE_CHILD_HOLDER_WITH_TEMP = """
import os
import pathlib
import sys
import tempfile
import time
from mutmut_win.process.run_lock import DatabaseRunLocks

db_path = pathlib.Path(sys.argv[1])
ready_path = pathlib.Path(sys.argv[2])
tempfile.tempdir = sys.argv[3]
lock = DatabaseRunLocks(db_path).acquire()
ready_tmp = ready_path.with_name(f".{ready_path.name}.{os.getpid()}.tmp")
ready_tmp.write_text(str(os.getpid()), encoding="ascii")
os.replace(ready_tmp, ready_path)
while True:
    time.sleep(1)
"""


def _wait_for_pid(path: Path, process: subprocess.Popen[bytes], timeout: float = 10.0) -> int:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.is_file():
            try:
                pid = int(path.read_text(encoding="ascii"))
            except (
                OSError,
                ValueError,
            ):
                # A ready marker is a content-bearing synchronization
                # primitive, not merely a pathname.  Keep waiting if an
                # antivirus/indexer or a non-atomic older publisher exposes a
                # transient empty/read-locked file.
                pass
            else:
                if pid > 0:
                    return pid
        if process.poll() is not None:
            pytest.fail(f"lock-holder child exited early with {process.returncode}")
        time.sleep(0.02)
    pytest.fail("lock-holder child did not publish its ready marker")


@pytest.mark.integration
def test_live_child_excludes_parent_then_abrupt_death_allows_safe_takeover(
    tmp_path: Path,
) -> None:
    lock_path = tmp_path / "run.lock"
    ready_path = tmp_path / "ready.txt"
    project_root = Path(__file__).resolve().parents[2]
    child = subprocess.Popen(  # noqa: S603 - controlled interpreter and script
        [sys.executable, "-c", _CHILD_HOLDER, str(lock_path), str(ready_path)],
        cwd=project_root,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    owner_process: psutil.Process | None = None

    try:
        child_pid = _wait_for_pid(ready_path, child)
        owner_process = psutil.Process(child_pid)

        with pytest.raises(RunLockHeldError) as exc_info:
            WorkspaceRunLock(lock_path).acquire()
        assert exc_info.value.owner is not None
        assert exc_info.value.owner.pid == child_pid
        assert exc_info.value.owner.process_start_time > 0

        # Simulate a hard crash: no __exit__, owner JSON remains, but the OS
        # releases the stable guard descriptor.  PID/start-time proof then
        # permits exactly one new owner to replace the stale record.
        owner_process.kill()
        owner_process.wait(timeout=10)
        # On Windows ``sys.executable`` may be a venv launcher whose PID is
        # different from the interpreter PID recorded by the lock.  Reap that
        # launcher only after terminating the actual recorded owner.
        if child.poll() is None:
            child.kill()
        child.wait(timeout=10)

        with WorkspaceRunLock(lock_path) as replacement:
            assert replacement.owner is not None
            assert replacement.owner.pid != child_pid
            assert replacement.owner.pid > 0

        assert not lock_path.exists()
        assert lock_path.with_name(f"{lock_path.name}.guard").is_file()
    finally:
        if owner_process is not None:
            with contextlib.suppress(psutil.AccessDenied, psutil.NoSuchProcess):
                owner_process.kill()
        if child.poll() is None:
            child.kill()
        with contextlib.suppress(subprocess.TimeoutExpired):
            child.wait(timeout=5)


@pytest.mark.integration
def test_divergent_temp_roots_share_one_database_lock_domain_across_processes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """[M-036] two processes with diverging TEMP values see one lock domain.

    Deliberate contract change (M-036 = A): this replaces the former
    hardlink-alias convergence test.  The colocated lock domain lives in the
    canonical db parent, so a child process with its own effective TEMP root
    still excludes the parent's holder, and no lock artifacts are created
    under either TEMP root.
    """
    original = tmp_path / "workspace-a" / "shared.db"
    original.parent.mkdir()
    original.write_bytes(b"sqlite identity placeholder")
    child_temp = tmp_path / "child-temp"
    parent_temp = tmp_path / "parent-temp"
    child_temp.mkdir()
    parent_temp.mkdir()

    ready_path = tmp_path / "database-ready.txt"
    project_root = Path(__file__).resolve().parents[2]
    child = subprocess.Popen(  # noqa: S603 - controlled interpreter and script
        [
            sys.executable,
            "-c",
            _DATABASE_CHILD_HOLDER_WITH_TEMP,
            str(original),
            str(ready_path),
            str(child_temp),
        ],
        cwd=project_root,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    owner_process: psutil.Process | None = None
    try:
        owner_process = psutil.Process(_wait_for_pid(ready_path, child))

        monkeypatch.setattr(tempfile, "tempdir", str(parent_temp))
        with pytest.raises(RunLockHeldError):
            DatabaseRunLocks(original).acquire()

        for lock_path in database_lock_paths_for_db(original):
            assert lock_path.parent == original.parent
            assert child_temp not in lock_path.parents
            assert parent_temp not in lock_path.parents
        assert not any(child_temp.iterdir())
        assert not any(parent_temp.iterdir())

        owner_process.kill()
        owner_process.wait(timeout=10)
        if child.poll() is None:
            child.kill()
        child.wait(timeout=10)

        with DatabaseRunLocks(original) as replacement:
            assert replacement.acquired is True
    finally:
        if owner_process is not None:
            with contextlib.suppress(psutil.AccessDenied, psutil.NoSuchProcess):
                owner_process.kill()
        if child.poll() is None:
            child.kill()
        with contextlib.suppress(subprocess.TimeoutExpired):
            child.wait(timeout=5)
