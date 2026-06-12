"""MutationOrchestrator — coordinates the full mutation testing pipeline.

Walks source files, generates mutants, runs the clean-test baseline,
collects timing stats, builds ``MutationTask`` objects with computed
timeouts, and drives a ``SpawnPoolExecutor`` to run all mutation tests
in parallel.  Results are persisted via ``db.save_result`` and
summarised in a ``MutationRunResult``.
"""

from __future__ import annotations

import contextlib
import time
from pathlib import Path
from typing import TYPE_CHECKING

from mutmut_win.constants import EXIT_CODE_TIMEOUT, EXIT_CODE_TYPE_CHECK, status_by_exit_code
from mutmut_win.db import DEFAULT_DB_PATH, create_db, save_result
from mutmut_win.exceptions import (
    BadTestExecutionCommandsException,
    CleanTestFailedError,
    ForcedFailError,
)
from mutmut_win.models import (
    MutationResult,
    MutationRunResult,
    MutationTask,
    SourceFileMutationData,
)
from mutmut_win.stats import MutmutStats, collect_or_load_stats
from mutmut_win.test_mapping import match_mutant_names, tests_for_mutant_names

if TYPE_CHECKING:
    from mutmut_win.config import MutmutConfig
    from mutmut_win.models import TaskEvent
    from mutmut_win.process.executor import SpawnPoolExecutor
    from mutmut_win.runner import PytestRunner

#: Minimum timeout in seconds for any single mutation task — also the lower
#: clamp bound of the measured startup floor (issue #105).
_MIN_TIMEOUT: float = 5.0

