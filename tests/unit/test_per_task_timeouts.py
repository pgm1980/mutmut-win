"""Tests for the end-to-end per-task timeout architecture (Issue #81).

Audit A2-JT-003 (found independently by three agents): the worker computed
``max(60, timeout_multiplier)`` — the documented MULTIPLIER acted as flat
absolute seconds, every task got 60 s regardless of suite size, and the
per-task budgets computed by ``_apply_timeouts`` had ZERO readers.  The dead
``WallClockTimeout`` monitor and its ``TaskTimedOut`` event are removed
outright (three documented latent landmines, A2-EW-013/JT-008); unknown
event shapes now fail fast instead of being misparsed.  Companions:
A2-EW-009 (configured IL window never reached the monitor) and A2-EW-014
(``_read_last_lines`` loaded runaway logs fully).
"""

from __future__ import annotations

from queue import Queue
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest
from hypothesis import given
from hypothesis import strategies as st

import mutmut_win.process.worker as worker_module
from mutmut_win.config import MutmutConfig
from mutmut_win.models import MutationTask
from mutmut_win.orchestrator import _apply_timeouts
from mutmut_win.process.executor import SpawnPoolExecutor
from mutmut_win.process.worker import _maybe_start_loop_monitor, _read_last_lines, worker_main

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture(autouse=True)
def _no_real_task_jobs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mocked Popen objects carry fake PIDs — a real kill-on-close job
    assigned to such a PID could capture a FOREIGN process. Never create
    real jobs in unit tests."""
    monkeypatch.setattr(worker_module, "_create_task_job", lambda _pid: None)


def _config_data(**overrides: Any) -> dict[str, Any]:
    data = MutmutConfig(timeout_multiplier=10.0).model_dump()
    data["infinite_loop_detection"] = False
    data.update(overrides)
    return data


class TestWorkerUsesPerTaskTimeout:
    def test_wait_uses_task_timeout_seconds(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / "mutants").mkdir()

        task = MutationTask(
            mutant_name="pkg.x_f__mutmut_1", tests=[], timeout_seconds=123.0
        ).model_dump()
        task_q: Queue[Any] = Queue()
        task_q.put(task)
        task_q.put(None)
        event_q: Queue[Any] = Queue()

        fake_proc = MagicMock()
        fake_proc.pid = 12345
        fake_proc.wait.return_value = 0
        fake_proc.poll.return_value = 0

        with patch.object(worker_module.subprocess, "Popen", return_value=fake_proc):
            worker_main(task_q, event_q, _config_data())  # type: ignore[arg-type]

        fake_proc.wait.assert_called_once_with(timeout=123.0)


class TestApplyTimeoutsIsMultiplicative:
    @given(
        estimated=st.floats(min_value=0.01, max_value=500.0, allow_nan=False),
        multiplier=st.floats(min_value=0.1, max_value=100.0, allow_nan=False),
    )
    def test_timeout_is_floor_or_product(self, estimated: float, multiplier: float) -> None:
        task = MutationTask(mutant_name="pkg.x_f__mutmut_1", tests=["t1"])
        [result] = _apply_timeouts([task], {"t1": estimated}, multiplier)
        assert result.timeout_seconds == pytest.approx(max(5.0, estimated * multiplier))


class TestMonitorWindowWiring:
    def test_configured_window_reaches_the_monitor(self, tmp_path: Path) -> None:
        monitor_cls = MagicMock()
        with (
            patch("mutmut_win.process.loop_monitor.ProcessMonitor", monitor_cls),
            patch("mutmut_win.process.loop_monitor.has_psutil", return_value=True),
        ):
            _maybe_start_loop_monitor(True, 4711, tmp_path / "x.log", window_seconds=42.0)
        assert monitor_cls.call_args.kwargs["window_seconds"] == 42.0


class TestTailRead:
    def test_returns_last_n_lines_of_large_file(self, tmp_path: Path) -> None:
        log = tmp_path / "big.log"
        log.write_text(
            "\n".join(f"line{i}" for i in range(50_000)) + "\n", encoding="utf-8"
        )
        result = _read_last_lines(log, 5)
        assert result is not None
        lines = result.split("\n")
        assert lines == [f"line{i}" for i in range(49_995, 50_000)]

    def test_missing_file_returns_none(self, tmp_path: Path) -> None:
        assert _read_last_lines(tmp_path / "absent.log", 5) is None

    def test_short_file_returns_all_lines(self, tmp_path: Path) -> None:
        log = tmp_path / "small.log"
        log.write_text("a\nb\n", encoding="utf-8")
        assert _read_last_lines(log, 5) == "a\nb"


class TestUnknownEventShapeFailsFast:
    def test_unknown_event_dict_raises(self) -> None:
        executor = SpawnPoolExecutor(max_workers=1, config=MutmutConfig())
        executor._num_tasks = 1
        executor._event_queue.put({"weird": 1})

        with pytest.raises(RuntimeError, match="event"):
            list(executor.get_events())
