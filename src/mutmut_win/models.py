"""Domain models for mutmut-win.

All data structures use Pydantic v2 for validation and type safety.
Queue-transmitted models must be pickle-able.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import math
import stat
from pathlib import Path

from pydantic import BaseModel, Field, computed_field

from mutmut_win.atomic_file import ensure_atomic_bytes
from mutmut_win.constants import SOURCE_METADATA_SCHEMA


class MutationTask(BaseModel):
    """A single mutation test task to be executed by a worker.

    Sent from the main process to workers via task_queue.
    """

    mutant_name: str = Field(
        description="Unique mutant identifier (e.g. 'src/foo.py::bar__mutmut_1')",
    )
    tests: list[str] = Field(
        default_factory=list,
        description="Authoritative selection or non-authoritative scheduling hints",
    )
    test_selection_is_authoritative: bool = Field(
        default=True,
        description=(
            "Whether tests may narrow pytest collection. False keeps the full suite "
            "and uses observed node IDs only for task scheduling and estimates."
        ),
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
    fatal: bool = Field(
        default=False,
        description=(
            "Whether this completion represents a process-containment or frozen-input "
            "boundary failure that must abort the whole run rather than count as an "
            "ordinary suspicious mutant verdict"
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
            "(context digest + sorted node IDs + per-test-file SHA-256) — the result-reuse "
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
    # Legacy stat fields remain readable for compatibility but never authorize
    # reuse. ``source_hash`` below is the generation/apply authority.
    source_mtime: float | None = None
    source_size: int | None = None
    # SHA-256 of the exact source bytes used for generation. The legacy stat
    # fields stay readable, but never authorize reuse or apply by themselves.
    source_hash: str | None = None
    # Per-file mutation selector (profile, name exclusions, covered lines).
    # This makes the helper safe even when called outside the orchestrator.
    generation_fingerprint: str | None = None
    # SHA-256 of the exact generated Python bytes published into staging.
    # Missing legacy values deliberately disable generation fast-path reuse.
    generated_hash: str | None = None

    @property
    def meta_path(self) -> Path:
        """Path to the JSON meta file for this source file."""
        return Path("mutants") / (self.path + ".meta")

    def load(self, *, heal_corrupt: bool = True) -> None:
        """Load mutation metadata from the JSON meta file.

        Tolerates corruption (issue #101 / A3-CM-009, confirmed via a
        truncated-file experiment): a half-written ``.meta`` used to raise
        an uncaught ``JSONDecodeError`` and block EVERY subsequent run
        until manual deletion. A corrupt file now warns, is removed (so the
        generation fast path rebuilds cleanly), and loading starts empty.
        Value coercion takes the same healing path (issue #124 / 360°-B10):
        structurally valid JSON with type-corrupt values (``"duration":
        null``) used to escape this net as an unhandled ``TypeError``.
        """
        try:
            with self.meta_path.open(encoding="utf-8") as f:
                raw_meta: object = json.load(f)
        except FileNotFoundError:
            return
        except (
            json.JSONDecodeError,
            UnicodeDecodeError,
        ):
            self._reset_loaded_fields()
            if heal_corrupt:
                self._discard_corrupt_meta()
            return

        try:
            if not isinstance(raw_meta, dict):
                raise TypeError("meta root must be an object")
            meta: dict[str, object] = raw_meta
            raw_schema = meta.pop("schema", None)
            if raw_schema not in {None, SOURCE_METADATA_SCHEMA}:
                raise TypeError("unsupported mutation metadata schema")
            raw_exit = meta.pop("exit_code_by_key", {})
            if not isinstance(raw_exit, dict):
                raise TypeError("exit_code_by_key must be an object")
            loaded_exit: dict[str, int | None] = {}
            for key, value in raw_exit.items():
                if not isinstance(key, str) or (
                    value is not None and (not isinstance(value, int) or isinstance(value, bool))
                ):
                    raise TypeError("exit codes must map string keys to integers or null")
                loaded_exit[key] = value
            self.exit_code_by_key = loaded_exit

            raw_dur = meta.pop("durations_by_key", {})
            self.durations_by_key = _validated_nonnegative_float_map(raw_dur, "durations_by_key")

            raw_est = meta.pop("estimated_durations_by_key", {})
            self.estimated_time_of_tests_by_mutant = _validated_nonnegative_float_map(
                raw_est, "estimated_durations_by_key"
            )

            raw_tc = meta.pop("type_check_error_by_key", {})
            if not isinstance(raw_tc, dict) or any(
                not isinstance(k, str) or not isinstance(v, str) for k, v in raw_tc.items()
            ):
                raise TypeError("type_check_error_by_key must map strings to strings")
            self.type_check_error_by_key = dict(raw_tc)

            raw_mtime = meta.pop("source_mtime", None)
            if raw_mtime is not None and (
                not isinstance(raw_mtime, (int, float))
                or isinstance(raw_mtime, bool)
                or not math.isfinite(raw_mtime)
            ):
                raise TypeError("source_mtime must be finite or null")
            self.source_mtime = float(raw_mtime) if raw_mtime is not None else None
            raw_size = meta.pop("source_size", None)
            if raw_size is not None and (
                not isinstance(raw_size, int) or isinstance(raw_size, bool) or raw_size < 0
            ):
                raise TypeError("source_size must be a non-negative integer or null")
            self.source_size = raw_size
            raw_hash = meta.pop("source_hash", None)
            self.source_hash = _validated_optional_sha256(raw_hash, "source_hash")
            raw_generation = meta.pop("generation_fingerprint", None)
            self.generation_fingerprint = _validated_optional_sha256(
                raw_generation, "generation_fingerprint"
            )
            raw_generated_hash = meta.pop("generated_hash", None)
            self.generated_hash = _validated_optional_sha256(raw_generated_hash, "generated_hash")
        except (
            TypeError,
            ValueError,
        ):
            # Type-corrupt values inside structurally valid JSON (issue #124
            # / 360°-B10) heal exactly like decode corruption — partial
            # state is reset so the fast path rebuilds from scratch.
            self._reset_loaded_fields()
            if heal_corrupt:
                self._discard_corrupt_meta()

    def _reset_loaded_fields(self) -> None:
        """Reset every field ``load`` may have partially populated."""
        self.exit_code_by_key = {}
        self.durations_by_key = {}
        self.estimated_time_of_tests_by_mutant = {}
        self.type_check_error_by_key = {}
        self.source_mtime = None
        self.source_size = None
        self.source_hash = None
        self.generation_fingerprint = None
        self.generated_hash = None

    def _discard_corrupt_meta(self) -> None:
        """Warn about and remove a corrupt ``.meta`` so the fast path rebuilds."""
        import contextlib
        import sys

        # stderr: this also runs inside the GENERATION pool children, whose
        # OS fd 1 bypasses any parent redirect (issue #127 / 360°-A6).
        print(
            f"Warning: corrupted meta file {self.meta_path} — rebuilding from scratch.",
            file=sys.stderr,
        )
        with contextlib.suppress(OSError):
            self.meta_path.unlink()

    def save(self) -> None:
        """Save mutation metadata to the JSON meta file (atomically).

        Writes to an exclusively-created random sibling and swaps via
        ``os.replace``.  No predictable sidecar is opened, so a pre-existing
        hardlink or symlink cannot redirect the write outside the workspace.
        """
        self.meta_path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(self._payload(generation_only=False), indent=4).encode("utf-8")
        ensure_atomic_bytes(self.meta_path, payload)

    def save_generation_metadata(self) -> None:
        """Publish deterministic sidecar bytes before executable phases.

        SQLite is the verdict authority.  The richer sidecar may be written
        after a run for the browser, but tests can read files under
        ``mutants/`` directly.  A fast-path run therefore restores this
        generation-only form before collecting or executing any test.
        """

        self.meta_path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(self._payload(generation_only=True), indent=4).encode("utf-8")
        ensure_atomic_bytes(self.meta_path, payload)

    def _payload(self, *, generation_only: bool) -> dict[str, object]:
        exit_codes = (
            dict.fromkeys(self.exit_code_by_key) if generation_only else dict(self.exit_code_by_key)
        )
        return {
            "schema": SOURCE_METADATA_SCHEMA,
            "exit_code_by_key": exit_codes,
            "durations_by_key": {} if generation_only else self.durations_by_key,
            "type_check_error_by_key": {} if generation_only else self.type_check_error_by_key,
            "estimated_durations_by_key": (
                {} if generation_only else self.estimated_time_of_tests_by_mutant
            ),
            "source_mtime": self.source_mtime,
            "source_size": self.source_size,
            "source_hash": self.source_hash,
            "generation_fingerprint": self.generation_fingerprint,
            "generated_hash": self.generated_hash,
        }


def _validated_nonnegative_float_map(raw: object, field_name: str) -> dict[str, float]:
    """Validate a persisted mapping without permissive JSON coercion."""
    if not isinstance(raw, dict):
        raise TypeError(f"{field_name} must be an object")
    validated: dict[str, float] = {}
    for key, value in raw.items():
        if (
            not isinstance(key, str)
            or not isinstance(value, (int, float))
            or isinstance(value, bool)
            or not math.isfinite(value)
            or value < 0
        ):
            raise TypeError(f"{field_name} must map strings to finite non-negative numbers")
        validated[key] = float(value)
    return validated


def _validated_optional_sha256(raw: object, field_name: str) -> str | None:
    """Validate a SHA-256 hex digest while allowing legacy missing values."""
    if raw is None:
        return None
    if (
        not isinstance(raw, str)
        or len(raw) != 64
        or any(char not in "0123456789abcdefABCDEF" for char in raw)
    ):
        raise TypeError(f"{field_name} must be a SHA-256 hex digest or null")
    return raw.lower()


_SOURCE_METADATA_FIELDS: frozenset[str] = frozenset(
    {
        "schema",
        "exit_code_by_key",
        "durations_by_key",
        "type_check_error_by_key",
        "estimated_durations_by_key",
        "source_mtime",
        "source_size",
        "source_hash",
        "generation_fingerprint",
        "generated_hash",
    }
)


def read_owned_source_metadata(meta_path: Path) -> dict[str, object] | None:
    """Read a proven mutmut-win sidecar without healing lookalike fixtures.

    Ownership requires the explicit schema, exact writer field set, valid
    generation hashes and a regular companion generated ``.py`` whose bytes
    match the committed digest.  An arbitrary project fixture named
    ``*.meta`` therefore never enters corruption healing or cache authority.
    """

    if not meta_path.name.casefold().endswith(".py.meta"):
        return None
    try:
        mode = meta_path.lstat().st_mode
        is_link_like = meta_path.is_symlink() or meta_path.is_junction()
        raw: object = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, RuntimeError, json.JSONDecodeError, UnicodeDecodeError):  # fmt: skip
        return None
    if is_link_like or not stat.S_ISREG(mode) or not isinstance(raw, dict):
        return None
    if set(raw) != _SOURCE_METADATA_FIELDS or raw.get("schema") != SOURCE_METADATA_SCHEMA:
        return None
    exit_codes = raw.get("exit_code_by_key")
    if not isinstance(exit_codes, dict) or any(
        not isinstance(name, str)
        or (value is not None and (not isinstance(value, int) or isinstance(value, bool)))
        for name, value in exit_codes.items()
    ):
        return None
    try:
        source_hash = _validated_optional_sha256(raw.get("source_hash"), "source_hash")
        generation_fingerprint = _validated_optional_sha256(
            raw.get("generation_fingerprint"), "generation_fingerprint"
        )
        generated_hash = _validated_optional_sha256(raw.get("generated_hash"), "generated_hash")
    except (TypeError, ValueError):  # fmt: skip
        return None
    if source_hash is None or generation_fingerprint is None or generated_hash is None:
        return None
    companion = meta_path.with_name(meta_path.name[: -len(".meta")])
    try:
        companion_mode = companion.lstat().st_mode
        companion_is_link = companion.is_symlink() or companion.is_junction()
        companion_hash = hashlib.sha256(companion.read_bytes()).hexdigest()
    except (OSError, RuntimeError):  # fmt: skip
        return None
    if companion_is_link or not stat.S_ISREG(companion_mode) or companion_hash != generated_hash:
        return None
    return raw


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
    # New in v2.14.0 (#127, 360°-A7): a collapsed worker pool (all workers
    # dead, tasks never started) used to end exactly like a successful run —
    # exit 0, gate judged over the checked remainder. `run_aborted` marks a
    # run that ended prematurely WITHOUT a user interrupt; the never-checked
    # remainder stays in `unchecked` (sum invariant as for interrupts).
    # Producer: the orchestrator reads the executor's collapse declaration.
    run_aborted: bool = False
    # Authority is separate from technical completion: an incomplete execution
    # basis may still produce useful local diagnostics, but it cannot authorize
    # cache reuse, CI export, or a score gate.
    execution_basis_complete: bool = False
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
