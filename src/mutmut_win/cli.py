"""Click CLI for mutmut-win.

Entry point for all command-line interaction with mutmut-win.
Provides run, results, show, apply, and browse sub-commands.
"""

from __future__ import annotations

import sys
from pathlib import Path

import click

from mutmut_win import __version__
from mutmut_win.browser import ResultBrowser
from mutmut_win.config import MutmutConfig, load_config
from mutmut_win.db import DEFAULT_DB_PATH, load_results
from mutmut_win.exceptions import MutmutWinError
from mutmut_win.mutant_diff import apply_mutant, render_function_diff, resolve_mutant
from mutmut_win.orchestrator import MutationOrchestrator
from mutmut_win.process.executor import SpawnPoolExecutor
from mutmut_win.runner import PytestRunner
from mutmut_win.stats import load_stats, save_cicd_stats
from mutmut_win.test_mapping import (
    mangled_name_from_mutant_name,
    match_mutant_names,
    tests_for_mutant_names,
)


@click.group()
@click.version_option(version=__version__)
def cli() -> None:
    """mutmut-win — Windows-native mutation testing for Python."""


def _warn_treat_timeout_as_kill_deprecated() -> None:
    """Deprecation notice for the Sprint-23 stopgap flag (issue #117).

    Superseded by true infinite-loop detection (v2.5.0, honest since
    v2.8.0). Decision closed: deprecate now — functional through 2.x —
    remove in a future major release.
    """
    click.echo(
        "Warning: --treat-timeout-as-kill is deprecated — superseded by "
        "infinite-loop detection (since v2.5.0). The flag stays functional "
        "in 2.x and will be removed in a future major release.",
        err=True,
    )


def _load_config_or_exit() -> MutmutConfig:
    """Load the project config; exit 2 with the message on ConfigError.

    Issue #109 / A4-UI-011: a corrupted pyproject.toml surfaced as a RAW
    traceback in ``show``/``apply`` (``run`` got its clean path in #102).
    Config errors follow the #102 convention: exit code 2, message only.
    """
    from mutmut_win.exceptions import ConfigError

    try:
        return load_config()
    except ConfigError as exc:
        click.echo(str(exc), err=True)
        sys.exit(2)


