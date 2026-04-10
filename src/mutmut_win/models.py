"""Domain models for mutmut-win.

All data structures use Pydantic v2 for validation and type safety.
Queue-transmitted models must be pickle-able.
"""

from __future__ import annotations

import datetime
import json
from pathlib import Path

from pydantic import BaseModel, Field


class MutationTask(BaseModel):
    """A single mutation test task to be executed by a worker.

    Sent from the main process to workers via task_queue.
    """

    mutant_name: str = Field(
        description="Unique mutant identifier (e.g. 'src/foo.py::bar__mutmut_1')",
    )
    tests: list[str] = Field(
        default_factory=list,
        description="Test names to run for this mutant",
    )
    estimated_time: float = Field(
        default=0.0,
        ge=0.0,
        description="Estimated test runtime in seconds",
    )
    timeout_seconds: float = Field(
        default=30.0,
        gt=0.0,
        description="Wall-clock timeout for this task in seconds",
    )


class TaskStarted(BaseModel):
    """Event: a worker has started processing a mutation task.

    Sent from worker to main process via event_queue.
    """

    mutant_name: str
    worker_pid: int
    timestamp: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(tz=datetime.UTC),
    )


class TaskCompleted(BaseModel):
    """Event: a worker has finished processing a mutation task.

    Sent from worker to main process via event_queue.
    """

    mutant_name: str
    worker_pid: int
    exit_code: int
    duration: float = Field(ge=0.0, description="Duration in seconds")
    last_output: str | None = Field(
        default=None,
        description="Last pytest output lines (captured on timeout/suspicious exit codes)",
    )


class TaskTimedOut(BaseModel):
    """Event: a mutation task exceeded its wall-clock timeout.

    Injected by the timeout monitor into event_queue.
    """

    mutant_name: str
    worker_pid: int


# Union type for all events that flow through the event queue.
TaskEvent = TaskStarted | TaskCompleted | TaskTimedOut


class MutationResult(BaseModel):
    """Result of a single mutation test."""

    mutant_name: str
    status: str = Field(description="survived, killed, timeout, suspicious, etc.")
    exit_code: int | None = None
    duration: float | None = Field(default=None, ge=0.0)
    last_output: str | None = Field(
        default=None,
        description="Last pytest output lines (captured on timeout/suspicious exit codes)",
    )


class SourceFileMutationData(BaseModel):
    """Mutation data for a single source file.

    Tracks mutant generation, test assignment, and results.
    Compatible with mutmut's JSON meta file format.
    """

    path: str = Field(description="Relative path to the source file")
    exit_code_by_key: dict[str, int | None] = Field(default_factory=dict)
    durations_by_key: dict[str, float] = Field(default_factory=dict)
    estimated_time_of_tests_by_mutant: dict[str, float] = Field(default_factory=dict)
    type_check_error_by_key: dict[str, str] = Field(default_factory=dict)

    @property
    def meta_path(self) -> Path:
        """Path to the JSON meta file for this source file."""
        return Path("mutants") / (self.path + ".meta")

    def load(self) -> None:
        """Load mutation metadata from the JSON meta file."""
        try:
            with self.meta_path.open(encoding="utf-8") as f:
                meta: dict[str, object] = json.load(f)
        except FileNotFoundError:
            return

        raw_exit = meta.pop("exit_code_by_key", {})
        if isinstance(raw_exit, dict):
            self.exit_code_by_key = {str(k): v for k, v in raw_exit.items()}

        raw_dur = meta.pop("durations_by_key", {})
        if isinstance(raw_dur, dict):
            self.durations_by_key = {str(k): float(v) for k, v in raw_dur.items()}

        raw_est = meta.pop("estimated_durations_by_key", {})
        if isinstance(raw_est, dict):
            self.estimated_time_of_tests_by_mutant = {str(k): float(v) for k, v in raw_est.items()}

        raw_tc = meta.pop("type_check_error_by_key", {})
        if isinstance(raw_tc, dict):
            self.type_check_error_by_key = {str(k): str(v) for k, v in raw_tc.items()}

    def save(self) -> None:
        """Save mutation metadata to the JSON meta file."""
        self.meta_path.parent.mkdir(parents=True, exist_ok=True)
        with self.meta_path.open("w", encoding="utf-8") as f:
            json.dump(
                {
                    "exit_code_by_key": self.exit_code_by_key,
                    "durations_by_key": self.durations_by_key,
                    "type_check_error_by_key": self.type_check_error_by_key,
                    "estimated_durations_by_key": self.estimated_time_of_tests_by_mutant,
                },
                f,
                indent=4,
            )


class MutationRunResult(BaseModel):
    """Summary result of a complete mutation testing run."""

    total_mutants: int = 0
    killed: int = 0
    survived: int = 0
    timeout: int = 0
    suspicious: int = 0
    skipped: int = 0
    no_tests: int = 0
    type_check_caught: int = 0
    duration_seconds: float = 0.0

    @property
    def score(self) -> float:
        """Mutation score as percentage (killed / (total - skipped - no_tests))."""
        denominator = self.total_mutants - self.skipped - self.no_tests
        if denominator <= 0:
            return 0.0
        return (self.killed / denominator) * 100.0