#: Lower bound of the full-suite fallback budget when no stats are available
#: (the budget scales with the measured clean-run wall time above this) —
#: also the upper clamp bound of the measured startup floor (issue #105).
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
        no_progress: bool = False,
        purge_stale_results: bool = False,
        rerun_all: bool = False,
    ) -> None:
        self._config = config
        self._db_path = db_path
        self._mutant_names: tuple[str, ...] | None = mutant_names
        self._no_progress = no_progress
        # Issue #96 / A3-OS-012: on FULL runs the CLI opts in to purging DB
        # rows of mutants that are no longer generated. Default False — the
        # safe polarity for a destructive operation: subset runs
        # (--mutant-names/--since-commit) know only a slice of the valid set
        # and must never purge.
        self._purge_stale_results = purge_stale_results
        # Issue #119 / external QA RUN-001: --rerun-all disables result
        # reuse — every dispatchable mutant executes even when a cached
        # verdict could be reused.
        self._rerun_all = rerun_all

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
        import sys

        # Force line-buffered stdout so progress output is visible immediately
        # in non-interactive contexts (CI/CD, piped output, editors).
        # Without this, print() output accumulates in a buffer and the user
        # sees no progress for minutes.
        if not sys.stdout.line_buffering:
            sys.stdout.reconfigure(line_buffering=True)  # type: ignore[union-attr]
        _ensure_tolerant_stdout()

        wall_start = time.monotonic()

        # ------------------------------------------------------------------
        # Step 1: Generate mutants for all source files.
        # ------------------------------------------------------------------
        all_tasks, source_data_by_file, fast_path_names = self._generate_mutants()

        if not all_tasks:
            print("No mutants generated.")
            return MutationRunResult(
                total_mutants=0,
                duration_seconds=time.monotonic() - wall_start,
            )

        # The COMPLETE generation set, captured before any filtering — the
        # purge reference for full runs (issue #96): filtered-out mutants
        # still exist as valid mutants and must never be treated as stale.
        all_generated_names = {t.mutant_name for t in all_tasks}

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
        if not all_tasks:
            # Every mutant was caught by the type checker — a legitimate,
            # successful run, not an IndexError (issue #93 / A3-OS-010).
            create_db(self._db_path)
            self._maybe_purge_stale(all_generated_names)
            _persist_type_check_kills(self._db_path, type_checked_names)
            for sfd in source_data_by_file.values():
                sfd.save()
            summary = MutationRunResult(
                total_mutants=len(type_checked_names),
                type_check_caught=len(type_checked_names),
                duration_seconds=time.monotonic() - wall_start,
            )
            print(f"All {len(type_checked_names)} mutants caught by the type checker.")
            _print_summary(summary)
            return summary

        # ------------------------------------------------------------------
        # Step 2: Validate the clean test suite.
        # ------------------------------------------------------------------
        # Explicit staging setup (issue #116 / A2-RN-010): the .pth blocker
        # is written ONCE here instead of as a side effect of every env
        # build; it covers all phases and the workers (same staging dir).
        self._runner.write_pth_blocker()
        print("Running clean test suite…")
        clean_start = time.monotonic()
        clean_exit = self._runner.run_clean_test()
        clean_wall_seconds = time.monotonic() - clean_start
        if clean_exit != 0:
            from mutmut_win.runner import decode_pytest_exit

            if clean_exit == 4:
                # pytest usage error — the docstring of this exception promised
                # a producer since day one (issue #114 / A4-QX-005): bad CLI
                # args always hit the clean run first, BEFORE any mutant runs.
                detail = f"pytest: {decode_pytest_exit(clean_exit)}"
                tail = self._runner.last_diagnostic_output
                if tail:
                    detail += f"\n--- pytest output (tail) ---\n{tail}"
                raise BadTestExecutionCommandsException(
                    list(self._config.pytest_add_cli_args), detail=detail
                )
            if clean_exit == EXIT_CODE_TIMEOUT:
                msg = (
                    f"Clean test run timed out after {self._config.clean_run_timeout}s. "
                    "The trampolined suite in mutants/ runs slower than the native "
                    "suite — raise [tool.mutmut].clean_run_timeout in pyproject.toml."
                )
            else:
                # Issue #99 / A2-RN-001: decode the exit class instead of the
                # blanket "Fix tests" (plain wrong for usage errors or empty
                # collection) and show the captured pytest tail.
                msg = (
                    f"Clean test run failed with exit code {clean_exit} "
                    f"({decode_pytest_exit(clean_exit)})."
                )
            tail = self._runner.last_diagnostic_output
            if tail:
                msg += f"\n--- pytest output (tail) ---\n{tail}"
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
        # Issue #111 / A2-RN-006: the pre-#111 gate accepted ANY non-zero exit
        # — including a timeout translated into "trampoline works" and
        # failures from arbitrarily broken tests.
        if ff_exit == EXIT_CODE_TIMEOUT:
            msg = (
                f"Forced-fail verification timed out after "
                f"{self._config.forced_fail_timeout}s — a hung suite proves "
                "nothing about the trampoline (configure "
                "[tool.mutmut].forced_fail_timeout)."
            )
            raise ForcedFailError(msg)
        if not self._runner.last_forced_fail_attributed:
            msg = (
                f"Tests failed under the forced-fail run (exit {ff_exit}), but no "
                "MutmutProgrammaticFailException appeared in the output — the "
                "failure does not stem from the trampoline and cannot prove "
                "the mutant switch works."
            )
            tail = self._runner.last_diagnostic_output
            if tail:
                msg += f"\n--- pytest output (tail) ---\n{tail}"
            raise ForcedFailError(msg)

        # ------------------------------------------------------------------
        # Step 5: Assign specific tests and compute timeouts.
        # ------------------------------------------------------------------
        all_tasks = _assign_tests_to_tasks(all_tasks, mutmut_stats)

        # Issue #106 / A4-QX-007: a mapped-but-uncovered mutant must never be
        # dispatched — its task would run the FULL suite (no node-id args),
        # burning the suite runtime per mutant and producing random
        # full-suite kills. The honest verdict is "no tests" (exit 33).
        all_tasks, no_test_names = _split_no_test_tasks(all_tasks, mutmut_stats)
        if no_test_names:
            print(
                f"{len(no_test_names)} mutants have no covering tests — "
                f"recorded as 'no tests', not dispatched."
            )

        # ------------------------------------------------------------------
        # Step 5b: Reuse cached verdicts for unchanged mutants (issue #119 /
        # external QA RUN-001 — the README promised this cache for releases;
        # the DB was write-only for `run` until v2.13.0).
        # ------------------------------------------------------------------
        tests_fp_by_name = _build_tests_fingerprints(all_tasks)
        reused_results: list[MutationResult] = []
        if not self._rerun_all and fast_path_names:
            reused_results, all_tasks = _split_reusable_tasks(
                all_tasks, fast_path_names, tests_fp_by_name, self._db_path
            )
        if reused_results:
            print(
                f"Reused {len(reused_results)} cached verdicts from the previous run "
                f"({len(all_tasks)} dispatched; --rerun-all forces execution)."
            )

        if not all_tasks:
            # Everything was verdicted without dispatch (no tests, type-check
            # kills and/or reused cached verdicts) — a legitimate, successful
            # run (cf. #93). Reused rows are already persisted.
            create_db(self._db_path)
            self._maybe_purge_stale(all_generated_names)
            _persist_type_check_kills(self._db_path, type_checked_names)
            _persist_no_test_mutants(self._db_path, no_test_names, source_data_by_file)
            for sfd in source_data_by_file.values():
                sfd.save()
            summary = MutationRunResult(
                total_mutants=(len(no_test_names) + len(type_checked_names) + len(reused_results)),
                type_check_caught=len(type_checked_names),
                no_tests=len(no_test_names),
                duration_seconds=time.monotonic() - wall_start,
            )
            for reused in reused_results:
                _increment_summary(summary, reused.status)
            _print_summary(summary)
            return summary

        multiplier = self._config.timeout_multiplier
        startup_floor = _compute_startup_floor(clean_wall_seconds, mutmut_stats.duration_by_test)
        # Issue #105 / DOG-001: the timeout model must not be a black box —
        # the measured floor decides over timeout-vs-killed for every task.
        total_test_time = sum(mutmut_stats.duration_by_test.values())
        print(
            f"Timeout model: startup floor {startup_floor:.1f}s + test time x {multiplier} "
            f"(clean run {clean_wall_seconds:.1f}s - measured test time {total_test_time:.1f}s)"
        )
        tasks_with_timeouts = _apply_timeouts(
            all_tasks,
            mutmut_stats.duration_by_test,
            multiplier,
            startup_floor=startup_floor,
            clean_wall_seconds=clean_wall_seconds,
        )

        # Sort by estimated_time ascending: run fast mutants first (mirrors mutmut 3.5.0).
        tasks_with_timeouts.sort(key=lambda t: t.estimated_time)

        # Issue #110 / DOG-002: the window-vs-timeout hint (A2-JT-018) is
        # emitted here, ONCE per run — the previous per-worker guard meant
        # N-fold spam on N worker processes. Compared against the SMALLEST
        # budget: the most at-risk task — if the window doesn't cover half
        # of that one, it covers half of none.
        if self._config.infinite_loop_detection and tasks_with_timeouts:
            window = self._config.infinite_loop_window_seconds
            smallest_budget = min(t.timeout_seconds for t in tasks_with_timeouts)
            if window >= smallest_budget / 2:
                print(
                    f"IL-MONITOR HINT: IL window covers >=50% of the smallest task "
                    f"timeout ({window:.0f}s window vs {smallest_budget:.0f}s timeout). "
                    f"First-sample CPU priming may dilute the mean; consider a smaller "
                    f"infinite_loop_window_seconds."
                )

        # ------------------------------------------------------------------
        # Step 6 + 7: Run mutation tests via the pool executor.
        # ------------------------------------------------------------------
        create_db(self._db_path)
        self._maybe_purge_stale(all_generated_names)
        # Type-check kills go to the DB (issue #93 / A3-OS-003: they only
        # ever flowed into the in-memory summary, so `results` and the CICD
        # export diverged from the run gate forever) and into their OWN
        # bucket — the score formula counts the kill class, buckets stay
        # disjoint (#91).
        _persist_type_check_kills(self._db_path, type_checked_names)
        _persist_no_test_mutants(self._db_path, no_test_names, source_data_by_file)
        summary = MutationRunResult(
            total_mutants=(
                len(tasks_with_timeouts)
                + len(type_checked_names)
                + len(no_test_names)
                + len(reused_results)
            ),
            type_check_caught=len(type_checked_names),
            no_tests=len(no_test_names),
        )
        # Reused verdicts count like real completions (sum invariant, #91);
        # their rows are already in the DB and stay untouched.
        for reused in reused_results:
            _increment_summary(summary, reused.status)
        completed = 0
        total = len(tasks_with_timeouts)

        executor = self._get_executor()
        interrupted = False
        try:
            executor.start(tasks_with_timeouts)
            for event in executor.get_events():
                is_completion = _update_summary_and_persist(
                    event, summary, self._db_path, source_data_by_file, tests_fp_by_name
                )
                # Only count completed/timed-out mutants, not started events.
                if is_completion:
                    completed += 1
                    if not self._no_progress:
                        _print_live_progress(completed, total, summary)
        except KeyboardInterrupt:
            interrupted = True
            print("\nInterrupted — shutting down workers…")
        finally:
            # Issue #79 / A2-EW-001: shutdown must run on EVERY exit path —
            # any other exception used to leave workers and the queue feeder
            # alive, hanging the interpreter at exit.
            executor.shutdown(timeout=5.0 if interrupted else 10.0)

        # Issue #94 / A3-OS-005: an aborted run must say so. The unprocessed
        # remainder is excluded from the score denominator (a partial run is
        # scored over what it checked) and keeps the sum invariant.
        summary.was_interrupted = interrupted
        summary.unchecked = max(0, total - completed)

        # ------------------------------------------------------------------
        # Step 8: Persist SourceFileMutationData meta files.
        # ------------------------------------------------------------------
        for sfd in source_data_by_file.values():
            sfd.save()

        summary.duration_seconds = time.monotonic() - wall_start
        # Issue #109 / A4-UI-016: the summary ALWAYS prints — --no-progress
        # suppresses only the live lines. A quiet run that ends without any
        # result output at all was seen live in the Sprint 33 dogfooding
        # mid-gate (exit 0, no numbers).
        _print_summary(summary)
        return summary

    def dry_run(self) -> MutationRunResult:
        """Count mutants without running tests or touching the filesystem.

        Reads source files in-memory and counts how many mutants would be
        generated, without creating the ``mutants/`` directory or any files.
        This prevents the "cache poisoning" problem where a dry-run leaves
        behind a ``mutants/`` directory that blocks the next real run.

        Returns:
            ``MutationRunResult`` with only ``total_mutants`` set.
        """
        from mutmut_win.file_setup import walk_source_files
        from mutmut_win.mutation import mutate_file_contents

        total = 0
        for src_file in walk_source_files(self._config):
            rel_path = str(src_file)
            if self._config.should_ignore_for_mutation(rel_path):
                continue
            try:
                code = src_file.read_text(encoding="utf-8")
                _mutated_code, mutant_names = mutate_file_contents(rel_path, code)
                total += len(mutant_names)
            except Exception:  # noqa: S112 — dry-run must not crash on unparseable files
                continue

        result = MutationRunResult(total_mutants=total)
        print(f"Dry run: {total} mutants would be generated.")
        return result

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _generate_mutants(
        self,
    ) -> tuple[list[MutationTask], dict[str, SourceFileMutationData], set[str]]:
        """Walk source directories and generate mutants for all eligible files.

        Steps:

        1. Copy source files to ``mutants/`` staging directory.
        2. Copy ``also_copy`` files/directories into ``mutants/``.
        3. Fix ``sys.path`` so test processes import the mutated code.
        4. Optionally gather coverage data (``mutate_only_covered_lines``).
        5. For each source file call ``create_mutants_for_file`` to generate
           mutated output and build the ``MutationTask`` list.
        Returns:
            A tuple of (flat task list, mapping of file path to
            SourceFileMutationData, qualified names of all mutants whose file
            took the unchanged-staging fast path — the result-reuse
            candidates of issue #119).
        """
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

        # The generation fast path may only run when the mutant universe is
        # unchanged — a config edit (paths/do_not_mutate/coverage gating)
        # used to leave stale mutants in place (issue #101 / A3-OS-008).
        from mutmut_win.file_setup import config_fingerprint_matches

        allow_fast_path = config_fingerprint_matches(self._config)
        if not allow_fast_path:
            print("Configuration changed — regenerating all mutants.")

        # Build per-file args for the pool worker.
        file_args: list[tuple[str, Path, Path, set[int] | None, bool]] = []
        for rel_path, src_file in source_files:
            output_path = Path("mutants") / src_file
            file_covered: set[int] | None = None
            if covered_lines_map is not None:
                from mutmut_win.code_coverage import get_covered_lines_for_file

                file_covered = get_covered_lines_for_file(rel_path, covered_lines_map)
            file_args.append((rel_path, src_file, output_path, file_covered, allow_fast_path))

        # Step 5: Generate per-file mutants.
        # Use multiprocessing.Pool for parallel generation (mirrors mutmut 3.5.0)
        # when max_children > 1; fall back to sequential for max_children == 1.
        import multiprocessing

        if self._config.max_children > 1:
            with multiprocessing.Pool(processes=self._config.max_children) as pool:
                raw_results: list[tuple[str, list[str], Exception | None, list[str], bool]] = list(
                    pool.imap_unordered(_create_mutants_worker, file_args)
                )
        else:
            raw_results = [_create_mutants_worker(args) for args in file_args]

        # Mutants of files whose staging was reused unchanged — the result-
        # reuse candidates (issue #119): only for these can a prior verdict
        # still describe the current code.
        fast_path_names: set[str] = set()

        for result in raw_results:
            rel_path_result, mutant_names, error, warn_msgs, took_fast_path = result
            for msg in warn_msgs:
                print(f"Warning: {msg}")
            if error is not None:
                print(f"Warning: could not mutate {rel_path_result}: {error}")
                continue
            if not mutant_names:
                continue
            src_file_result = Path(rel_path_result)
            qualified_names = [get_mutant_name(src_file_result, name) for name in mutant_names]
            if took_fast_path:
                fast_path_names.update(qualified_names)
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

        return all_tasks, source_data, fast_path_names

    def _maybe_purge_stale(self, all_generated_names: set[str]) -> None:
        """Purge DB rows of mutants outside the current generation set.

        Only acts when the CLI opted in (full run, issue #96 / A3-OS-012);
        logs the deleted count so the cleanup is visible, never silent.

        Args:
            all_generated_names: The complete, unfiltered generation set.
        """
        if not self._purge_stale_results:
            return
        from mutmut_win.db import delete_results_not_in

        deleted = delete_results_not_in(self._db_path, all_generated_names)
        if deleted:
            print(f"Purged {deleted} stale result rows (mutants no longer generated).")

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
    args: tuple[str, Path, Path, set[int] | None, bool],
) -> tuple[str, list[str], Exception | None, list[str], bool]:
    """Top-level picklable worker for parallel mutant generation.

    Called by ``multiprocessing.Pool.imap_unordered`` inside
    ``MutationOrchestrator._generate_mutants``.  The ``rel_path`` is echoed
    back so the parent can correlate results despite unordered delivery.

    Args:
        args: A tuple of ``(rel_path, filename, output_path, covered_lines,
              allow_fast_path)`` where ``rel_path`` is the string path
              relative to the project root.

    Returns:
        A tuple of ``(rel_path, mutant_names, error, warning_messages,
        took_fast_path)`` where ``error`` is ``None`` on success,
        ``mutant_names`` may be empty, and ``took_fast_path`` marks files
        whose staging was reused unchanged (issue #119 result reuse).
    """
    from mutmut_win.file_setup import create_mutants_for_file

    rel_path, filename, output_path, covered_lines, allow_fast_path = args
    try:
        mutant_names, warns, took_fast_path = create_mutants_for_file(
            filename, output_path, covered_lines, allow_fast_path=allow_fast_path
        )
        warn_msgs = [str(w.message) for w in warns]
        return rel_path, mutant_names, None, warn_msgs, took_fast_path
    except Exception as exc:  # broad catch: pool workers must not crash the parent
        return rel_path, [], exc, [], False