@cli.command()
@click.option("--max-children", type=int, default=None, help="Number of worker processes.")
@click.option(
    "--paths-to-mutate",
    multiple=True,
    type=str,
    help="Source paths to mutate (overrides pyproject.toml). Repeatable.",
)
@click.option(
    "--tests-dir",
    type=str,
    default=None,
    help="Test directory (overrides pyproject.toml).",
)
@click.option(
    "--min-score",
    # FloatRange: 150 used to execute the FULL run before the gate
    # trivially failed; -5 made the gate a no-op (issue #120 / CLI-001).
    type=click.FloatRange(0, 100),
    default=None,
    help="Exit with code 1 if mutation score is below this threshold (0-100).",
)
@click.option(
    "--output",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format.",
)
@click.option(
    "--since-commit",
    type=str,
    default=None,
    help="Only mutate files changed since this git commit (e.g. HEAD~3).",
)
@click.option("--no-progress", is_flag=True, default=False, help="Suppress live progress output.")
@click.option("--debug", is_flag=True, default=False, help="Enable debug output.")
@click.option("--dry-run", is_flag=True, default=False, help="Count mutants without running tests.")
@click.option(
    "--timeout-multiplier",
    type=float,
    default=None,
    help="Timeout multiplier (overrides pyproject.toml).",
)
@click.option(
    "--do-not-mutate",
    multiple=True,
    type=str,
    help="Glob pattern for files to exclude from mutation. Repeatable.",
)
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="Delete mutants/ and .mutmut-cache/ before running (clean slate).",
)
@click.option(
    "--rerun-all",
    is_flag=True,
    default=False,
    help=(
        "Execute every mutant even when a cached verdict could be reused "
        "(unchanged source + unchanged covering tests)."
    ),
)
@click.option(
    "--treat-timeout-as-kill",
    is_flag=True,
    default=False,
    help=(
        "(DEPRECATED — superseded by infinite-loop detection; removal in a "
        "future major release.) Count TIMEOUT mutants toward the kill bucket "
        "for --min-score and score reporting. Workaround for Bug #71 "
        "(Hypothesis tests turn infinite-loop mutations into TIMEOUT)."
    ),
)
@click.option(
    "--extra-paths-to-copy",
    multiple=True,
    type=str,
    help=(
        "Sibling directories to copy into mutants/ and add to the worker's "
        "PYTHONPATH. Use when tests import from packages outside the wheel "
        "(e.g. benchmarks/). Repeatable. Overrides [tool.mutmut].extra_paths."
    ),
)
@click.option(
    "--no-infinite-loop-detection",
    "no_infinite_loop_detection",
    is_flag=True,
    default=False,
    help=(
        "Disable triple-check IL classification (Issue #71). Wall-clock "
        "timeouts will be bucketed as plain TIMEOUT regardless of CPU / "
        "output / process status. Off by default — IL detection is on."
    ),
)
@click.option(
    "--infinite-loop-cpu-threshold",
    type=float,
    default=None,
    help=(
        "Override the mean-CPU%% threshold (0 - 10000) above which a timed-out "
        "mutant is reclassified as killed_by_infinite_loop. pyproject default "
        "is 70.0."
    ),
)
@click.argument("mutant_names", nargs=-1)
def run(
    max_children: int | None,
    paths_to_mutate: tuple[str, ...],
    tests_dir: str | None,
    min_score: float | None,
    output: str,
    since_commit: str | None,
    no_progress: bool,
    debug: bool,
    dry_run: bool,
    timeout_multiplier: float | None,
    do_not_mutate: tuple[str, ...],
    force: bool,
    rerun_all: bool,
    treat_timeout_as_kill: bool,
    extra_paths_to_copy: tuple[str, ...],
    no_infinite_loop_detection: bool,
    infinite_loop_cpu_threshold: float | None,
    mutant_names: tuple[str, ...],
) -> None:
    """Run mutation testing.

    Optionally filter to specific MUTANT_NAMES. When omitted, all mutants are tested.
    """
    import contextlib

    if treat_timeout_as_kill:
        _warn_treat_timeout_as_kill_deprecated()

    # Issue #103 / A4-UI-006 + issue #127 / 360°-A6: with --output json the
    # stdout stream must carry EXACTLY the JSON. The redirect therefore
    # starts BEFORE the --force echo and the config load — both used to
    # print prose to stdout ahead of the old, run()-only redirect scope.
    # (Child-process diagnostics are born on stderr instead: the workers'
    # OS-level fd 1 is beyond any parent redirect.)
    with contextlib.ExitStack() as prose_stack:
        if output == "json":
            prose_stack.enter_context(contextlib.redirect_stdout(sys.stderr))

        # --force: clean slate — delete mutants/ and .mutmut-cache/ before running
        if force:
            import shutil

            for dirname in ("mutants", ".mutmut-cache"):
                p = Path(dirname)
                if p.exists():
                    shutil.rmtree(p, ignore_errors=True)
                    # Issue #101 / A3-FD-009: rmtree(ignore_errors=True) plus an
                    # unconditional success message sold a PARTIAL deletion
                    # (files locked by another process) as a clean slate.
                    if p.exists():
                        click.echo(
                            f"Warning: could not fully remove {dirname}/ "
                            f"(files in use?) — the run may see stale state.",
                            err=True,
                        )
                    else:
                        click.echo(f"Removed {dirname}/")

        # Issue #120 / CFG-001 (external QA): a broken [tool.mutmut] used to
        # escape as a 47-line traceback with exit 1 while CLI flags with the
        # SAME rules exited 2 — one config-error contract for every command.
        config = _load_config_or_exit()

        # --- Apply CLI overrides to config ---
        overrides: dict[str, object] = {}
        if max_children is not None:
            overrides["max_children"] = max_children
        if paths_to_mutate:
            overrides["paths_to_mutate"] = list(paths_to_mutate)
        if tests_dir is not None:
            overrides["tests_dir"] = [tests_dir]
        if timeout_multiplier is not None:
            overrides["timeout_multiplier"] = timeout_multiplier
        if debug:
            overrides["debug"] = True
        if do_not_mutate:
            overrides["do_not_mutate"] = list(config.do_not_mutate) + list(do_not_mutate)
        if extra_paths_to_copy:
            overrides["extra_paths"] = list(extra_paths_to_copy)
        if no_infinite_loop_detection:
            overrides["infinite_loop_detection"] = False
        if infinite_loop_cpu_threshold is not None:
            overrides["infinite_loop_cpu_threshold"] = infinite_loop_cpu_threshold

        # --since-commit: resolve changed .py files via git
        if since_commit is not None:
            import subprocess as sp

            # git command is fully controlled — commit hash is validated by git itself
            git_result = sp.run(  # noqa: S603 — git CLI with controlled args
                ["git", "diff", "--name-only", f"{since_commit}..HEAD"],  # noqa: S607 — git is a well-known executable
                capture_output=True,
                encoding="utf-8",
            )
            # Issue #102 / A3-CM-006: the returncode was never checked — an
            # invalid ref meant "nothing changed" + exit 0, a FALSE CI success.
            if git_result.returncode != 0:
                click.echo(
                    f"git diff failed (exit {git_result.returncode}): {git_result.stderr.strip()}",
                    err=True,
                )
                sys.exit(2)
            tests_dirs = tuple(d.strip("/").strip("\\") for d in config.tests_dir)

            def _is_mutation_target(name: str) -> bool:
                # Deleted files and test files used to become mutation targets.
                if not name.endswith(".py") or not Path(name).exists():
                    return False
                parts = Path(name).parts
                return all(parts[0] != td for td in tests_dirs)

            changed_py = [
                f for f in git_result.stdout.strip().split("\n") if f and _is_mutation_target(f)
            ]
            if not changed_py:
                click.echo("No .py files changed since the given commit.", err=True)
                sys.exit(0)
            overrides["paths_to_mutate"] = changed_py

        if overrides:
            # Issue #102 / A3-CM-004: model_copy(update=...) bypasses ALL pydantic
            # constraints — '--max-children 0' was an accepted hang. Re-validate
            # the merged config so the field constraints apply to CLI input too.
            from pydantic import ValidationError

            try:
                config = MutmutConfig.model_validate({**config.model_dump(), **overrides})
            except ValidationError as exc:
                click.echo(f"Invalid option value:\n{exc}", err=True)
                sys.exit(2)

        # Issue #120 / CLI-002 (external QA): a typo'd mutation root used to
        # yield "No mutants generated." with exit 0 — a false CI success. A
        # missing path is a configuration error per the documented contract.
        missing_paths = [p for p in config.paths_to_mutate if not Path(p).exists()]
        if missing_paths:
            plural = "ies do" if len(missing_paths) > 1 else "y does"
            click.echo(
                f"paths_to_mutate entr{plural} not exist: {', '.join(missing_paths)}",
                err=True,
            )
            sys.exit(2)

        runner = PytestRunner(config)
        executor = SpawnPoolExecutor(max_workers=config.max_children, config=config)
        # Only a FULL run may purge stale DB rows (issue #96): subset runs know
        # just a slice of the valid mutant set and must never delete history.
        # A --paths-to-mutate override narrows the staging to that slice, so it
        # counts as a subset run too (issue #120 / RUN-002 — the purge used to
        # delete every result outside the given paths).
        is_full_run = not mutant_names and since_commit is None and not paths_to_mutate
        orchestrator = MutationOrchestrator(
            config,
            runner=runner,
            executor=executor,
            mutant_names=mutant_names if mutant_names else None,
            no_progress=no_progress,
            purge_stale_results=is_full_run,
            rerun_all=rerun_all,
        )

        try:
            result = orchestrator.dry_run() if dry_run else orchestrator.run()
        except MutmutWinError as exc:
            # Issue #102 / A4-UI-005: --debug was a dead flag while this except
            # swallowed tracebacks exactly where debug should help.
            # Issue #114 / A4-QX-006: only DOMAIN errors get the one-line
            # rendering — a foreign exception is a mutmut-win bug and propagates
            # with its full traceback instead of masquerading as a clean error.
            if debug or config.debug:
                import traceback

                click.echo(traceback.format_exc(), err=True)
            click.echo(f"Error: {exc}", err=True)
            sys.exit(1)

    # --- Output ---
    if output == "json":
        click.echo(result.model_dump_json(indent=2))

    # --- Interrupt honesty (issue #94 / A3-OS-005) ---
    if result.was_interrupted:
        # A partial score is misleading in both directions — the gate is
        # skipped, and CI can detect the abort via the conventional SIGINT
        # exit code.
        if min_score is not None:
            click.echo("Run was interrupted — score gate skipped.", err=True)
        click.echo(
            f"Run interrupted: checked "
            f"{result.total_mutants - result.unchecked} of {result.total_mutants} mutants.",
            err=True,
        )
        sys.exit(130)

    # --- Pool-collapse honesty (issue #127 / 360°-A7) ---
    if result.run_aborted:
        # The collapse is the failure — fail closed regardless of any gate.
        # Exit 1 (runtime failure), NOT 130: that code is reserved for user
        # interrupts and CI tells the two apart exactly there.
        if min_score is not None:
            click.echo("Run was aborted — score gate skipped.", err=True)
        click.echo(
            f"Run aborted: worker pool collapsed — checked "
            f"{result.total_mutants - result.unchecked} of {result.total_mutants} mutants.",
            err=True,
        )
        sys.exit(1)

    # --- Score gate ---
    if min_score is not None:
        testable = result.total_mutants - result.skipped - result.no_tests - result.unchecked
        if testable <= 0:
            # Issue #97 / A3-OS-026: fail-closed is right, but 'score 0.0%
            # below threshold' blamed a score that never existed.
            click.echo(
                "No testable mutants — score gate failed closed "
                "(nothing was measured, so nothing can pass).",
                err=True,
            )
            sys.exit(1)
        gate_score = result.compute_score(treat_timeout_as_kill=treat_timeout_as_kill)
        if gate_score < min_score:
            qualifier = " (timeouts counted as kills)" if treat_timeout_as_kill else ""
            click.echo(
                f"Mutation score {gate_score:.1f}%{qualifier} is below threshold {min_score}%",
                err=True,
            )
            sys.exit(1)


