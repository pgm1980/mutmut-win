"""Regression tests for the shutdown hang (Issue #79, audit A2-EW-001 — S1).

``SpawnPoolExecutor.shutdown()`` used to kill workers but never close the
queues.  With a populated ``task_queue`` (beyond the ~64 KB pipe buffer) and
all readers dead, the parent's feeder thread blocked at interpreter exit
forever (``multiprocessing`` joins it without timeout).  The orchestrator
event loop additionally skipped ``shutdown()`` on any exception other than
``KeyboardInterrupt``.

The hang regression runs OUT OF PROCESS with a hard watchdog timeout so a
regression fails the test instead of hanging CI.
"""

from __future__ import annotations

import contextlib
import os
import signal
import subprocess
import sys
import textwrap
import time
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import psutil
import pytest

from mutmut_win.config import MutmutConfig
from mutmut_win.exceptions import CleanTestFailedError
from mutmut_win.orchestrator import MutationOrchestrator
from mutmut_win.process.executor import SpawnPoolExecutor

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration

_DRIVER = textwrap.dedent(
    """
    import sys

    from mutmut_win.config import MutmutConfig
    from mutmut_win.process.executor import SpawnPoolExecutor

    def main() -> None:
        executor = SpawnPoolExecutor(max_workers=2, config=MutmutConfig())
        # Fill the task queue well beyond the OS pipe buffer (~64 KB) WITHOUT
        # spawning any consumer — this is exactly the post-abort state: items
        # buffered, all readers dead.  The feeder thread now owns unflushed
        # data; before the fix the interpreter never exited.
        for i in range(2000):
            executor._task_queue.put({"mutant_name": "x" * 200, "pad": "y" * 200, "i": i})
        executor.shutdown()
        print("SHUTDOWN_COMPLETE", flush=True)

    if __name__ == "__main__":
        main()
    """
)

_SUSPENDED_START_DRIVER = textwrap.dedent(
    """
    import os
    import pathlib
    import sys
    import time

    from mutmut_win.config import MutmutConfig
    from mutmut_win.process.executor import SpawnPoolExecutor
    from mutmut_win.pytest_boundary import prepare_pytest_boundary

    def main() -> None:
        site_dir = pathlib.Path(sys.argv[1])
        site_marker = pathlib.Path(sys.argv[2])
        start_marker = pathlib.Path(sys.argv[3])
        os.environ["MUTMUT_SITE_PROBE"] = "1"
        os.environ["MUTMUT_SITE_MARKER"] = str(site_marker)
        existing = os.environ.get("PYTHONPATH", "")
        os.environ["PYTHONPATH"] = os.pathsep.join(
            [str(site_dir), *([existing] if existing else [])]
        )

        config = MutmutConfig()
        executor = SpawnPoolExecutor(max_workers=1, config=config)
        staging = pathlib.Path("mutants")
        staging.mkdir(exist_ok=True)
        boundary = prepare_pytest_boundary(
            project_root=pathlib.Path.cwd(),
            staging_root=staging,
            tests_dir=list(config.tests_dir),
        )
        executor.configure_pytest_boundary(boundary.to_dict())
        # Well beyond an anonymous-pipe buffer.  A wedged sitecustomize must
        # not make Process.start() block while this payload is serialized.
        executor._config_data["oversized_probe"] = "x" * 2_000_000
        executor.start([])

        deadline = time.monotonic() + 10.0
        while not site_marker.is_file() and time.monotonic() < deadline:
            time.sleep(0.02)
        if not site_marker.is_file():
            raise RuntimeError("sitecustomize probe did not start")
        start_marker.write_text(site_marker.read_text(encoding="ascii"), encoding="ascii")
        # Bypass multiprocessing finalizers. Closing the parent-owned Job
        # handle at process teardown must still reap worker + early descendant.
        os._exit(93)

    if __name__ == "__main__":
        main()
    """
)

_WEDGED_SITECUSTOMIZE = textwrap.dedent(
    """
    import os
    import pathlib
    import subprocess
    import sys
    import time

    if os.environ.get("MUTMUT_SITE_PROBE") == "1":
        child_env = os.environ.copy()
        child_env["MUTMUT_SITE_PROBE"] = "0"
        child = subprocess.Popen(
            [sys.executable, "-S", "-c", "import time; time.sleep(120)"],
            env=child_env,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        marker = pathlib.Path(os.environ["MUTMUT_SITE_MARKER"])
        marker_temp = marker.with_suffix(".tmp")
        marker_temp.write_text(f"{os.getpid()},{child.pid}", encoding="ascii")
        marker_temp.replace(marker)
        while True:
            time.sleep(1)
    """
)


