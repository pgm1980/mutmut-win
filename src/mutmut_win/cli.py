"""Click CLI for mutmut-win.

Entry point for all command-line interaction with mutmut-win.
Provides run, results, show, apply, and browse sub-commands.
"""

from __future__ import annotations

import sys
from pathlib import Path

import click

from mutmut_win.browser import ResultBrowser
from mutmut_win.config import load_config
from mutmut_win.db import DEFAULT_DB_PATH, load_results
from mutmut_win.mutant_diff import apply_mutant, get_diff_for_mutant
from mutmut_win.orchestrator import MutationOrchestrator
from mutmut_win.process.executor import SpawnPoolExecutor
from mutmut_win.runner import PytestRunner


@click.group()
def cli() -> None:
    """mutmut-win — Windows-native mutation testing for Python."""


@cli.command()
@click.option("--max-children", type=int, default=None, help="Number of worker processes.")
@click.argument("mutant_names", nargs=-1)
def run(max_children: int | None, mutant_names: tuple[str, ...]) -> None:
    """Run mutation testing.

    Optionally filter to specific MUTANT_NAMES. When omitted, all mutants are tested.
    """
    config = load_config()
    if max_children is not None:
        config = config.model_copy(update={"max_children": max_children})

    runner = PytestRunner(config)
    executor = SpawnPoolExecutor(max_workers=config.max_children, config=config)
    orchestrator = MutationOrchestrator(config, runner=runner, executor=executor)

    if mutant_names:
        click.echo("Note: mutant name filtering not yet implemented; running all mutants.")

    try:
        orchestrator.run()
    except Exception as exc:  # surface all errors with a clean message
        click.echo(f"Error: {exc}", err=True)
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