@cli.command()
@click.option("--all", "show_all", is_flag=True, default=False, help="Include killed mutants.")
@click.option(
    "--treat-timeout-as-kill",
    is_flag=True,
    default=False,
    help=(
        "(DEPRECATED — superseded by infinite-loop detection; removal in a "
        "future major release.) Count TIMEOUT mutants toward the kill bucket "
        "in the displayed score. Workaround for Bug #71 (Hypothesis tests "
        "turn infinite-loop mutations into TIMEOUT)."
    ),
)
def results(show_all: bool, treat_timeout_as_kill: bool) -> None:
    """Print a summary of mutation testing results from the cache database.

    Empty-DB convention (issue #109 / A4-UI-013): informational queries
    (``results``, ``time-estimates``) exit 0 with an explicit notice; only
    the CI gate (``export-cicd-stats``) fails on an empty result set.
    """
    if treat_timeout_as_kill:
        _warn_treat_timeout_as_kill_deprecated()

    all_results = load_results(DEFAULT_DB_PATH)

    if not all_results:
        click.echo("No results found. Run 'mutmut-win run' first.")
        return

    counts: dict[str, int] = {}
    for result in all_results:
        counts[result.status] = counts.get(result.status, 0) + 1

    total = len(all_results)
    # Issue #122 / external QA SCO-003: `results` used to fold type-check
    # kills into "Killed" with no line of their own, while the run summary
    # and the CI JSON keep the category separate — one scheme everywhere.
    type_check = counts.get("caught by type check", 0)
    kill_aggregate = (
        counts.get("killed", 0)
        + counts.get("killed_by_infinite_loop", 0)  # Issue #71 — IL classification
    )
    il_killed = counts.get("killed_by_infinite_loop", 0)
    segfault = counts.get("segfault", 0)
    timeout = counts.get("timeout", 0)
    skipped = counts.get("skipped", 0)
    no_tests = counts.get("no tests", 0)

    denominator = total - skipped - no_tests
    # Kill class mirrors MutationRunResult.score / CicdStats.score (#91):
    # a crash under a mutant is a detection.
    effective_killed = (
        kill_aggregate + type_check + segfault + (timeout if treat_timeout_as_kill else 0)
    )
    score = (effective_killed / denominator * 100.0) if denominator > 0 else 0.0

    click.echo(f"Total:      {total}")
    if il_killed > 0:
        click.echo(f"Killed:     {kill_aggregate}  (incl. {il_killed} infinite-loop)")
    else:
        click.echo(f"Killed:     {kill_aggregate}")
    if type_check > 0:
        click.echo(f"Type-check:  {type_check}")
    # Render EVERY status that occurs (issue #91 / A4-UI-009: segfault,
    # interrupted and not-checked rows used to count in Total and the score
    # denominator while appearing in no output line). The fixed list keeps
    # the established order and zero-lines; legacy/unknown statuses from
    # older DBs follow generically when present.
    aggregated = {"killed", "caught by type check", "killed_by_infinite_loop"}
    preferred_order = ["survived", "timeout", "suspicious", "skipped", "no tests", "segfault"]
    always_shown = {"survived", "timeout", "suspicious", "skipped", "no tests"}
    remaining = sorted(s for s in counts if s not in aggregated and s not in preferred_order)
    for status in [*preferred_order, *remaining]:
        count = counts.get(status, 0)
        if count == 0 and status not in always_shown:
            continue
        # Width 12: the longest standard label ("Suspicious:", 11 chars)
        # keeps at least one space before its value (issue #115 /
        # A4-UI-015 — it used to print "Suspicious:1"); legacy labels
        # wider than the field get a single separating space.
        label = status.capitalize() + ":"
        line = f"{label:<12}{count}" if len(label) < 12 else f"{label} {count}"
        click.echo(line)
    if treat_timeout_as_kill and timeout > 0:
        click.echo(f"Score:      {score:.1f}% (Bug #71: {timeout} timeouts counted as kills)")
    else:
        click.echo(f"Score:      {score:.1f}%")

    if show_all:
        click.echo("")
        for result in sorted(all_results, key=lambda r: r.mutant_name):
            click.echo(f"  {result.mutant_name}: {result.status}")
    else:
        surviving = [r for r in all_results if r.status == "survived"]
        if surviving:
            click.echo("\nSurviving mutants:")
            for result in sorted(surviving, key=lambda r: r.mutant_name):
                click.echo(f"  {result.mutant_name}")


