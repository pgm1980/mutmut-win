"""Tests for worker-liveness handling in ``get_events`` (Issue #80, A2-EW-002 — S1).

``get_events()`` used to block forever in ``event_queue.get()`` when a worker
died hard (OS kill, native crash, BaseException during put): the in-flight
task never produced a completion, so ``finished < num_tasks`` never resolved.

The protocol under test (fixed in a 10-step sequential-thinking session):
poll with timeout → on idle, sweep liveness → synthesize a ``TaskCompleted``
(exit 35, explanatory ``last_output``) for the dead worker's in-flight tasks →
ignore a late-flushed REAL completion for an already-synthesized mutant
(single-count guarantee) → abort loudly when the whole pool is dead and tasks
were never started.  Deterministic via fake worker objects injected into the
executor; the poll interval is patched down for speed.
"""

from __future__ import annotations

import queue as queue_module
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pytest

import mutmut_win.process.executor as executor_module
from mutmut_win.config import MutmutConfig
from mutmut_win.models import TaskCompleted, TaskStarted
from mutmut_win.process.executor import SpawnPoolExecutor

if TYPE_CHECKING:
    from collections.abc import Iterator

    from mutmut_win.models import TaskEvent


@dataclass
class _FakeWorker:
    pid: int
    alive: bool
    exitcode: int | None = None

    def is_alive(self) -> bool:
        return self.alive


#: Script token meaning "nothing readable right now" (raises queue.Empty).
_EMPTY = object()


class _ScriptedQueue:
    """Fake event queue with separate scripts for blocking/non-blocking reads.

    M-054: the real race is that a dead worker's completion is already in the
    pipe but NOT visible to a blocking ``get(timeout=...)`` whose deadline
    expired just before the bytes arrived. Only the non-blocking drain taken
    after the liveness observation may read those items before any synthesis
    is allowed.
    """

    def __init__(self, blocking: list[Any], nowait: list[Any], *, max_gets: int = 50) -> None:
        self._blocking = list(blocking)
        self._nowait = list(nowait)
        self._gets = 0
        self._max_gets = max_gets

    def get(self, timeout: float | None = None) -> Any:  # noqa: ARG002  # mp.Queue signature
        self._gets += 1
        if self._gets > self._max_gets:
            # Pre-fix hang guard (M-054): the old idle tick could loop forever
            # when an in-flight task's dead owner was already 'handled' — fail
            # the red run loudly instead of blocking the suite.
            raise AssertionError("get_events looped without completing (M-054 hang guard)")
        return self._next(self._blocking)

    def get_nowait(self) -> Any:
        return self._next(self._nowait)

    @staticmethod
    def _next(script: list[Any]) -> Any:
        item = script.pop(0) if script else _EMPTY
        if item is _EMPTY:
            raise queue_module.Empty
        return item