class TestShutdownHangRegression:
    @pytest.mark.skipif(sys.platform != "win32", reason="Windows atomic Job-list creation")
    def test_pool_has_no_post_create_assignment_hard_exit_window(self, tmp_path: Path) -> None:
        """The legacy assignment hook must be unreachable for real workers."""
        driver = tmp_path / "atomic_pool_driver.py"
        driver.write_text(
            textwrap.dedent(
                """
                import os
                import pathlib
                from mutmut_win.config import MutmutConfig
                from mutmut_win.process import job_object
                from mutmut_win.process.executor import SpawnPoolExecutor
                from mutmut_win.pytest_boundary import prepare_pytest_boundary

                def forbidden_post_create_assignment(*_args):
                    os._exit(91)

                if __name__ == "__main__":
                    job_object.assign_process_handle_to_job = forbidden_post_create_assignment
                    config = MutmutConfig()
                    executor = SpawnPoolExecutor(1, config)
                    staging = pathlib.Path("mutants")
                    staging.mkdir(exist_ok=True)
                    boundary = prepare_pytest_boundary(
                        project_root=pathlib.Path.cwd(),
                        staging_root=staging,
                        tests_dir=list(config.tests_dir),
                    )
                    executor.configure_pytest_boundary(boundary.to_dict())
                    executor.start([])
                    executor.shutdown()
                """
            ),
            encoding="utf-8",
        )

        result = subprocess.run(  # noqa: S603
            [sys.executable, str(driver)],
            cwd=tmp_path,
            timeout=20,
        )
        assert result.returncode == 0

    def test_shutdown_with_full_queue_does_not_hang_interpreter(self, tmp_path: Path) -> None:
        driver = tmp_path / "driver.py"
        driver.write_text(_DRIVER, encoding="utf-8")

        try:
            result = subprocess.run(  # noqa: S603 — fully controlled command
                [sys.executable, str(driver)],
                capture_output=True,
                encoding="utf-8",
                timeout=30,
                cwd=tmp_path,
            )
        except subprocess.TimeoutExpired:
            pytest.fail(
                "interpreter hung at exit with a full task queue — "
                "A2-EW-001 regression (queues not closed in shutdown())"
            )

        assert "SHUTDOWN_COMPLETE" in result.stdout
        assert result.returncode == 0

    def test_shutdown_is_idempotent(self) -> None:
        executor = SpawnPoolExecutor(max_workers=1, config=MutmutConfig())
        executor.shutdown()
        executor.shutdown()  # second call must be a no-op, not an error

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows pool containment")
    def test_wedged_sitecustomize_large_payload_is_contained_and_nonblocking(
        self, tmp_path: Path
    ) -> None:
        driver = tmp_path / "suspended_start_hard_exit.py"
        site_dir = tmp_path / "startup_probe"
        site_dir.mkdir()
        site_marker = tmp_path / "site_pids.txt"
        start_marker = tmp_path / "start_returned_pids.txt"
        driver.write_text(_SUSPENDED_START_DRIVER, encoding="utf-8")
        (site_dir / "sitecustomize.py").write_text(_WEDGED_SITECUSTOMIZE, encoding="utf-8")

        launcher = subprocess.Popen(  # noqa: S603 — controlled test driver
            [
                sys.executable,
                str(driver),
                str(site_dir),
                str(site_marker),
                str(start_marker),
            ],
            cwd=tmp_path,
        )
        launcher.wait(timeout=20)
        assert launcher.returncode == 93
        assert start_marker.is_file(), "Process.start() did not return past wedged sitecustomize"
        pids = [int(value) for value in start_marker.read_text(encoding="ascii").split(",")]
        assert len(pids) == 2

        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline:
            alive_pids = []
            for pid in pids:
                try:
                    process = psutil.Process(pid)
                    if process.is_running() and process.status() != psutil.STATUS_ZOMBIE:
                        alive_pids.append(pid)
                except psutil.NoSuchProcess:
                    pass
            if not alive_pids:
                break
            time.sleep(0.05)
        else:
            for pid in alive_pids:
                with contextlib.suppress(psutil.Error):
                    psutil.Process(pid).kill()
            pytest.fail(f"contained startup process(es) survived parent hard exit: {alive_pids}")

    @pytest.mark.skipif(os.name != "posix", reason="POSIX process-group containment")
    def test_worker_sigkill_reaps_registered_pytest_session(self, tmp_path: Path) -> None:
        """A hard-dead worker cannot strand its already-started test group."""
        mutants = tmp_path / "mutants"
        mutants.mkdir()
        marker = tmp_path / "pytest_pid.txt"
        (mutants / "_mutmut_phase_guard.py").write_text(
            "import os\n"
            "from pathlib import Path\n"
            "def pytest_runtest_logreport(report):\n"
            "    path = os.environ.get('MUTMUT_PYTEST_PHASE_SENTINEL_PATH')\n"
            "    proof = os.environ.get('MUTMUT_PYTEST_PHASE_SENTINEL_PROOF')\n"
            "    if report.when == 'call' and path and proof:\n"
            "        Path(path).write_text(proof, encoding='utf-8')\n",
            encoding="utf-8",
        )
        (mutants / "test_escape.py").write_text(
            "import os, pathlib, signal, time\n"
            "def test_escape():\n"
            "    pathlib.Path(os.environ['MUTMUT_POSIX_MARKER']).write_text("
            "str(os.getpid()), encoding='ascii')\n"
            "    time.sleep(0.5)\n"
            "    os.kill(os.getppid(), signal.SIGKILL)\n"
            "    time.sleep(120)\n",
            encoding="utf-8",
        )
        driver = tmp_path / "posix_worker_crash.py"
        driver.write_text(
            textwrap.dedent(
                """
                import os
                import pathlib
                import sys
                from mutmut_win.config import MutmutConfig
                from mutmut_win.models import MutationTask
                from mutmut_win.process.executor import SpawnPoolExecutor
                from mutmut_win.pytest_boundary import prepare_pytest_boundary

                if __name__ == "__main__":
                    os.chdir(pathlib.Path(__file__).parent)
                    os.environ["MUTMUT_POSIX_MARKER"] = sys.argv[1]
                    executor = SpawnPoolExecutor(
                        1,
                        MutmutConfig(
                            tests_dir=["test_escape.py"],
                            infinite_loop_detection=False,
                        ),
                    )
                    boundary = prepare_pytest_boundary(
                        project_root=pathlib.Path.cwd(),
                        staging_root=pathlib.Path("mutants"),
                        tests_dir=["test_escape.py"],
                    )
                    executor.configure_pytest_boundary(boundary.to_dict())
                    executor.start([MutationTask(mutant_name="m", timeout_seconds=60)])
                    print([(type(event).__name__, getattr(event, "exit_code", None))
                           for event in executor.get_events()], flush=True)
                    executor.shutdown(timeout=0.5)
                """
            ),
            encoding="utf-8",
        )

        result = subprocess.run(  # noqa: S603
            [sys.executable, str(driver), str(marker)],
            cwd=tmp_path,
            text=True,
            capture_output=True,
            timeout=30,
        )
        assert result.returncode == 0, result.stderr
        assert "TaskCompleted" in result.stdout
        pytest_pid = int(marker.read_text(encoding="ascii"))
        time.sleep(0.2)
        try:
            process = psutil.Process(pytest_pid)
            alive = process.is_running() and process.status() != psutil.STATUS_ZOMBIE
        except psutil.NoSuchProcess:
            alive = False
        if alive:
            with contextlib.suppress(ProcessLookupError, PermissionError):
                os.killpg(pytest_pid, signal.SIGKILL)
        assert not alive, f"pytest session {pytest_pid} survived its worker's SIGKILL"


