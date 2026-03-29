"""Unit tests for mutmut_win.process.worker."""

from __future__ import annotations

import os
from queue import Queue
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from mutmut_win.models import MutationTask, TaskCompleted, TaskStarted
from mutmut_win.process.worker import MUTANT_ENV_VAR, worker_main

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(**overrides: Any) -> dict[str, Any]:
    """Return a minimal config_data dict accepted by worker_main."""
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
    }
    base.update(overrides)
    return base


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

        fake_result = MagicMock()
        fake_result.returncode = 0

        with patch("mutmut_win.process.worker.subprocess.run", return_value=fake_result):
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

        fake_result = MagicMock()
        fake_result.returncode = 1

        with patch("mutmut_win.process.worker.subprocess.run", return_value=fake_result):
            worker_main(task_q, event_q, _make_config())  # type: ignore[arg-type]

        event_q.get()  # TaskStarted
        completed_raw = event_q.get()
        completed = TaskCompleted.model_validate(completed_raw)
        assert completed.exit_code == 1

    def test_mutant_env_var_is_set(self) -> None:
        """MUTANT_UNDER_TEST env var must be forwarded to subprocess.run."""
        task_q: _SimpleQueue = _SimpleQueue()
        event_q: _SimpleQueue = _SimpleQueue()

        task_q.put(_simple_task())
        task_q.put(None)

        fake_result = MagicMock()
        fake_result.returncode = 0

        captured_env: dict[str, str] = {}

        def fake_run(cmd: list[str], **kwargs: Any) -> MagicMock:  # noqa: ARG001
            env = kwargs.get("env", {})
            captured_env.update(env)
            return fake_result

        with patch("mutmut_win.process.worker.subprocess.run", side_effect=fake_run):
            worker_main(task_q, event_q, _make_config())  # type: ignore[arg-type]

        assert captured_env.get(MUTANT_ENV_VAR) == "src/foo.py::bar__mutmut_1"

    def test_pytest_extra_args_forwarded(self) -> None:
        """pytest_add_cli_args from config must appear in the subprocess cmd."""
        task_q: _SimpleQueue = _SimpleQueue()
        event_q: _SimpleQueue = _SimpleQueue()

        task_q.put(_simple_task())
        task_q.put(None)

        fake_result = MagicMock()
        fake_result.returncode = 0

        captured_cmds: list[list[str]] = []

        def fake_run(cmd: list[str], **kwargs: Any) -> MagicMock:  # noqa: ARG001
            captured_cmds.append(list(cmd))
            return fake_result

        with patch("mutmut_win.process.worker.subprocess.run", side_effect=fake_run):
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

        fake_result = MagicMock()
        fake_result.returncode = 0

        with patch("mutmut_win.process.worker.subprocess.run", return_value=fake_result):
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

        fake_result = MagicMock()
        fake_result.returncode = 0
        captured: list[list[str]] = []

        def fake_run(cmd: list[str], **kwargs: Any) -> MagicMock:  # noqa: ARG001
            captured.append(list(cmd))
            return fake_result

        with patch("mutmut_win.process.worker.subprocess.run", side_effect=fake_run):
            worker_main(task_q, event_q, _make_config())  # type: ignore[arg-type]

        assert len(captured) == 1
        # Should not include any test path args beyond the base pytest flags
        assert "tests/test_foo.py" not in captured[0]


class TestMutantEnvVar:
    def test_constant_value(self) -> None:
        assert MUTANT_ENV_VAR == "MUTANT_UNDER_TEST"


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

    fake_result = MagicMock()
    fake_result.returncode = exit_code

    with patch("mutmut_win.process.worker.subprocess.run", return_value=fake_result):
        worker_main(task_q, event_q, _make_config())  # type: ignore[arg-type]

    event_q.get()  # TaskStarted
    completed = TaskCompleted.model_validate(event_q.get())
    assert completed.exit_code == expected