@pytest.fixture
def fast_poll(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(executor_module, "_EVENT_POLL_SECONDS", 0.05)


def _executor(num_tasks: int, workers: list[_FakeWorker]) -> SpawnPoolExecutor:
    ex = SpawnPoolExecutor(max_workers=1, config=MutmutConfig())
    ex._num_tasks = num_tasks
    ex._workers = workers  # type: ignore[assignment]  # fakes satisfy the used protocol
    return ex


def _drain(events: Iterator[TaskEvent]) -> list[TaskEvent]:
    return list(events)


@pytest.mark.usefixtures("fast_poll")
class TestDeadWorkerSynthesis:
    def test_inflight_task_of_dead_worker_is_synthesized(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        dead = _FakeWorker(pid=111, alive=False, exitcode=-9)
        ex = _executor(num_tasks=2, workers=[dead])
        ex._event_queue.put(
            TaskStarted(mutant_name="pkg.x_a__mutmut_1", worker_pid=111).model_dump()
        )

        events = _drain(ex.get_events())

        completions = [e for e in events if isinstance(e, TaskCompleted)]
        assert len(completions) == 1
        synthetic = completions[0]
        assert synthetic.mutant_name == "pkg.x_a__mutmut_1"
        assert synthetic.exit_code == 35  # suspicious
        assert synthetic.last_output is not None
        assert "died" in synthetic.last_output
        # Second task never started and the pool is dead -> loud abort.
        out = capsys.readouterr().err  # abort prose lives on stderr (#127/A6+A7)
        assert "never started" in out

    def test_late_real_completion_after_synthetic_is_dropped(self) -> None:
        dead = _FakeWorker(pid=111, alive=False, exitcode=1)
        alive = _FakeWorker(pid=222, alive=True)
        ex = _executor(num_tasks=2, workers=[dead, alive])
        # Worker 111 started m1, then died; its completion flushes LATE
        # (after our synthetic) — the single-count guarantee must drop it.
        ex._event_queue.put(TaskStarted(mutant_name="m1", worker_pid=111).model_dump())

        collected: list[TaskEvent] = []
        gen = ex.get_events()
        for event in gen:
            collected.append(event)
            if isinstance(event, TaskCompleted) and event.mutant_name == "m1":
                # Synthetic for m1 just arrived: now the late real completion
                # shows up, followed by the alive worker finishing m2.
                ex._event_queue.put(
                    TaskCompleted(
                        mutant_name="m1", worker_pid=111, exit_code=1, duration=0.1
                    ).model_dump()
                )
                ex._event_queue.put(TaskStarted(mutant_name="m2", worker_pid=222).model_dump())
                ex._event_queue.put(
                    TaskCompleted(
                        mutant_name="m2", worker_pid=222, exit_code=0, duration=0.1
                    ).model_dump()
                )

        m1_completions = [
            e for e in collected if isinstance(e, TaskCompleted) and e.mutant_name == "m1"
        ]
        m2_completions = [
            e for e in collected if isinstance(e, TaskCompleted) and e.mutant_name == "m2"
        ]
        assert len(m1_completions) == 1  # the synthetic one only
        assert m1_completions[0].exit_code == 35
        assert len(m2_completions) == 1  # generator ended exactly at num_tasks

    def test_all_dead_with_unstarted_tasks_aborts_loudly(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        dead = _FakeWorker(pid=111, alive=False, exitcode=-1073741819)
        ex = _executor(num_tasks=5, workers=[dead])

        events = _drain(ex.get_events())

        assert events == []  # nothing started, nothing fabricated
        out = capsys.readouterr().err  # abort prose lives on stderr (#127/A6+A7)
        assert "never started" in out

    def test_unknown_recovery_event_remains_unchecked_and_is_not_persisted(
        self, tmp_path: object, capsys: pytest.CaptureFixture
    ) -> None:
        """A2-EW-012: recovery events without an extractable task name used to
        create a literal 'unknown' row in the DB while the real mutant stayed
        unreported — now they remain unchecked and write nothing."""
        from pathlib import Path

        from mutmut_win.db import create_db, load_results
        from mutmut_win.models import MutationRunResult
        from mutmut_win.orchestrator import _update_summary_and_persist

        db_path = Path(str(tmp_path)) / "results.sqlite"
        create_db(db_path)
        summary = MutationRunResult(total_mutants=1)
        event = TaskCompleted(mutant_name="unknown", worker_pid=1, exit_code=35, duration=0.0)

        is_completion = _update_summary_and_persist(event, summary, db_path, {})

        assert is_completion is False  # no attributable mutant completion
        assert load_results(db_path) == []  # no ghost row
        assert summary.suspicious == 0  # no bucket pollution
        assert "unchecked" in capsys.readouterr().out

    def test_normally_exited_workers_trigger_no_synthetics(self) -> None:
        # A worker that exited cleanly (sentinel) is also not alive — but its
        # completions arrived before any idle tick, so no synthesis happens.
        done = _FakeWorker(pid=111, alive=False, exitcode=0)
        ex = _executor(num_tasks=1, workers=[done])
        ex._event_queue.put(TaskStarted(mutant_name="m1", worker_pid=111).model_dump())
        ex._event_queue.put(
            TaskCompleted(mutant_name="m1", worker_pid=111, exit_code=1, duration=0.2).model_dump()
        )

        events = _drain(ex.get_events())

        completions = [e for e in events if isinstance(e, TaskCompleted)]
        assert len(completions) == 1
        assert completions[0].exit_code == 1  # the real one, untouched


@pytest.mark.usefixtures("fast_poll")
class TestIdleTickDrainsBeforeSweep:
    """M-054: sweep classification must not eat real verdicts of dead workers.

    The old idle tick swept purely on ``worker.is_alive()``: a worker that
    had published its completion and exited cleanly (sentinel consumed, feeder
    thread joined at interpreter exit) could still be declared dead BEFORE
    the executor read the completion — replacing a correct verdict with a
    synthetic exit 35. The fixed order is: liveness snapshot -> full
    non-blocking drain over the same event path -> sweep of the snapshot ->
    all-dead check against the snapshot.
    """

    def test_clean_exit_final_completion_racing_poll_deadline_is_not_synthesized(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        done = _FakeWorker(pid=111, alive=False, exitcode=0)
        ex = _executor(num_tasks=1, workers=[done])
        ex._event_queue = _ScriptedQueue(  # type: ignore[assignment]
            blocking=[
                TaskStarted(mutant_name="m1", worker_pid=111).model_dump(),
                _EMPTY,
            ],
            nowait=[
                TaskCompleted(
                    mutant_name="m1", worker_pid=111, exit_code=1, duration=0.1
                ).model_dump(),
                _EMPTY,
            ],
        )

        events = _drain(ex.get_events())

        completions = [e for e in events if isinstance(e, TaskCompleted)]
        assert len(completions) == 1
        assert completions[0].exit_code == 1  # real verdict, never a synthetic 35
        assert ex.aborted is False
        # The drain reached num_tasks: no synthesis and no drop warning fired.
        assert not [r for r in caplog.records if "synthesizing" in r.getMessage()]
        assert not [r for r in caplog.records if "dropping late real completion" in r.getMessage()]

    def test_late_started_of_handled_dead_worker_is_synthesized(self) -> None:
        dead = _FakeWorker(pid=111, alive=False, exitcode=-9)
        alive = _FakeWorker(pid=222, alive=True)
        ex = _executor(num_tasks=1, workers=[dead, alive])
        ex._event_queue = _ScriptedQueue(  # type: ignore[assignment]
            blocking=[
                _EMPTY,  # first idle tick: sweep records 111 without a task
                TaskStarted(mutant_name="m1", worker_pid=111).model_dump(),
            ],
            nowait=[_EMPTY],
        )

        collected: list[TaskEvent] = []
        for event in ex.get_events():
            collected.append(event)
            if isinstance(event, TaskStarted):
                # The second worker dies after the late start landed.
                alive.alive = False

        completions = [e for e in collected if isinstance(e, TaskCompleted)]
        assert len(completions) == 1
        assert completions[0].exit_code == 35  # no completion ever came -> suspicious
        assert "died" in (completions[0].last_output or "")
        assert ex.aborted is False  # the start WAS observed; no 'never started' abort

    def test_late_started_of_dead_worker_followed_by_real_completion_keeps_real_verdict(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Keep a potential pre-fix watchdog hang bounded for the red run.
        monkeypatch.setattr(executor_module, "_STARTUP_GRACE_SECONDS", 0.5)
        dead = _FakeWorker(pid=111, alive=False, exitcode=-9)
        alive = _FakeWorker(pid=222, alive=True)
        ex = _executor(num_tasks=1, workers=[dead, alive])
        ex._event_queue = _ScriptedQueue(  # type: ignore[assignment]
            blocking=[
                _EMPTY,
                TaskStarted(mutant_name="m1", worker_pid=111).model_dump(),
            ],
            nowait=[
                _EMPTY,  # first idle tick's drain: still nothing
                TaskCompleted(
                    mutant_name="m1", worker_pid=111, exit_code=0, duration=0.1
                ).model_dump(),
            ],
        )

        events = _drain(ex.get_events())

        completions = [e for e in events if isinstance(e, TaskCompleted)]
        assert len(completions) == 1
        assert completions[0].exit_code == 0  # real verdict kept, no synthesis
        assert ex.aborted is False

    def test_fatal_completion_in_drain_aborts_without_sweep(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        dead = _FakeWorker(pid=111, alive=False, exitcode=-9)
        ex = _executor(num_tasks=1, workers=[dead])
        fatal = TaskCompleted(
            mutant_name="m1",
            worker_pid=111,
            exit_code=35,
            duration=0.0,
            last_output="WorkerEnvironmentError: Task preparation failed",
            fatal=True,
        )
        ex._event_queue = _ScriptedQueue(  # type: ignore[assignment]
            blocking=[_EMPTY],
            nowait=[fatal.model_dump()],
        )

        events = _drain(ex.get_events())

        assert len(events) == 1
        assert isinstance(events[0], TaskCompleted)
        assert events[0].fatal is True
        assert ex.aborted is True
        assert "fatal execution-boundary failure" in (ex.abort_reason or "")
        # The fatal completion left the loop before any sweep could run.
        assert not [r for r in caplog.records if "synthesizing" in r.getMessage()]
