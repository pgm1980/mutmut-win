"""Regression tests for Bug #12 — Worker crash recovery.

The original ``worker_main`` loop was robust against ``subprocess.TimeoutExpired``
and ``OSError`` from ``subprocess.run`` (both result in a ``TaskCompleted``
event with a sentinel exit code). Anything else — a ``Pydantic ValidationError``
on a corrupted task dict, an unexpected exception inside the per-task block,
a transient libcst / filesystem error — would crash the worker mid-task. The
orchestrator's ``get_events()`` would then block forever waiting for a
``TaskCompleted`` that will never arrive, hanging the entire run.

These tests verify that the worker now catches arbitrary exceptions per task,
emits a synthetic ``TaskCompleted`` so the orchestrator can make progress,
and stays alive to process the next task in the queue.

See critique-model-service ``_misc/mutmut-win-bugs.md`` (this repo's #12) and
Sprint 24 backlog for the recovery design.
"""

from __future__ import annotations

from queue import Queue
from typing import Any
from unittest.mock import MagicMock, patch

from mutmut_win.models import MutationTask, TaskCompleted
from mutmut_win.process.worker import worker_main


def _make_config(**overrides: Any) -> dict[str, Any]:
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


class _SimpleQueue:
    """Thread-safe queue stand-in for tests (duck-types multiprocessing.Queue)."""

    def __init__(self) -> None:
        self._q: Queue[Any] = Queue()

    def put(self, item: Any) -> None:
        self._q.put(item)

    def get(self) -> Any:
        return self._q.get()

    def empty(self) -> bool:
        return self._q.empty()


def _drain(event_q: _SimpleQueue) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    while not event_q.empty():
        out.append(event_q.get())
    return out


def test_worker_survives_corrupted_task_dict() -> None:
    """A task dict that fails ``MutationTask.model_validate`` must not kill the worker."""
    task_q: _SimpleQueue = _SimpleQueue()
    event_q: _SimpleQueue = _SimpleQueue()

    # Missing required ``mutant_name`` → ValidationError.
    task_q.put({"this_is_not": "a valid task dict"})

    # Follow up with a healthy task so we can prove the worker is still alive.
    healthy = MutationTask(mutant_name="src/foo.py::bar__mutmut_1").model_dump()
    task_q.put(healthy)
    task_q.put(None)

    fake_result = MagicMock()
    fake_result.returncode = 0

    with patch("mutmut_win.process.worker.subprocess.run", return_value=fake_result):
        worker_main(task_q, event_q, _make_config())  # type: ignore[arg-type]

    events = _drain(event_q)
    completed = [TaskCompleted.model_validate(e) for e in events if "exit_code" in e]

    # 1 synthetic suspicious event for the corrupted task,
    # plus 1 normal event for the healthy task.
    assert len(completed) == 2, (
        f"Expected 2 TaskCompleted events (1 synthetic + 1 real), got {len(completed)}:\n"
        + "\n".join(f"  {e}" for e in events)
    )

    # The synthetic one must have a non-zero (suspicious-ish) exit code so the
    # orchestrator can distinguish it from a regular pytest result.
    statuses = [c.exit_code for c in completed]
    assert any(code != 0 for code in statuses), (
        f"Expected at least one non-zero exit_code (from the synthetic recovery "
        f"event); got {statuses}"
    )


def test_worker_survives_unexpected_exception_in_subprocess_layer() -> None:
    """A non-OSError, non-TimeoutExpired exception from subprocess.run must not kill the worker."""
    task_q: _SimpleQueue = _SimpleQueue()
    event_q: _SimpleQueue = _SimpleQueue()

    healthy_after_crash = MutationTask(mutant_name="src/foo.py::bar__mutmut_2").model_dump()
    task_q.put(MutationTask(mutant_name="src/foo.py::bar__mutmut_1").model_dump())
    task_q.put(healthy_after_crash)
    task_q.put(None)

    # First call raises a generic RuntimeError; second call succeeds.
    fake_ok = MagicMock()
    fake_ok.returncode = 0

    def _flaky_run(*_args: Any, **_kwargs: Any) -> MagicMock:
        if not _flaky_run.first_call_done:  # type: ignore[attr-defined]
            _flaky_run.first_call_done = True  # type: ignore[attr-defined]
            msg = "synthetic crash inside subprocess layer"
            raise RuntimeError(msg)
        return fake_ok

    _flaky_run.first_call_done = False  # type: ignore[attr-defined]

    with patch("mutmut_win.process.worker.subprocess.run", side_effect=_flaky_run):
        worker_main(task_q, event_q, _make_config())  # type: ignore[arg-type]

    events = _drain(event_q)
    completed_events = [TaskCompleted.model_validate(e) for e in events if "exit_code" in e]

    # Both tasks must produce a TaskCompleted — the orchestrator can't recover
    # if the worker silently drops one.
    assert len(completed_events) == 2, (
        f"Worker died on the first task — orchestrator would hang. "
        f"Got {len(completed_events)} completed events:\n"
        + "\n".join(f"  {e}" for e in events)
    )

    names = {c.mutant_name for c in completed_events}
    assert names == {"src/foo.py::bar__mutmut_1", "src/foo.py::bar__mutmut_2"}, (
        f"Wrong set of completed mutants: {names}"
    )


def test_worker_recovery_event_marks_mutant_name() -> None:
    """The synthetic recovery event must carry the original mutant_name when known.

    If the task dict validated successfully and the crash happened later (in the
    subprocess layer), the recovery event must still carry ``task.mutant_name``
    so the orchestrator can pin the result to the right mutant.
    """
    task_q: _SimpleQueue = _SimpleQueue()
    event_q: _SimpleQueue = _SimpleQueue()

    task_q.put(MutationTask(mutant_name="src/important.py::critical__mutmut_42").model_dump())
    task_q.put(None)

    with patch(
        "mutmut_win.process.worker.subprocess.run",
        side_effect=RuntimeError("boom"),
    ):
        worker_main(task_q, event_q, _make_config())  # type: ignore[arg-type]

    events = _drain(event_q)
    completed_events = [TaskCompleted.model_validate(e) for e in events if "exit_code" in e]

    assert len(completed_events) == 1
    assert completed_events[0].mutant_name == "src/important.py::critical__mutmut_42"
