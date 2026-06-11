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

import subprocess
import sys
import textwrap
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

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


class TestShutdownHangRegression:
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
