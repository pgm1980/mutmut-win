"""MutationOrchestrator — coordinates the full mutation testing pipeline.

Walks source files, generates mutants, runs the clean-test baseline,
collects timing stats, builds ``MutationTask`` objects with computed
timeouts, and drives a ``SpawnPoolExecutor`` to run all mutation tests
in parallel.  Results are persisted via ``db.save_result`` and
summarised in a ``MutationRunResult``.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING

from mutmut_win.constants import EXIT_CODE_TIMEOUT, status_by_exit_code
from mutmut_win.db import DEFAULT_DB_PATH, create_db, save_result
from mutmut_win.exceptions import CleanTestFailedError, ForcedFailError
from mutmut_win.models import MutationRunResult, MutationTask, SourceFileMutationData

if TYPE_CHECKING:
    from mutmut_win.config import MutmutConfig
    from mutmut_win.models import TaskEvent
    from mutmut_win.process.executor import SpawnPoolExecutor
    from mutmut_win.runner import PytestRunner

#: Minimum timeout in seconds for any single mutation task.
_MIN_TIMEOUT: float = 5.0

#: Default multiplier applied to the estimated time when no stats are available.
_FALLBACK_TIMEOUT: float = 60.0


class MutationOrchestrator:
    """Coordinates the full mutation testing pipeline.

    Steps performed by ``run()``:

    1. Walk source files and generate mutants (via ``mutation.mutate_file_contents``).
    2. Run clean test baseline to ensure the suite passes without mutations.
    3. Collect per-test timing statistics.
    4. Run a forced-fail check to verify the trampoline mechanism.
    5. Build ``MutationTask`` objects with computed wall-clock timeouts.
    6. Start a ``SpawnPoolExecutor`` and stream events.
    7. Map exit codes to statuses, persist results, return summary.

    Args:
        config: Validated ``MutmutConfig`` instance.
        runner: Optional ``PytestRunner`` override (injected for testing).
        executor: Optional ``SpawnPoolExecutor`` override (injected for testing).
        db_path: Path to the SQLite result cache.
    """

    def __init__(
        self,
        config: MutmutConfig,
        *,
        runner: PytestRunner | None = None,
        executor: SpawnPoolExecutor | None = None,
        db_path: Path = DEFAULT_DB_PATH,
    ) -> None:
        self._config = config
        self._db_path = db_path

        # Allow dependency injection for unit testing.
        if runner is not None:
            self._runner: PytestRunner = runner
        else:
            from mutmut_win.runner import PytestRunner as _PytestRunner

            self._runner = _PytestRunner(config)

        self._executor_override: SpawnPoolExecutor | None = executor

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self) -> MutationRunResult:
        """Execute the full mutation testing pipeline.

        Returns:
            ``MutationRunResult`` summarising killed, survived, timed-out and
            other mutant counts together with an overall mutation score.

        Raises:
            CleanTestFailedError: If the clean test run returns a non-zero exit code.
            ForcedFailError: If the forced-fail check does not detect failures.
        """
        wall_start = time.monotonic()

        # ------------------------------------------------------------------
        # Step 1: Generate mutants for all source files.
        # ------------------------------------------------------------------
        all_tasks, source_data_by_file = self._generate_mutants()

        if not all_tasks:
            print("No mutants generated.")
            return MutationRunResult(
                total_mutants=0,
                duration_seconds=time.monotonic() - wall_start,
            )

        # ------------------------------------------------------------------
        # Step 2: Validate the clean test suite.
        # ------------------------------------------------------------------
        print("Running clean test suite…")
        clean_exit = self._runner.run_clean_test()
        if clean_exit != 0:
            msg = f"Clean test run failed with exit code {clean_exit}. Fix tests before mutating."
            raise CleanTestFailedError(msg)

        # ------------------------------------------------------------------
        # Step 3: Collect per-test timing stats.
        # ------------------------------------------------------------------
        print("Collecting test timing statistics…")
        stats = self._runner.run_stats()

        # ------------------------------------------------------------------
        # Step 4: Verify trampoline with a forced-fail run.
        # ------------------------------------------------------------------
        print("Running forced-fail verification…")
        # Pick the first mutant name as the activation token.
        first_mutant = all_tasks[0].mutant_name
        ff_exit = self._runner.run_forced_fail(first_mutant)
        if ff_exit == 0:
            msg = (
                "Forced-fail check passed with exit code 0 — "
                "the trampoline mechanism does not appear to work correctly."
            )
            raise ForcedFailError(msg)

        # ------------------------------------------------------------------
        # Step 5: Compute timeouts and build final task list.
        # ------------------------------------------------------------------
        multiplier = self._config.timeout_multiplier
        tasks_with_timeouts = _apply_timeouts(all_tasks, stats, multiplier)

        # ------------------------------------------------------------------
        # Step 6 + 7: Run mutation tests via the pool executor.
        # ------------------------------------------------------------------
        create_db(self._db_path)
        summary = MutationRunResult(total_mutants=len(tasks_with_timeouts))
        completed = 0
        total = len(tasks_with_timeouts)

        executor = self._get_executor()
        try:
            executor.start(tasks_with_timeouts)
            for event in executor.get_events():
                _update_summary_and_persist(event, summary, self._db_path, source_data_by_file)
                completed += 1
                if completed % max(1, total // 20) == 0 or completed == total:
                    pct = completed / total * 100
                    print(f"Progress: {completed}/{total} ({pct:.0f}%)")
        except KeyboardInterrupt:
            print("\nInterrupted — shutting down workers…")
            executor.shutdown(timeout=5.0)
        else:
            executor.shutdown()

        # ------------------------------------------------------------------
        # Step 8: Persist SourceFileMutationData meta files.
        # ------------------------------------------------------------------
        for sfd in source_data_by_file.values():
            sfd.save()

        summary.duration_seconds = time.monotonic() - wall_start
        _print_summary(summary)
        return summary

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _generate_mutants(
        self,
    ) -> tuple[list[MutationTask], dict[str, SourceFileMutationData]]:
        """Walk source directories and generate mutants for all eligible files.

        When ``config.mutate_only_covered_lines`` is enabled, coverage data is
        collected first and only lines executed by the test suite are mutated.

        Returns:
            A tuple of (flat task list, mapping of file path to SourceFileMutationData).
        """
        from mutmut_win.mutation import mutate_file_contents

        # Collect all eligible source files first (needed for coverage).
        source_files_by_glob: list[tuple[str, Path]] = []
        for path_glob in self._config.paths_to_mutate:
            base = Path(path_glob)
            if base.is_file():
                candidates = [base]
            else:
                candidates = sorted(base.rglob("*.py")) if base.is_dir() else []
            for src_file in candidates:
                rel_path = str(src_file)
                if not self._config.should_ignore_for_mutation(rel_path):
                    source_files_by_glob.append((rel_path, src_file))

        # Optionally gather coverage data to filter mutations.
        covered_lines: dict[str, set[int]] | None = None
        if self._config.mutate_only_covered_lines:
            covered_lines = self._gather_coverage(
                [rel for rel, _ in source_files_by_glob],
            )

        all_tasks: list[MutationTask] = []
        source_data: dict[str, SourceFileMutationData] = {}

        for rel_path, src_file in source_files_by_glob:
            try:
                code = src_file.read_text(encoding="utf-8")

                # Determine per-file covered lines (None = no filter).
                file_covered: set[int] | None = None
                if covered_lines is not None:
                    from mutmut_win.code_coverage import get_covered_lines_for_file

                    file_covered = get_covered_lines_for_file(rel_path, covered_lines)

                _mutated_code, mutant_names = mutate_file_contents(
                    rel_path,
                    code,
                    file_covered,
                )
            except Exception as exc:  # broad catch: log and continue with remaining files
                print(f"Warning: could not mutate {rel_path}: {exc}")
                continue

            if not mutant_names:
                continue

            sfd = SourceFileMutationData(path=rel_path)
            sfd.load()
            source_data[rel_path] = sfd

            all_tasks.extend(
                MutationTask(
                    mutant_name=name,
                    tests=[],
                    estimated_time=0.0,
                    timeout_seconds=_FALLBACK_TIMEOUT,
                )
                for name in mutant_names
            )

        return all_tasks, source_data

    def _gather_coverage(
        self,
        source_files: list[str],
    ) -> dict[str, set[int]]:
        """Run tests with coverage tracking and return covered lines per file.

        Args:
            source_files: Relative paths of source files to track.

        Returns:
            Mapping of absolute file paths to sets of covered line numbers.
        """
        from mutmut_win.code_coverage import gather_coverage

        print("Collecting coverage data (mutate_only_covered_lines is enabled)…")
        return gather_coverage(self._runner, source_files)

    def _get_executor(self) -> SpawnPoolExecutor:
        """Return the executor to use, creating a default one if needed."""
        if self._executor_override is not None:
            return self._executor_override
        from mutmut_win.process.executor import SpawnPoolExecutor as _SpawnPoolExecutor

        return _SpawnPoolExecutor(
            max_workers=self._config.max_children,
            config=self._config,
        )


# ---------------------------------------------------------------------------
# Module-level helpers (pure functions — easy to unit-test independently)
# ---------------------------------------------------------------------------


def _apply_timeouts(
    tasks: list[MutationTask],
    stats: dict[str, float],
    multiplier: float,
) -> list[MutationTask]:
    """Return a copy of *tasks* with ``timeout_seconds`` computed from *stats*.

    The timeout for a task is ``max(_MIN_TIMEOUT, estimated_time * multiplier)``.
    If no timing data is available for a task's tests, ``_FALLBACK_TIMEOUT`` is used.

    Args:
        tasks: Original mutation tasks (not mutated in-place).
        stats: Per-test duration mapping from ``PytestRunner.run_stats()``.
        multiplier: Timeout multiplier from ``MutmutConfig.timeout_multiplier``.

    Returns:
        New list of ``MutationTask`` instances with updated timeout values.
    """
    updated: list[MutationTask] = []
    for task in tasks:
        if task.tests:
            estimated = sum(stats.get(t, 0.0) for t in task.tests)
        elif stats:
            # No test assignment yet — use the mean of all known durations.
            estimated = sum(stats.values()) / len(stats)
        else:
            estimated = 0.0

        timeout = max(_MIN_TIMEOUT, estimated * multiplier) if estimated > 0 else _FALLBACK_TIMEOUT

        updated.append(
            task.model_copy(update={"estimated_time": estimated, "timeout_seconds": timeout})
        )
    return updated


def _update_summary_and_persist(
    event: TaskEvent,
    summary: MutationRunResult,
    db_path: Path,
    source_data_by_file: dict[str, SourceFileMutationData],
) -> None:
    """Update *summary* counters and persist the result for a finished event.

    Args:
        event: A ``TaskCompleted`` or ``TaskTimedOut`` event (``TaskStarted`` is ignored).
        summary: Mutable summary object to update in-place.
        db_path: Path to the SQLite result cache.
        source_data_by_file: Mapping of file path to ``SourceFileMutationData``.
    """
    from mutmut_win.models import TaskCompleted, TaskStarted, TaskTimedOut

    if isinstance(event, TaskStarted):
        return

    if isinstance(event, TaskTimedOut):
        mutant_name = event.mutant_name
        status = status_by_exit_code[EXIT_CODE_TIMEOUT]
        exit_code: int | None = EXIT_CODE_TIMEOUT
        duration: float | None = None
    elif isinstance(event, TaskCompleted):
        mutant_name = event.mutant_name
        exit_code = event.exit_code
        duration = event.duration
        status = status_by_exit_code[exit_code]
    else:
        return

    # Update summary counters.
    _increment_summary(summary, status)

    # Persist to SQLite.
    save_result(db_path, mutant_name, status, exit_code, duration)

    # Update in-memory SourceFileMutationData.
    _update_source_data(mutant_name, exit_code, duration, source_data_by_file)


def _increment_summary(summary: MutationRunResult, status: str) -> None:
    """Increment the appropriate counter on *summary* for *status*.

    Args:
        summary: Mutable ``MutationRunResult`` to update.
        status: Mutation status string from ``constants.status_by_exit_code``.
    """
    match status:
        case "killed" | "caught by type check":
            summary.killed += 1
        case "survived":
            summary.survived += 1
        case "timeout":
            summary.timeout += 1
        case "suspicious":
            summary.suspicious += 1
        case "skipped":
            summary.skipped += 1
        case "no tests":
            summary.no_tests += 1


def _update_source_data(
    mutant_name: str,
    exit_code: int | None,
    duration: float | None,
    source_data_by_file: dict[str, SourceFileMutationData],
) -> None:
    """Write exit code and duration into the matching ``SourceFileMutationData``.

    Args:
        mutant_name: Mutant identifier used to locate the owning source file.
        exit_code: Pytest exit code.
        duration: Test run duration in seconds, or ``None``.
        source_data_by_file: Mapping of file path to ``SourceFileMutationData``.
    """
    # Derive file path from mutant_name: the mutant name format is
    # "<module>.<mangled_name>__mutmut_<n>" where module comes from the
    # source file path.  We match by checking which sfd key the mutant
    # appears to belong to via a prefix comparison.
    for file_path, sfd in source_data_by_file.items():
        # Normalise path separator for comparison.
        norm_path = file_path.replace("\\", "/").replace("/", ".").removesuffix(".py")
        if mutant_name.startswith(norm_path):
            sfd.exit_code_by_key[mutant_name] = exit_code
            if duration is not None:
                sfd.durations_by_key[mutant_name] = duration
            return


def _print_summary(result: MutationRunResult) -> None:
    """Print a human-readable mutation run summary to stdout.

    Args:
        result: Completed ``MutationRunResult`` to display.
    """
    print("\n--- Mutation Testing Summary ---")
    print(f"Total mutants : {result.total_mutants}")
    print(f"Killed        : {result.killed}")
    print(f"Survived      : {result.survived}")
    print(f"Timeout       : {result.timeout}")
    print(f"Suspicious    : {result.suspicious}")
    print(f"Skipped       : {result.skipped}")
    print(f"No tests      : {result.no_tests}")
    print(f"Score         : {result.score:.1f}%")
    print(f"Duration      : {result.duration_seconds:.1f}s")