def _format_forensics_panel(status: str | None, forensics: dict[str, object] | None) -> str | None:
    """Render the IL forensics panel for ``show``, or None for non-IL mutants.

    NULL-safe in two ways: rows written before v2.8.0 have no forensics at
    all (column is NULL), and a recorded dict may lack individual keys.

    Args:
        status: The mutant's persisted status, or ``None`` if unknown.
        forensics: The persisted forensics snapshot, or ``None``.

    Returns:
        The panel text, or ``None`` if *status* is not an IL kill.
    """
    if status != "killed_by_infinite_loop":
        return None
    confidence = forensics.get("confidence", "unknown") if forensics else "unknown"
    lines = ["", f"Infinite-loop verdict — confidence: {confidence}"]
    if forensics is None:
        lines.append("  No forensics recorded (run predates v2.8.0).")
        return "\n".join(lines)
    lines.extend(
        [
            f"  CPU:           {forensics.get('cpu_pct_mean', '?')} % mean / "
            f"{forensics.get('cpu_pct_max', '?')} % max",
            f"  Output growth: {forensics.get('output_growth_bytes', '?')} bytes "
            f"over {forensics.get('window_seconds', '?')} s window",
            f"  Running ratio: {_format_ratio(forensics.get('running_ratio'))} "
            f"({forensics.get('samples_collected', '?')} samples)",
        ]
    )
    tail = forensics.get("last_output_tail")
    if tail:
        lines.append("  Last output tail:")
        lines.extend(f"    {tail_line}" for tail_line in str(tail).splitlines())
    return "\n".join(lines)