class TestOrchestratorAlwaysShutsDown:
    def test_shutdown_called_on_unexpected_event_loop_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Any exception in the event loop must still shut the executor down
        (previously only success and KeyboardInterrupt did)."""
        monkeypatch.chdir(tmp_path)
        src = tmp_path / "src"
        src.mkdir()
        (src / "target.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")

        runner = MagicMock()
        runner.run_clean_test.return_value = 0
        runner.run_forced_fail.return_value = 1
        runner.collect_tests.return_value = []
        runner.run_stats.return_value = None

        executor = MagicMock()
        executor.start.return_value = None
        executor.get_events.side_effect = RuntimeError("boom in event loop")

        cfg = MutmutConfig(paths_to_mutate=["src"])
        orch = MutationOrchestrator(cfg, runner=runner, executor=executor, db_path=tmp_path / "db")
        with pytest.raises(RuntimeError, match="boom in event loop"):
            orch.run()
        executor.shutdown.assert_called_once()

    def test_shutdown_not_required_before_executor_started(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Failures BEFORE the executor exists (e.g. clean-test gate) must not
        trip over the finally block."""
        monkeypatch.chdir(tmp_path)
        src = tmp_path / "src"
        src.mkdir()
        (src / "target.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")

        runner = MagicMock()
        runner.run_clean_test.return_value = 1  # gate fails before pool start

        cfg = MutmutConfig(paths_to_mutate=["src"])
        orch = MutationOrchestrator(
            cfg, runner=runner, executor=MagicMock(), db_path=tmp_path / "db"
        )
        with pytest.raises(CleanTestFailedError):
            orch.run()
