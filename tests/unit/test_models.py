"""Tests for mutmut_win.models."""

from __future__ import annotations

import pickle

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from mutmut_win.models import (
    MutationResult,
    MutationRunResult,
    MutationTask,
    TaskCompleted,
    TaskStarted,
    TaskTimedOut,
)


class TestMutationTask:
    def test_minimal_creation(self) -> None:
        task = MutationTask(mutant_name="foo.py::bar__mutmut_1")
        assert task.mutant_name == "foo.py::bar__mutmut_1"
        assert task.tests == []
        assert task.estimated_time == 0.0
        assert task.timeout_seconds == 30.0

    def test_full_creation(self) -> None:
        task = MutationTask(
            mutant_name="foo.py::bar__mutmut_1",
            tests=["test_foo.py::test_bar"],
            estimated_time=1.5,
            timeout_seconds=60.0,
        )
        assert task.tests == ["test_foo.py::test_bar"]
        assert task.estimated_time == 1.5
        assert task.timeout_seconds == 60.0

    def test_negative_estimated_time_rejected(self) -> None:
        with pytest.raises(ValidationError):
            MutationTask(mutant_name="x", estimated_time=-1.0)

    def test_zero_timeout_rejected(self) -> None:
        with pytest.raises(ValidationError):
            MutationTask(mutant_name="x", timeout_seconds=0.0)

    @given(st.text(min_size=1, max_size=100))
    def test_pickle_roundtrip(self, name: str) -> None:
        task = MutationTask(mutant_name=name)
        # pickle is safe here: we control both serialization and deserialization
        restored = pickle.loads(pickle.dumps(task))  # noqa: S301
        assert restored == task


class TestTaskEvents:
    def test_task_started_has_timestamp(self) -> None:
        event = TaskStarted(mutant_name="m1", worker_pid=1234)
        assert event.timestamp is not None

    def test_task_completed(self) -> None:
        event = TaskCompleted(mutant_name="m1", worker_pid=1234, exit_code=0, duration=1.5)
        assert event.exit_code == 0
        assert event.duration == 1.5

    def test_task_timed_out(self) -> None:
        event = TaskTimedOut(mutant_name="m1", worker_pid=1234)
        assert event.mutant_name == "m1"

    @given(st.integers(min_value=0, max_value=255))
    def test_completed_pickle_roundtrip(self, exit_code: int) -> None:
        event = TaskCompleted(mutant_name="test", worker_pid=100, exit_code=exit_code, duration=0.1)
        # pickle is safe here: we control both serialization and deserialization
        restored = pickle.loads(pickle.dumps(event))  # noqa: S301
        assert restored == event


class TestMutationResult:
    def test_basic_result(self) -> None:
        result = MutationResult(mutant_name="m1", status="killed", exit_code=1, duration=0.5)
        assert result.status == "killed"

    def test_result_without_optional_fields(self) -> None:
        result = MutationResult(mutant_name="m1", status="timeout")
        assert result.exit_code is None
        assert result.duration is None


class TestMutationRunResult:
    def test_score_calculation(self) -> None:
        result = MutationRunResult(
            total_mutants=100,
            killed=80,
            survived=10,
            timeout=5,
            suspicious=3,
            skipped=2,
        )
        # score = killed / (total - skipped - no_tests) = 80 / (100 - 2 - 0)
        assert result.score == pytest.approx(81.63, rel=0.01)

    def test_score_with_no_mutants(self) -> None:
        result = MutationRunResult()
        assert result.score == 0.0

    def test_score_all_skipped(self) -> None:
        result = MutationRunResult(total_mutants=10, skipped=10)
        assert result.score == 0.0
