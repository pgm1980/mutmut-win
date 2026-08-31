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

from dataclasses import dataclass
from typing import TYPE_CHECKING

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
