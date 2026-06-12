"""Domain models for mutmut-win.

All data structures use Pydantic v2 for validation and type safety.
Queue-transmitted models must be pickle-able.
"""

from __future__ import annotations

import datetime
import json
from pathlib import Path

from pydantic import BaseModel, Field, computed_field


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
    forensics: dict[str, object] | None = Field(
        default=None,
        description=(
            "Optional IL-detection forensic snapshot from the triple-check "
            "classifier (Issue #71). Populated when the worker timed out and "
            "infinite_loop_detection was active. Stored as plain dict so it "
            "round-trips through multiprocessing.Queue pickling without "
            "binding to loop_monitor types."
        ),
    )


# Union type for all events that flow through the event queue.  Timeouts are
# reported by the worker itself as TaskCompleted with exit code 36/38 — the
# separate TaskTimedOut event belonged to the never-wired WallClockTimeout
# monitor and was removed with it (issue #81 / A2-JT-003).
TaskEvent = TaskStarted | TaskCompleted


class MutationResult(BaseModel):
    """Result of a single mutation test."""

    mutant_name: str
    status: str = Field(
        description=("survived, killed, timeout, killed_by_infinite_loop, suspicious, etc.")
    )
    exit_code: int | None = None
    duration: float | None = Field(default=None, ge=0.0)
    last_output: str | None = Field(
        default=None,
        description="Last pytest output lines (captured on timeout/suspicious exit codes)",
    )
    forensics: dict[str, object] | None = Field(
        default=None,
        description=(
            "Optional IL-detection forensic snapshot (cpu mean/max, output "
            "growth, running ratio, confidence). Populated only when the "
            "triple-check classifier ran — Issue #71. Stored as a plain dict "
            "so the orchestrator can pickle it across the multiprocessing "
            "boundary without depending on loop_monitor types."
        ),
    )
    tests_fingerprint: str | None = Field(
        default=None,
        description=(
            "Fingerprint of the test basis this verdict was produced under "
            "(sorted node IDs + per-test-file mtime/size) — the result-reuse "
            "condition of issue #119. NULL for verdicts that are never "
            "reused (type-check kills, no tests) and for pre-v2.13 rows."
        ),
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
    # Source fingerprint at generation time (issue #101 / A3-FD-004): the
    # fast path compares EQUALITY against the live source — a restore with
    # an older timestamp is inequality and regenerates. Defaults keep
    # pre-v2.10 meta files loadable (their None never matches → regenerate).
    source_mtime: float | None = None
    source_size: int | None = None

    @property
    def meta_path(self) -> Path:
        """Path to the JSON meta file for this source file."""
        return Path("mutants") / (self.path + ".meta")

    def load(self) -> None:
        """Load mutation metadata from the JSON meta file.

        Tolerates corruption (issue #101 / A3-CM-009, confirmed via a
        truncated-file experiment): a half-written ``.meta`` used to raise
        an uncaught ``JSONDecodeError`` and block EVERY subsequent run
        until manual deletion. A corrupt file now warns, is removed (so the
        generation fast path rebuilds cleanly), and loading starts empty.
        """
        try:
            with self.meta_path.open(encoding="utf-8") as f:
                meta: dict[str, object] = json.load(f)
        except FileNotFoundError:
            return
        except (json.JSONDecodeError, UnicodeDecodeError):
            import contextlib

            print(f"Warning: corrupted meta file {self.meta_path} — rebuilding from scratch.")
            with contextlib.suppress(OSError):
                self.meta_path.unlink()
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

        raw_mtime = meta.pop("source_mtime", None)
        self.source_mtime = float(raw_mtime) if isinstance(raw_mtime, (int, float)) else None
        raw_size = meta.pop("source_size", None)
        self.source_size = int(raw_size) if isinstance(raw_size, int) else None

    def save(self) -> None:
        """Save mutation metadata to the JSON meta file (atomically).

        Writes to a sibling ``.tmp`` and swaps via ``Path.replace`` —
        atomic on the same volume — so a crash mid-write (the A3-CM-009
        scenario) can never leave a truncated ``.meta`` behind.
        """
        self.meta_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.meta_path.with_suffix(self.meta_path.suffix + ".tmp")
        with tmp_path.open("w", encoding="utf-8") as f:
            json.dump(
                {
                    "exit_code_by_key": self.exit_code_by_key,
                    "durations_by_key": self.durations_by_key,
                    "type_check_error_by_key": self.type_check_error_by_key,
                    "estimated_durations_by_key": self.estimated_time_of_tests_by_mutant,
                    "source_mtime": self.source_mtime,
                    "source_size": self.source_size,
                },
                f,
                indent=4,
            )
        tmp_path.replace(self.meta_path)


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
    # New in v2.9.0 (#91, A2-EW-004): crashes used to count in the denominator
    # without any bucket. Buckets are DISJOINT — kill-class aggregation
    # happens in the score formula, never by folding buckets into each other.
    segfault: int = 0
    # New in v2.9.0 (#94, A3-OS-005): an interrupted run used to end exactly
    # like a complete one. `was_interrupted` marks the RUN; `unchecked` keeps
    # the sum invariant (buckets + unchecked == total) and is excluded from
    # the score denominator — a partial run is scored over what it checked.
    was_interrupted: bool = False
    unchecked: int = 0
    duration_seconds: float = 0.0

    # Serialized into model_dump()/JSON (issue #97 / A3-OS-014: the CI
    # channel was blind on the one number it gates on). Additive only —
    # the JSON is a CI contract.
    @computed_field  # type: ignore[prop-decorator]  # documented pydantic v2 pattern for serialized properties
    @property
    def score(self) -> float:
        """Mutation score as percentage (kill class / (total - skipped - no_tests)).

        The kill class is ``killed + type_check_caught + segfault``: a suite
        that crashes under a mutant has detected it just as surely as a
        failing assertion (issue #91).
        """
        return self.compute_score(treat_timeout_as_kill=False)

    def compute_score(self, treat_timeout_as_kill: bool = False) -> float:
        """Mutation score with optional timeout-as-kill accounting.

        Default behaviour matches ``score`` (timeouts excluded from the
        numerator). Setting ``treat_timeout_as_kill=True`` counts timeout
        mutants toward the kill bucket — a downstream mitigation for Bug #71
        where Hypothesis tests turn infinite-loop mutations into TIMEOUT
        instead of KILLED, deflating the reported score.
        """
        denominator = self.total_mutants - self.skipped - self.no_tests - self.unchecked
        if denominator <= 0:
            return 0.0
        kill_class = self.killed + self.type_check_caught + self.segfault
        effective_killed = kill_class + (self.timeout if treat_timeout_as_kill else 0)
        return (effective_killed / denominator) * 100.0