def _format_ratio(value: object) -> str:
    """Format a running ratio as e.g. ``1.00``, or ``?`` if absent/non-numeric."""
    if isinstance(value, int | float):
        return f"{value:.2f}"
    return "?"


@cli.command()
@click.argument("mutant_name")
def show(mutant_name: str) -> None:
    """Show the diff for a specific mutant MUTANT_NAME.

    MUTANT_NAME is an exact mutant name or a glob pattern (*, ?, [...])
    that matches exactly ONE mutant — the same matching rule as `run`;
    an ambiguous pattern fails and lists the candidates.
    """
    mutants_dir = Path("mutants")
    if not mutants_dir.is_dir():
        click.echo("No mutants directory found. Run 'mutmut-win run' first.", err=True)
        sys.exit(1)

    config = _load_config_or_exit()
    try:
        # Resolve the pattern ONCE (issue #127 / 360°-A9): header, diff AND
        # the forensics DB lookup below all use the resolved name — the old
        # flow resolved inside the diff helper only, so a glob rendered the
        # diff but silently lost the forensics panel.
        resolved_name, data = resolve_mutant(mutant_name, config)
        diff = render_function_diff(data.path, resolved_name)
    except (FileNotFoundError, MutmutWinError) as exc:
        click.echo(str(exc), err=True)
        sys.exit(1)

    if diff:
        click.echo(f"# {resolved_name}")
        click.echo(diff)
    else:
        click.echo(f"No diff found for '{resolved_name}'.")

    if DEFAULT_DB_PATH.exists():
        row = next(
            (r for r in load_results(DEFAULT_DB_PATH) if r.mutant_name == resolved_name), None
        )
        if row is not None:
            panel = _format_forensics_panel(row.status, row.forensics)
            if panel is not None:
                click.echo(panel)