def _filter_tasks_by_names(
    tasks: list[MutationTask],
    mutant_names: tuple[str, ...],
) -> list[MutationTask]:
    """Return only tasks whose ``mutant_name`` matches any of *mutant_names*.

    Delegates to :func:`mutmut_win.test_mapping.match_mutant_names` — the
    one matching rule shared with ``show``/``apply``/``time-estimates``
    (issue #115 / A4-UI-012).

    Args:
        tasks: Full list of mutation tasks.
        mutant_names: Filter patterns supplied by the caller.

    Returns:
        Filtered list of tasks (may be empty).
    """
    matched = set(match_mutant_names(mutant_names, [task.mutant_name for task in tasks]))
    return [task for task in tasks if task.mutant_name in matched]


def _compute_startup_floor(
    clean_wall_seconds: float,
    duration_by_test: dict[str, float],
) -> float:
    """Return the measured per-process startup overhead, clamped to [5s, 60s].

    Issue #105 / DOG-001: every task subprocess pays a constant overhead
    (interpreter start, suite imports, pytest collection) BEFORE the first
    test runs — 16.5s wall for 0.86s of tests in the dogfooding pilot.  The
    clean run over the full suite happens in the same trampolined
    environment as the workers, so ``clean_wall - sum(test durations)`` is a
    self-calibrating, project-specific measurement of that overhead (a
    slightly conservative upper bound: workers collect fewer node IDs).

    The clamp guards degenerate measurements: stale cached durations can
    exceed a fresh, faster clean run (negative difference), and empty stats
    degenerate the difference to the full wall time.  Bounds reuse the two
    existing documented constants — no new magic numbers.

    Trade-off (issue #105 worst-case accounting): a truly hanging mutant now
    lives up to ``floor`` seconds longer before the timeout fires.  IL
    detection verdicts on its own window well before that, and #106 removes
    the unmapped full-suite hang pool entirely — while WITHOUT the floor,
    72% of the pilot's mutants were unassessable pseudo-timeouts.

    Args:
        clean_wall_seconds: Measured wall time of the clean run (step 2).
        duration_by_test: Per-test durations from the stats plugin.

    Returns:
        The startup floor in seconds, within ``[_MIN_TIMEOUT, _FALLBACK_TIMEOUT]``.
    """
    raw = clean_wall_seconds - sum(duration_by_test.values())
    return min(_FALLBACK_TIMEOUT, max(_MIN_TIMEOUT, raw))


