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
    _get_diff(mutant_name)


def _get_diff(mutant_name: str) -> None:
    """Print the unified diff for *mutant_name*, reading from the mutants/ directory.

    Args:
        mutant_name: Unique mutant identifier (e.g. 'src/foo.py::bar__mutmut_1').
    """
    import difflib

    # Derive the source file path from the mutant name.
    # Convention: mutant_name uses dot-separated module path + __mutmut_N suffix.
    # We look under the mutants/ directory for the compiled source.
    mutants_dir = Path("mutants")
    if not mutants_dir.is_dir():
        click.echo("No mutants directory found. Run 'mutmut-win run' first.", err=True)
        sys.exit(1)

    # Find mutant file: walk all .py under mutants/, look for the mutant name in it
    found_path: Path | None = None
    for py_file in mutants_dir.rglob("*.py"):
        try:
            content = py_file.read_text(encoding="utf-8")
        except OSError:
            continue
        if mutant_name in content:
            found_path = py_file
            break

    if found_path is None:
        click.echo(f"Mutant '{mutant_name}' not found in mutants/ directory.", err=True)
        sys.exit(1)

    # The original source file is at the same relative path without the mutants/ prefix
    rel_path = found_path.relative_to(mutants_dir)
    orig_path = Path(rel_path)

    if not orig_path.exists():
        click.echo(f"Original source '{orig_path}' not found.", err=True)
        sys.exit(1)

    orig_lines = orig_path.read_text(encoding="utf-8").splitlines(keepends=True)
    mutant_lines = found_path.read_text(encoding="utf-8").splitlines(keepends=True)

    diff = list(
        difflib.unified_diff(
            orig_lines,
            mutant_lines,
            fromfile=str(orig_path),
            tofile=str(found_path),
        )
    )
    if diff:
        click.echo(f"# {mutant_name}")
        click.echo("".join(diff))
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

    found_path: Path | None = None
    for py_file in mutants_dir.rglob("*.py"):
        try:
            content = py_file.read_text(encoding="utf-8")
        except OSError:
            continue
        if mutant_name in content:
            found_path = py_file
            break

    if found_path is None:
        click.echo(f"Mutant '{mutant_name}' not found in mutants/ directory.", err=True)
        sys.exit(1)

    rel_path = found_path.relative_to(mutants_dir)
    orig_path = Path(rel_path)

    if not orig_path.exists():
        click.echo(f"Original source '{orig_path}' not found.", err=True)
        sys.exit(1)

    mutant_content = found_path.read_text(encoding="utf-8")
    orig_path.write_text(mutant_content, encoding="utf-8")
    click.echo(f"Applied mutant '{mutant_name}' to '{orig_path}'.")


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
