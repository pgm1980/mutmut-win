"""MutationOrchestrator — coordinates the full mutation testing pipeline.

Walks source files, generates mutants, runs the clean-test baseline,
collects timing stats, builds ``MutationTask`` objects with computed
timeouts, and drives a ``SpawnPoolExecutor`` to run all mutation tests
in parallel.  Results are persisted via ``db.save_result`` and
summarised in a ``MutationRunResult``.
"""

from __future__ import annotations

import fnmatch
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
        mutant_names: tuple[str, ...] | None = None,
    ) -> None:
        self._config = config
        self._db_path = db_path
        self._mutant_names: tuple[str, ...] | None = mutant_names

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
        # Step 1a: Filter to specific mutant names if requested (fnmatch supported).
        # ------------------------------------------------------------------
        if self._mutant_names:
            all_tasks = _filter_tasks_by_names(all_tasks, self._mutant_names)
            if not all_tasks:
                print("No mutants match the given names.")
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

        # Sort by estimated_time ascending: run fast mutants first (mirrors mutmut 3.5.0).
        tasks_with_timeouts.sort(key=lambda t: t.estimated_time)

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
                is_completion = _update_summary_and_persist(
                    event, summary, self._db_path, source_data_by_file
                )
                # Only count completed/timed-out mutants, not started events.
                if is_completion:
                    completed += 1
                    _print_live_progress(completed, total, summary)
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
           Uses ``multiprocessing.Pool.imap_unordered`` for parallelism
           (mirrors mutmut 3.5.0 ``create_mutants``).

        Returns:
            A tuple of (flat task list, mapping of file path to SourceFileMutationData).
        """
        import multiprocessing

        from mutmut_win.file_setup import (
            copy_also_copy_files,
            copy_src_dir,
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

        # Build per-file args for the pool worker.
        file_args: list[tuple[str, Path, Path, set[int] | None]] = []
        for rel_path, src_file in source_files:
            output_path = Path("mutants") / src_file
            file_covered: set[int] | None = None
            if covered_lines_map is not None:
                from mutmut_win.code_coverage import get_covered_lines_for_file

                file_covered = get_covered_lines_for_file(rel_path, covered_lines_map)
            file_args.append((rel_path, src_file, output_path, file_covered))

        # Step 5: Generate per-file mutants.
        # Use multiprocessing.Pool for parallel generation (mirrors mutmut 3.5.0) when
        # max_children > 1; fall back to sequential iteration for max_children == 1 to
        # avoid spawn overhead in tests and single-core environments.
        if self._config.max_children > 1:
            with multiprocessing.Pool(processes=self._config.max_children) as pool:
                raw_results: list[tuple[str, list[str], Exception | None, list[str]]] = list(
                    pool.imap_unordered(_create_mutants_worker, file_args)
                )
        else:
            raw_results = [_create_mutants_worker(args) for args in file_args]

        for result in raw_results:
            rel_path_result, mutant_names, error, warn_msgs = result
            for msg in warn_msgs:
                print(f"Warning: {msg}")
            if error is not None:
                print(f"Warning: could not mutate {rel_path_result}: {error}")
                continue
            if not mutant_names:
                continue
            src_file_result = Path(rel_path_result)
            qualified_names = [get_mutant_name(src_file_result, name) for name in mutant_names]
            sfd = SourceFileMutationData(path=rel_path_result)
            sfd.load()
            source_data[rel_path_result] = sfd
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


def _create_mutants_worker(
    args: tuple[str, Path, Path, set[int] | None],
) -> tuple[str, list[str], Exception | None, list[str]]:
    """Top-level picklable worker for parallel mutant generation.

    Called by ``multiprocessing.Pool.imap_unordered`` inside
    ``MutationOrchestrator._generate_mutants``.  The ``rel_path`` is echoed
    back so the parent can correlate results despite unordered delivery.

    Args:
        args: A tuple of ``(rel_path, filename, output_path, covered_lines)``
              where ``rel_path`` is the string path relative to the project root.

    Returns:
        A tuple of ``(rel_path, mutant_names, error, warning_messages)`` where
        ``error`` is ``None`` on success and ``mutant_names`` may be empty.
    """
    from mutmut_win.file_setup import create_mutants_for_file

    rel_path, filename, output_path, covered_lines = args
    try:
        mutant_names, warns = create_mutants_for_file(filename, output_path, covered_lines)
        warn_msgs = [str(w.message) for w in warns]
        return rel_path, mutant_names, None, warn_msgs
    except Exception as exc:  # broad catch: pool workers must not crash the parent
        return rel_path, [], exc, []


def _filter_tasks_by_names(
    tasks: list[MutationTask],
    mutant_names: tuple[str, ...],
) -> list[MutationTask]:
    """Return only tasks whose ``mutant_name`` matches any of *mutant_names*.

    Supports ``fnmatch`` glob patterns (e.g. ``src.foo.*``).  A task is
    included if its name is an exact match **or** matches at least one pattern
    via :func:`fnmatch.fnmatch`.

    Args:
        tasks: Full list of mutation tasks.
        mutant_names: Filter patterns supplied by the caller.

    Returns:
        Filtered list of tasks (may be empty).
    """
    filtered: list[MutationTask] = []
    for task in tasks:
        key = task.mutant_name
        if key in mutant_names or any(fnmatch.fnmatch(key, pattern) for pattern in mutant_names):
            filtered.append(task)
    return filtered


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
    """Run the type checker and mark caught mutants using CST-based line matching.

    Mirrors mutmut 3.5.0's ``filter_mutants_with_type_checker()``: runs the
    type checker inside ``mutants/``, parses errors, then uses
    ``MutatedMethodsCollector`` to determine which *specific* mutant function
    contains the error line.  Only that exact mutant is marked — not the
    entire module.

    Args:
        tasks: All pending mutation tasks.
        source_data_by_file: Updated in-place for caught mutants.
        type_check_command: Command list, e.g. ``["mypy", "--output=json", "."]``.

    Returns:
        ``(remaining_tasks, caught_mutant_names)``
    """
    import os

    import libcst as cst

    from mutmut_win.file_setup import get_mutant_name
    from mutmut_win.type_checker_filter import (
        FailedTypeCheckMutant,
        MutatedMethodsCollector,
        group_by_path,
    )
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

    errors_by_path = group_by_path(errors)
    mutants_to_skip: dict[str, FailedTypeCheckMutant] = {}

    for path, errors_of_file in errors_by_path.items():
        try:
            with (mutants_dir / path).open(encoding="utf-8") as f:
                source = f.read()
        except OSError:
            continue

        wrapper = cst.MetadataWrapper(cst.parse_module(source))
        visitor = MutatedMethodsCollector(path)
        wrapper.visit(visitor)
        mutated_methods = visitor.found_mutants

        for error in errors_of_file:
            mutant = next(
                (
                    m
                    for m in mutated_methods
                    if m.line_number_start <= error.line_number <= m.line_number_end
                ),
                None,
            )
            if mutant is None:
                # Error outside any mutated method — skip (don't crash)
                continue

            try:
                rel_path = path.relative_to(Path().absolute())
            except ValueError:
                rel_path = path
            mutant_name = get_mutant_name(rel_path, mutant.function_name)

            mutants_to_skip[mutant_name] = FailedTypeCheckMutant(
                method_location=mutant,
                name=mutant_name,
                error=error,
            )

    # Remove caught mutants from tasks and update source_data.
    caught = set(mutants_to_skip.keys())
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
) -> bool:
    """Update *summary* counters and persist the result for a finished event.

    Args:
        event: A ``TaskCompleted`` or ``TaskTimedOut`` event (``TaskStarted`` is ignored).
        summary: Mutable summary object to update in-place.
        db_path: Path to the SQLite result cache.
        source_data_by_file: Mapping of file path to ``SourceFileMutationData``.

    Returns:
        ``True`` if the event represents a completed/timed-out mutant
        (i.e. a progress-relevant event), ``False`` for ``TaskStarted``.
    """
    from mutmut_win.models import TaskCompleted, TaskStarted, TaskTimedOut

    if isinstance(event, TaskStarted):
        return False

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
        return False

    # Update summary counters.
    _increment_summary(summary, status)

    # Persist to SQLite.
    save_result(db_path, mutant_name, status, exit_code, duration)

    # Update in-memory SourceFileMutationData.
    _update_source_data(mutant_name, exit_code, duration, source_data_by_file)
    return True


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


def _print_live_progress(completed: int, total: int, summary: MutationRunResult) -> None:
    """Print a single-line emoji progress indicator after each mutant finishes.

    Output format (mirrors mutmut reference)::

        12/65  🎉 8  🫥 1  ⏰ 0  🤔 0  🙁 3  🔇 0  🧙 0

    Args:
        completed: Number of mutants processed so far.
        total: Total number of mutants to process.
        summary: Live ``MutationRunResult`` with current counts.
    """
    line = (
        f"{completed}/{total}"
        f"  \U0001f389 {summary.killed}"
        f"  \U0001fae5 {summary.no_tests}"
        f"  \u23f0 {summary.timeout}"
        f"  \U0001f914 {summary.suspicious}"
        f"  \U0001f641 {summary.survived}"
        f"  \U0001f507 {summary.skipped}"
        f"  \U0001f9d9 {summary.type_check_caught}"
    )
    print(line)


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
