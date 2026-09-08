"""Click CLI for mutmut-win.

Entry point for all command-line interaction with mutmut-win.
Provides run, results, show, apply, and browse sub-commands.
"""

from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, TextIO

import click

from mutmut_win import __version__
from mutmut_win.browser import ResultBrowser
from mutmut_win.config import MutmutConfig, load_config
from mutmut_win.db import (
    DEFAULT_DB_PATH,
    RunBasisIncompleteness,
    invalidate_latest_run_evidence,
    known_run_basis_incompleteness,
    load_current_run,
    load_results,
    validate_cache_path,
)
from mutmut_win.exceptions import (
    MutmutWinError,
    StagingNamespaceCollisionError,
    UnsafeWorkspaceStateError,
)
from mutmut_win.mutant_diff import apply_mutant, render_function_diff_bytes, resolve_mutant
from mutmut_win.orchestrator import MutationOrchestrator
from mutmut_win.process.executor import SpawnPoolExecutor
from mutmut_win.process.run_lock import (
    DatabaseRunLocks,
    WorkspaceRunLock,
    run_lock_path_for_db,
)
from mutmut_win.runner import PytestRunner
from mutmut_win.stats import (
    build_run_basis_evidence,
    compute_cicd_stats,
    load_stats,
    save_cicd_stats,
)
from mutmut_win.test_mapping import (
    mangled_name_from_mutant_name,
    match_mutant_names,
    tests_for_mutant_names,
)

if TYPE_CHECKING:
    from mutmut_win.db import MutationRunState
    from mutmut_win.models import MutationResult


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


def _finite_score(
    _ctx: click.Context,
    _param: click.Parameter,
    value: float | None,
) -> float | None:
    """Reject NaN/Infinity before they can neutralise score comparisons."""
    if value is not None and not math.isfinite(value):
        raise click.BadParameter("must be a finite number between 0 and 100")
    return value


def _emit_json_error(stream: TextIO | None, message: str, exit_code: int) -> None:
    """Keep the JSON channel machine-readable on an early run failure."""
    if stream is not None:
        click.echo(
            json.dumps({"error": message, "exit_code": exit_code}, indent=2),
            file=stream,
        )


def _fixed_workspace_root_refusal(dirname: str, *, action: str) -> str | None:
    """Return a fail-closed reason when a fixed state root is redirected."""
    path = Path(dirname)
    try:
        expected = Path.cwd().resolve() / dirname
        resolved = path.resolve(strict=False)
        junction_check = getattr(path, "is_junction", None)
        is_link_like = path.is_symlink() or (callable(junction_check) and junction_check())
    except (
        OSError,
        RuntimeError,
    ):
        is_link_like = True
        resolved = None
        expected = Path.cwd() / dirname
    if is_link_like or resolved != expected:
        return (
            f"Refusing {action}: {dirname}/ is a link, junction, or resolves outside the workspace."
        )
    return None


def _force_cleanup_refusal(dirname: str) -> str | None:
    """Return a fail-closed reason when a fixed --force root is unsafe."""
    return _fixed_workspace_root_refusal(dirname, action="--force cleanup")


def _require_safe_workspace_roots(
    *dirnames: str,
    action: str = "workspace state access",
) -> None:
    """Reject redirected fixed state roots without creating either root."""
    for dirname in dirnames:
        refusal = _fixed_workspace_root_refusal(dirname, action=action)
        if refusal is not None:
            raise UnsafeWorkspaceStateError(refusal)


def _uses_default_cache_root(path: Path) -> bool:
    """Return whether *path* is lexically inside this workspace's cache root."""
    return path.absolute().parent == (Path.cwd() / DEFAULT_DB_PATH.parent).absolute()


def _basis_excluded_paths(path: Path) -> tuple[Path, ...]:
    database = path.absolute()
    return (
        database,
        Path(f"{database}-journal"),
        Path(f"{database}-wal"),
        Path(f"{database}-shm"),
    )


