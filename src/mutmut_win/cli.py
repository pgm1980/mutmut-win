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
from mutmut_win.config import load_config
from mutmut_win.db import DEFAULT_DB_PATH, load_results
from mutmut_win.mutant_diff import apply_mutant, get_diff_for_mutant
from mutmut_win.orchestrator import MutationOrchestrator
from mutmut_win.process.executor import SpawnPoolExecutor
from mutmut_win.runner import PytestRunner
from mutmut_win.stats import load_stats, save_cicd_stats
from mutmut_win.test_mapping import mangled_name_from_mutant_name, tests_for_mutant_names


@click.group()
@click.version_option(version=__version__)
def cli() -> None:
    """mutmut-win — Windows-native mutation testing for Python."""


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
    type=float,
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
    mutant_names: tuple[str, ...],
) -> None:
    """Run mutation testing.

    Optionally filter to specific MUTANT_NAMES. When omitted, all mutants are tested.
    """
    config = load_config()

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

    # --since-commit: resolve changed .py files via git
    if since_commit is not None:
        import subprocess as sp

        # git command is fully controlled — commit hash is validated by git itself
        git_result = sp.run(  # noqa: S603 — git CLI with controlled args
            ["git", "diff", "--name-only", f"{since_commit}..HEAD"],  # noqa: S607 — git is a well-known executable
            capture_output=True,
            encoding="utf-8",
        )
        changed_py = [f for f in git_result.stdout.strip().split("\n") if f.endswith(".py") and f]
        if not changed_py:
            click.echo("No .py files changed since the given commit.", err=True)
            sys.exit(0)
        overrides["paths_to_mutate"] = changed_py

    if overrides:
        config = config.model_copy(update=overrides)

    runner = PytestRunner(config)
    executor = SpawnPoolExecutor(max_workers=config.max_children, config=config)
    orchestrator = MutationOrchestrator(
        config,
        runner=runner,
        executor=executor,
        mutant_names=mutant_names if mutant_names else None,
        no_progress=no_progress,
    )

    try:
        result = orchestrator.dry_run() if dry_run else orchestrator.run()
    except Exception as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    # --- Output ---
    if output == "json":
        click.echo(result.model_dump_json(indent=2))

    # --- Score gate ---
    if min_score is not None and result.score < min_score:
        click.echo(
            f"Mutation score {result.score:.1f}% is below threshold {min_score}%",
            err=True,
        )
        sys.exit(1)


@cli.command()
@click.option("--all", "show_all", is_flag=True, default=False, help="Include killed mutants.")
def results(show_all: bool) -> None:
    """Print a summary of mutation testing results from the cache database."""
    all_results = load_results(DEFAULT_DB_PATH)

    if not all_results:
        click.echo("No results found. Run 'mutmut-win run' first.")
        return

    counts: dict[str, int] = {}
    for result in all_results:
        counts[result.status] = counts.get(result.status, 0) + 1

    total = len(all_results)
    killed = counts.get("killed", 0) + counts.get("caught by type check", 0)
    survived = counts.get("survived", 0)
    timeout = counts.get("timeout", 0)
    skipped = counts.get("skipped", 0)
    no_tests = counts.get("no tests", 0)
    suspicious = counts.get("suspicious", 0)

    denominator = total - skipped - no_tests
    score = (killed / denominator * 100.0) if denominator > 0 else 0.0

    click.echo(f"Total:     {total}")
    click.echo(f"Killed:    {killed}")
    click.echo(f"Survived:  {survived}")
    click.echo(f"Timeout:   {timeout}")
    click.echo(f"Suspicious:{suspicious}")
    click.echo(f"Skipped:   {skipped}")
    click.echo(f"No tests:  {no_tests}")
    click.echo(f"Score:     {score:.1f}%")

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


@cli.command()
@click.argument("mutant_name")
def show(mutant_name: str) -> None:
    """Show the diff for a specific mutant MUTANT_NAME."""
    mutants_dir = Path("mutants")
    if not mutants_dir.is_dir():
        click.echo("No mutants directory found. Run 'mutmut-win run' first.", err=True)
        sys.exit(1)

    config = load_config()
    try:
        diff = get_diff_for_mutant(mutant_name, config)
    except FileNotFoundError as exc:
        click.echo(str(exc), err=True)
        sys.exit(1)

    if diff:
        click.echo(f"# {mutant_name}")
        click.echo(diff)
    else:
        click.echo(f"No diff found for '{mutant_name}'.")


@cli.command()
@click.argument("mutant_name")
def apply(mutant_name: str) -> None:
    """Apply mutant MUTANT_NAME to the source file on disk."""
    mutants_dir = Path("mutants")
    if not mutants_dir.is_dir():
        click.echo("No mutants directory found. Run 'mutmut-win run' first.", err=True)
        sys.exit(1)

    config = load_config()
    try:
        apply_mutant(mutant_name, config)
    except FileNotFoundError as exc:
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

    When MUTANT_NAMES are given, only those mutants are shown; otherwise all
    mutants recorded in the results cache are listed.  Estimates are derived
    from the stats-collected per-test durations.

    Exits with code 1 if no stats are available.
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

    # Filter to requested mutant names (if any).
    if mutant_names:
        filtered = [r for r in all_results if r.mutant_name in mutant_names]
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
    mutation data is found.
    """
    all_results = load_results(DEFAULT_DB_PATH)
    if not all_results:
        click.echo("No results found. Run 'mutmut-win run' first.", err=True)
        sys.exit(1)

    pairs: list[tuple[str, str | None]] = [(r.mutant_name, r.status) for r in all_results]
    mutants_dir = Path("mutants")
    cicd = save_cicd_stats(pairs, mutants_dir)
    click.echo(f"Saved CI/CD stats to {mutants_dir / 'mutmut-cicd-stats.json'}")
    click.echo(f"Score: {cicd.score:.1f}%  ({cicd.killed} killed / {cicd.total} total)")
