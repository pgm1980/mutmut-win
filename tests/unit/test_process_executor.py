"""Unit tests for mutmut_win.process.executor (SpawnPoolExecutor)."""

from __future__ import annotations

import os
from pathlib import Path
from queue import Queue
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from mutmut_win.config import MutmutConfig
from mutmut_win.exceptions import ProcessContainmentError, PytestBoundaryError
from mutmut_win.models import MutationTask, TaskCompleted, TaskStarted
from mutmut_win.process.executor import SpawnPoolExecutor
from mutmut_win.pytest_boundary import prepare_pytest_boundary

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _config(**overrides: Any) -> MutmutConfig:
    """Return a minimal MutmutConfig, optionally overriding fields."""
    defaults: dict[str, Any] = {"max_children": 2}
    defaults.update(overrides)
    return MutmutConfig(**defaults)


def _tasks(n: int) -> list[MutationTask]:
    return [MutationTask(mutant_name=f"src/foo.py::bar__mutmut_{i}") for i in range(n)]


@pytest.fixture(autouse=True)
def _isolated_staging(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "mutants").mkdir()


def _configured_executor(max_workers: int, config: MutmutConfig) -> SpawnPoolExecutor:
    executor = SpawnPoolExecutor(max_workers=max_workers, config=config)
    boundary = prepare_pytest_boundary(
        project_root=Path.cwd(),
        staging_root=Path("mutants"),
        tests_dir=list(config.tests_dir),
    )
    executor.configure_pytest_boundary(boundary.to_dict())
    return executor


class _FakeQueue:
    """In-process queue stub that satisfies the get/put interface."""

    def __init__(self) -> None:
        self._q: Queue[Any] = Queue()

    def put(self, item: Any) -> None:
        self._q.put(item)

    def get(self, timeout: float | None = None) -> Any:
        # Matches multiprocessing.Queue.get(timeout=...) used by the polling
        # event loop (issue #80); stdlib Queue raises queue.Empty on timeout.
        return self._q.get(timeout=timeout)

    def empty(self) -> bool:
        return self._q.empty()

    def get_nowait(self) -> Any:
        return self._q.get_nowait()


class _FakeProcess:
    """Mock for multiprocessing.Process."""

    def __init__(self, **_kwargs: Any) -> None:
        self._alive = False
        self.pid: int | None = None

    def start(self) -> None:
        self._alive = True
        self.pid = 99999

    def is_alive(self) -> bool:
        return self._alive

    def kill(self) -> None:
        self._alive = False

    def join(self, timeout: float | None = None) -> None:  # noqa: ARG002  # mock signature matches multiprocessing.Process.join
        self._alive = False


class _FakeMpContext:
    """Minimal multiprocessing context stub."""

    def __init__(self, task_queue: _FakeQueue, event_queue: _FakeQueue) -> None:
        self._task_q = task_queue
        self._event_q = event_queue
        self._queue_call_count = 0
        self._processes: list[_FakeProcess] = []

    def Queue(self) -> _FakeQueue:  # noqa: N802  # matches multiprocessing API
        # First call → task queue, second call → event queue.
        self._queue_call_count += 1
        if self._queue_call_count == 1:
            return self._task_q
        return self._event_q

    def Process(self, **kwargs: Any) -> _FakeProcess:  # noqa: N802
        proc = _FakeProcess(**kwargs)
        self._processes.append(proc)
        return proc

    def get_start_method(self) -> str:
        return "spawn"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSpawnPoolExecutorInit:
    def test_creates_with_valid_config(self) -> None:
        executor = _configured_executor(max_workers=2, config=_config())
        assert executor._max_workers == 2

    def test_config_serialised_to_dict(self) -> None:
        cfg = _config(max_children=4)
        executor = SpawnPoolExecutor(max_workers=4, config=cfg)
        assert isinstance(executor._config_data, dict)
        assert executor._config_data["max_children"] == 4


