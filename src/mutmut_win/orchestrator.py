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

from mutmut_win.constants import EXIT_CODE_TIMEOUT, EXIT_CODE_TYPE_CHECK, status_by_exit_code
from mutmut_win.db import DEFAULT_DB_PATH, create_db, save_result
from mutmut_win.exceptions import CleanTestFailedError, ForcedFailError
from mutmut_win.models import MutationRunResult, MutationTask, SourceFileMutationData
from mutmut_win.stats import MutmutStats, collect_or_load_stats
from mutmut_win.test_mapping import tests_for_mutant_names

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
        # Step 1b: Apply type-checker filter (if configured).
        # ------------------------------------------------------------------
        type_checked_names: set[str] = set()
        if self._config.type_check_command:
            all_tasks, type_checked_names = _filter_with_type_checker(
                all_tasks,
                source_data_by_file,
                self._config.type_check_command,
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
        # Step 3: Collect per-test timing stats (load from cache if available).
        # ------------------------------------------------------------------
        print("Collecting test timing statistics…")
        mutmut_stats: MutmutStats = collect_or_load_stats(self._runner)

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
        # Step 5: Assign specific tests and compute timeouts.
        # ------------------------------------------------------------------
        all_tasks = _assign_tests_to_tasks(all_tasks, mutmut_stats)
        multiplier = self._config.timeout_multiplier
        tasks_with_timeouts = _apply_timeouts(all_tasks, mutmut_stats.duration_by_test, multiplier)

        # ------------------------------------------------------------------
        # Step 6 + 7: Run mutation tests via the pool executor.
        # ------------------------------------------------------------------
        create_db(self._db_path)
        # Total includes the type-checker-caught mutants (already counted).
        summary = MutationRunResult(
            total_mutants=len(tasks_with_timeouts) + len(type_checked_names),
            killed=len(type_checked_names),
        )
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

        Steps:

        1. Copy source files to ``mutants/`` staging directory.
        2. Copy ``also_copy`` files/directories into ``mutants/``.
        3. Fix ``sys.path`` so test processes import the mutated code.
        4. Optionally gather coverage data (``mutate_only_covered_lines``).
        5. For each source file call ``create_mutants_for_file`` to generate
           mutated output and build the ``MutationTask`` list.

        Returns:
            A tuple of (flat task list, mapping of file path to SourceFileMutationData).
        """
        from mutmut_win.file_setup import (
            copy_also_copy_files,
            copy_src_dir,
            create_mutants_for_file,
            get_mutant_name,
            setup_source_paths,
            walk_source_files,
        )

        # Step 1-3: Prepare the mutants/ directory and sys.path.
        copy_src_dir(self._config)
        copy_also_copy_files(self._config)
        setup_source_paths()

        # Collect all eligible source files (needed before coverage run).
        source_files: list[tuple[str, Path]] = []
        for src_file in walk_source_files(self._config):
            rel_path = str(src_file)
            if not self._config.should_ignore_for_mutation(rel_path):
                source_files.append((rel_path, src_file))

        # Step 4: Optionally gather coverage to restrict which lines are mutated.
        covered_lines_map: dict[str, set[int]] | None = None
        if self._config.mutate_only_covered_lines:
            covered_lines_map = self._gather_coverage(
                [rel for rel, _ in source_files],
            )

        all_tasks: list[MutationTask] = []
        source_data: dict[str, SourceFileMutationData] = {}

        # Step 5: Generate per-file mutants.
        for rel_path, src_file in source_files:
            output_path = Path("mutants") / src_file

            # Determine per-file covered lines (None = no filter).
            file_covered: set[int] | None = None
            if covered_lines_map is not None:
                from mutmut_win.code_coverage import get_covered_lines_for_file

                file_covered = get_covered_lines_for_file(rel_path, covered_lines_map)

            try:
                mutant_names, _warns = create_mutants_for_file(
                    src_file,
                    output_path,
                    file_covered,
                )
            except Exception as exc:  # broad catch: log and continue with remaining files
                print(f"Warning: could not mutate {rel_path}: {exc}")
                continue

            if not mutant_names:
                continue

            # Build fully qualified names via get_mutant_name.
            qualified_names = [get_mutant_name(src_file, name) for name in mutant_names]

            sfd = SourceFileMutationData(path=rel_path)
            sfd.load()
            source_data[rel_path] = sfd

            all_tasks.extend(
                MutationTask(
                    mutant_name=qname,
                    tests=[],
                    estimated_time=0.0,
                    timeout_seconds=_FALLBACK_TIMEOUT,
                )
                for qname in qualified_names
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


def _assign_tests_to_tasks(
    tasks: list[MutationTask],
    stats: MutmutStats,
) -> list[MutationTask]:
    """Return a copy of *tasks* with the ``tests`` field populated from *stats*.

    Uses :func:`~mutmut_win.test_mapping.tests_for_mutant_names` to look up
    which test node IDs exercise each mutant.  Tasks with no matching tests
    keep an empty list.

    Args:
        tasks: Mutation tasks whose ``tests`` fields should be filled.
        stats: Stats data containing ``tests_by_mangled_function_name``.

    Returns:
        New list of ``MutationTask`` instances with ``tests`` populated.
    """
    result: list[MutationTask] = []
    for task in tasks:
        assigned = tests_for_mutant_names(
            [task.mutant_name],
            stats.tests_by_mangled_function_name,
        )
        result.append(task.model_copy(update={"tests": sorted(assigned)}))
    return result


def _filter_with_type_checker(
    tasks: list[MutationTask],
    source_data_by_file: dict[str, SourceFileMutationData],
    type_check_command: list[str],
) -> tuple[list[MutationTask], set[str]]:
    """Run the type checker against the mutants directory and mark caught mutants.

    Runs *type_check_command* inside the ``mutants/`` directory.  Any error
    reported by the type checker is used to derive a mutant name; matching
    tasks are removed from the pending list and recorded with exit code 37
    (``caught by type check``) in *source_data_by_file*.

    The error-to-mutant mapping uses a file-path heuristic: when the type
    checker reports an error in a file under ``mutants/``, all pending tasks
    whose ``mutant_name`` matches the same module path are considered caught.
    This is a conservative approximation — the full CST-based line-number
    matching from the reference implementation requires ``MutatedMethodsCollector``
    which is a future extension.

    Args:
        tasks: All pending mutation tasks.
        source_data_by_file: Mapping of file path to ``SourceFileMutationData``
            updated in-place for caught mutants.
        type_check_command: The type checker command to run (e.g.
            ``["mypy", "--output=json", "."]``).

    Returns:
        A tuple of ``(remaining_tasks, caught_mutant_names)`` where
        ``caught_mutant_names`` is the set of mutant names removed from the
        task list.
    """
    import os

    from mutmut_win.type_checking import run_type_checker

    caught: set[str] = set()

    mutants_dir = Path("mutants")
    if not mutants_dir.exists():
        return tasks, caught

    orig_cwd = Path.cwd()
    try:
        os.chdir(mutants_dir)
        errors = run_type_checker(type_check_command)
    finally:
        os.chdir(orig_cwd)

    if not errors:
        return tasks, caught

    # Collect the set of erroneous file paths (relative to mutants/).
    erroneous_modules: set[str] = set()
    for error in errors:
        error_path = Path(error.file_path)
        try:
            rel = error_path.relative_to(mutants_dir.resolve())
        except ValueError:
            # Try relative to absolute mutants_dir.
            try:
                rel = error_path.relative_to(mutants_dir.absolute())
            except ValueError:
                continue
        # Convert path to dotted module name prefix (without .py suffix).
        module_prefix = str(rel).replace("\\", "/").replace("/", ".").removesuffix(".py")
        erroneous_modules.add(module_prefix)

    # Match each pending task against erroneous module prefixes.
    for task in tasks:
        for module_prefix in erroneous_modules:
            if task.mutant_name.startswith(module_prefix):
                caught.add(task.mutant_name)
                break

    # Remove caught mutants from tasks and update source_data_by_file.
    remaining = [t for t in tasks if t.mutant_name not in caught]
    for mutant_name in caught:
        _update_source_data(
            mutant_name,
            EXIT_CODE_TYPE_CHECK,
            None,
            source_data_by_file,
        )

    return remaining, caught


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
