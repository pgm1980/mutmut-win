"""Unit tests for mutmut_win.process.worker."""

from __future__ import annotations

import os
import subprocess
import sys
from queue import Queue
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest

if TYPE_CHECKING:
    from pathlib import Path

import mutmut_win.process.worker as worker_module
from mutmut_win.models import MutationTask, TaskCompleted, TaskStarted
from mutmut_win.process.worker import MUTANT_ENV_VAR, worker_main


@pytest.fixture(autouse=True)
def _no_real_task_jobs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mocked Popen objects carry fake PIDs — a real kill-on-close job
    assigned to such a PID could capture a FOREIGN process (issue #82).
    Unit tests must never create real job objects."""
    monkeypatch.setattr(worker_module, "_create_task_job", lambda _pid: None)


@pytest.fixture(autouse=True)
def _isolated_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Run in a temp cwd with a mutants/ dir.

    These tests exercise code that resolves 'mutants' RELATIVE TO THE CWD
    (sitecustomize writes, temp log files). They only passed from the repo
    root because a real mutants/ happened to exist there — and they wrote
    artifacts into it (A2-RN-010). Under dogfooding (#98) the suite itself
    runs INSIDE mutants/, where 'mutants/mutants' does not exist.
    """
    monkeypatch.chdir(tmp_path)
    (tmp_path / "mutants").mkdir(exist_ok=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(**overrides: Any) -> dict[str, Any]:
    """Return a minimal config_data dict accepted by worker_main.

    IL detection is OFF by default in these tests so the worker doesn't try to
    import psutil / spawn a ProcessMonitor thread against the mocked subprocess.
    Tests that exercise IL detection live in test_loop_monitor.py.
    """
    base: dict[str, Any] = {
        "paths_to_mutate": ["src/"],
        "tests_dir": ["tests/"],
        "do_not_mutate": [],
        "also_copy": [],
        "max_children": 1,
        "timeout_multiplier": 10.0,
        "max_stack_depth": -1,
        "debug": False,
        "pytest_add_cli_args": [],
        "pytest_add_cli_args_test_selection": [],
        "mutate_only_covered_lines": False,
        "type_check_command": [],
        "infinite_loop_detection": False,
    }
    base.update(overrides)
    return base


def _make_popen_mock(exit_code: int = 0) -> MagicMock:
    """Return a Mock that quacks like ``subprocess.Popen`` for worker tests."""
    fake_proc = MagicMock()
    fake_proc.pid = 12345
    fake_proc.wait.return_value = exit_code
    fake_proc.poll.return_value = exit_code  # already exited
    return fake_proc


def _simple_task(**overrides: Any) -> dict[str, Any]:
    task = MutationTask(mutant_name="src/foo.py::bar__mutmut_1", tests=["tests/test_foo.py"])
    data = task.model_dump()
    data.update(overrides)
    return data


class _SimpleQueue:
    """Thread-safe queue that behaves like multiprocessing.Queue for tests."""

    def __init__(self) -> None:
        self._q: Queue[Any] = Queue()

    def put(self, item: Any) -> None:
        self._q.put(item)

    def get(self) -> Any:
        return self._q.get()

    def empty(self) -> bool:
        return self._q.empty()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestWorkerMain:
    """Tests for worker_main() running with mocked subprocess."""

    def test_sentinel_exits_immediately(self) -> None:
        """A lone sentinel (None) must cause the worker to return."""
        task_q: _SimpleQueue = _SimpleQueue()
        event_q: _SimpleQueue = _SimpleQueue()
        task_q.put(None)

        # Must not block / raise.
        worker_main(task_q, event_q, _make_config())  # type: ignore[arg-type]
        assert event_q.empty()

    def test_task_produces_started_and_completed_events(self) -> None:
        """One task + sentinel must produce TaskStarted then TaskCompleted."""
        task_q: _SimpleQueue = _SimpleQueue()
        event_q: _SimpleQueue = _SimpleQueue()

        task_q.put(_simple_task())
        task_q.put(None)

        with patch(
            "mutmut_win.process.worker.subprocess.Popen",
            return_value=_make_popen_mock(exit_code=0),
        ):
            worker_main(task_q, event_q, _make_config())  # type: ignore[arg-type]

        started_raw = event_q.get()
        completed_raw = event_q.get()
        assert event_q.empty()

        started = TaskStarted.model_validate(started_raw)
        completed = TaskCompleted.model_validate(completed_raw)

        assert started.mutant_name == "src/foo.py::bar__mutmut_1"
        assert started.worker_pid == os.getpid()
        assert completed.mutant_name == "src/foo.py::bar__mutmut_1"
        assert completed.exit_code == 0
        assert completed.duration >= 0.0

    def test_non_zero_exit_code_forwarded(self) -> None:
        """Non-zero pytest exit code must be forwarded in TaskCompleted."""
        task_q: _SimpleQueue = _SimpleQueue()
        event_q: _SimpleQueue = _SimpleQueue()

        task_q.put(_simple_task())
        task_q.put(None)

        with patch(
            "mutmut_win.process.worker.subprocess.Popen",
            return_value=_make_popen_mock(exit_code=1),
        ):
            worker_main(task_q, event_q, _make_config())  # type: ignore[arg-type]

        event_q.get()  # TaskStarted
        completed_raw = event_q.get()
        completed = TaskCompleted.model_validate(completed_raw)
        assert completed.exit_code == 1

    def test_mutant_env_var_is_set(self) -> None:
        """MUTANT_UNDER_TEST env var must be forwarded to subprocess."""
        task_q: _SimpleQueue = _SimpleQueue()
        event_q: _SimpleQueue = _SimpleQueue()

        task_q.put(_simple_task())
        task_q.put(None)

        captured_env: dict[str, str] = {}

        def fake_popen(cmd: list[str], **kwargs: Any) -> MagicMock:  # noqa: ARG001
            env = kwargs.get("env", {})
            captured_env.update(env)
            return _make_popen_mock(exit_code=0)

        with patch("mutmut_win.process.worker.subprocess.Popen", side_effect=fake_popen):
            worker_main(task_q, event_q, _make_config())  # type: ignore[arg-type]

        assert captured_env.get(MUTANT_ENV_VAR) == "src/foo.py::bar__mutmut_1"

    def test_pythonunbuffered_is_set_for_the_subprocess(self) -> None:
        """Issue #88 / A2-JT-002: block buffering froze the log's st_size, so
        the classifier's output signal saw 0 bytes while the suite was making
        progress.  PYTHONUNBUFFERED=1 makes st_size honest for the whole tree."""
        task_q: _SimpleQueue = _SimpleQueue()
        event_q: _SimpleQueue = _SimpleQueue()

        task_q.put(_simple_task())
        task_q.put(None)

        captured_env: dict[str, str] = {}

        def fake_popen(cmd: list[str], **kwargs: Any) -> MagicMock:  # noqa: ARG001
            captured_env.update(kwargs.get("env", {}))
            return _make_popen_mock(exit_code=0)

        with patch("mutmut_win.process.worker.subprocess.Popen", side_effect=fake_popen):
            worker_main(task_q, event_q, _make_config())  # type: ignore[arg-type]

        assert captured_env.get("PYTHONUNBUFFERED") == "1"

    # The window-vs-timeout hint (A2-JT-018) moved to the orchestrator —
    # once per RUN instead of once per worker process (issue #110 /
    # DOG-002); its tests live in test_hygiene_110.py. The worker stays
    # silent about it:
    def test_worker_emits_no_window_hint(self, capsys: pytest.CaptureFixture[str]) -> None:
        task_q: _SimpleQueue = _SimpleQueue()
        event_q: _SimpleQueue = _SimpleQueue()

        # 15s timeout vs the default 10s window WOULD have triggered the
        # old worker-side hint; the notice now lives in the orchestrator.
        task_q.put(_simple_task(timeout_seconds=15.0))
        task_q.put(None)

        config = _make_config(infinite_loop_detection=True)
        with patch(
            "mutmut_win.process.worker.subprocess.Popen",
            side_effect=lambda *_a, **_k: _make_popen_mock(exit_code=0),
        ):
            worker_main(task_q, event_q, config)  # type: ignore[arg-type]

        assert "IL-MONITOR" not in capsys.readouterr().out

    def test_anomalous_exit_captures_the_log_tail(self) -> None:
        """Issue #91 / A4-QX-025: exit 2 (collection error caused by the
        mutant) is a kill — its forensics are the pytest output.  The worker
        must capture the log tail for every anomalous exit, not only for
        timeout (36/38) and suspicious (35)."""
        task_q: _SimpleQueue = _SimpleQueue()
        event_q: _SimpleQueue = _SimpleQueue()
        task_q.put(_simple_task())
        task_q.put(None)

        def fake_popen(cmd: list[str], **kwargs: Any) -> MagicMock:  # noqa: ARG001
            os.write(kwargs["stdout"], b"!!! Interrupted: 1 error during collection !!!\n")
            return _make_popen_mock(exit_code=2)

        with patch("mutmut_win.process.worker.subprocess.Popen", side_effect=fake_popen):
            worker_main(task_q, event_q, _make_config())  # type: ignore[arg-type]

        event_q.get()  # TaskStarted
        completed = TaskCompleted.model_validate(event_q.get())
        assert completed.exit_code == 2
        assert completed.last_output is not None
        assert "error during collection" in completed.last_output

    def test_clean_exit_does_not_capture_output(self) -> None:
        task_q: _SimpleQueue = _SimpleQueue()
        event_q: _SimpleQueue = _SimpleQueue()
        task_q.put(_simple_task())
        task_q.put(None)

        with patch(
            "mutmut_win.process.worker.subprocess.Popen",
            return_value=_make_popen_mock(exit_code=1),
        ):
            worker_main(task_q, event_q, _make_config())  # type: ignore[arg-type]

        event_q.get()  # TaskStarted
        completed = TaskCompleted.model_validate(event_q.get())
        assert completed.last_output is None  # a plain kill needs no forensics

    def test_timeout_path_declares_the_platform_status_signal(self) -> None:
        """Issue #90 / A2-JT-016: the worker must tell the classifier whether
        the status signal is real on this platform (False on win32, where
        psutil reports everything as 'running') and forward the sampler error
        count — this is the plumbing the win32 confidence cap hangs on."""
        captured: dict[str, Any] = {}

        class _FakeMonitor:
            sampler_errors = 7

            def take_samples_snapshot(self) -> list[Any]:
                return []

            def shutdown(self, timeout: float = 1.0) -> None:
                pass

        def fake_classify(
            _samples: Any,
            _thresholds: Any,
            _last_output: Any,
            *,
            status_signal_available: bool,
            sampler_errors: int,
        ) -> MagicMock:
            captured["status_signal_available"] = status_signal_available
            captured["sampler_errors"] = sampler_errors
            classification = MagicMock()
            classification.verdict = "timeout"
            classification.confidence = "low"
            classification.forensics.model_dump.return_value = {}
            return classification

        proc = _make_popen_mock()
        proc.wait.side_effect = subprocess.TimeoutExpired(cmd="pytest", timeout=1)

        task_q: _SimpleQueue = _SimpleQueue()
        event_q: _SimpleQueue = _SimpleQueue()
        task_q.put(_simple_task(timeout_seconds=60.0))
        task_q.put(None)

        config = _make_config(infinite_loop_detection=True)
        with (
            patch("mutmut_win.process.worker.subprocess.Popen", return_value=proc),
            patch.object(worker_module, "_kill_proc_tree"),
            patch.object(worker_module, "_maybe_start_loop_monitor", return_value=_FakeMonitor()),
            patch.object(worker_module, "_classify_with_monitor", side_effect=fake_classify),
        ):
            worker_main(task_q, event_q, config)  # type: ignore[arg-type]

        assert captured["status_signal_available"] == (sys.platform != "win32")
        assert captured["sampler_errors"] == 7

    def test_pytest_extra_args_forwarded(self) -> None:
        """pytest_add_cli_args from config must appear in the subprocess cmd."""
        task_q: _SimpleQueue = _SimpleQueue()
        event_q: _SimpleQueue = _SimpleQueue()

        task_q.put(_simple_task())
        task_q.put(None)

        captured_cmds: list[list[str]] = []

        def fake_popen(cmd: list[str], **kwargs: Any) -> MagicMock:  # noqa: ARG001
            captured_cmds.append(list(cmd))
            return _make_popen_mock(exit_code=0)

        with patch("mutmut_win.process.worker.subprocess.Popen", side_effect=fake_popen):
            worker_main(
                task_q,  # type: ignore[arg-type]
                event_q,  # type: ignore[arg-type]
                _make_config(pytest_add_cli_args=["--no-header", "-x"]),
            )

        assert len(captured_cmds) == 1
        assert "--no-header" in captured_cmds[0]
        assert "-x" in captured_cmds[0]

    def test_multiple_tasks_processed_in_order(self) -> None:
        """Multiple tasks must each produce a start/complete pair."""
        task_q: _SimpleQueue = _SimpleQueue()
        event_q: _SimpleQueue = _SimpleQueue()

        names = [f"src/foo.py::bar__mutmut_{i}" for i in range(3)]
        for name in names:
            task = MutationTask(mutant_name=name).model_dump()
            task_q.put(task)
        task_q.put(None)

        with patch(
            "mutmut_win.process.worker.subprocess.Popen",
            return_value=_make_popen_mock(exit_code=0),
        ):
            worker_main(task_q, event_q, _make_config())  # type: ignore[arg-type]

        events = []
        while not event_q.empty():
            events.append(event_q.get())

        # 3 tasks x (TaskStarted + TaskCompleted) = 6 events
        assert len(events) == 6

    def test_task_without_tests_runs_pytest_without_test_args(self) -> None:
        """A task with no tests list must run pytest without extra test args."""
        task_q: _SimpleQueue = _SimpleQueue()
        event_q: _SimpleQueue = _SimpleQueue()

        bare_task = MutationTask(mutant_name="src/foo.py::x__mutmut_1").model_dump()
        task_q.put(bare_task)
        task_q.put(None)

        captured: list[list[str]] = []

        def fake_popen(cmd: list[str], **kwargs: Any) -> MagicMock:  # noqa: ARG001
            captured.append(list(cmd))
            return _make_popen_mock(exit_code=0)

        with patch("mutmut_win.process.worker.subprocess.Popen", side_effect=fake_popen):
            worker_main(task_q, event_q, _make_config())  # type: ignore[arg-type]

        assert len(captured) == 1
        # Should not include any test path args beyond the base pytest flags
        assert "tests/test_foo.py" not in captured[0]


class TestMutantEnvVar:
    def test_constant_value(self) -> None:
        assert MUTANT_ENV_VAR == "MUTANT_UNDER_TEST"


def test_scale_il_window_clamps_to_task_budget_and_keeps_fields() -> None:
    """_scale_il_window down-scales the window for a fast task, preserves the
    other tunables, and is a no-op for a slow task (IL-001)."""
    from mutmut_win.process.loop_monitor import IlThresholds

    thresholds = IlThresholds(window_seconds=10.0, cpu_threshold=55.0, output_threshold=42)

    fast = worker_module._scale_il_window(thresholds, timeout_seconds=6.0)
    assert fast.window_seconds == pytest.approx(3.0)  # min(10, 6/2)
    # the model_copy must leave the other tunables untouched
    assert fast.cpu_threshold == pytest.approx(55.0)
    assert fast.output_threshold == 42

    slow = worker_module._scale_il_window(thresholds, timeout_seconds=600.0)
    assert slow.window_seconds == pytest.approx(10.0)  # default left untouched


@pytest.mark.parametrize(
    ("exit_code", "expected"),
    [
        (0, 0),
        (1, 1),
        (2, 2),
        (5, 5),
    ],
)
def test_various_exit_codes_forwarded(exit_code: int, expected: int) -> None:
    """Parametrised check that all exit codes are forwarded correctly."""
    task_q: _SimpleQueue = _SimpleQueue()
    event_q: _SimpleQueue = _SimpleQueue()

    task_q.put(MutationTask(mutant_name="m1").model_dump())
    task_q.put(None)

    with patch(
        "mutmut_win.process.worker.subprocess.Popen",
        return_value=_make_popen_mock(exit_code=exit_code),
    ):
        worker_main(task_q, event_q, _make_config())  # type: ignore[arg-type]

    event_q.get()  # TaskStarted
    completed = TaskCompleted.model_validate(event_q.get())
    assert completed.exit_code == expected
