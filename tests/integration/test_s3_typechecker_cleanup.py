"""Real Windows containment controls for diagnostic cleanup ordering (S3-017)."""

import contextlib
import subprocess
import sys
import time
from typing import TYPE_CHECKING

import psutil
import pytest
from pydantic import BaseModel

from mutmut_win import type_checking
from mutmut_win.exceptions import TypeCheckCommandError

if TYPE_CHECKING:
    from pathlib import Path


class CleanupObservation(BaseModel):
    """Bind the observed ordering and native identities to one timeout arm."""

    snapshot_enabled: bool
    host_process_count: int
    root_pid: int = 0
    root_create_time: float | None = None
    close_preceded_snapshot: bool = False
    snapshot_seconds: float = 0.0
    elapsed_seconds: float = 0.0
    identities: list[tuple[int, float]] = []


@pytest.mark.integration
@pytest.mark.parametrize("snapshot_enabled", [True, False], ids=["snapshot", "bypass"])
def test_authoritative_job_close_precedes_host_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, snapshot_enabled: bool
) -> None:
    """Host enumeration cannot postpone termination of a real contained tree."""
    pid_file = tmp_path / "identities.txt"
    checker = tmp_path / "checker.py"
    checker.write_text(
        "import pathlib, subprocess, sys, time, psutil\n"
        "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])\n"
        "root = psutil.Process()\n"
        "descendant = psutil.Process(child.pid)\n"
        "pathlib.Path(sys.argv[1]).write_text("
        "f'{root.pid} {root.create_time()}\\n{child.pid} {descendant.create_time()}', "
        "encoding='ascii')\n"
        "time.sleep(30)\n",
        encoding="utf-8",
    )
    observation = CleanupObservation(
        snapshot_enabled=snapshot_enabled, host_process_count=len(psutil.pids())
    )
    original_close = type_checking._close_type_checker_job
    original_snapshot = type_checking._snapshot_process_tree
    closed = False

    def observe_close(handle: int) -> None:
        nonlocal closed
        original_close(handle)
        closed = True

    def observe_snapshot(pid: int, root_create_time: float | None = None) -> list[psutil.Process]:
        observation.root_pid = pid
        observation.root_create_time = root_create_time
        observation.close_preceded_snapshot = closed
        started = time.monotonic()
        members = original_snapshot(pid, root_create_time) if snapshot_enabled else []
        observation.snapshot_seconds = time.monotonic() - started
        return members

    monkeypatch.setattr(type_checking, "TYPE_CHECK_TIMEOUT_SECONDS", 2)
    monkeypatch.setattr(type_checking, "_close_type_checker_job", observe_close)
    monkeypatch.setattr(type_checking, "_snapshot_process_tree", observe_snapshot)
    started = time.monotonic()
    try:
        with pytest.raises(TypeCheckCommandError, match="timed out") as error:
            type_checking.run_type_checker([sys.executable, str(checker), str(pid_file)])
        observation.elapsed_seconds = time.monotonic() - started
        assert isinstance(error.value.__cause__, subprocess.TimeoutExpired)
        assert pid_file.is_file(), "checker never reached descendant creation"
        observation.identities = [
            (int(pid), float(created))
            for pid, created in (line.split() for line in pid_file.read_text().splitlines())
        ]
        assert len(observation.identities) == 2
        assert observation.root_pid > 0
        assert observation.root_create_time is not None
        # A Windows venv launcher may be the Popen root, with the script in
        # its child. Bind that additional identity instead of equating PIDs.
        assert all(created >= observation.root_create_time for _, created in observation.identities)
        observation.identities.append((observation.root_pid, observation.root_create_time))
        for pid, created in observation.identities:
            with contextlib.suppress(psutil.NoSuchProcess):
                process = psutil.Process(pid)
                if process.create_time() == created:
                    process.wait(timeout=3)
                    assert not process.is_running(), f"contained identity survived: {pid}"
        assert closed, "native Job Object was never closed"
        assert observation.close_preceded_snapshot, (
            "diagnostic host enumeration started before authoritative Job Object cleanup"
        )
    finally:
        print(observation.model_dump_json())
        # Only our file-bound native identities may be cleaned after an assertion failure.
        if pid_file.is_file():
            for line in pid_file.read_text().splitlines():
                pid, created = line.split()
                with contextlib.suppress(psutil.NoSuchProcess):
                    process = psutil.Process(int(pid))
                    if process.create_time() == float(created):
                        process.kill()
                        process.wait(timeout=3)