class TestSpawnPoolExecutorStart:
    def test_start_refuses_a_missing_pytest_boundary(self) -> None:
        executor = SpawnPoolExecutor(max_workers=1, config=_config())

        with pytest.raises(PytestBoundaryError, match="configure_pytest_boundary"):
            executor.start([])

    def test_tasks_and_sentinels_enqueued(self) -> None:
        """start() must enqueue N task dicts followed by max_workers sentinels."""
        task_q: _FakeQueue = _FakeQueue()
        event_q: _FakeQueue = _FakeQueue()

        executor = _configured_executor(max_workers=2, config=_config())
        executor._task_queue = task_q  # type: ignore[assignment]
        executor._event_queue = event_q  # type: ignore[assignment]
        executor._mp_ctx = _FakeMpContext(task_q, event_q)  # type: ignore[assignment]

        tasks = _tasks(3)
        with patch.object(executor, "_make_worker_process", return_value=_FakeProcess()):
            executor.start(tasks)

        # Drain queue to check contents: 3 task dicts + 2 sentinels
        items = []
        while not task_q.empty():
            items.append(task_q.get())

        task_dicts = [i for i in items if i is not None]
        sentinels = [i for i in items if i is None]
        assert len(task_dicts) == 3
        assert len(sentinels) == 2

    def test_num_tasks_recorded(self) -> None:
        """_num_tasks must reflect the number of tasks given to start()."""
        task_q: _FakeQueue = _FakeQueue()
        event_q: _FakeQueue = _FakeQueue()

        executor = _configured_executor(max_workers=1, config=_config())
        executor._task_queue = task_q  # type: ignore[assignment]
        executor._event_queue = event_q  # type: ignore[assignment]
        executor._mp_ctx = _FakeMpContext(task_q, event_q)  # type: ignore[assignment]

        with patch.object(executor, "_make_worker_process", return_value=_FakeProcess()):
            executor.start(_tasks(5))

        assert executor._num_tasks == 5

    def test_workers_spawned(self) -> None:
        """start() must spawn exactly max_workers processes."""
        task_q: _FakeQueue = _FakeQueue()
        event_q: _FakeQueue = _FakeQueue()

        executor = _configured_executor(max_workers=3, config=_config())
        executor._task_queue = task_q  # type: ignore[assignment]
        executor._event_queue = event_q  # type: ignore[assignment]

        spawned: list[_FakeProcess] = []

        def make_process() -> _FakeProcess:
            p = _FakeProcess()
            spawned.append(p)
            return p

        executor._mp_ctx = _FakeMpContext(task_q, event_q)  # type: ignore[assignment]
        with patch.object(executor, "_make_worker_process", side_effect=make_process):
            executor.start(_tasks(4))

        assert len(spawned) == 3
        assert all(p.is_alive() for p in spawned)

    def test_later_worker_start_failure_reaps_pool_before_task_publication(self) -> None:
        """Partial pool creation is all-or-nothing at the task-queue boundary."""
        executor = _configured_executor(max_workers=2, config=_config())
        first = _FakeProcess()
        second = _FakeProcess()

        def fail_start() -> None:
            raise ProcessContainmentError("worker assignment denied")

        second.start = fail_start  # type: ignore[method-assign]
        task_queue = MagicMock()
        executor._task_queue = task_queue

        with (
            patch.object(executor, "_make_worker_process", side_effect=[first, second]),
            pytest.raises(ProcessContainmentError, match="assignment denied"),
        ):
            executor.start(_tasks(2))

        assert first.is_alive() is False
        assert executor._workers == []
        task_queue.put.assert_not_called()