def _stable_live_basis(config: MutmutConfig, path: Path) -> str:
    """Compute one stable export-time basis or reject concurrent drift."""
    excluded_paths = _basis_excluded_paths(path)
    first = build_run_basis_evidence(config, excluded_paths=excluded_paths)
    second = build_run_basis_evidence(config, excluded_paths=excluded_paths)
    if first != second:
        raise MutmutWinError(
            "source, test, configuration, dependency, or environment inputs changed "
            "while CI/CD evidence was being validated"
        )
    if not first.complete:
        raise MutmutWinError(
            "the complete execution basis cannot be fingerprinted; "
            "CI/CD evidence is unavailable when dependency/import inputs are unobservable "
            "or a generic type_check_command is configured"
        )
    return first.digest


def _load_config_or_exit(json_stdout: TextIO | None = None) -> MutmutConfig:
    """Load the project config; exit 2 with the message on ConfigError.

    Issue #109 / A4-UI-011: a corrupted pyproject.toml surfaced as a RAW
    traceback in ``show``/``apply`` (``run`` got its clean path in #102).
    Config errors follow the #102 convention: exit code 2, message only.
    """
    from mutmut_win.exceptions import ConfigError

    try:
        return load_config()
    except ConfigError as exc:
        message = str(exc)
        click.echo(message, err=True)
        _emit_json_error(json_stdout, message, 2)
        sys.exit(2)


def _load_results_or_exit(path: Path = DEFAULT_DB_PATH) -> list[MutationResult]:
    """Load cached results; on a corrupt cache DB, exit 1 with a clean message.

    External QA CACHE-001: a garbage ``mutmut-cache.db`` used to escape as a raw
    ``sqlite3`` traceback from the read commands (``results`` /
    ``export-cicd-stats`` / ``show`` / ``time-estimates``); ``run`` already had
    its clean path via the orchestrator's domain-error handler. ``run --force``
    recovers by deleting ``.mutmut-cache/`` first.
    """
    _current, results = _load_result_snapshot_or_exit(path)
    return results


