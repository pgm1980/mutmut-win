"""Unit tests for mutmut_win.process.executor (SpawnPoolExecutor)."""

from __future__ import annotations

import os
from queue import Queue
from typing import Any
from unittest.mock import patch

from mutmut_win.config import MutmutConfig
from mutmut_win.models import MutationTask, TaskCompleted, TaskStarted
from mutmut_win.process.executor import SpawnPoolExecutor

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


class _FakeQueue:
    """In-process queue stub that satisfies the get/put interface."""

    def __init__(self) -> None:
        self._q: Queue[Any] = Queue()

    def put(self, item: Any) -> None:
        self._q.put(item)

    def get(self) -> Any:
        return self._q.get()

    def empty(self) -> bool:
        return self._q.empty()

    def get_nowait(self) -> Any:
        return self._q.get_nowait()


class _FakeProcess:
    """Mock for multiprocessing.Process."""

    def __init__(self, **_kwargs: Any) -> None:
        self._alive = False

    def start(self) -> None:
        self._alive = True

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
        executor = SpawnPoolExecutor(max_workers=2, config=_config())
        assert executor._max_workers == 2

    def test_config_serialised_to_dict(self) -> None:
        cfg = _config(max_children=4)
        executor = SpawnPoolExecutor(max_workers=4, config=cfg)
        assert isinstance(executor._config_data, dict)
        assert executor._config_data["max_children"] == 4


class TestSpawnPoolExecutorStart:
    def test_tasks_and_sentinels_enqueued(self) -> None:
        """start() must enqueue N task dicts followed by max_workers sentinels."""
        task_q: _FakeQueue = _FakeQueue()
        event_q: _FakeQueue = _FakeQueue()

        executor = SpawnPoolExecutor(max_workers=2, config=_config())
        executor._task_queue = task_q  # type: ignore[assignment]
        executor._event_queue = event_q  # type: ignore[assignment]
        executor._mp_ctx = _FakeMpContext(task_q, event_q)  # type: ignore[assignment]

        tasks = _tasks(3)
        with patch.object(executor._mp_ctx, "Process", return_value=_FakeProcess()):
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

        executor = SpawnPoolExecutor(max_workers=1, config=_config())
        executor._task_queue = task_q  # type: ignore[assignment]
        executor._event_queue = event_q  # type: ignore[assignment]
        executor._mp_ctx = _FakeMpContext(task_q, event_q)  # type: ignore[assignment]

        with patch.object(executor._mp_ctx, "Process", return_value=_FakeProcess()):
            executor.start(_tasks(5))

        assert executor._num_tasks == 5

    def test_workers_spawned(self) -> None:
        """start() must spawn exactly max_workers processes."""
        task_q: _FakeQueue = _FakeQueue()
        event_q: _FakeQueue = _FakeQueue()

        executor = SpawnPoolExecutor(max_workers=3, config=_config())
        executor._task_queue = task_q  # type: ignore[assignment]
        executor._event_queue = event_q  # type: ignore[assignment]

        spawned: list[_FakeProcess] = []

        def make_process(**kwargs: Any) -> _FakeProcess:
            p = _FakeProcess(**kwargs)
            spawned.append(p)
            return p

        executor._mp_ctx = _FakeMpContext(task_q, event_q)  # type: ignore[assignment]
        with patch.object(executor._mp_ctx, "Process", side_effect=make_process):
            executor.start(_tasks(4))

        assert len(spawned) == 3
        assert all(p.is_alive() for p in spawned)


class TestSpawnPoolExecutorGetEvents:
    """Test get_events() by seeding the event_queue with pre-built event dicts."""

    def _seed_events(
        self, event_q: _FakeQueue, task_names: list[str], exit_code: int = 0
    ) -> None:
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

    def test_timed_out_event_counted_as_finished(self) -> None:
        """A TaskTimedOut in the queue must count toward the finished tally."""
        from mutmut_win.models import TaskTimedOut

        task_q: _FakeQueue = _FakeQueue()
        event_q: _FakeQueue = _FakeQueue()

        executor = SpawnPoolExecutor(max_workers=1, config=_config())
        executor._task_queue = task_q  # type: ignore[assignment]
        executor._event_queue = event_q  # type: ignore[assignment]
        executor._num_tasks = 1

        event_q.put(TaskStarted(mutant_name="m1", worker_pid=os.getpid()).model_dump())
        event_q.put(TaskTimedOut(mutant_name="m1", worker_pid=os.getpid()).model_dump())

        events = list(executor.get_events())
        assert len(events) == 2
        assert isinstance(events[1], TaskTimedOut)


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


class TestSpawnPoolExecutorGetContext:
    def test_uses_spawn_context(self) -> None:
        """Executor must use the 'spawn' multiprocessing context."""
        executor = SpawnPoolExecutor(max_workers=1, config=_config())
        ctx = executor._mp_ctx
        assert ctx.get_start_method() == "spawn"