class TestSpawnPoolExecutorGetEvents:
    """Test get_events() by seeding the event_queue with pre-built event dicts."""

    def _seed_events(self, event_q: _FakeQueue, task_names: list[str], exit_code: int = 0) -> None:
        """Push started + completed pairs for each task name."""
        for name in task_names:
            event_q.put(TaskStarted(mutant_name=name, worker_pid=os.getpid()).model_dump())
            event_q.put(
                TaskCompleted(
                    mutant_name=name,
                    worker_pid=os.getpid(),
                    exit_code=exit_code,
                    duration=0.01,
                ).model_dump()
            )

    def test_yields_all_events_for_n_tasks(self) -> None:
        task_q: _FakeQueue = _FakeQueue()
        event_q: _FakeQueue = _FakeQueue()

        executor = SpawnPoolExecutor(max_workers=1, config=_config())
        executor._task_queue = task_q  # type: ignore[assignment]
        executor._event_queue = event_q  # type: ignore[assignment]
        executor._num_tasks = 2

        self._seed_events(event_q, ["m1", "m2"])

        events = list(executor.get_events())
        # 2 tasks x (started + completed) = 4 events
        assert len(events) == 4

    def test_started_and_completed_types_correct(self) -> None:
        task_q: _FakeQueue = _FakeQueue()
        event_q: _FakeQueue = _FakeQueue()

        executor = SpawnPoolExecutor(max_workers=1, config=_config())
        executor._task_queue = task_q  # type: ignore[assignment]
        executor._event_queue = event_q  # type: ignore[assignment]
        executor._num_tasks = 1

        self._seed_events(event_q, ["only_task"])

        events = list(executor.get_events())
        assert isinstance(events[0], TaskStarted)
        assert isinstance(events[1], TaskCompleted)


class TestSpawnPoolExecutorShutdown:
    def test_shutdown_kills_alive_workers(self) -> None:
        """shutdown() must kill any still-alive workers."""
        executor = SpawnPoolExecutor(max_workers=2, config=_config())

        alive_proc = _FakeProcess()
        alive_proc._alive = True
        dead_proc = _FakeProcess()
        dead_proc._alive = False

        executor._workers = [alive_proc, dead_proc]  # type: ignore[list-item]
        executor.shutdown(timeout=0.1)

        assert not alive_proc.is_alive()
        assert executor._workers == []

    def test_shutdown_clears_worker_list(self) -> None:
        executor = SpawnPoolExecutor(max_workers=1, config=_config())

        p = _FakeProcess()
        p._alive = False
        executor._workers = [p]  # type: ignore[list-item]
        executor.shutdown()
        assert executor._workers == []

    def test_cleanup_failures_do_not_skip_later_resources_or_escape(self) -> None:
        """Every cleanup stage is independent and bounded."""
        executor = SpawnPoolExecutor.__new__(SpawnPoolExecutor)
        executor._shutdown_done = False
        executor._posix_groups_by_worker = {}
        executor._posix_group_by_task = {}

        worker = MagicMock()
        worker.pid = 123
        worker.join.side_effect = OSError("join denied")
        worker.is_alive.return_value = True
        worker.kill.side_effect = OSError("kill denied")
        executor._workers = [worker]

        task_queue = MagicMock()
        task_queue.close.side_effect = OSError("task close denied")
        event_queue = MagicMock()
        containment_queue = MagicMock()
        containment_queue._reader = None
        executor._task_queue = task_queue
        executor._event_queue = event_queue
        executor._containment_queue = containment_queue
        executor._job_handle = 77

        with patch("mutmut_win.process.job_object.close_job") as close_job:
            executor.shutdown(timeout=0.0)

        event_queue.cancel_join_thread.assert_called_once()
        event_queue.close.assert_called_once()
        containment_queue.close.assert_called_once()
        close_job.assert_called_once_with(77)
        assert executor._job_handle is None
        assert executor._workers == []


class TestSpawnPoolExecutorGetContext:
    def test_uses_spawn_context(self) -> None:
        """Executor must use the 'spawn' multiprocessing context."""
        executor = SpawnPoolExecutor(max_workers=1, config=_config())
        ctx = executor._mp_ctx
        assert ctx.get_start_method() == "spawn"