def _load_result_snapshot_or_exit(
    path: Path = DEFAULT_DB_PATH,
) -> tuple[MutationRunState | None, list[MutationResult]]:
    """Load the current run population, falling back only for legacy DBs."""
    try:
        if _uses_default_cache_root(path):
            _require_safe_workspace_roots(".mutmut-cache")
        current = load_current_run(path)
        if current is None:
            return None, load_results(path)

        from mutmut_win.models import MutationResult

        completed_by_name = {result.mutant_name: result for result in current.completed_results}
        results: list[MutationResult] = []
        for mutant_name in current.planned_names:
            completed = completed_by_name.get(mutant_name)
            if completed is None:
                results.append(MutationResult(mutant_name=mutant_name, status="not checked"))
                continue
            results.append(
                MutationResult(
                    mutant_name=completed.mutant_name,
                    status=completed.status,
                    exit_code=completed.exit_code,
                    duration=completed.duration,
                    last_output=completed.last_output,
                    forensics=completed.forensics,
                    tests_fingerprint=completed.tests_fingerprint,
                )
            )
        return current, results
    except MutmutWinError as exc:
        click.echo(str(exc), err=True)
        sys.exit(1)


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
    "--profile",
    type=click.Choice(["basic", "advanced", "all"], case_sensitive=False),
    default=None,
    help=(
        "Operator profile (overrides pyproject.toml): basic = mutmut's 15 base "
        "operators; advanced = + mutmut-win's extras (default); all = + the "
        "aggressive operators."
    ),
)
@click.option(
    "--min-score",
    # FloatRange: 150 used to execute the FULL run before the gate
    # trivially failed; -5 made the gate a no-op (issue #120 / CLI-001).
    type=click.FloatRange(0, 100),
    callback=_finite_score,
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
        "Relative project or explicit ../ sibling directories to copy into mutants/ "
        "and add to the staged test PYTHONPATH. External absolute and Windows "
        "anchored-relative paths are rejected. Repeatable. Overrides "
        "[tool.mutmut].extra_paths."
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
    profile: str | None,
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

    json_stdout = sys.stdout if output == "json" else None
    explicit_selection = bool(mutant_names or paths_to_mutate or since_commit is not None)

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

        # A linked cache can resolve the canonical DB lock into its external
        # target, while linked staging can redirect generation writes. Reject
        # both fixed roots before deriving/acquiring the lock for every real
        # run (not just destructive --force). A dry-run is read-only.
        if not dry_run or force:
            action = "--force cleanup" if force else "workspace state access"
            try:
                _require_safe_workspace_roots(
                    "mutants",
                    ".mutmut-cache",
                    action=action,
                )
            except UnsafeWorkspaceStateError as exc:
                message = str(exc)
                click.echo(message, err=True)
                _emit_json_error(json_stdout, message, 1)
                sys.exit(1)

        # Serialize every state-changing run before ``--force`` can remove
        # shared staging/cache state. The OS guard survives crashes; owner
        # metadata carries PID/start-time diagnostics and is never guessed
        # stale. A read-only dry-run needs no lock unless --force itself was
        # explicitly requested.
        workspace_lock: WorkspaceRunLock | None = None
        if not dry_run or force:
            try:
                # Validate the database file and SQLite sidecars before
                # canonicalising the lock path.  Otherwise a file-level link
                # could redirect the lock and its owner metadata outside the
                # workspace before the database layer gets a chance to refuse
                # the unsafe cache.
                validate_cache_path(DEFAULT_DB_PATH)
                workspace_lock = prose_stack.enter_context(
                    WorkspaceRunLock(run_lock_path_for_db(DEFAULT_DB_PATH))
                )
            except MutmutWinError as exc:
                if debug:
                    import traceback

                    click.echo(traceback.format_exc(), err=True)
                message = f"Error: {exc}"
                click.echo(message, err=True)
                _emit_json_error(json_stdout, message, 1)
                sys.exit(1)

            # Close the validate/acquire race before any cache or staging
            # access. The concrete writers retain their own destination
            # checks as a final boundary.
            try:
                _require_safe_workspace_roots("mutants", ".mutmut-cache")
                validate_cache_path(DEFAULT_DB_PATH)
            except UnsafeWorkspaceStateError as exc:
                message = str(exc)
                click.echo(message, err=True)
                _emit_json_error(json_stdout, message, 1)
                sys.exit(1)

        # Issue #120 / CFG-001 (external QA): a broken [tool.mutmut] used to
        # escape as a 47-line traceback with exit 1 while CLI flags with the
        # SAME rules exited 2 — one config-error contract for every command.
        config = _load_config_or_exit(json_stdout)

        # A score gate is release/CI authority over the complete configured
        # mutant universe. Name, path and --since-commit selections are
        # intentionally subset runs; judging their denominator could turn a
        # one-mutant retest into a false 100% project score. Reject the
        # incompatible request before any expensive generation or git diff.
        subset_selection_requested = bool(
            mutant_names or since_commit is not None or paths_to_mutate
        )
        if min_score is not None and subset_selection_requested:
            message = (
                "--min-score requires a full unfiltered run; mutant names, "
                "--paths-to-mutate, and --since-commit cannot authorize a project score"
            )
            click.echo(message, err=True)
            _emit_json_error(json_stdout, message, 2)
            sys.exit(2)

        # --- Apply CLI overrides to config ---
        overrides: dict[str, object] = {}
        if max_children is not None:
            overrides["max_children"] = max_children
        if paths_to_mutate:
            overrides["paths_to_mutate"] = list(paths_to_mutate)
        if tests_dir is not None:
            overrides["tests_dir"] = [tests_dir]
        if profile is not None:
            overrides["mutation_profile"] = profile
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

        # Validate every ordinary override before --since-commit interprets
        # changed paths.  In particular, the effective --tests-dir must be the
        # exclusion boundary below; consulting the pre-override config let a
        # changed custom_tests/*.py file become a mutation target.
        if overrides:
            from pydantic import ValidationError

            try:
                config = MutmutConfig.model_validate({**config.model_dump(), **overrides})
            except ValidationError as exc:
                message = f"Invalid option value:\n{exc}"
                click.echo(message, err=True)
                _emit_json_error(json_stdout, message, 2)
                sys.exit(2)
            overrides = {}

        # --since-commit: resolve changed .py files via git
        if since_commit is not None:
            import subprocess as sp

            # git command is fully controlled — commit hash is validated by git itself.
            # Diff against the REF alone (no ..HEAD): committed AND
            # working-tree changes count — the documented "check what you
            # just changed" workflow includes uncommitted edits (issue #128
            # / 360°-A4). Untracked files stay invisible to git diff.
            git_result = sp.run(  # noqa: S603 — git CLI with controlled args
                ["git", "diff", "--name-only", "-z", since_commit],  # noqa: S607 — git is a well-known executable
                capture_output=True,
            )
            # Issue #102 / A3-CM-006: the returncode was never checked — an
            # invalid ref meant "nothing changed" + exit 0, a FALSE CI success.
            if git_result.returncode != 0:
                stderr = (
                    git_result.stderr.decode("utf-8", errors="replace")
                    if isinstance(git_result.stderr, bytes)
                    else git_result.stderr
                )
                message = f"git diff failed (exit {git_result.returncode}): {stderr.strip()}"
                click.echo(message, err=True)
                _emit_json_error(json_stdout, message, 2)
                sys.exit(2)

            def _comparison_parts(path_text: str) -> tuple[str, ...]:
                return tuple(os.path.normcase(part) for part in Path(path_text).parts)

            tests_dir_parts = tuple(
                _comparison_parts(target.split("::", 1)[0].strip("/").strip("\\"))
                for target in config.tests_dir
            )

            def _is_mutation_target(name: str) -> bool:
                # Deleted files and test files used to become mutation targets.
                if not name.casefold().endswith(".py") or not Path(name).exists():
                    return False
                parts = _comparison_parts(name)
                # Component-prefix match (issue #128 / 360°-A4): the old
                # parts[0] comparison against the FULL tests_dir string never
                # matched nested dirs like "tests/unit/" — changed TEST files
                # became mutation targets.
                return all(parts[: len(td)] != td for td in tests_dir_parts)

            if isinstance(git_result.stdout, bytes):
                changed_names = [
                    raw.decode("utf-8", errors="surrogateescape")
                    for raw in git_result.stdout.split(b"\0")
                    if raw
                ]
            else:
                # Test doubles and third-party subprocess seams may still
                # return text. Production uses bytes so ``-z`` can preserve
                # every pathname without Git's C-style quoting.
                separator = "\0" if "\0" in git_result.stdout else "\n"
                changed_names = [name for name in git_result.stdout.split(separator) if name]
            changed_py = [name for name in changed_names if _is_mutation_target(name)]
            if not changed_py:
                message = "No mutation-target .py files changed since the given commit."
                # A valid diff with no changed production target is an
                # incremental no-op, not malformed input.  This distinction
                # matters in CI: an invalid ref above still exits 2, while a
                # docs/tests-only change can end successfully without
                # fabricating mutation evidence (MW221-043).
                if json_stdout is not None:
                    from mutmut_win.models import MutationRunResult

                    click.echo(MutationRunResult().model_dump_json(indent=2), file=json_stdout)
                else:
                    click.echo(message)
                return
            overrides["paths_to_mutate"] = changed_py

        if overrides:
            # Issue #102 / A3-CM-004: model_copy(update=...) bypasses ALL pydantic
            # constraints — '--max-children 0' was an accepted hang. Re-validate
            # the merged config so the field constraints apply to CLI input too.
            from pydantic import ValidationError

            try:
                config = MutmutConfig.model_validate({**config.model_dump(), **overrides})
            except ValidationError as exc:
                message = f"Invalid option value:\n{exc}"
                click.echo(message, err=True)
                _emit_json_error(json_stdout, message, 2)
                sys.exit(2)

        # Issue #120 / CLI-002 (external QA): a typo'd mutation root used to
        # yield "No mutants generated." with exit 0 — a false CI success. A
        # missing path is a configuration error per the documented contract.
        missing_paths = [p for p in config.paths_to_mutate if not Path(p).exists()]
        if missing_paths:
            plural = "ies do" if len(missing_paths) > 1 else "y does"
            message = f"paths_to_mutate entr{plural} not exist: {', '.join(missing_paths)}"
            click.echo(message, err=True)
            _emit_json_error(json_stdout, message, 2)
            sys.exit(2)

        # Build and validate the exact staging-input plan before --force can
        # delete prior evidence and before an executor or database is created.
        # A project file that would be overwritten by mutmut-win-owned
        # metadata/plugins is a configuration error, not a cleanable cache.
        from mutmut_win.file_setup import validate_staging_namespace

        try:
            validate_staging_namespace(config)
        except StagingNamespaceCollisionError as exc:
            message = str(exc)
            click.echo(message, err=True)
            _emit_json_error(json_stdout, message, 2)
            sys.exit(2)

        # --force: clean slate — only after the effective configuration and
        # read-only namespace plan have been proven safe. The workspace lock
        # acquired above continues to serialize both removals.
        if force:
            import shutil

            for dirname in ("mutants", ".mutmut-cache"):
                p = Path(dirname)
                if p.exists():
                    refusal = _force_cleanup_refusal(dirname)
                    if refusal is not None:
                        click.echo(refusal, err=True)
                        _emit_json_error(json_stdout, refusal, 1)
                        sys.exit(1)
                    shutil.rmtree(p, ignore_errors=True)
                    # Issue #101 / A3-FD-009: rmtree(ignore_errors=True) plus an
                    # unconditional success message sold a PARTIAL deletion
                    # (files locked by another process) as a clean slate.
                    if p.exists():
                        message = (
                            f"Could not fully remove {dirname}/ (files in use?); "
                            "refusing to run with stale state."
                        )
                        click.echo(message, err=True)
                        _emit_json_error(json_stdout, message, 1)
                        sys.exit(1)
                    else:
                        click.echo(f"Removed {dirname}/")

        # Only a FULL run may purge stale DB rows (issue #96): subset runs know
        # just a slice of the valid mutant set and must never delete history.
        # A --paths-to-mutate override narrows the staging to that slice, so it
        # counts as a subset run too (issue #120 / RUN-002 — the purge used to
        # delete every result outside the given paths).
        is_full_run = not mutant_names and since_commit is None and not paths_to_mutate
        try:
            runner = PytestRunner(config)
            # A dry-run is a source-only preview: constructing the Windows
            # executor here would create a Job Object even though no worker
            # can be used.  Keep the existing injection point for real runs,
            # but let MutationOrchestrator retain its lazy default for the
            # preview path.
            executor = (
                None
                if dry_run
                else SpawnPoolExecutor(max_workers=config.max_children, config=config)
            )
            orchestrator = MutationOrchestrator(
                config,
                runner=runner,
                executor=executor,
                mutant_names=mutant_names if mutant_names else None,
                no_progress=no_progress,
                purge_stale_results=is_full_run,
                is_full_run=is_full_run,
                rerun_all=rerun_all,
                workspace_lock=workspace_lock,
            )
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
            message = f"Error: {exc}"
            click.echo(message, err=True)
            _emit_json_error(json_stdout, message, 1)
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

    # --- Empty-run honesty (MW220-034) ---
    # A dry-run is an informational preview and may legitimately count zero.
    # A real run that selected or generated nothing is not evidence that the
    # mutation suite passed.  Explicit filters are usage/domain errors; a full
    # empty generation is a runtime failure.  JSON was already emitted above.
    if not dry_run and result.total_mutants == 0:
        if explicit_selection:
            click.echo("No mutants matched the explicit run selection.", err=True)
            sys.exit(2)
        click.echo("No testable mutants were generated; mutation run failed closed.", err=True)
        sys.exit(1)

    # --- Score gate ---
    if min_score is not None:
        if not result.execution_basis_complete:
            click.echo(
                "Execution basis incomplete — score gate failed closed; not all "
                "execution inputs could be fingerprinted.",
                err=True,
            )
            sys.exit(1)
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

    current_run, all_results = _load_result_snapshot_or_exit(DEFAULT_DB_PATH)

    if current_run is not None:
        reused = sum(result.reused for result in current_run.completed_results)
        click.echo(
            f"Run status: {current_run.status} "
            f"({len(current_run.completed_names)} completed, "
            f"{len(current_run.pending_names)} pending, {reused} reused)"
        )
        if not current_run.is_full_run:
            click.echo(
                "Latest run is a subset selection; release-ready: no. "
                "Displayed totals and score cover only this subset.",
                err=True,
            )
        if current_run.evidence_invalidated:
            click.echo(
                "Evidence invalidated: yes; release-ready: no. "
                "The recorded execution basis is no longer authoritative; "
                "re-run 'mutmut-win run'.",
                err=True,
            )
        elif current_run.status == "completed":
            basis_issue = known_run_basis_incompleteness(current_run)
            if basis_issue is RunBasisIncompleteness.MALFORMED:
                click.echo(
                    "WARNING: persisted execution-basis evidence is malformed; "
                    "release-ready: no. Rebuild the cache with 'mutmut-win run --force'.",
                    err=True,
                )
            elif basis_issue is RunBasisIncompleteness.GENERIC_TYPE_CHECK_COMMAND:
                click.echo(
                    "Run technically completed with a generic type_check_command; "
                    "execution basis incomplete; release-ready: no.",
                    err=True,
                )
            elif basis_issue is RunBasisIncompleteness.MISSING:
                click.echo(
                    "Run technically completed; execution basis incomplete; release-ready: no.",
                    err=True,
                )

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
    # Use the same aggregator as the CI export instead of maintaining a third
    # score formula here (MW220-037). Rows without a verdict cannot contribute
    # evidence and therefore leave the score input, matching MutationRunResult's
    # ``unchecked`` denominator contract.
    measured_pairs: list[tuple[str, str | None]] = [
        (result.mutant_name, result.status)
        for result in all_results
        if result.status not in {"not checked", "check was interrupted by user"}
    ]
    aggregate = compute_cicd_stats(measured_pairs)
    type_check = aggregate.caught_by_type_check
    kill_aggregate = aggregate.killed
    il_killed = aggregate.killed_by_infinite_loop
    timeout = aggregate.timeout
    score_kills = aggregate.effective_killed + (timeout if treat_timeout_as_kill else 0)
    score = (score_kills / aggregate.scoreable * 100.0) if aggregate.scoreable > 0 else 0.0

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


def _write_stdout_bytes(payload: bytes) -> None:
    """Write patch output without encoding or Windows CRLF rewriting."""
    stream = click.get_binary_stream("stdout")
    stream.write(payload)
    stream.flush()


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
        diff = render_function_diff_bytes(data.path, resolved_name)
    except (FileNotFoundError, MutmutWinError) as exc:
        click.echo(str(exc), err=True)
        sys.exit(1)

    if diff:
        _write_stdout_bytes(f"# {resolved_name}\n".encode() + diff)
    else:
        click.echo(f"No diff found for '{resolved_name}'.")

    if DEFAULT_DB_PATH.exists():
        row = next(
            (r for r in _load_results_or_exit(DEFAULT_DB_PATH) if r.mutant_name == resolved_name),
            None,
        )
        if row is not None:
            panel = _format_forensics_panel(row.status, row.forensics)
            if panel is not None:
                # Keep stdout a directly pipeable patch stream. Interactive
                # users still see the forensic explanation on stderr, while
                # ``mutmut-win show NAME > mutant.patch`` remains valid.
                click.echo(panel, err=True)


@cli.command()
@click.argument("mutant_name")
def apply(mutant_name: str) -> None:
    """Apply mutant MUTANT_NAME to the source file on disk.

    MUTANT_NAME is an exact mutant name or a glob pattern that matches
    exactly ONE mutant; an ambiguous pattern fails and lists the
    candidates — apply never applies a set.
    """
    try:
        _require_safe_workspace_roots("mutants", ".mutmut-cache")
        validate_cache_path(DEFAULT_DB_PATH)
        with (
            WorkspaceRunLock(run_lock_path_for_db(DEFAULT_DB_PATH)),
            DatabaseRunLocks(DEFAULT_DB_PATH),
        ):
            _require_safe_workspace_roots("mutants", ".mutmut-cache")
            validate_cache_path(DEFAULT_DB_PATH)
            mutants_dir = Path("mutants")
            if not mutants_dir.is_dir():
                click.echo("No mutants directory found. Run 'mutmut-win run' first.", err=True)
                sys.exit(1)

            config = _load_config_or_exit()
            # Resolve before revoking evidence: a typo or ambiguous glob has
            # not changed the source and must leave the latest run snapshot
            # and CI artifact intact.
            resolved_name, _data = resolve_mutant(mutant_name, config)
            # Revoke prior evidence before the irreversible source replacement.
            # If invalidation or artifact cleanup fails, apply must not touch
            # the source.  If apply itself later fails, losing reusable evidence
            # is conservative; retaining a green pre-apply snapshot is not.
            invalidate_latest_run_evidence(DEFAULT_DB_PATH)
            artifact_path = mutants_dir / "mutmut-cicd-stats.json"
            try:
                artifact_path.unlink(missing_ok=True)
            except OSError as exc:
                raise MutmutWinError(
                    f"Could not remove CI/CD artifact before applying mutant "
                    f"{artifact_path}: {exc}; source was not changed"
                ) from exc
            apply_mutant(resolved_name, config)
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
    try:
        app = ResultBrowser(show_killed=show_killed)
        app.run()
    except MutmutWinError as exc:
        click.echo(f"Could not open result browser: {exc}", err=True)
        sys.exit(1)


@cli.command("tests-for-mutant")
@click.argument("name")
def tests_for_mutant_cmd(name: str) -> None:
    """Show the tests mapped to mutant NAME.

    Loads the stats cache and prints each test node ID that covers the
    mutated function.  Exits with code 1 if no stats are available.
    """
    stats = load_stats()
    if stats is None:
        click.echo(
            "No stats found. Run 'mutmut-win run' first to collect stats.",
            err=True,
        )
        sys.exit(1)

    mapped_tests = tests_for_mutant_names([name], stats.tests_by_mangled_function_name)
    if not stats.mapping_is_authoritative:
        click.echo(
            "Test mapping is incomplete; mutation runs execute the full test suite "
            "for this mutant. Observed tests follow:"
        )
        for test in sorted(mapped_tests):
            click.echo(test)
        return
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
    stats = load_stats()
    if stats is None:
        click.echo(
            "No stats found. Run 'mutmut-win run' first to collect stats.",
            err=True,
        )
        sys.exit(1)

    all_results = _load_results_or_exit(DEFAULT_DB_PATH)
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
        except ValueError:
            times_and_names.append((0.0, result.mutant_name))
            continue
        if stats.mapping_is_authoritative:
            test_ids = stats.tests_by_mangled_function_name.get(mangled, set())
        else:
            # Runtime safety matches `_assign_tests_to_tasks`: a partial
            # mapping cannot narrow execution, so estimate the clean suite.
            test_ids = set(stats.duration_by_test)
        estimated = sum(stats.duration_by_test.get(t, 0.0) for t in test_ids)
        times_and_names.append((estimated, result.mutant_name))

    for estimated, mutant_name in sorted(times_and_names):
        if not stats.mapping_is_authoritative:
            click.echo(f"{int(estimated * 1000)}ms (full suite; mapping incomplete)  {mutant_name}")
        elif estimated == 0.0:
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
    try:
        _require_safe_workspace_roots("mutants", ".mutmut-cache")
        validate_cache_path(DEFAULT_DB_PATH)
        with (
            WorkspaceRunLock(run_lock_path_for_db(DEFAULT_DB_PATH)),
            DatabaseRunLocks(DEFAULT_DB_PATH),
        ):
            _require_safe_workspace_roots("mutants", ".mutmut-cache")
            validate_cache_path(DEFAULT_DB_PATH)
            _export_cicd_stats_locked()
    except MutmutWinError as exc:
        click.echo(f"CI/CD export could not acquire a consistent state: {exc}", err=True)
        sys.exit(1)


def _export_cicd_stats_locked() -> None:
    """Export one snapshot while the cache/staging state lock is held."""
    _require_safe_workspace_roots("mutants", ".mutmut-cache")
    mutants_dir = Path("mutants")
    artifact_path = mutants_dir / "mutmut-cicd-stats.json"
    # Revoke any previous artifact before reading persisted authority. A
    # corrupt snapshot must not leave an older green export in place merely
    # because validation fails before the normal evidence checks below.
    artifact_path.unlink(missing_ok=True)
    current_run, all_results = _load_result_snapshot_or_exit(DEFAULT_DB_PATH)
    if current_run is None:
        artifact_path.unlink(missing_ok=True)
        if all_results:
            click.echo(
                "Legacy mutation results have no verifiable run basis; "
                "CI/CD export failed closed. Re-run 'mutmut-win run'.",
                err=True,
            )
        else:
            click.echo("No results found. Run 'mutmut-win run' first.", err=True)
        sys.exit(1)
    if not all_results:
        artifact_path.unlink(missing_ok=True)
        click.echo("No results found. Run 'mutmut-win run' first.", err=True)
        sys.exit(1)

    if current_run is not None and (current_run.status != "completed" or current_run.pending_names):
        artifact_path.unlink(missing_ok=True)
        click.echo(
            "Latest mutation run is incomplete "
            f"(status={current_run.status}, pending={len(current_run.pending_names)}); "
            "CI/CD export failed closed.",
            err=True,
        )
        sys.exit(1)

    if current_run is not None and current_run.evidence_invalidated:
        artifact_path.unlink(missing_ok=True)
        click.echo(
            "Latest mutation run evidence was invalidated because its recorded "
            "execution basis is no longer authoritative; "
            "re-run 'mutmut-win run' before CI/CD export.",
            err=True,
        )
        sys.exit(1)

    if current_run.universe_fingerprint is None or current_run.plan_digest is None:
        artifact_path.unlink(missing_ok=True)
        click.echo(
            "Latest mutation run predates verifiable ordered-plan evidence; "
            "CI/CD export failed closed. Re-run 'mutmut-win run'.",
            err=True,
        )
        sys.exit(1)

    if current_run.basis_fingerprint is None or current_run.basis_config_json is None:
        artifact_path.unlink(missing_ok=True)
        click.echo(
            "Latest mutation run predates verifiable source/test/config evidence or its "
            "execution basis was incomplete; "
            "CI/CD export failed closed. Re-run 'mutmut-win run'.",
            err=True,
        )
        sys.exit(1)
    try:
        effective_config = MutmutConfig.model_validate_json(current_run.basis_config_json)
    except ValueError:
        artifact_path.unlink(missing_ok=True)
        click.echo(
            "Latest mutation run has an invalid persisted basis config; "
            "CI/CD export failed closed.",
            err=True,
        )
        sys.exit(1)
    if not current_run.is_full_run:
        artifact_path.unlink(missing_ok=True)
        click.echo(
            "Latest mutation run was a subset selection and cannot authorize a full-run "
            "CI/CD score; re-run 'mutmut-win run' without mutant or path filters.",
            err=True,
        )
        sys.exit(1)
    try:
        live_basis = _stable_live_basis(effective_config, DEFAULT_DB_PATH)
    except MutmutWinError:
        artifact_path.unlink(missing_ok=True)
        raise
    if live_basis != current_run.basis_fingerprint:
        artifact_path.unlink(missing_ok=True)
        click.echo(
            "Source, test, configuration, dependency, or environment inputs changed since "
            "the latest mutation run; "
            "CI/CD export failed closed. Re-run 'mutmut-win run'.",
            err=True,
        )
        sys.exit(1)

    # Persist the same measured population used by ``results``. An unchecked
    # or interrupted row is not a mutation verdict and must not dilute the CI
    # score (MW220-037).
    pairs: list[tuple[str, str | None]] = [
        (r.mutant_name, r.status)
        for r in all_results
        if r.status not in {"not checked", "check was interrupted by user"}
    ]
    if not pairs:
        artifact_path.unlink(missing_ok=True)
        click.echo("No completed mutation verdicts found; CI/CD export failed closed.", err=True)
        sys.exit(1)
    cicd = save_cicd_stats(pairs, mutants_dir)
    click.echo(f"Saved CI/CD stats to {mutants_dir / 'mutmut-cicd-stats.json'}")
    # Issue #122 / external QA SCO-001: "(40 killed / 78 total)" next to a
    # 71.4% score invited verifying it with the WRONG denominator — the
    # parenthetical now shows the kill class over the scoreable set.
    click.echo(
        f"Score: {cicd.score:.1f}%  ({cicd.effective_killed} killed / {cicd.scoreable} scoreable)"
    )