def _apply_timeouts(
    tasks: list[MutationTask],
    stats: dict[str, float],
    multiplier: float,
    *,
    startup_floor: float,
    clean_wall_seconds: float,
) -> list[MutationTask]:
    """Return a copy of *tasks* with ``timeout_seconds`` computed from *stats*.

    The budget for a task with timing data is
    ``max(_MIN_TIMEOUT, startup_floor + estimated_time * multiplier)`` —
    the additive floor covers the constant process overhead the multiplier
    cannot scale (issue #105 / DOG-001: 175/244 pilot mutants timed out
    with FINISHED pytest summaries in their tails).

    Without any timing data the task runs the full suite, so its budget is
    ``max(_FALLBACK_TIMEOUT, clean_wall_seconds * multiplier)`` — the
    measured wall time of exactly such a run; a flat 60s would pseudo-
    timeout every suite that takes longer than a minute.

    ``estimated_time`` stays free of the floor: it means "estimated TEST
    runtime" and feeds the fast-first sort.

    Args:
        tasks: Original mutation tasks (not mutated in-place).
        stats: Per-test duration mapping from the stats plugin.
        multiplier: Timeout multiplier from ``MutmutConfig.timeout_multiplier``.
        startup_floor: Measured startup overhead from :func:`_compute_startup_floor`.
        clean_wall_seconds: Measured wall time of the clean run (step 2).

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

        if estimated > 0:
            timeout = max(_MIN_TIMEOUT, startup_floor + estimated * multiplier)
        else:
            timeout = max(_FALLBACK_TIMEOUT, clean_wall_seconds * multiplier)

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
        to_mutants_relative,
    )
    from mutmut_win.type_checking import TypeCheckingError, run_type_checker

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

    # Normalize every checker-reported path to the mutants-relative form
    # BEFORE grouping — mypy reports relative-to-mutants, pyright absolute,
    # and the parsers bind some paths to the mutants cwd. Without this the
    # derived names never matched the task names (issue #93 / A3-CM-002).
    normalized: list[TypeCheckingError] = []
    for error in errors:
        mutants_rel = to_mutants_relative(error.file_path, mutants_dir)
        if mutants_rel is None:
            continue  # error outside mutants/ cannot belong to a mutant
        normalized.append(
            TypeCheckingError(
                file_path=mutants_rel,
                line_number=error.line_number,
                error_description=error.error_description,
            )
        )

    errors_by_path = group_by_path(normalized)
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

            mutant_name = get_mutant_name(path, mutant.function_name)
            mutants_to_skip[mutant_name] = FailedTypeCheckMutant(
                method_location=mutant,
                name=mutant_name,
                error=error,
            )

    # Only mutants that are part of THIS run count as caught — without the
    # intersection, subset runs (--mutant-names/--since-commit) booked
    # foreign mutants into their score (issue #93 / A3-OS-009).
    task_names = {t.mutant_name for t in tasks}
    caught = set(mutants_to_skip.keys()) & task_names
    remaining = [t for t in tasks if t.mutant_name not in caught]
    for mutant_name in caught:
        _update_source_data(
            mutant_name,
            EXIT_CODE_TYPE_CHECK,
            None,
            source_data_by_file,
        )

    return remaining, caught


def _ensure_tolerant_stdout() -> None:
    """Make stdout survive emoji on narrow encodings (issue #103 / A4-QX-003).

    The progress line and the browser print emoji; on a cp1252 console (the
    Windows default for redirected output without ``PYTHONUTF8``) a strict
    stream raised ``UnicodeEncodeError`` and ABORTED the run. Decorative
    output must never kill a mutation run — non-UTF-8 streams degrade to
    ``errors="replace"``; UTF-8 streams are left untouched.
    """
    import sys

    encoding = (getattr(sys.stdout, "encoding", None) or "").lower().replace("-", "")
    if encoding != "utf8":
        with contextlib.suppress(AttributeError, OSError):
            sys.stdout.reconfigure(errors="replace")  # type: ignore[union-attr]


def _persist_type_check_kills(db_path: Path, caught_names: set[str]) -> None:
    """Write one ``caught by type check`` row per caught mutant (issue #93).

    Args:
        db_path: Path to the SQLite result cache (must already exist).
        caught_names: Fully qualified names of the caught mutants.
    """
    for name in sorted(caught_names):
        save_result(db_path, name, "caught by type check", EXIT_CODE_TYPE_CHECK, None)


#: Verdicts a later run may reuse for an unchanged mutant (issue #119 /
#: external QA RUN-001). timeout/suspicious are environment-sensitive,
#: 'no tests' is re-verdicted from the current mapping each run (#106),
#: type-check kills are re-produced by the filter each run, and interrupt
#: placeholders carry no verdict — extending this set must be a conscious
#: decision (the pin test enforces that).
REUSABLE_STATUSES: frozenset[str] = frozenset(
    {"killed", "survived", "segfault", "killed_by_infinite_loop"}
)


def _build_tests_fingerprints(tasks: list[MutationTask]) -> dict[str, str]:
    """Fingerprint every task's test basis (issue #119 result reuse).

    One stat cache per call — the same few test files back thousands of
    tasks, so each file is stat'ed exactly once.

    Args:
        tasks: Tasks after test assignment.

    Returns:
        Mapping of mutant name to fingerprint. Tasks without assigned tests
        (full-suite fallback — no stats) get NO entry: nothing is known
        about their test basis, so they are never reusable.
    """
    stat_cache: dict[str, str] = {}
    return {
        task.mutant_name: _tests_fingerprint(task.tests, stat_cache) for task in tasks if task.tests
    }


def _tests_fingerprint(tests: list[str], stat_cache: dict[str, str] | None = None) -> str:
    """Hash a test basis: sorted node IDs + per-test-file (mtime_ns, size).

    Adding, removing or renaming a covering test changes the node-ID part;
    editing a test BODY changes the file part — both invalidate reuse
    (issue #119: a node-ID-only hash would have kept cached verdicts after
    assertions were strengthened). A missing test file hashes
    deterministically as ``missing`` — still different from any fingerprint
    recorded while the file existed.

    Args:
        tests: pytest node IDs assigned to one mutant.
        stat_cache: Optional shared file-stat cache (filled on demand).

    Returns:
        A 16-hex-digit digest of the test basis.
    """
    import hashlib

    if stat_cache is None:
        stat_cache = {}
    hasher = hashlib.sha256()
    for node_id in sorted(tests):
        hasher.update(node_id.encode("utf-8"))
        hasher.update(b"\n")
        file_part = node_id.split("::", 1)[0]
        if file_part not in stat_cache:
            try:
                stat = Path(file_part).stat()
                stat_cache[file_part] = f"{stat.st_mtime_ns}:{stat.st_size}"
            except OSError:
                stat_cache[file_part] = "missing"
        hasher.update(stat_cache[file_part].encode("utf-8"))
        hasher.update(b"\n")
    return hasher.hexdigest()[:16]


def _split_reusable_tasks(
    tasks: list[MutationTask],
    fast_path_names: set[str],
    tests_fp_by_name: dict[str, str],
    db_path: Path,
) -> tuple[list[MutationResult], list[MutationTask]]:
    """Split *tasks* into reused prior verdicts and tasks to dispatch.

    The issue-#119 condition matrix — a prior verdict is reused iff ALL of:
    the mutant's file took the staging fast path this run (source
    fingerprint unchanged, #101), the task has a test fingerprint
    (assigned tests) matching the one stored with the verdict, and the
    stored status is in :data:`REUSABLE_STATUSES`. Reused rows are NOT
    rewritten — the original verdict, duration and forensics stay.

    Args:
        tasks: Dispatchable tasks after the no-tests split.
        fast_path_names: Qualified names from unchanged-staging files.
        tests_fp_by_name: Current test fingerprints per mutant name.
        db_path: Path to the SQLite result cache.

    Returns:
        ``(reused_rows, remaining_tasks)``
    """
    from mutmut_win.db import load_results

    prior = {row.mutant_name: row for row in load_results(db_path)}
    if not prior:
        return [], tasks

    reused: list[MutationResult] = []
    remaining: list[MutationTask] = []
    for task in tasks:
        row = prior.get(task.mutant_name)
        fingerprint = tests_fp_by_name.get(task.mutant_name)
        if (
            row is not None
            and task.mutant_name in fast_path_names
            and fingerprint is not None
            and row.tests_fingerprint == fingerprint
            and row.status in REUSABLE_STATUSES
        ):
            reused.append(row)
        else:
            remaining.append(task)
    return reused, remaining


def _split_no_test_tasks(
    tasks: list[MutationTask],
    stats: MutmutStats,
) -> tuple[list[MutationTask], set[str]]:
    """Split off mutants whose test mapping is present but empty (issue #106).

    A4-QX-007: a task with ``tests=[]`` was dispatched without node-id
    arguments, so pytest ran the FULL suite for that one mutant — per
    unmapped mutant. The honest verdict for "the mapping knows this suite
    and no test hits this mutant" is ``no tests``, produced here and never
    dispatched.

    The split applies only when a mapping EXISTS: an empty mapping means the
    stats collection failed or recorded nothing (possibly a broken
    hit-recording, QX-017/018) — there the full-suite fallback remains the
    safe choice (loud since #99), because "no tests for everything" would
    misreport a broken stats run as untested code.

    Args:
        tasks: Tasks after :func:`_assign_tests_to_tasks`.
        stats: Stats whose ``tests_by_mangled_function_name`` decides whether
            a mapping exists at all.

    Returns:
        ``(dispatchable_tasks, no_test_mutant_names)``
    """
    if not stats.tests_by_mangled_function_name:
        return tasks, set()
    dispatchable = [t for t in tasks if t.tests]
    no_tests = {t.mutant_name for t in tasks if not t.tests}
    return dispatchable, no_tests


def _persist_no_test_mutants(
    db_path: Path,
    no_test_names: set[str],
    source_data_by_file: dict[str, SourceFileMutationData],
) -> None:
    """Write one ``no tests`` row (exit 33) per uncovered mutant (issue #106).

    Mirrors the #93 pattern for type-check kills: the verdict must reach the
    DB (``results``/CICD read it) and the ``.meta`` files, not only the
    in-memory summary.

    Args:
        db_path: Path to the SQLite result cache (must already exist).
        no_test_names: Mutants the mapping covers with zero tests.
        source_data_by_file: Meta-file records, updated with exit code 33.
    """
    from mutmut_win.constants import EXIT_CODE_NO_TESTS

    for name in sorted(no_test_names):
        save_result(db_path, name, "no tests", EXIT_CODE_NO_TESTS, None)
        _update_source_data(name, EXIT_CODE_NO_TESTS, None, source_data_by_file)


def _update_summary_and_persist(
    event: TaskEvent,
    summary: MutationRunResult,
    db_path: Path,
    source_data_by_file: dict[str, SourceFileMutationData],
    tests_fp_by_name: dict[str, str] | None = None,
) -> bool:
    """Update *summary* counters and persist the result for a finished event.

    Args:
        event: A ``TaskCompleted`` event (``TaskStarted`` is ignored; worker
            timeouts arrive as completions with exit code 36/38).
        summary: Mutable summary object to update in-place.
        db_path: Path to the SQLite result cache.
        source_data_by_file: Mapping of file path to ``SourceFileMutationData``.
        tests_fp_by_name: Test fingerprints per mutant name — stored with the
            verdict as the result-reuse condition of issue #119.

    Returns:
        ``True`` if the event represents a completed mutant (i.e. a
        progress-relevant event), ``False`` for ``TaskStarted``.
    """
    from mutmut_win.models import TaskCompleted, TaskStarted

    if isinstance(event, TaskStarted):
        return False

    last_output: str | None = None
    if isinstance(event, TaskCompleted):
        mutant_name = event.mutant_name
        exit_code: int | None = event.exit_code
        duration: float | None = event.duration
        status = status_by_exit_code[exit_code]
        last_output = event.last_output
        forensics = event.forensics
    else:
        return False

    if mutant_name == "unknown":
        # Worker recovery could not extract a task name (issue #80 /
        # A2-EW-012): keep the finished-accounting intact (the worker DID
        # consume a task) but do not pollute the DB/meta with a ghost
        # "unknown" mutant row — the real mutant stays visibly unchecked.
        print(
            "Warning: a worker failed before its task name was known — "
            "one mutant remains unchecked (no result row written)."
        )
        return True

    # Update summary counters.
    _increment_summary(summary, status)

    # Persist to SQLite — including the IL forensics snapshot, which was
    # silently dropped here before issue #85 / A2-JT-004 (column always NULL).
    save_result(
        db_path,
        mutant_name,
        status,
        exit_code,
        duration,
        last_output,
        forensics,
        tests_fingerprint=(tests_fp_by_name or {}).get(mutant_name),
    )

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
        case "killed" | "caught by type check" | "killed_by_infinite_loop":
            # Issue #71: killed_by_infinite_loop is a true kill (suite never
            # terminates under the mutant — observable behaviour change).
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
        case "segfault":
            summary.segfault += 1
        case _:
            # Issue #91 / A2-EW-004: no status may ever count toward the
            # total without a visible bucket again. Unknown statuses land
            # in suspicious — loudly, not silently.
            summary.suspicious += 1
            print(
                f"Warning: unknown mutant status {status!r} counted as "
                f"suspicious — the status map and the summary buckets have "
                f"drifted apart."
            )


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
    if result.was_interrupted:
        checked = result.total_mutants - result.unchecked
        print(f"INTERRUPTED   : checked {checked} of {result.total_mutants} mutants")
    print(f"Total mutants : {result.total_mutants}")
    print(f"Killed        : {result.killed}")
    if result.type_check_caught:
        print(f"Type-check    : {result.type_check_caught}")
    if result.segfault:
        print(f"Segfault      : {result.segfault}")
    print(f"Survived      : {result.survived}")
    print(f"Timeout       : {result.timeout}")
    print(f"Suspicious    : {result.suspicious}")
    print(f"Skipped       : {result.skipped}")
    print(f"No tests      : {result.no_tests}")
    if result.unchecked:
        print(f"Unchecked     : {result.unchecked}")
    print(f"Score         : {result.score:.1f}%")
    print(f"Duration      : {result.duration_seconds:.1f}s")