@cli.command()
@click.argument("mutant_name")
def apply(mutant_name: str) -> None:
    """Apply mutant MUTANT_NAME to the source file on disk.

    MUTANT_NAME is an exact mutant name or a glob pattern that matches
    exactly ONE mutant; an ambiguous pattern fails and lists the
    candidates — apply never applies a set.
    """
    mutants_dir = Path("mutants")
    if not mutants_dir.is_dir():
        click.echo("No mutants directory found. Run 'mutmut-win run' first.", err=True)
        sys.exit(1)

    config = _load_config_or_exit()
    try:
        apply_mutant(mutant_name, config)
    except (FileNotFoundError, MutmutWinError) as exc:
        click.echo(str(exc), err=True)
        sys.exit(1)

    click.echo(f"Applied mutant '{mutant_name}'.")


@cli.command()
@click.option(
    "--show-killed",
    is_flag=True,
    default=False,
    help="Display mutants killed by tests and type checker.",
)
def browse(show_killed: bool) -> None:
    """Launch TUI result browser."""
    app = ResultBrowser(show_killed=show_killed)
    app.run()


@cli.command("tests-for-mutant")
@click.argument("name")
def tests_for_mutant_cmd(name: str) -> None:
    """Show the tests mapped to mutant NAME.

    Loads the stats cache and prints each test node ID that covers the
    mutated function.  Exits with code 1 if no stats are available.
    """
    mutants_dir = Path("mutants")
    stats = load_stats(mutants_dir)
    if stats is None:
        click.echo(
            "No stats found. Run 'mutmut-win run' first to collect stats.",
            err=True,
        )
        sys.exit(1)

    mapped_tests = tests_for_mutant_names([name], stats.tests_by_mangled_function_name)
    if not mapped_tests:
        click.echo(f"No tests found for mutant '{name}'.")
        return

    for test in sorted(mapped_tests):
        click.echo(test)


