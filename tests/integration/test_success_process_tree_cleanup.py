"""Successful subprocess phases must not leak background descendants."""

from __future__ import annotations

import contextlib
import sys
import time
from queue import Queue
from typing import TYPE_CHECKING

import psutil
import pytest

import mutmut_win.type_checking as type_checking
from mutmut_win.config import MutmutConfig
from mutmut_win.exceptions import ProcessContainmentError
from mutmut_win.models import MutationTask, TaskCompleted, TaskStarted
from mutmut_win.process.worker import worker_main
from mutmut_win.runner import PytestRunner
from tests.unit.phase_mock_util import frozen_worker_config

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration


def _wait_until_dead(pid: int, timeout: float = 5.0) -> bool:
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


def _cleanup(pid: int | None) -> None:
    if pid is None:
        return
    with contextlib.suppress(psutil.AccessDenied, psutil.NoSuchProcess):
        psutil.Process(pid).kill()


def _write_passing_spawn_test(mutants_dir: Path, pid_file: Path) -> None:
    tests_dir = mutants_dir / "tests"
    tests_dir.mkdir(parents=True)
    (tests_dir / "test_spawn.py").write_text(
        "import pathlib\n"
        "import subprocess\n"
        "import sys\n"
        "def test_spawn_background_child():\n"
        "    child = subprocess.Popen([sys.executable, '-c', "
        "'import time; time.sleep(60)'])\n"
        f"    pathlib.Path({str(pid_file)!r}).write_text(str(child.pid), encoding='ascii')\n"
        "    assert child.pid > 0\n",
        encoding="utf-8",
    )


def test_successful_type_checker_reaps_background_child(tmp_path: Path) -> None:
    pid_file = tmp_path / "checker-child.pid"
    checker = tmp_path / "checker.py"
    checker.write_text(
        "import pathlib, subprocess, sys\n"
        "child = subprocess.Popen([sys.executable, '-c', "
        "'import time; time.sleep(60)'])\n"
        "pathlib.Path(sys.argv[1]).write_text(str(child.pid), encoding='ascii')\n"
        "print('[]')\n",
        encoding="utf-8",
    )
    child_pid: int | None = None
    try:
        result = type_checking._run_type_check_process(
            [sys.executable, str(checker), str(pid_file)], timeout=10
        )
        assert result.returncode == 0
        child_pid = int(pid_file.read_text(encoding="ascii"))
        assert _wait_until_dead(child_pid), "successful checker leaked its background child"
    finally:
        _cleanup(child_pid)


def test_successful_clean_phase_reaps_background_child(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    mutants_dir = project / "mutants"
    pid_file = tmp_path / "clean-child.pid"
    _write_passing_spawn_test(mutants_dir, pid_file)
    monkeypatch.chdir(project)
    runner = PytestRunner(MutmutConfig(tests_dir=["tests"], clean_run_timeout=15))

    child_pid: int | None = None
    try:
        assert runner.run_clean_test() == 0
        child_pid = int(pid_file.read_text(encoding="ascii"))
        assert _wait_until_dead(child_pid), "successful clean phase leaked its background child"
    finally:
        _cleanup(child_pid)


def test_successful_worker_task_reaps_background_child(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    mutants_dir = project / "mutants"
    pid_file = tmp_path / "worker-child.pid"
    _write_passing_spawn_test(mutants_dir, pid_file)
    monkeypatch.chdir(project)
    task_queue: Queue[object] = Queue()
    event_queue: Queue[dict[str, object]] = Queue()
    task_queue.put(
        MutationTask(
            mutant_name="src/pkg.py::f__mutmut_1",
            timeout_seconds=15,
        ).model_dump()
    )
    task_queue.put(None)
    config = frozen_worker_config(
        {
            "tests_dir": ["tests"],
            "pytest_add_cli_args": [],
            "pytest_add_cli_args_test_selection": [],
            "infinite_loop_detection": False,
        }
    )

    child_pid: int | None = None
    try:
        worker_main(task_queue, event_queue, config)  # type: ignore[arg-type]
        assert isinstance(TaskStarted.model_validate(event_queue.get()), TaskStarted)
        completed = TaskCompleted.model_validate(event_queue.get())
        assert completed.exit_code == 0
        child_pid = int(pid_file.read_text(encoding="ascii"))
        assert _wait_until_dead(child_pid), "successful worker leaked its background child"
    finally:
        _cleanup(child_pid)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows Job Object fail-closed contract")
def test_windows_type_checker_refuses_to_start_without_job_object(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    marker = tmp_path / "checker-started.txt"
    checker = tmp_path / "checker.py"
    checker.write_text(
        f"from pathlib import Path\nPath({str(marker)!r}).write_text('started')\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(type_checking, "_create_type_checker_job", lambda: None)

    with pytest.raises(ProcessContainmentError, match="Job Object"):
        type_checking._run_type_check_process([sys.executable, str(checker)], timeout=10)

    assert not marker.exists(), "uncontained checker was resumed before refusal"