@cli.command("time-estimates")
@click.argument("mutant_names", nargs=-1)
def time_estimates_cmd(mutant_names: tuple[str, ...]) -> None:
    """Show estimated run times for mutants.

    When MUTANT_NAMES are given (exact names or glob patterns — the same
    matching rule as `run`), only those mutants are shown; otherwise all
    mutants recorded in the results cache are listed.  Estimates are derived
    from the stats-collected per-test durations.

    Exits with code 1 if no stats are available.  An empty results DB is
    informational — notice plus exit 0 (issue #109 / A4-UI-013 convention).
    """
    mutants_dir = Path("mutants")
    stats = load_stats(mutants_dir)
    if stats is None:
        click.echo(
            "No stats found. Run 'mutmut-win run' first to collect stats.",
            err=True,
        )
        sys.exit(1)

    all_results = load_results(DEFAULT_DB_PATH)
    if not all_results:
        click.echo("No results found. Run 'mutmut-win run' first.")
        return

    # Filter to requested mutant names (if any) — same exact+glob rule as
    # `run` and `show`/`apply` (issue #115 / A4-UI-012).
    if mutant_names:
        matched = set(match_mutant_names(mutant_names, [r.mutant_name for r in all_results]))
        filtered = [r for r in all_results if r.mutant_name in matched]
        if not filtered:
            click.echo(f"No results found for the given mutant names: {list(mutant_names)}")
            return
        target_results = filtered
    else:
        target_results = all_results

    times_and_names: list[tuple[float, str]] = []
    for result in target_results:
        try:
            mangled = mangled_name_from_mutant_name(result.mutant_name)
        except AssertionError:
            times_and_names.append((0.0, result.mutant_name))
            continue
        test_ids = stats.tests_by_mangled_function_name.get(mangled, set())
        estimated = sum(stats.duration_by_test.get(t, 0.0) for t in test_ids)
        times_and_names.append((estimated, result.mutant_name))

    for estimated, mutant_name in sorted(times_and_names):
        if estimated == 0.0:
            click.echo(f"<no tests>  {mutant_name}")
        else:
            click.echo(f"{int(estimated * 1000)}ms  {mutant_name}")


@cli.command("export-cicd-stats")
def export_cicd_stats_cmd() -> None:
    """Export aggregated mutation stats to mutants/mutmut-cicd-stats.json.

    The output JSON is intended for use in CI/CD pipelines to gate pull
    requests based on mutation score.  Exits with code 1 if no previous
    mutation data is found — deliberately stricter than the informational
    queries (issue #109 / A4-UI-013): an empty result set in a gate context
    means the pipeline ran nothing, and silence would read as green.
    """
    all_results = load_results(DEFAULT_DB_PATH)
    if not all_results:
        click.echo("No results found. Run 'mutmut-win run' first.", err=True)
        sys.exit(1)

    pairs: list[tuple[str, str | None]] = [(r.mutant_name, r.status) for r in all_results]
    mutants_dir = Path("mutants")
    cicd = save_cicd_stats(pairs, mutants_dir)
    click.echo(f"Saved CI/CD stats to {mutants_dir / 'mutmut-cicd-stats.json'}")
    # Issue #122 / external QA SCO-001: "(40 killed / 78 total)" next to a
    # 71.4% score invited verifying it with the WRONG denominator — the
    # parenthetical now shows the kill class over the scoreable set.
    click.echo(
        f"Score: {cicd.score:.1f}%  ({cicd.effective_killed} killed / {cicd.scoreable} scoreable)"
    )
