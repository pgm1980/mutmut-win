"""File setup utilities for mutmut-win mutation testing pipeline.

Handles copying source files to the mutants/ staging directory, setting up
sys.path for correct import resolution, and generating per-file mutant code.

These functions are ported from mutmut's ``__main__.py`` and adapted for:
- Windows-compatible path handling (os.sep-aware)
- Explicit encoding='utf-8' on all file I/O
- Config passed as parameter instead of global state
- Integration with mutmut_win's Pydantic models and mutation engine
"""

from __future__ import annotations

import ast
import contextlib
import hashlib
import importlib.machinery
import itertools
import json
import os
import re
import shutil
import stat
import sys
import time
import tokenize
import warnings
from io import BytesIO, StringIO, TextIOWrapper
from pathlib import Path
from typing import IO, TYPE_CHECKING, Literal

import libcst as cst

from mutmut_win.atomic_file import atomic_copy_file, atomic_write_bytes
from mutmut_win.constants import (
    SOURCE_ROOT_NAMES,
    WORKSPACE_EXCLUDED_DIR_NAMES,
    WORKSPACE_RECURSIVE_EXCLUDED_DIR_NAMES,
    Profile,
    configured_staging_relative_path,
)
from mutmut_win.exceptions import (
    MutationSurfaceDegradedWarning,
    StagingNamespaceCollisionError,
    StaleStagingError,
    UnsafeStagingError,
)
from mutmut_win.gitignore_boundary import GitignoreBoundary
from mutmut_win.models import SourceFileMutationData, read_owned_source_metadata

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Sequence

    from mutmut_win.config import MutmutConfig

#: Directory names excluded from every staging walk (mirror AND also_copy).
#: One list for both passes (issue #129 / 360°-C4): the two sites used to
#: carry diverging literals, and tooling trees (node_modules, .claude, …)
#: were mirrored into mutants/ on every first run.
_STAGING_SKIP_DIRS: frozenset[str] = WORKSPACE_EXCLUDED_DIR_NAMES
_STAGING_RECURSIVE_SKIP_DIRS: frozenset[str] = WORKSPACE_RECURSIVE_EXCLUDED_DIR_NAMES

# Stable workspace coordination artifacts belong beside the project, never in
# the import staging tree. The guard intentionally survives clean releases.
_STAGING_SKIP_FILES: frozenset[str] = frozenset(
    {".mutmut-win.run.lock", ".mutmut-win.run.lock.guard"}
)
_PERSISTENT_STAGING_STATE_FILES: frozenset[str] = frozenset({".mutmut-config-fingerprint"})

# These paths are produced inside executable staging after the live project
# mirror is copied. A project input at the same target must be rejected,
# never silently replaced. The helper modules are additionally reserved as
# import names under every source root that precedes ``mutants/`` on the child
# PYTHONPATH (CX221-038).
_FIXED_STAGING_ARTIFACT_OWNERS: dict[str, str] = {
    ".mutmut-config-fingerprint": "the mutation-universe fingerprint",
    "mutmut-cicd-stats.json": "the CI/CD statistics export",
}
_STAGING_HELPER_MODULE_OWNERS: dict[str, str] = {
    "_mutmut_phase_guard": "the pytest phase guard",
    "_mutmut_stats_plugin": "the pytest statistics plugin",
    "sitecustomize": "the editable-install path blocker",
}


def _is_dotenv_name(name: str) -> bool:
    """Return whether *name* is a dotenv file tests may discover upward.

    Shared by staging (which keeps dotenv secrets out of ``mutants/``) and
    the run-basis digest (which must keep binding their bytes: tests can read
    them through upward dotenv discovery even though they are never staged,
    MBR-2026-09-14-01 carve-out).
    """
    folded = name.casefold()
    return folded == ".env" or (
        folded.startswith(".env.")
        and folded not in {".env.example", ".env.sample", ".env.template"}
    )


def _skip_automatic_root_file(name: str) -> bool:
    """Keep coordination files and dotenv secrets out of automatic staging."""
    folded = name.casefold()
    if folded in _STAGING_SKIP_FILES or (
        folded.startswith(".mutmut-win-") and folded.endswith((".run.lock", ".run.lock.guard"))
    ):
        return True
    return _is_dotenv_name(name)


def _configured_entry_boundary(
    project_boundary: GitignoreBoundary,
    project_root: Path,
    entry: Path,
) -> GitignoreBoundary | None:
    """Return the boundary governing one explicitly configured entry's tree.

    Explicitly named entries are force-included (``git add -f`` semantics):
    every path component is force-entered so an entry inside an ignored
    subtree still stages.  Ignore files at or below the entry keep governing
    its contents.  Entries outside the project root have no project-local
    gitignore domain and return ``None`` (nothing excluded).
    """
    try:
        relative = entry.resolve(strict=False).relative_to(project_root)
    except (OSError, ValueError):  # fmt: skip
        return None
    if str(relative) in {".", ""}:
        return project_boundary
    return project_boundary.descend_forced(*relative.parts)


def _walk_boundary_map(
    walk_root: Path,
    boundary: GitignoreBoundary | None,
) -> dict[Path, GitignoreBoundary | None]:
    """Seed the per-directory boundary map for one os.walk invocation."""
    return {walk_root: boundary}


def _forced_mutation_roots(
    config: MutmutConfig,
    project_boundary: GitignoreBoundary,
    project_root: Path,
) -> list[tuple[Path, GitignoreBoundary | None]]:
    """Return mutation roots the regular mirror walk would prune (M-032).

    ``paths_to_mutate`` entries are force-included by the mutation search
    (``git add -f`` semantics via :func:`_configured_entry_boundary`), while
    the automatic mirror resolves the project tree with normal ``descend()``
    rules and prunes ignored subtrees — so explicitly configured, git-ignored
    mutation roots were mutated but never staged.  This helper derives exactly
    those roots the normal walk would prune, together with the forced boundary
    governing their contents, so preflight and copy phase walk the same
    surface as the mutation search (Q-14).

    Args:
        config: Active ``MutmutConfig`` instance.
        project_boundary: Boundary loaded at *project_root*.
        project_root: Resolved project root.

    Returns:
        Sorted ``(root, boundary)`` pairs; *root* is the canonical
        project-relative walk path of one forced entry.
    """
    forced: list[tuple[tuple[str, ...], Path, GitignoreBoundary | None]] = []
    for raw in config.paths_to_mutate:
        entry = Path(raw)
        try:
            relative = entry.resolve(strict=False).relative_to(project_root)
        except (OSError, ValueError):  # fmt: skip
            continue
        if str(relative) in {".", ""} or not entry.exists():
            continue
        parts = relative.parts
        if _is_staging_skip_dir(parts[-1], at_workspace_root=len(parts) == 1):
            # Only gitignore-based pruning is forced here (M-032 scope); a
            # root the staging filter skips for workspace reasons (venv,
            # caches, …) is not resurrected by being configured.
            continue
        folded = tuple(part.casefold() for part in parts)
        if any(folded[: len(other)] == other for other, _root, _boundary in forced):
            # A descendant of an already forced root shares its walk.
            continue
        parent_boundary = project_boundary.descend(*parts[:-1])
        pruned_by_regular_walk = (
            parent_boundary.excludes_directory(parts[-1])
            if entry.is_dir()
            else parent_boundary.excludes_file(parts[-1])
        )
        if not pruned_by_regular_walk:
            continue
        forced.append(
            (
                folded,
                Path(*parts),
                _configured_entry_boundary(project_boundary, project_root, entry),
            )
        )
    forced.sort(key=lambda item: item[0])
    return [(root, boundary) for _key, root, boundary in forced]


def _iter_mirror_walk_entries(
    *,
    excluded_resolved: frozenset[Path],
    warn_on_skip: bool,
    forced_roots: Sequence[tuple[Path, GitignoreBoundary | None]] = (),
) -> Iterator[tuple[bool, Path, Path]]:
    """Yield ``(is_directory, source, relative_target)`` mirror walk entries.

    Q-14: the namespace preflight (:func:`_iter_automatic_staging_inputs`) and
    the copy phase (:func:`copy_src_dir`) share this single walk source, so
    both model exactly the same surface.  The walked roots are the standard
    ``SOURCE_ROOT_NAMES`` plus the project root plus the forced mutation
    roots of M-032 (git-ignored ``paths_to_mutate`` entries entered with
    ``git add -f`` boundaries).  Directory entries are yielded parents-first;
    ``relative_target`` equals the project-relative source path.

    Args:
        excluded_resolved: Resolved caller-owned paths never staged.
        warn_on_skip: Emit :class:`RuntimeWarning` for pruned links and
            unprovable containment (the copy phase does, the read-only
            preflight stays silent).
        forced_roots: ``(root, boundary)`` pairs from
            :func:`_forced_mutation_roots`.
    """
    project_root = Path.cwd().resolve()
    project_boundary = GitignoreBoundary.load(project_root)

    def skipped(candidate: Path, detail: str) -> None:
        if warn_on_skip:
            _warn_skipped_source_link(candidate, detail)

    walk_roots: list[tuple[Path, GitignoreBoundary | None, bool]] = [
        (Path(name), project_boundary.descend(name), False) for name in SOURCE_ROOT_NAMES
    ]
    walk_roots.append((Path(), project_boundary, True))
    walk_roots.extend((root, boundary, False) for root, boundary in forced_roots)
    for source_root, root_boundary, is_dot_root in walk_roots:
        if not source_root.exists():
            continue
        if not source_root.is_dir():
            # A forced single-file mutation root (M-032) is staged as one
            # target without a boundary check, exactly like walk_all_files
            # treats configured file entries.
            try:
                if _is_link_or_reparse(source_root):
                    skipped(source_root, "file links are not copied into executable staging")
                    continue
                resolved = source_root.resolve(strict=True)
                resolved.relative_to(project_root)
            except (OSError, ValueError) as exc:
                skipped(source_root, f"cannot prove project containment ({exc})")
                continue
            if resolved in excluded_resolved:
                continue
            yield False, source_root, source_root
            continue
        boundaries = _walk_boundary_map(source_root, root_boundary)
        for root_str, dirs, files in os.walk(source_root):
            source_directory = Path(root_str)
            boundary = boundaries.get(source_directory)
            try:
                if _is_link_or_reparse(source_directory):
                    skipped(
                        source_directory,
                        "directory links are not copied into executable staging",
                    )
                    dirs[:] = []
                    continue
                source_directory.resolve(strict=True).relative_to(project_root)
            except (OSError, ValueError) as exc:
                skipped(source_directory, f"cannot prove project containment ({exc})")
                dirs[:] = []
                continue
            # Skip cache/venv/tooling directories (issue #129 / 360°-C4) and
            # git-ignored subtrees (MBR-2026-09-14-01).
            safe_dirs: list[str] = []
            at_workspace_root = source_directory.resolve() == project_root
            for directory in dirs:
                if _is_staging_skip_dir(directory, at_workspace_root=at_workspace_root):
                    continue
                if boundary is not None and boundary.excludes_directory(directory):
                    continue
                candidate = source_directory / directory
                try:
                    if _is_link_or_reparse(candidate):
                        skipped(
                            candidate,
                            "directory links are not copied into executable staging",
                        )
                        continue
                    candidate.resolve().relative_to(project_root)
                except (OSError, ValueError) as exc:
                    skipped(candidate, f"cannot prove project containment ({exc})")
                    continue
                safe_dirs.append(directory)
                if boundary is not None:
                    boundaries[candidate] = boundary.enter(directory)
            dirs[:] = safe_dirs
            if is_dot_root and at_workspace_root:
                # The explicit roots above already mirrored src/source —
                # walking them again from "." doubled the largest trees
                # (issue #129 / 360°-C4). Top level only: a NESTED foo/src
                # is not covered by the explicit roots and must stay.
                source_root_names = {name.casefold() for name in SOURCE_ROOT_NAMES}
                dirs[:] = [name for name in dirs if name.casefold() not in source_root_names]
            yield True, source_directory, source_directory
            for name in files:
                if _skip_automatic_root_file(name):
                    continue
                if boundary is not None and boundary.excludes_file(name):
                    continue
                source = source_directory / name
                try:
                    if _is_link_or_reparse(source):
                        skipped(source, "file links are not copied into executable staging")
                        continue
                    resolved = source.resolve(strict=True)
                    resolved.relative_to(project_root)
                except (OSError, ValueError) as exc:
                    skipped(source, f"cannot prove project containment ({exc})")
                    continue
                if resolved in excluded_resolved:
                    continue
                yield False, source, source


def _is_staging_skip_dir(name: str, *, at_workspace_root: bool) -> bool:
    """Apply root-only and recursive exclusions with Windows case-folding."""
    folded = name.casefold()
    return folded in _STAGING_RECURSIVE_SKIP_DIRS or (
        at_workspace_root and folded in _STAGING_SKIP_DIRS
    )


def _is_link_or_reparse(path: Path) -> bool:
    metadata = path.lstat()
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    attributes = getattr(metadata, "st_file_attributes", 0)
    junction_check = getattr(path, "is_junction", None)
    return bool(
        stat.S_ISLNK(metadata.st_mode)
        or (reparse_flag and attributes & reparse_flag)
        or (callable(junction_check) and junction_check())
    )


def _retry_readonly_removal(
    operation: Callable[[str], object],
    raw_path: str,
    error: BaseException,
) -> None:
    """Retry deletion after safely clearing an owned staging attribute.

    A DOS read-only attribute is shared by every hardlink to the same file.
    Clearing it before proving sole staging ownership could therefore mutate a
    live file outside ``mutants/`` even though the subsequent unlink remains
    contained.  Freeze and revalidate the staging identity on both sides of
    ``chmod`` and restore the original mode when deletion does not complete.
    """

    if not isinstance(error, PermissionError):
        raise error
    path, metadata = _checked_owned_staging_leaf(Path(raw_path), allow_directory=True)
    identity = _staging_identity(metadata)
    original_mode = stat.S_IMODE(metadata.st_mode)
    mode_changed = False
    try:
        path.chmod(original_mode | stat.S_IWRITE, follow_symlinks=False)
        mode_changed = True
        _require_same_owned_staging_leaf(path, identity, allow_directory=True)
        operation(raw_path)
    finally:
        if mode_changed:
            _restore_staging_leaf_mode(path, identity, original_mode)


def _unlink_staging_file(path: Path) -> None:
    """Delete one owned staging file, including copy2-preserved read-only files."""

    try:
        path.unlink(missing_ok=True)
    except PermissionError as exc:
        _retry_readonly_removal(os.unlink, str(path), exc)


def _warn_skipped_source_link(path: Path, detail: str) -> None:
    warnings.warn(
        f"Skipping linked or redirected source path {path}: {detail}",
        RuntimeWarning,
        stacklevel=3,
    )


def _validated_mutants_root() -> Path:
    """Return the canonical staging root, rejecting root redirection."""
    project_root = Path.cwd().resolve()
    expected = project_root / "mutants"
    try:
        resolved = Path("mutants").resolve(strict=False)
    except (OSError, RuntimeError) as exc:
        raise UnsafeStagingError(f"Cannot resolve staging root {expected}: {exc}") from exc
    if resolved != expected:
        raise UnsafeStagingError(
            f"Unsafe staging root {expected}: resolves through a symlink/junction to {resolved}"
        )
    return expected


def validate_staging_root() -> Path:
    """Return the canonical local staging root or fail closed if redirected."""
    return _validated_mutants_root()


def purge_staging_runtime_artifacts() -> None:
    """Remove inherited interpreter/tool state before freezing ``mutants/``.

    CPython consumes ``UNCHECKED_HASH`` bytecode without comparing it with the
    staged source.  Merely skipping ``__pycache__`` in a digest therefore
    allowed a stale or test-written pyc to turn survivors into false kills.
    The executable staging contract contains source/config/fixture bytes only:
    recursive tool-cache directories and sourceless ``*.pyc``/``*.pyo`` files
    are removed before the snapshot.  Any such entry created later is included
    in the full staging digest and makes the run fail closed.
    """

    mutants_root = _validated_mutants_root()
    staging = Path("mutants")
    if not staging.is_dir():
        return
    recursive_runtime_dirs = {name.casefold() for name in _STAGING_RECURSIVE_SKIP_DIRS}
    for root_str, dirs, files in os.walk(staging, topdown=True):
        directory = Path(root_str)
        retained: list[str] = []
        for name in dirs:
            candidate = directory / name
            if name.casefold() not in recursive_runtime_dirs:
                retained.append(name)
                continue
            _validated_staging_destination(candidate, mutants_root)
            shutil.rmtree(candidate, onexc=_retry_readonly_removal)
        dirs[:] = retained
        for name in files:
            if Path(name).suffix.casefold() not in {".pyc", ".pyo"}:
                continue
            candidate = directory / name
            _validated_staging_destination(candidate, mutants_root)
            _unlink_staging_file(candidate)


def _validated_staging_destination(destination: Path, mutants_root: Path) -> Path:
    """Return a contained lexical staging path with no redirected component."""
    lexical = destination.absolute()

    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    for component in reversed((lexical, *lexical.parents)):
        try:
            metadata = component.lstat()
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise UnsafeStagingError(
                f"Cannot inspect staging destination component {component}: {exc}"
            ) from exc
        attributes = getattr(metadata, "st_file_attributes", 0)
        junction_check = getattr(component, "is_junction", None)
        if (
            stat.S_ISLNK(metadata.st_mode)
            or bool(reparse_flag and attributes & reparse_flag)
            or (callable(junction_check) and junction_check())
        ):
            raise UnsafeStagingError(
                f"Unsafe staging destination {destination}: component {component} "
                "is a symlink/junction or reparse point"
            )
        if component != lexical and not stat.S_ISDIR(metadata.st_mode):
            raise UnsafeStagingError(
                f"Unsafe staging destination {destination}: parent component "
                f"{component} is not a directory"
            )
    try:
        resolved = destination.resolve(strict=False)
    except (OSError, RuntimeError) as exc:
        raise UnsafeStagingError(
            f"Cannot resolve staging destination {destination}: {exc}"
        ) from exc
    try:
        resolved.relative_to(mutants_root)
    except ValueError as exc:
        raise UnsafeStagingError(
            f"Unsafe staging destination {destination}: path escapes {mutants_root}"
        ) from exc
    return lexical


def _remove_staging_entry(lexical: Path, metadata: os.stat_result) -> None:
    """Remove one contained staging entry regardless of kind (Q-13).

    Directories go through ``rmtree`` with the read-only-aware ``onexc``
    hook, regular files through the owned-unlink helper.  A bounded retry
    with the same backoff as :func:`_copy_with_retry` absorbs transient
    Windows locks (Defender, Search Indexer) before the caller converts the
    failure into a domain error.
    """
    for attempt in range(5):
        try:
            if stat.S_ISDIR(metadata.st_mode):
                shutil.rmtree(lexical, onexc=_retry_readonly_removal)
            elif stat.S_ISREG(metadata.st_mode):
                _unlink_staging_file(lexical)
            else:
                raise UnsafeStagingError(
                    f"Unsafe staging entry {lexical}: not a regular file or directory"
                )
            return
        except UnsafeStagingError:
            raise
        except OSError:
            if attempt == 4:
                raise
            time.sleep(0.1 * (2**attempt))


def _reconcile_staging_kind(
    target: Path,
    *,
    want_directory: bool,
    mutants_root: Path,
) -> None:
    """Reconcile a staging target's kind before materializing it (Q-13).

    A mirror target whose live counterpart switched between file and
    directory used to abort the run with a raw ``FileExistsError`` (``mkdir``
    over a staged file) or ``PermissionError`` (``os.replace`` onto a staged
    directory) long before the deletion pass could react (M-030).  Before
    every materialization the staged entry's kind is checked against what
    this run is about to create; a conflicting entry is removed after
    revalidated containment.  Links/reparse points and entries that cannot
    be removed safely become :class:`UnsafeStagingError` — a single-line
    domain error instead of a traceback.

    The staging root itself is never reconciled away (requesting it as a
    file is refused), and persistent staging state files at the root are
    explicitly excluded.

    Args:
        target: Staging path about to be materialized.
        want_directory: Whether the upcoming materialization is a directory.
        mutants_root: Canonical staging root for containment revalidation.
    """
    lexical = _validated_staging_destination(target, mutants_root)
    if lexical == mutants_root:
        if want_directory:
            # The engine-owned staging root already exists as a directory;
            # materializing it again is a no-op.
            return
        raise UnsafeStagingError(f"Refusing to replace the staging root {mutants_root} with a file")
    if (
        lexical.parent == mutants_root
        and lexical.name.casefold() in _PERSISTENT_STAGING_STATE_FILES
    ):
        raise UnsafeStagingError(f"Refusing to replace persistent staging state file {lexical}")
    try:
        metadata = lexical.lstat()
    except (FileNotFoundError, NotADirectoryError):  # fmt: skip
        return  # absent, or under a vanished parent: nothing to reconcile
    except OSError as exc:
        raise UnsafeStagingError(f"Cannot inspect staging target {lexical}: {exc}") from exc
    if _is_link_or_reparse(lexical):
        raise UnsafeStagingError(
            f"Staging type conflict at {lexical}: link/reparse point is never replaced"
        )
    staged_is_directory = stat.S_ISDIR(metadata.st_mode)
    if want_directory:
        if staged_is_directory:
            return
    elif stat.S_ISREG(metadata.st_mode):
        return
    staged_kind = "directory" if staged_is_directory else "file"
    wanted_kind = "directory" if want_directory else "file"
    try:
        _remove_staging_entry(lexical, metadata)
    except OSError as exc:
        raise UnsafeStagingError(
            f"Staging type conflict at {lexical}: expected {wanted_kind}, "
            f"found {staged_kind}; cannot remove the staged {staged_kind} ({exc})"
        ) from exc
    print(f"     replaced staged {staged_kind} after type change: {lexical}")


def _staging_identity(metadata: os.stat_result) -> tuple[int, int]:
    """Return the stable filesystem identity used by staging attribute guards."""

    identity = (int(metadata.st_dev), int(metadata.st_ino))
    if identity[1] == 0:
        raise UnsafeStagingError("Cannot establish a stable identity for a staging leaf")
    return identity


def _checked_owned_staging_leaf(
    path: Path,
    *,
    allow_directory: bool = False,
) -> tuple[Path, os.stat_result]:
    """Return one contained, non-redirected, solely owned staging leaf."""

    mutants_root = _validated_mutants_root()
    lexical = _validated_staging_destination(path, mutants_root)
    if lexical == mutants_root:
        raise UnsafeStagingError("Refusing to change attributes on the staging root itself")
    try:
        metadata = lexical.lstat()
    except OSError as exc:
        raise UnsafeStagingError(f"Cannot inspect staging leaf {lexical}: {exc}") from exc

    is_regular = stat.S_ISREG(metadata.st_mode)
    if not is_regular and not (allow_directory and stat.S_ISDIR(metadata.st_mode)):
        raise UnsafeStagingError(f"Unsafe staging leaf {lexical}: not a regular owned file")
    if is_regular and metadata.st_nlink != 1:
        raise UnsafeStagingError(
            f"Unsafe staging leaf {lexical}: read-only file has {metadata.st_nlink} hardlinks"
        )
    _staging_identity(metadata)
    return lexical, metadata


def _require_same_owned_staging_leaf(
    path: Path,
    identity: tuple[int, int],
    *,
    allow_directory: bool = False,
) -> os.stat_result:
    """Revalidate that *path* still names the frozen owned staging leaf."""

    _lexical, metadata = _checked_owned_staging_leaf(
        path,
        allow_directory=allow_directory,
    )
    if _staging_identity(metadata) != identity:
        raise UnsafeStagingError(f"Unsafe staging leaf {path}: identity changed during operation")
    return metadata


def _restore_staging_leaf_mode(path: Path, identity: tuple[int, int], mode: int) -> None:
    """Best-effort restore *mode* only while the frozen leaf still owns *path*."""

    try:
        metadata = path.lstat()
    except OSError:
        return
    try:
        if _staging_identity(metadata) != identity:
            return
    except UnsafeStagingError:
        return
    with contextlib.suppress(OSError):
        path.chmod(mode, follow_symlinks=False)


@contextlib.contextmanager
def _temporarily_writable_staging_leaf(path: Path) -> Iterator[None]:
    """Make an existing read-only Windows staging leaf replaceable, safely.

    Windows refuses an atomic replace when the existing destination carries
    the DOS read-only attribute.  The exception is intentionally limited to a
    regular, non-reparse leaf with one link.  On a successful atomic publish
    the old identity disappears, so its mode is not applied to the new file;
    on failure the old mode is restored in ``finally``.
    """

    if os.name != "nt":
        yield
        return
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        yield
        return
    if stat.S_IMODE(metadata.st_mode) & stat.S_IWRITE:
        yield
        return

    checked_path, metadata = _checked_owned_staging_leaf(path)
    identity = _staging_identity(metadata)
    original_mode = stat.S_IMODE(metadata.st_mode)
    mode_changed = False
    try:
        checked_path.chmod(original_mode | stat.S_IWRITE, follow_symlinks=False)
        mode_changed = True
        current = _require_same_owned_staging_leaf(checked_path, identity)
        if not stat.S_IMODE(current.st_mode) & stat.S_IWRITE:
            raise UnsafeStagingError(
                f"Cannot make read-only staging leaf replaceable: {checked_path}"
            )
        yield
    finally:
        if mode_changed:
            _restore_staging_leaf_mode(checked_path, identity, original_mode)


# ---------------------------------------------------------------------------
# Directory walking helpers
# ---------------------------------------------------------------------------


def walk_all_files(config: MutmutConfig) -> Iterator[tuple[str, str]]:
    """Yield (root, filename) for all files in config.paths_to_mutate.

    Git-ignored subtrees inside a configured mutation root are pruned
    (MBR-2026-09-14-01): ignored files are not mutation targets.  The
    configured entry itself is force-included, matching ``git add -f``
    semantics elsewhere in staging.

    Args:
        config: Active ``MutmutConfig`` instance.

    Yields:
        Tuples of (root directory string, filename string).
    """
    project_root = Path.cwd().resolve()
    project_boundary = GitignoreBoundary.load(project_root)
    for path in config.paths_to_mutate:
        p = Path(path)
        if not p.is_dir():
            if p.is_file():
                yield "", str(path)
                continue
        else:
            entry_boundary = _configured_entry_boundary(project_boundary, project_root, p)
            boundaries: dict[Path, GitignoreBoundary | None] = _walk_boundary_map(p, entry_boundary)
            for root, dirs, files in os.walk(path):
                walk_directory = Path(root)
                boundary = boundaries.get(walk_directory)
                # Never feed staging/cache/tool environments back into the
                # mutation engine. Resolve children as a junction/symlink
                # defence in addition to the fast name filter.
                safe_dirs: list[str] = []
                at_workspace_root = Path(root).resolve() == project_root
                for directory in dirs:
                    if _is_staging_skip_dir(directory, at_workspace_root=at_workspace_root):
                        continue
                    if boundary is not None and boundary.excludes_directory(directory):
                        continue
                    candidate = Path(root) / directory
                    try:
                        if _is_link_or_reparse(candidate):
                            _warn_skipped_source_link(
                                candidate,
                                "directory links are not traversed during mutation discovery",
                            )
                            continue
                        candidate.resolve().relative_to(project_root)
                    except (OSError, ValueError) as exc:
                        _warn_skipped_source_link(
                            candidate, f"cannot prove project containment ({exc})"
                        )
                        continue
                    safe_dirs.append(directory)
                    if boundary is not None:
                        boundaries[candidate] = boundary.enter(directory)
                dirs[:] = safe_dirs
                for filename in files:
                    if boundary is not None and boundary.excludes_file(filename):
                        continue
                    candidate = Path(root) / filename
                    try:
                        if _is_link_or_reparse(candidate):
                            _warn_skipped_source_link(
                                candidate,
                                "file links are not mutation inputs",
                            )
                            continue
                        candidate.resolve().relative_to(project_root)
                    except (OSError, ValueError) as exc:
                        # A file symlink can escape even when its containing
                        # directory is inside the project. Never feed that
                        # external target to staging/mutation implicitly.
                        _warn_skipped_source_link(
                            candidate, f"cannot prove project containment ({exc})"
                        )
                        continue
                    yield root, filename


def walk_source_files(config: MutmutConfig) -> Iterator[Path]:
    """Yield Path objects for all .py source files in config.paths_to_mutate.

    Args:
        config: Active ``MutmutConfig`` instance.

    Yields:
        ``Path`` objects pointing to Python source files.
    """
    for root, filename in walk_all_files(config):
        if filename.casefold().endswith(".py"):
            yield Path(root) / filename


def _staging_key(path: Path) -> tuple[str, ...]:
    """Return a Windows-identity key for a staging-relative path."""

    return tuple(part.casefold() for part in path.parts if part not in {"", "."})


def _iter_automatic_staging_inputs(
    excluded_resolved: frozenset[Path],
    *,
    forced_roots: Sequence[tuple[Path, GitignoreBoundary | None]] = (),
) -> Iterator[tuple[Path, Path]]:
    """Yield file/directory ownership planned for the automatic root mirror.

    The walk itself comes from :func:`_iter_mirror_walk_entries` (Q-14), the
    single walk source shared with :func:`copy_src_dir`.  *forced_roots*
    (M-032) adds the git-ignored mutation roots the regular walk would prune,
    so the namespace preflight models exactly the surface the copy phase
    stages — mutation search and mirror no longer disagree about explicitly
    configured entries.
    """

    for is_directory, source, relative_target in _iter_mirror_walk_entries(
        excluded_resolved=excluded_resolved,
        warn_on_skip=False,
        forced_roots=forced_roots,
    ):
        if is_directory:
            if _staging_key(relative_target):
                # ``mutants/`` itself is the engine-owned staging root, not a
                # project input that conflicts with every configured mirror
                # nested below it.  Descendant directories remain explicit
                # ownership entries so empty namespace packages participate
                # in collision preflight.
                yield source, relative_target
            continue
        yield source, relative_target


def _iter_configured_staging_inputs(
    config: MutmutConfig,
    excluded_resolved: frozenset[Path],
) -> Iterator[tuple[Path, Path]]:
    """Yield planned file mirrors from ``also_copy`` and ``extra_paths``.

    Explicitly configured entries are force-included (``git add -f``
    semantics), but git-ignored subtrees *inside* a configured tree are
    pruned exactly like Git would prune them.
    """

    project_root = Path.cwd().resolve()
    mutants_root = project_root / "mutants"
    project_boundary = GitignoreBoundary.load(project_root)
    for raw in (*config.also_copy, *config.extra_paths):
        path = Path(raw)
        destination = configured_staging_relative_path(path, project_root=project_root)
        if destination is None:
            continue
        if _is_staging_skip_dir(path.name, at_workspace_root=True):
            continue
        try:
            resolved_path = path.resolve()
            if resolved_path in (project_root, mutants_root):
                continue
        except (
            OSError,
            RuntimeError,
        ):  # fmt: skip
            continue
        if not path.exists():
            continue
        if path.is_file():
            try:
                if path.resolve(strict=True) not in excluded_resolved:
                    yield path, destination
            except OSError:
                continue
            continue
        entry_boundary = _configured_entry_boundary(project_boundary, project_root, path)
        boundaries = _walk_boundary_map(path, entry_boundary)
        for root_str, dirs, files in os.walk(path):
            walk_directory = Path(root_str)
            boundary = boundaries.get(walk_directory)
            safe_dirs: list[str] = []
            for name in dirs:
                if _is_staging_skip_dir(name, at_workspace_root=False):
                    continue
                if boundary is not None and boundary.excludes_directory(name):
                    continue
                safe_dirs.append(name)
                if boundary is not None:
                    boundaries[walk_directory / name] = boundary.enter(name)
            dirs[:] = safe_dirs
            relative_root = Path(root_str).relative_to(path)
            yield Path(root_str), destination / relative_root
            for name in files:
                if boundary is not None and boundary.excludes_file(name):
                    continue
                source = Path(root_str) / name
                try:
                    if source.resolve(strict=True) in excluded_resolved:
                        continue
                except OSError:
                    continue
                yield source, destination / relative_root / name


def _helper_owner_for_target(
    target: Path,
    *,
    active_helpers: dict[str, str],
    import_roots: Sequence[Path],
    is_directory: bool = False,
) -> str | None:
    """Return the internal owner shadowed by one planned import target."""

    key = _staging_key(target)
    for configured_root in import_roots:
        import_root = _staging_key(configured_root)
        if key[: len(import_root)] != import_root or len(key) <= len(import_root):
            continue
        remainder = key[len(import_root) :]
        first = remainder[0]
        for module_name, owner in active_helpers.items():
            folded_module = module_name.casefold()
            # An empty directory is already a PEP 420 namespace. Publishing
            # the helper would replace its import identity even without any
            # descendant files. A same-named extensionless regular file is
            # ordinary user data and must remain allowed (CX221-068).
            if first == folded_module and (len(remainder) > 1 or is_directory):
                return owner
            if len(remainder) == 1 and any(
                first == f"{folded_module}{suffix.casefold()}"
                for suffix in (".py", *importlib.machinery.EXTENSION_SUFFIXES)
            ):
                return owner
    return None


_LiveInputRelation = Literal[
    "same",
    "different",
    "left_missing",
    "right_missing",
    "both_missing",
]


def _live_input_is_gone(path: Path) -> bool:
    """Return whether *path* is provably absent (fail-closed otherwise).

    Existence is decided per ``lstat`` with separate exception branches: a
    missing path component (``FileNotFoundError``/``NotADirectoryError``) is
    "gone", while any other :class:`OSError` propagates so the caller keeps
    treating the identity as unprovable instead of fail-open guessing (an
    ``os.path.lexists`` probe can report ``False`` on permission errors).
    """
    try:
        path.lstat()
    except (FileNotFoundError, NotADirectoryError):  # fmt: skip
        return True
    return False


def _live_input_relation(left: Path, right: Path) -> _LiveInputRelation:
    """Classify whether two planned live inputs denote the same object.

    ``samefile``/``resolve`` identity is only meaningful while both entries
    exist; a deleted file made the historical boolean helper answer "different"
    for what is really "not determinable" and turned vanished inputs into
    false namespace collisions (M-033).  The relation therefore distinguishes:

    * ``same``/``different`` — both exist and the identity was decided;
    * ``left_missing``/``right_missing``/``both_missing`` — the vanished
      side(s) stage nothing anymore, so they cannot collide;
    * ``different`` — also the fail-closed verdict when an :class:`OSError`
      other than absence prevents proving the identity (e.g. a
      :class:`PermissionError`).
    """
    try:
        return "same" if left.samefile(right) else "different"
    except FileNotFoundError, NotADirectoryError:
        try:
            left_gone = _live_input_is_gone(left)
            right_gone = _live_input_is_gone(right)
        except OSError:
            # Absence is not provable either — stay fail-closed.
            return "different"
        if left_gone and right_gone:
            return "both_missing"
        if left_gone:
            return "left_missing"
        if right_gone:
            return "right_missing"
        # Both entries (re)appeared after samefile failed: a race decided to
        # resolve both paths again before falling back to the lexical match.
    except OSError:
        return "different"
    try:
        if os.path.normcase(str(left.resolve(strict=True))) == os.path.normcase(
            str(right.resolve(strict=True))
        ):
            return "same"
    except OSError:
        return "different"
    return "different"


def _same_live_input(left: Path, right: Path) -> bool:
    """Return whether two planned sources identify the same live object."""
    return _live_input_relation(left, right) == "same"


def _same_planned_input(left: Path, right: Path) -> bool:
    """Compare configured input identities even when both paths are absent."""

    try:
        return os.path.normcase(str(left.resolve(strict=False))) == os.path.normcase(
            str(right.resolve(strict=False))
        )
    except (
        OSError,
        RuntimeError,
    ):  # fmt: skip
        return False


def _iter_configured_staging_roots(
    config: MutmutConfig,
    excluded_resolved: frozenset[Path],
) -> Iterator[tuple[Path, Path]]:
    """Yield canonical live roots and their staging-relative destinations."""

    project_root = Path.cwd().resolve()
    mutants_root = project_root / "mutants"
    for raw in (*config.also_copy, *config.extra_paths):
        path = Path(raw)
        destination = configured_staging_relative_path(path, project_root=project_root)
        if destination is None or _is_staging_skip_dir(path.name, at_workspace_root=True):
            continue
        try:
            source = path.resolve(strict=True)
        except OSError:
            continue
        if source in excluded_resolved or source in (project_root, mutants_root):
            continue
        if source.is_file() or source.is_dir():
            yield source, destination


def _iter_missing_configured_staging_roots(
    config: MutmutConfig,
    excluded_resolved: frozenset[Path],
) -> Iterator[tuple[Path, Path]]:
    """Yield absent configured inputs whose staging targets would be removed.

    A missing ``also_copy``/``extra_paths`` entry is not a no-op: the copy
    phase deletes its previous destination so stale executable bytes cannot
    survive.  The preflight must therefore model that destructive ownership
    even though there is no live source to enumerate.
    """

    project_root = Path.cwd().resolve()
    mutants_root = project_root / "mutants"
    for raw in (*config.also_copy, *config.extra_paths):
        path = Path(raw)
        destination = configured_staging_relative_path(path, project_root=project_root)
        if destination is None or _is_staging_skip_dir(path.name, at_workspace_root=True):
            continue
        if path.exists():
            continue
        try:
            source = path.resolve(strict=False)
        except (
            OSError,
            RuntimeError,
        ):  # fmt: skip
            source = path.absolute()
        if source in excluded_resolved or source in (project_root, mutants_root):
            continue
        yield source, destination


def _staging_targets_overlap(left: Path, right: Path) -> bool:
    """Return whether either staging target contains the other on Windows."""

    left_key = _staging_key(left)
    right_key = _staging_key(right)
    if not left_key or not right_key:
        return left_key == right_key
    return left_key[: len(right_key)] == right_key or right_key[: len(left_key)] == left_key


def _mapped_live_input(root_source: Path, root_target: Path, target: Path) -> Path | None:
    """Map one descendant staging target back through a configured live root."""

    root_key = _staging_key(root_target)
    target_key = _staging_key(target)
    if target_key[: len(root_key)] != root_key:
        return None
    relative_parts = target.parts[len(root_target.parts) :]
    if not relative_parts:
        return root_source
    if not root_source.is_dir():
        return None
    return root_source.joinpath(*relative_parts)


def validate_staging_namespace(
    config: MutmutConfig,
    *,
    excluded_paths: Sequence[Path] = (),
) -> None:
    """Reject live inputs that collide with mutmut-win-owned staging paths.

    This is a read-only preflight. It models both automatic and configured
    mirrors, compares with Windows case-insensitive identity, and runs before
    ``--force``, cache creation, or staging publication. It is repeated at
    the copy boundary to narrow the validation/use race.
    """

    excluded_resolved: set[Path] = set()
    for excluded in excluded_paths:
        try:
            excluded_resolved.add(excluded.resolve())
        except OSError:
            continue
    frozen_exclusions = frozenset(excluded_resolved)

    exact_owners = {
        _staging_key(Path(name)): owner for name, owner in _FIXED_STAGING_ARTIFACT_OWNERS.items()
    }
    for source in _selected_mutation_sources(config):
        metadata_target = Path(f"{source}.meta")
        exact_owners[_staging_key(metadata_target)] = f"mutation metadata for {source}"

    active_helpers = dict(_STAGING_HELPER_MODULE_OWNERS)
    if not any(Path(name).is_dir() for name in SOURCE_ROOT_NAMES):
        # No editable source root means the runner deliberately does not
        # publish its sitecustomize blocker; a flat-layout project may retain
        # its own startup module without colliding.
        active_helpers.pop("sitecustomize")

    import_roots = [Path(), *(Path(name) for name in SOURCE_ROOT_NAMES)]
    project_root = Path.cwd().resolve()
    for raw in config.extra_paths:
        extra_path = configured_staging_relative_path(raw, project_root=project_root)
        if extra_path is not None:
            import_roots.append(extra_path)

    collisions: set[tuple[str, str, str]] = set()
    forced_roots = _forced_mutation_roots(
        config,
        GitignoreBoundary.load(project_root),
        project_root,
    )
    automatic_inputs = list(
        _iter_automatic_staging_inputs(frozen_exclusions, forced_roots=forced_roots)
    )
    configured_inputs = list(_iter_configured_staging_inputs(config, frozen_exclusions))
    planned_inputs = itertools.chain(automatic_inputs, configured_inputs)
    target_owners: dict[tuple[str, ...], tuple[Path, str]] = {}
    for source, target in planned_inputs:
        target_key = _staging_key(target)
        previous = target_owners.get(target_key)
        if previous is not None:
            relation = _live_input_relation(previous[0], source)
            if relation in {"right_missing", "both_missing"}:
                # M-033: the entry vanished after the planned inputs were
                # frozen — nothing will be staged from it, so it neither
                # collides nor owns the target, and no reserved-name check
                # applies.  copy_src_dir repeats this validation at the copy
                # boundary, where the walk no longer sees the file at all.
                continue
            if relation != "different":
                # Identical, or the previous owner itself vanished and the
                # current source takes over the target.
                target_owners[target_key] = (source, str(source))
            else:
                collisions.add(
                    (
                        str(target),
                        str(source),
                        f"another live staging input {previous[1]}",
                    )
                )
        else:
            target_owners[target_key] = (source, str(source))
        owner = exact_owners.get(_staging_key(target))
        if owner is None:
            owner = _helper_owner_for_target(
                target,
                active_helpers=active_helpers,
                import_roots=import_roots,
                is_directory=source.is_dir(),
            )
        if owner is not None:
            collisions.add((str(target), str(source), owner))

    configured_roots = list(_iter_configured_staging_roots(config, frozen_exclusions))
    for configured_source, configured_target in configured_roots:
        configured_key = _staging_key(configured_target)
        for automatic_source, automatic_target in automatic_inputs:
            automatic_key = _staging_key(automatic_target)
            if automatic_key[: len(configured_key)] == configured_key:
                expected_source = _mapped_live_input(
                    configured_source,
                    configured_target,
                    automatic_target,
                )
                # M-033: a vanished automatic input stages nothing and cannot
                # collide — regardless of the configured side (the trigger's
                # expected_source denotes the very same deleted file).  A
                # vanished configured-side descendant with a still-live
                # automatic source stays a collision: the configured mirror's
                # deletion pass would erase that automatic copy.
                if expected_source is None or _live_input_relation(
                    expected_source, automatic_source
                ) in {"different", "left_missing"}:
                    collisions.add(
                        (
                            str(configured_target),
                            str(configured_source),
                            f"automatic project input {automatic_source}",
                        )
                    )
            elif configured_key[: len(automatic_key)] == automatic_key:
                expected_source = _mapped_live_input(
                    automatic_source,
                    automatic_target,
                    configured_target,
                )
                if expected_source is None or not _same_live_input(
                    expected_source, configured_source
                ):
                    collisions.add(
                        (
                            str(configured_target),
                            str(configured_source),
                            f"automatic project input {automatic_source}",
                        )
                    )

    for index, (left_source, left_target) in enumerate(configured_roots):
        left_key = _staging_key(left_target)
        for right_source, right_target in configured_roots[index + 1 :]:
            right_key = _staging_key(right_target)
            if right_key[: len(left_key)] == left_key:
                mapped_left = _mapped_live_input(left_source, left_target, right_target)
                if mapped_left is not None and _same_live_input(mapped_left, right_source):
                    continue
            elif left_key[: len(right_key)] == right_key:
                mapped_right = _mapped_live_input(right_source, right_target, left_target)
                if mapped_right is not None and _same_live_input(mapped_right, left_source):
                    continue
            else:
                continue
            collisions.add(
                (
                    str(right_target),
                    str(right_source),
                    f"configured staging input {left_source} at mutants/{left_target}",
                )
            )

    # Missing configured inputs still own a cleanup destination.  Reject any
    # overlap with a live mirror before ``copy_src_dir`` creates or changes a
    # staging file; otherwise ``copy_also_copy_files`` could erase an
    # automatic/configured mirror that was copied only moments earlier.
    missing_configured_roots = list(
        _iter_missing_configured_staging_roots(config, frozen_exclusions)
    )
    for missing_source, missing_target in missing_configured_roots:
        owner = exact_owners.get(_staging_key(missing_target))
        if owner is None:
            owner = _helper_owner_for_target(
                missing_target,
                active_helpers=active_helpers,
                import_roots=import_roots,
            )
        if owner is not None:
            collisions.add((str(missing_target), str(missing_source), owner))

        for automatic_source, automatic_target in automatic_inputs:
            if not _staging_targets_overlap(missing_target, automatic_target):
                continue
            automatic_key = _staging_key(automatic_target)
            missing_key = _staging_key(missing_target)
            if missing_key[: len(automatic_key)] == automatic_key:
                mapped_source = _mapped_live_input(
                    automatic_source,
                    automatic_target,
                    missing_target,
                )
                if mapped_source is not None and _same_planned_input(mapped_source, missing_source):
                    # A redundant missing descendant of the same automatic
                    # live directory shares that mirror's cleanup authority.
                    continue
            collisions.add(
                (
                    str(missing_target),
                    str(missing_source),
                    f"automatic project input {automatic_source}",
                )
            )
        for configured_source, configured_target in configured_roots:
            if not _staging_targets_overlap(missing_target, configured_target):
                continue
            configured_key = _staging_key(configured_target)
            missing_key = _staging_key(missing_target)
            if missing_key[: len(configured_key)] == configured_key:
                mapped_source = _mapped_live_input(
                    configured_source,
                    configured_target,
                    missing_target,
                )
                if mapped_source is not None and _same_planned_input(mapped_source, missing_source):
                    # A redundant missing descendant of the same configured
                    # live tree only tightens that tree's stale cleanup.
                    continue
            collisions.add(
                (
                    str(missing_target),
                    str(missing_source),
                    f"configured staging input {configured_source} at mutants/{configured_target}",
                )
            )

    if not collisions:
        return
    details = "\n".join(
        f"- {source} -> mutants/{target}: reserved for {owner}"
        for target, source, owner in sorted(
            collisions,
            key=lambda item: (_staging_key(Path(item[0])), item[1].casefold()),
        )
    )
    raise StagingNamespaceCollisionError(
        "Live project inputs collide with mutmut-win's reserved staging namespace:\n"
        f"{details}\nRename or move the listed project inputs; --force cannot make this safe."
    )


# ---------------------------------------------------------------------------
# Source directory copying
# ---------------------------------------------------------------------------


def _copy_with_retry(
    src: Path,
    dst: Path,
    *,
    is_tree: bool = False,
    max_attempts: int = 5,
    **kwargs: object,
) -> None:
    """Copy a file or directory tree with retry logic for Windows file locks.

    On Windows, recently written files can be temporarily locked by Defender,
    the Search Indexer, or NTFS journaling.  This wrapper retries with
    exponential backoff (0.1 s, 0.2 s, 0.4 s, 0.8 s) before giving up.

    Args:
        src: Source path.
        dst: Destination path.
        is_tree: If True, use ``shutil.copytree`` instead of ``shutil.copy2``.
        max_attempts: Maximum number of attempts before raising.
        **kwargs: Additional keyword arguments forwarded to the copy function.
    """

    def copy_once() -> None:
        if is_tree:
            shutil.copytree(src, dst, **kwargs)  # type: ignore[arg-type]
            return

        # The destination is published through the still-private atomic
        # sibling.  Never close and reopen its random pathname: a directory
        # watcher could otherwise replace it with an external hardlink.
        atomic_copy_file(src, dst)

    publish_guard = contextlib.nullcontext() if is_tree else _temporarily_writable_staging_leaf(dst)
    with publish_guard:
        for attempt in range(max_attempts):
            try:
                copy_once()
                return
            except OSError:
                if attempt < max_attempts - 1:
                    time.sleep(0.1 * (2**attempt))
        # Final attempt — let the exception propagate if it still fails.
        copy_once()


def _atomic_write_text(
    path: Path,
    content: str,
    *,
    encoding: str = "utf-8",
    translate_newlines: bool = True,
) -> str:
    """Publish encoded text and return the SHA-256 of the exact written bytes."""
    path.parent.mkdir(parents=True, exist_ok=True)
    # Keep text-file callers' platform newline behavior. Generated Python opts
    # out because the CST already contains the source's physical newlines.
    if translate_newlines:
        content = content.replace("\n", os.linesep)
    payload = content.encode(encoding)
    with _temporarily_writable_staging_leaf(path):
        atomic_write_bytes(path, payload)
    return hashlib.sha256(payload).hexdigest()


_CODING_COOKIE = re.compile(
    r"(?i)^(?P<prefix>[ \t\f]*\#.*?coding[:=][ \t]*)(?P<encoding>[-_.a-z0-9]+)"
)


def _decode_python_source(payload: bytes) -> tuple[str, str]:
    """Decode PEP 263 source without changing its physical newline bytes."""
    encoding, _consumed = tokenize.detect_encoding(BytesIO(payload).readline)
    with TextIOWrapper(BytesIO(payload), encoding=encoding, newline="") as source_file:
        return source_file.read(), encoding


def _rewrite_coding_cookie(source: str, encoding: str) -> str:
    # PEP 263 counts physical source lines delimited by LF. ``str.splitlines``
    # also treats NEL, VT, FF and the Unicode line separators as boundaries;
    # one of those characters in physical line 1 must not hide a valid cookie
    # on physical line 2 when generated identifiers require a UTF-8 fallback.
    parts = source.split("\n")
    lines = [f"{part}\n" for part in parts[:-1]]
    if parts[-1]:
        lines.append(parts[-1])
    for index in range(min(2, len(lines))):
        rewritten, count = _CODING_COOKIE.subn(
            lambda match: f"{match.group('prefix')}{encoding}",
            lines[index],
            count=1,
        )
        if count:
            lines[index] = rewritten
            break
    return "".join(lines)


def _atomic_write_generated_python(
    path: Path,
    content: str,
    *,
    source_encoding: str,
) -> str:
    """Publish generated Python without contradicting its PEP 263 cookie."""
    try:
        return _atomic_write_text(path, content, encoding=source_encoding, translate_newlines=False)
    except UnicodeEncodeError:
        # Generated private method identifiers can contain the Unicode scope
        # separator even when the user source is cp1252/latin-1.  Staging is an
        # internal derivative, so normalize it to UTF-8 and update the cookie;
        # ``apply`` still writes the public source in its original encoding.
        utf8_content = _rewrite_coding_cookie(content, "utf-8")
        return _atomic_write_text(path, utf8_content, encoding="utf-8", translate_newlines=False)


def copy_src_dir(
    config: MutmutConfig,
    *,
    excluded_paths: Sequence[Path] = (),
) -> None:
    """Copy the ENTIRE source tree to the mutants/ staging directory.

    Copies ALL files from standard source directories (the
    ``SOURCE_ROOT_NAMES`` roots plus the project root) — not just the files
    in ``paths_to_mutate``.  This ensures that non-mutated modules are
    available for import when pytest runs inside ``mutants/``.  Without
    this, cross-package imports in conftest.py fail.

    ``paths_to_mutate`` only controls which files get **mutated**, not
    which files get **copied**.

    Updates files whose exact content differs from the last copy.  Stat data
    is only a cheap pre-check for plain mirrors; SHA-256 equality is the reuse
    authority for both plain and generator-owned files (see
    :func:`_mirror_is_stale`).

    Git-ignored ``paths_to_mutate`` roots are walked with ``git add -f``
    boundaries (:func:`_forced_mutation_roots`, M-032) so mutation targets
    keep their whole tree — non-.py resources included — in executable
    staging.  The walk itself comes from :func:`_iter_mirror_walk_entries`
    (Q-14), the single source shared with the namespace preflight.
    Type changes (file <-> directory) of a mirrored path are reconciled
    before every materialization (:func:`_reconcile_staging_kind`, Q-13).

    Args:
        config: Active ``MutmutConfig`` instance.
        excluded_paths: Exact project files owned by the caller that must not
            enter staging. This is intentionally path-specific: broad suffix
            exclusions would also drop legitimate test fixtures such as
            ``tests/fixture.sqlite``.
    """
    validate_staging_namespace(config, excluded_paths=excluded_paths)
    expected_targets: set[Path] = set()
    # Track every automatic mirror root, including the project-root grab-bag
    # and the forced mutation roots (M-032).  The deletion pass is deliberately
    # limited to Python modules and their metadata, so generated non-source
    # artifacts remain distinguishable while deleted root-level imports cannot
    # haunt the next clean run; the project root subsumes the explicit
    # src/source mirrors.
    synced_roots: list[Path] = [Path()]
    # Retain policy (M-002): generator output survives only for files the
    # current run still (re)generates AND only outside the coverage mode.
    retained_generation_keys = _generation_target_keys(config)
    project_root = Path.cwd().resolve()
    project_boundary = GitignoreBoundary.load(project_root)
    forced_roots = _forced_mutation_roots(config, project_boundary, project_root)
    mutants_root = _validated_mutants_root()
    Path("mutants").mkdir(exist_ok=True)
    excluded_resolved: set[Path] = set()
    for excluded in excluded_paths:
        try:
            excluded_resolved.add(excluded.resolve())
        except OSError:
            # A missing or temporarily inaccessible caller-owned path cannot
            # be encountered by the file walk below either.
            continue

    for is_directory, source, relative_target in _iter_mirror_walk_entries(
        excluded_resolved=frozenset(excluded_resolved),
        warn_on_skip=True,
        forced_roots=forced_roots,
    ):
        if is_directory:
            # Directory entries are import-visible under PEP 420 even when
            # they contain no files.  Materialize every validated live
            # directory so a clean first run has the same namespace-package
            # topology as the project; excluded/link roots were pruned above.
            # Type changes are reconciled before materialization (Q-13).
            target_directory = Path("mutants") / relative_target
            _reconcile_staging_kind(
                target_directory, want_directory=True, mutants_root=mutants_root
            )
            target_directory.mkdir(exist_ok=True, parents=True)
            continue

        target_path = Path("mutants") / relative_target
        _reconcile_staging_kind(target_path, want_directory=False, mutants_root=mutants_root)
        expected_targets.add(target_path)

        if target_path.exists():
            if source.is_file():
                retain = _staging_key(source) in retained_generation_keys
                if _mirror_is_stale(source, target_path, retain_generated=retain):
                    removed_sidecar = _refresh_staged_mirror(source, target_path)
                    if removed_sidecar:
                        print(f"     restored unmutated: {source} (not retained for this run)")
                    else:
                        print(f"     updated: {source} (source changed since last run)")
            continue

        target_path.parent.mkdir(exist_ok=True, parents=True)
        _copy_with_retry(source, target_path)

    _sync_deleted_sources(
        expected_targets,
        synced_roots,
        set(_STAGING_RECURSIVE_SKIP_DIRS),
        _configured_mirror_destinations(config, mutants_root),
    )
    # Heal staging created before run-lock and dotenv files were excluded.
    for candidate in Path("mutants").rglob("*"):
        if _skip_automatic_root_file(candidate.name):
            _validated_staging_destination(candidate, mutants_root)
            with contextlib.suppress(OSError):
                candidate.unlink()


def _selected_mutation_sources(config: MutmutConfig) -> Iterator[Path]:
    """Yield the mutation targets of the run with orchestrator parity.

    Applies the same ``walk_source_files`` + ``resolve()`` deduplication +
    ``should_ignore_for_mutation(str(path))`` filter that
    ``MutationOrchestrator._generate_mutants`` uses, so reservation, retain
    policy, and generation share one selection.
    """
    seen: set[Path] = set()
    for source in walk_source_files(config):
        resolved = source.resolve()
        if resolved in seen or config.should_ignore_for_mutation(str(source)):
            continue
        seen.add(resolved)
        yield source


def _generation_target_keys(config: MutmutConfig) -> frozenset[tuple[str, ...]]:
    """Return the staging keys of files the current run will (re)generate.

    With ``mutate_only_covered_lines`` the set is empty: the coverage phase
    requires unmutated bytes for every target, so no generator output is
    retained in that mode.
    """
    if config.mutate_only_covered_lines:
        return frozenset()
    return frozenset(_staging_key(source) for source in _selected_mutation_sources(config))


def _retain_generation_sidecar(staged: Path, *, companion_is_current: bool) -> bool:
    """Return True if *staged* is a proven-own sidecar kept for result reuse.

    A staged ``.meta`` file survives a deletion pass only when it carries
    the engine's own metadata format (user fixtures in other shapes stay
    untouched by this helper's verdict) and its companion file is still an
    expected, current input — the same rule the automatic-mirror pass has
    applied since issue #129, now shared by configured mirrors.
    """
    if not staged.name.casefold().endswith(".meta"):
        return False
    if not companion_is_current:
        return False
    return read_owned_source_metadata(staged) is not None


def _refresh_staged_mirror(source: Path, target: Path) -> bool:
    """Copy *source* over the staged *target*, invalidating an own sidecar.

    Returns:
        True if a proven-own generation sidecar next to *target* was removed.

    A staged ``<name>.meta`` is only treated as a generator sidecar when no
    live ``<source>.meta`` fixture exists — that fixture's staged copy is an
    independent mirror target, not engine metadata.
    """
    meta_path = target.with_name(target.name + ".meta")
    live_meta = source.with_name(source.name + ".meta")
    owned_sidecar = read_owned_source_metadata(meta_path) is not None and not live_meta.exists()
    _copy_with_retry(source, target)
    if owned_sidecar and meta_path.exists():
        _unlink_staging_file(meta_path)
        return True
    return False


def _mirror_is_stale(source: Path, target: Path, *, retain_generated: bool = True) -> bool:
    """Return True if the staged mirror *target* must be refreshed.

    Two regimes (issue #129 / 360°-B6a):

    * Files WITH a ``.meta`` sibling are (or were) mutation targets — their
      staged content is the trampolined GENERATOR output (newer and bigger
      than the source by construction) and the ``.meta`` source fingerprint
      is the staleness truth there. The mirror refreshes only when the live
      source SHA-256 differs; legacy metadata without a hash is invalidated.

      With ``retain_generated=False`` (the retain policy of M-002) generator
      output is never kept: the target is stale regardless of the hash, so
      the caller restores the unmutated bytes for phases that require them
      (coverage collection, deselected targets).

    * Plain mirror copies (no ``.meta``) were created by ``copy2`` and
      therefore normally carry the SOURCE's stat data. Any stat inequality
      refreshes immediately, while stat equality is still verified by hash.
    """
    try:
        src_stat = source.stat()
        dst_stat = target.stat()
    except OSError:
        return True
    meta_path = target.with_name(target.name + ".meta")
    owned_metadata = read_owned_source_metadata(meta_path)
    if owned_metadata is not None:
        if not retain_generated:
            return True
        recorded = owned_metadata["source_hash"]
        return not isinstance(recorded, str) or recorded != _content_hash(source)
    if (
        src_stat.st_mtime_ns != dst_stat.st_mtime_ns
        or src_stat.st_size != dst_stat.st_size
        or stat.S_IMODE(src_stat.st_mode) != stat.S_IMODE(dst_stat.st_mode)
    ):
        return True
    # Stat equality is a cheap early check, never proof of content identity.
    return _content_hash(source) != _content_hash(target)


def _content_hash(path: Path) -> str:
    """Return the SHA-256 digest of a file's exact bytes."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_verified_generated_bytes(
    source_path: Path | str,
    expected_generated_hash: str | None,
) -> bytes:
    """Read one staged module only when generation metadata proves its bytes.

    The generated Python file and its ``.meta`` sidecar are published in two
    atomic steps.  A crash, stale mirror, or later edit can therefore leave a
    syntactically valid but unauthorised staged module.  Every consumer that
    displays, applies, or executes it must bind the exact bytes to
    ``generated_hash`` rather than trusting the filename.
    """

    mutants_root = _validated_mutants_root()
    target = _validated_staging_destination(Path("mutants") / source_path, mutants_root)
    payload = target.read_bytes()
    actual_hash = hashlib.sha256(payload).hexdigest()
    if expected_generated_hash is None or actual_hash != expected_generated_hash:
        raise StaleStagingError(
            f"{target} content cannot be proven to match its generated metadata — "
            "re-run 'mutmut-win run' before using this staging tree."
        )
    return payload


def _sync_tree(
    source_root: Path,
    destination_root: Path,
    *,
    excluded_resolved: frozenset[Path] = frozenset(),
    ignore_boundary: GitignoreBoundary | None = None,
    retained_generation_keys: frozenset[tuple[str, ...]] = frozenset(),
) -> None:
    """Mirror *source_root* into *destination_root* (issue #129 / B6b+C2).

    content-aware per-file sync replacing the previous ``copytree``:

    * copy a file only when missing or stale (:func:`_mirror_is_stale`
      hash-authoritative regime, including same-size/same-mtime edits and
      backdated restores);
    * DELETE staged files whose source disappeared — under ``copytree`` a
      removed test file kept RUNNING inside the staging forever;
    * the deletion pass never leaves *destination_root* (containment of the
      root itself is guard 4's job in :func:`copy_also_copy_files`);
    * git-ignored subtrees are neither copied nor retained
      (MBR-2026-09-14-01): the deletion pass treats an ignored live source
      like an absent one so pre-fix staged leftovers are purged;
    * generation sidecars next to a current, expected companion survive the
      deletion pass (M-031), and refreshing a mirror target invalidates a
      proven-own sidecar so no stale fingerprint outlives its bytes;
    * ``retained_generation_keys`` (staging keys relative to ``mutants/``)
      apply the M-002 retain policy: files the run still generates keep
      their trampolined output, everything else is restored unmutated;
    * type changes (file <-> directory) of a mirrored path are reconciled
      before every materialization (:func:`_reconcile_staging_kind`, Q-13):
      a conflicting staged entry is removed instead of aborting the run, and
      the deletion pass judges staged files type-aware.
    """
    mutants_root = _validated_mutants_root()
    _reconcile_staging_kind(destination_root, want_directory=True, mutants_root=mutants_root)
    _validated_staging_destination(destination_root, mutants_root)
    destination_rel = destination_root.resolve().relative_to(mutants_root.resolve())
    destination_key = _staging_key(destination_rel)
    source_boundaries: dict[Path, GitignoreBoundary | None] = {source_root: ignore_boundary}
    for root_str, dirs, files in os.walk(source_root):
        walk_directory = Path(root_str)
        boundary = source_boundaries.get(walk_directory)
        safe_dirs: list[str] = []
        boundary_pruned_content = False
        for name in dirs:
            if _is_staging_skip_dir(name, at_workspace_root=False):
                continue
            if boundary is not None and boundary.excludes_directory(name):
                boundary_pruned_content = True
                continue
            safe_dirs.append(name)
            if boundary is not None:
                source_boundaries[walk_directory / name] = boundary.enter(name)
        dirs[:] = safe_dirs
        rel_root = Path(root_str).relative_to(source_root)
        destination_directory = destination_root / rel_root
        # Q-13: reconcile BEFORE the mkdir condition — a live folder that the
        # boundary fully prunes skips the mkdir, and an old same-named staged
        # file would otherwise survive the deletion pass type-blind.
        _reconcile_staging_kind(
            destination_directory, want_directory=True, mutants_root=mutants_root
        )
        retained_files: list[str] = []
        for name in files:
            if boundary is not None and boundary.excludes_file(name):
                boundary_pruned_content = True
                continue
            src_file = Path(root_str) / name
            try:
                if src_file.resolve(strict=True) in excluded_resolved:
                    continue
            except OSError:
                # An input that cannot be resolved cannot safely defeat an
                # exact caller-owned exclusion through a transient alias.
                continue
            retained_files.append(name)
        if retained_files or safe_dirs or not boundary_pruned_content:
            # A directory whose every child the boundary pruned has no
            # staged representation at all (MBR-2026-09-14-01).  Directories
            # that are merely empty, or emptied by the exact caller-owned
            # exclusions, keep the historical mirror behaviour.
            _validated_staging_destination(destination_directory, mutants_root)
            destination_directory.mkdir(parents=True, exist_ok=True)
        for name in retained_files:
            src_file = Path(root_str) / name
            dst_file = destination_root / rel_root / name
            _reconcile_staging_kind(dst_file, want_directory=False, mutants_root=mutants_root)
            _validated_staging_destination(dst_file, mutants_root)
            if dst_file.exists():
                retain = (
                    *destination_key,
                    *_staging_key(rel_root / name),
                ) in retained_generation_keys
                if not _mirror_is_stale(src_file, dst_file, retain_generated=retain):
                    continue
                _refresh_staged_mirror(src_file, dst_file)
                continue
            dst_file.parent.mkdir(parents=True, exist_ok=True)
            _copy_with_retry(src_file, dst_file)

    if not destination_root.is_dir():
        return
    cleanup_candidates: list[tuple[Path, bool]] = []
    # Boundary state is tracked by destination-relative path: the staged tree
    # mirrors the source structure, so staged rel_root == source rel_root.
    staged_boundaries: dict[Path, GitignoreBoundary | None] = {Path(): ignore_boundary}

    def live_is_current(
        live_path: Path,
        live_name: str,
        live_boundary: GitignoreBoundary | None,
    ) -> bool:
        try:
            return (
                # Type-aware (M-030): a staged FILE whose live counterpart
                # became a directory is not current — the copy pass above
                # reconciled the target, and a pruned live folder must not
                # keep an old same-named staged file alive either.
                live_path.is_file()
                and live_path.resolve(strict=True) not in excluded_resolved
                and not (live_boundary is not None and live_boundary.excludes_file(live_name))
            )
        except OSError:
            return False

    for root_str, dirs, files in os.walk(destination_root):
        staged_root = Path(root_str)
        rel_root = staged_root.relative_to(destination_root)
        boundary = staged_boundaries.get(rel_root)
        staged_safe_dirs: list[str] = []
        for directory in dirs:
            if _is_staging_skip_dir(directory, at_workspace_root=False):
                continue
            staged_directory = Path(root_str) / directory
            _validated_staging_destination(staged_directory, mutants_root)
            directory_excluded = boundary is not None and boundary.excludes_directory(directory)
            staged_safe_dirs.append(directory)
            child_boundary = boundary.enter(directory) if boundary is not None else None
            staged_boundaries[rel_root / directory] = child_boundary
            cleanup_candidates.append((staged_directory, directory_excluded))
        dirs[:] = staged_safe_dirs

        for name in files:
            source_is_current = live_is_current(source_root / rel_root / name, name, boundary)
            if source_is_current:
                continue
            stale_path = Path(root_str) / name
            _validated_staging_destination(stale_path, mutants_root)
            if name.casefold().endswith(".meta"):
                # M-031: a proven-own generation sidecar survives next to a
                # current, expected companion (the rule the automatic mirror
                # has always applied) so fast-path reuse keeps working in
                # configured mirrors.
                companion_name = name[: -len(".meta")]
                companion_is_current = (
                    live_is_current(
                        source_root / rel_root / companion_name, companion_name, boundary
                    )
                    and stale_path.with_name(companion_name).exists()
                )
                if _retain_generation_sidecar(
                    stale_path, companion_is_current=companion_is_current
                ):
                    continue
            _unlink_staging_file(stale_path)

    # Keep the configured mirror root itself stable, but do not retain nested
    # package shells after their live directories disappear.  For
    # ``extra_paths`` such a shell is directly import-visible and would create
    # a false PEP 420 namespace package.
    for staged_directory, directory_excluded in sorted(
        cleanup_candidates,
        key=lambda candidate: len(candidate[0].parts),
        reverse=True,
    ):
        relative_directory = staged_directory.relative_to(destination_root)
        source_directory = source_root / relative_directory
        try:
            source_directory_is_current = (
                source_directory.is_dir()
                and not _is_link_or_reparse(source_directory)
                and not directory_excluded
            )
        except OSError:
            source_directory_is_current = False
        if source_directory_is_current:
            continue
        try:
            next(staged_directory.iterdir())
        except StopIteration:
            _validated_staging_destination(staged_directory, mutants_root)
            try:
                staged_directory.rmdir()
            except FileNotFoundError:
                continue
            except PermissionError as exc:
                _retry_readonly_removal(os.rmdir, str(staged_directory), exc)
        except FileNotFoundError:
            continue


def _configured_mirror_destinations(
    config: MutmutConfig,
    mutants_root: Path,
) -> set[Path]:
    """Return staging roots whose deletion contract belongs to also-copy sync."""

    destinations: set[Path] = set()
    project_root = Path.cwd().resolve()
    for raw in (*config.also_copy, *config.extra_paths):
        path = Path(raw)
        if _is_staging_skip_dir(path.name, at_workspace_root=True):
            continue
        try:
            if path.resolve() in (Path.cwd().resolve(), mutants_root):
                continue
        except (OSError, RuntimeError):  # fmt: skip
            continue
        relative_destination = configured_staging_relative_path(
            path,
            project_root=project_root,
        )
        if relative_destination is None:
            continue
        destination = Path("mutants") / relative_destination
        try:
            validated = _validated_staging_destination(destination, mutants_root)
        except UnsafeStagingError:
            continue
        if validated != mutants_root:
            destinations.add(validated)
    return destinations


def _sync_deleted_sources(
    expected_targets: set[Path],
    synced_roots: list[Path],
    skip_dirs: set[str],
    separately_synced_destinations: set[Path],
) -> None:
    """Remove automatic staged mirrors whose source no longer exists.

    Deleted/renamed sources used to stay in ``mutants/`` forever — tests ran
    green against deleted modules and their ``.meta`` files survived with
    them (issue #101 / A3-FD-003 + the OS-012 remainder). Deliberately
    The mirror owns every staged file except explicit also-copy/extra-path
    destinations and the two persistent cache/fingerprint files.  That keeps
    deleted JSON fixtures, native modules and root-level helpers from haunting
    later runs while leaving each configured extra tree to ``_sync_tree``.

    Args:
        expected_targets: Every target path the copy walk produced.
        synced_roots: The source roots that were mirrored this run.
        skip_dirs: Directory names excluded from the copy walk.
        separately_synced_destinations: Staging roots owned by also-copy sync.
    """
    removed = 0
    mutants_root = _validated_mutants_root()
    folded_skip_dirs = {directory.casefold() for directory in skip_dirs}
    expected_absolute = {target.absolute() for target in expected_targets}

    def owned_elsewhere(path: Path) -> bool:
        absolute = path.absolute()
        return any(
            absolute == destination or absolute.is_relative_to(destination)
            for destination in separately_synced_destinations
        )

    # The project root subsumes explicit ``src``/``source`` mirrors. Walk the
    # staging tree once when it was part of this run rather than revisiting its
    # descendants and reporting duplicate removals.
    if Path() in synced_roots:
        synced_roots = [Path()]
    for source_root in synced_roots:
        staged_root = Path("mutants") / source_root
        _validated_staging_destination(staged_root, mutants_root)
        if not staged_root.is_dir():
            continue
        cleanup_candidates: list[Path] = []
        for root_str, dirs, files in os.walk(staged_root):
            safe_dirs: list[str] = []
            for directory in dirs:
                if directory.casefold() in folded_skip_dirs or directory.casefold() == "mutants":
                    continue
                staged_directory = Path(root_str) / directory
                _validated_staging_destination(staged_directory, mutants_root)
                if owned_elsewhere(staged_directory):
                    continue
                safe_dirs.append(directory)
                cleanup_candidates.append(staged_directory)
            dirs[:] = safe_dirs
            for name in files:
                staged = Path(root_str) / name
                _validated_staging_destination(staged, mutants_root)
                if owned_elsewhere(staged):
                    continue
                if staged.absolute() in expected_absolute:
                    continue
                if (
                    staged.parent.absolute() == mutants_root
                    and name.casefold() in _PERSISTENT_STAGING_STATE_FILES
                ):
                    continue
                if name.casefold().endswith(".meta"):
                    companion = Path(str(staged)[: -len(".meta")]).absolute()
                    if _retain_generation_sidecar(
                        staged, companion_is_current=companion in expected_absolute
                    ):
                        continue
                _unlink_staging_file(staged)
                removed += 1
                # Every companion is visited independently through the same
                # expected-input and configured-owner checks. Deleting a
                # *.py file must not also erase a live user *.py.meta fixture
                # or another mirror's independently owned input (CX221-067).

        # Files are synchronized first; then remove only directory shells
        # whose corresponding live directory disappeared.  Leaving one such
        # shell behind changes Python import semantics by creating a PEP 420
        # namespace package that does not exist in the live project.  Work
        # bottom-up so nested stale packages can empty their parents, while
        # preserving the staging root, live empty directories and every
        # explicit also-copy/extra-path mirror root.
        for staged_directory in sorted(
            cleanup_candidates,
            key=lambda candidate: len(candidate.parts),
            reverse=True,
        ):
            if owned_elsewhere(staged_directory):
                continue
            relative_directory = staged_directory.relative_to(staged_root)
            source_directory = source_root / relative_directory
            try:
                source_directory_is_current = source_directory.is_dir() and not _is_link_or_reparse(
                    source_directory
                )
            except OSError:
                source_directory_is_current = False
            if source_directory_is_current:
                continue
            try:
                next(staged_directory.iterdir())
            except StopIteration:
                _validated_staging_destination(staged_directory, mutants_root)
                try:
                    staged_directory.rmdir()
                except FileNotFoundError:
                    continue
                except PermissionError as exc:
                    _retry_readonly_removal(os.rmdir, str(staged_directory), exc)
            except FileNotFoundError:
                continue
    if removed:
        print(f"     removed {removed} stale staged files (sources deleted/renamed)")


def copy_also_copy_files(
    config: MutmutConfig,
    *,
    excluded_paths: Sequence[Path] = (),
) -> None:
    """Sync config.also_copy files/directories into the mutants/ directory.

    Trees are mirrored mtime-aware INCLUDING deletions via
    :func:`_sync_tree` (issue #129 / 360°-B6b+C2: ``copytree`` re-copied
    everything on every run and never deleted — removed test files kept
    running inside the staging forever). Cache/venv/tooling directories are
    skipped via the shared ``_STAGING_SKIP_DIRS`` walk filter.  Type changes
    (file <-> directory) at a configured target are reconciled before every
    materialization (:func:`_reconcile_staging_kind`, Q-13).

    Args:
        config: Active ``MutmutConfig`` instance.
        excluded_paths: Exact caller-owned state files that must neither enter
            staging directly nor through a configured directory mirror.
    """
    # extra_paths (Bug #69) are handled by the same copy mechanism as also_copy.
    # Their distinguishing trait — being added to the worker's PYTHONPATH — is
    # implemented in process/worker.py rather than here.
    paths_to_copy: list[str] = [*config.also_copy, *config.extra_paths]
    retained_generation_keys = _generation_target_keys(config)
    excluded_resolved: set[Path] = set()
    for excluded in excluded_paths:
        try:
            excluded_resolved.add(excluded.resolve())
        except OSError:
            continue
    frozen_exclusions = frozenset(excluded_resolved)

    mutants_root = _validated_mutants_root()
    project_root = Path.cwd().resolve()
    project_boundary = GitignoreBoundary.load(project_root)
    for path_str in paths_to_copy:
        path = Path(path_str)
        relative_destination = configured_staging_relative_path(path, project_root=project_root)
        if relative_destination is None:
            continue
        # Guard 1 (Bug #67): top-level virtualenv / cache directories must not
        # be mirrored into mutants/ even when the user lists them explicitly.
        # The walk filter inside _sync_tree only skips *children*, so a
        # top-level entry like ``also_copy = [".venv"]`` would otherwise be
        # mirrored wholesale — slow at best, broken on Windows because of
        # symlinked Scripts/python.exe.
        if _is_staging_skip_dir(path.name, at_workspace_root=True):
            print("     skipping", path_str, "(matches venv/cache skip list)")
            continue
        # Guard 2 (issue #101 / A3-FD-005): "." and mutants/ itself defeat the
        # name-based skip (``Path(".").name == ""``) and would nest the whole
        # project — including mutants/ and .git — into mutants/mutants.
        resolved_path = path.resolve()
        if resolved_path in (project_root, mutants_root):
            print("     skipping", path_str, "(would nest the project into mutants/)")
            continue
        # Absolute inputs and explicit ``..`` siblings share the central
        # planner/runner/worker mapping.  This prevents both prefix discard and
        # Windows 8.3/long-path divergence.
        destination = Path("mutants") / relative_destination
        # Guard 4 (containment, second line of defence): whatever the entry
        # looks like, the destination must stay inside mutants/.
        _validated_staging_destination(destination, mutants_root)
        try:
            path_is_excluded = path.resolve() in frozen_exclusions
        except OSError:
            path_is_excluded = False
        if path_is_excluded:
            if destination.exists():
                if destination.is_dir():
                    shutil.rmtree(destination, onexc=_retry_readonly_removal)
                else:
                    _unlink_staging_file(destination)
            print("     skipping", path_str, "(caller-owned state exclusion)")
            continue
        if not path.exists():
            # This destination is owned by the configured mirror.  If its
            # source disappears, retaining an old non-Python fixture/native
            # module lets workers execute bytes absent from the live run basis.
            # Remove the exact, revalidated destination instead of silently
            # accepting a haunted staging tree.
            try:
                destination_metadata = destination.lstat()
            except FileNotFoundError:
                continue
            _remove_staging_entry(destination, destination_metadata)
            print("     removed stale configured mirror", destination)
            continue
        print("     also copying", path_str)
        if path.is_file():
            # Q-13: type changes are reconciled before materialization — a
            # stale staged directory at a file target is removed here.
            _reconcile_staging_kind(destination, want_directory=False, mutants_root=mutants_root)
            _validated_staging_destination(destination, mutants_root)
            if destination.exists():
                retain = (
                    _staging_key(destination.resolve().relative_to(mutants_root.resolve()))
                    in retained_generation_keys
                )
                if _mirror_is_stale(path, destination, retain_generated=retain):
                    _refresh_staged_mirror(path, destination)
            elif _mirror_is_stale(path, destination):
                destination.parent.mkdir(parents=True, exist_ok=True)
                _copy_with_retry(path, destination)
        else:
            # Q-13: the mirror root itself is reconciled (a previously staged
            # file at the root target is removed) before the tree sync.
            _reconcile_staging_kind(destination, want_directory=True, mutants_root=mutants_root)
            _sync_tree(
                path,
                destination,
                excluded_resolved=frozen_exclusions,
                ignore_boundary=_configured_entry_boundary(
                    project_boundary,
                    project_root,
                    path,
                ),
                retained_generation_keys=retained_generation_keys,
            )

    # Sanitise the copied pyproject.toml — remove [tool.uv.sources] entries
    # that contain relative paths. These paths are relative to the original
    # project root and break when resolved from mutants/ (one level deeper).
    _sanitise_mutants_pyproject()


def _config_fingerprint(
    config: MutmutConfig,
    covered_lines_by_file: dict[str, set[int]] | None = None,
) -> str:
    """Return a digest for every input that selects the mutant universe."""
    import mutmut_win

    coverage_basis = None
    if covered_lines_by_file is not None:
        coverage_basis = {
            path: sorted(lines) for path, lines in sorted(covered_lines_by_file.items())
        }
    payload = json.dumps(
        {
            "engine_version": mutmut_win.__version__,
            "paths_to_mutate": sorted(config.paths_to_mutate),
            "do_not_mutate": sorted(config.do_not_mutate),
            "do_not_mutate_patterns": sorted(config.do_not_mutate_patterns),
            "mutate_only_covered_lines": config.mutate_only_covered_lines,
            "covered_lines_by_file": coverage_basis,
            "also_copy": sorted(config.also_copy),
            "extra_paths": sorted(config.extra_paths),
            "mutation_profile": config.mutation_profile.to_name(),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def persist_config_fingerprint(
    config: MutmutConfig,
    covered_lines_by_file: dict[str, set[int]] | None = None,
) -> None:
    """Atomically publish a completely generated mutant universe."""
    fingerprint_path = Path("mutants") / ".mutmut-config-fingerprint"
    mutants_root = _validated_mutants_root()
    _validated_staging_destination(fingerprint_path, mutants_root)
    _atomic_write_text(fingerprint_path, _config_fingerprint(config, covered_lines_by_file))


def config_fingerprint_matches(
    config: MutmutConfig,
    covered_lines_by_file: dict[str, set[int]] | None = None,
    *,
    persist: bool = True,
) -> bool:
    """Compare the universe fingerprint, optionally persisting a mismatch.

    The default preserves the public helper's historical compare-and-store
    behavior. The orchestrator uses persist=False and publishes only after
    every file succeeded, preventing a failed partial generation from
    authorizing the next run's fast path.
    """
    fingerprint = _config_fingerprint(config, covered_lines_by_file)
    fingerprint_path = Path("mutants") / ".mutmut-config-fingerprint"
    try:
        stored = fingerprint_path.read_text(encoding="utf-8").strip()
    except OSError:
        stored = None
    if stored == fingerprint:
        return True
    if persist:
        persist_config_fingerprint(config, covered_lines_by_file)
    return False


def _sanitise_mutants_pyproject() -> None:
    """Remove uv source tables from the copied pyproject.toml in mutants/.

    When mutmut-win copies pyproject.toml into the mutants/ staging directory,
    any ``[tool.uv.sources]`` entries with relative paths (e.g.
    ``../../_deps/my-package``) break because mutants/ is one directory level
    deeper. Removing the entire section is safe — the mutants/ directory uses
    the parent project's venv via sys.executable, not its own.

    Covers the parent table AND the subtable header syntax
    ``[tool.uv.sources.<pkg>]`` (issue #113 / A3-FD-008 — the subtable form
    kept the "Distribution not found at: file:///..." error alive). The
    inline dotted-key form (``sources.pkg = {...}`` inside ``[tool.uv]``)
    is NOT covered — that would need parse-and-rewrite, not a regex.
    """
    pyproject_path = Path("mutants") / "pyproject.toml"
    mutants_root = _validated_mutants_root()
    _validated_staging_destination(pyproject_path, mutants_root)
    if not pyproject_path.exists():
        return

    try:
        content = pyproject_path.read_text(encoding="utf-8")
    except OSError:
        return

    # Remove [tool.uv.sources] / [tool.uv.sources.<pkg>] sections — each
    # header plus everything until the next section header or EOF (the
    # final line may lack a trailing newline).
    import re

    cleaned = re.sub(
        r"\[tool\.uv\.sources(?:\.[^\]]+)?\]\s*\n(?:(?!\[)[^\n]*\n?)*",
        "",
        content,
    )

    # Also remove [tool.uv] if it only contained sources (now empty)
    cleaned = re.sub(
        r"\[tool\.uv\]\s*\n(?=\[|\Z)",
        "",
        cleaned,
    )

    if cleaned != content:
        for attempt in range(5):
            try:
                _atomic_write_text(pyproject_path, cleaned)
                break
            except OSError:
                if attempt < 4:
                    time.sleep(0.1 * (2**attempt))
                # Last attempt failed — continue silently, sanitisation is best-effort


# ---------------------------------------------------------------------------
# sys.path manipulation
# ---------------------------------------------------------------------------


def setup_source_paths() -> None:
    """Prepare ``sys.path`` inside an explicitly isolated test child.

    This compatibility helper must never run in the orchestration parent or a
    generation worker: Windows spawn would inherit the staging roots and lazy
    engine imports could then mutate the frozen staging tree.  Production
    pytest children receive the equivalent roots through the runner's explicit
    ``PYTHONPATH`` environment.  The following well-known source roots are
    considered: the current directory, ``src``, and ``source``.
    """
    source_code_paths = [Path(), *(Path(name) for name in SOURCE_ROOT_NAMES)]

    # Add mutated variants to the front of sys.path.
    for path in source_code_paths:
        mutated_path = Path("mutants") / path
        if mutated_path.exists():
            sys.path.insert(0, str(mutated_path.absolute()))

    # Remove the original source paths so they cannot shadow mutants.
    for path in source_code_paths:
        i = 0
        while i < len(sys.path):
            if Path(sys.path[i]).resolve() == path.resolve():
                del sys.path[i]
            else:
                i += 1


# ---------------------------------------------------------------------------
# Mutant naming helpers
# ---------------------------------------------------------------------------


def strip_prefix(s: str, *, prefix: str) -> str:
    """Strip *prefix* from *s* if present, otherwise return *s* unchanged.

    Args:
        s: Input string.
        prefix: Prefix to strip.

    Returns:
        String with the prefix removed, or the original string.
    """
    if s.startswith(prefix):
        return s[len(prefix) :]
    return s


def get_mutant_name(relative_source_path: Path, mutant_method_name: str) -> str:
    """Construct the fully qualified mutant name.

    Converts a relative source file path to a dotted module name, strips the
    leading source-root prefix (``src.`` or ``source.`` — the same roots the
    staging mirrors and the workers put on PYTHONPATH, issue #126 /
    360°-A3), and appends the mangled method name. On Windows, source-root
    and final ``__init__`` comparisons follow the filesystem's
    case-insensitive identity. The result MUST equal
    ``orig.__module__ + '.' + mangled_name``: the trampoline's prefix check
    and the stats mapping both depend on that identity — a root that is
    importable but not stripped turns every one of its mutants into
    ``no tests``.

    For example::

        get_mutant_name(Path("src/my_lib/utils.py"), "add__mutmut_1")
        # -> "my_lib.utils.add__mutmut_1"
        get_mutant_name(Path("source/my_lib/utils.py"), "add__mutmut_1")
        # -> "my_lib.utils.add__mutmut_1"

    Known limitation (documented in the README): a project whose tests
    import a root PACKAGE literally named ``src``/``source`` (``import
    src.foo``) is not supported — the layout convention wins.

    Args:
        relative_source_path: Path to the source file, relative to the project
            root (e.g. ``Path("src/my_lib/utils.py")``).
        mutant_method_name: The mangled function name returned by the mutation
            engine (e.g. ``"add__mutmut_1"``).

    Returns:
        Fully qualified mutant identifier string.
    """
    stem = str(relative_source_path)[: -len(relative_source_path.suffix)]
    if ".." in relative_source_path.parts:
        msg = (
            f"mutating path {relative_source_path} must be canonical and "
            "project-relative — '..' components produce mutant names that can "
            "never match the trampoline prefix or the stats mapping (M-034)"
        )
        raise ValueError(msg)
    module_components = stem.replace(os.sep, ".").replace("/", ".").split(".")
    for root in SOURCE_ROOT_NAMES:
        root_matches = module_components and module_components[0] == root
        if os.name == "nt" and module_components:
            root_matches = module_components[0].casefold() == root.casefold()
        if root_matches:
            # Exactly ONE root strips (src/source/pkg → source.pkg).
            module_components = module_components[1:]
            break
    if len(module_components) > 1:
        final_stem_is_init = module_components[-1] == "__init__"
        if os.name == "nt":
            final_stem_is_init = module_components[-1].casefold() == "__init__"
        if final_stem_is_init:
            # Package __init__ functions live in the package module itself.
            module_components.pop()
    module_name = ".".join(module_components)
    return f"{module_name}.{mutant_method_name}"


# ---------------------------------------------------------------------------
# Mutant file generation
# ---------------------------------------------------------------------------


def write_all_mutants_to_file(
    *,
    out: IO[str],
    source: str,
    filename: Path | str,
    covered_lines: set[int] | None = None,
    active_profile: Profile = Profile.ADVANCED,
    do_not_mutate_patterns: Sequence[str] = (),
) -> list[str]:
    """Generate mutated code and write it to *out*.

    Args:
        out: Writable text stream to receive the mutated source.
        source: Original Python source code.
        filename: Path to the source file (used by the mutation engine for
            context; the file is not re-read).
        covered_lines: Optional set of line numbers to restrict mutations to.
        active_profile: Operator profile to apply (default ``advanced`` = the
            historical operator set).

    Returns:
        List of mangled mutant method names (e.g. ``["add__mutmut_1", ...]``).
    """
    from mutmut_win.mutation import mutate_file_contents

    result, mutant_names = mutate_file_contents(
        str(filename), source, covered_lines, active_profile, do_not_mutate_patterns
    )
    out.write(result)
    return list(mutant_names)


class _FastPathMissError(Exception):
    """Internal sentinel: the .meta source fingerprint does not match."""


def create_mutants_for_file(
    filename: Path,
    output_path: Path,
    covered_lines: set[int] | None = None,
    *,
    allow_fast_path: bool = True,
    active_profile: Profile = Profile.ADVANCED,
    do_not_mutate_patterns: Sequence[str] = (),
) -> tuple[list[str], list[warnings.WarningMessage], bool]:
    """Generate mutants for a single source file and write to *output_path*.

    Reads the source, runs the mutation engine, writes the mutated code to
    *output_path*, validates the generated syntax, and saves a
    ``SourceFileMutationData`` meta file.

    If the source file is unmodified since the last mutant generation
    (source fingerprint match) the cached mutant names from ``.meta`` are
    returned without regenerating — signalled via the third return element
    so the orchestrator knows which files are candidates for result reuse
    (issue #119 / external QA RUN-001).

    Args:
        filename: Path to the original source file.
        output_path: Path where the mutated file should be written.
        covered_lines: Optional set of line numbers to restrict mutations to.

    Returns:
        A tuple of ``(mutant_names, warnings, took_fast_path)`` where
        *mutant_names* is a list of mangled method names, *warnings* is a
        list of any parse warnings, and *took_fast_path* is ``True`` iff the
        names came from the unchanged-staging fast path.
    """
    collected_warnings: list[warnings.WarningMessage] = []

    if ".." in filename.parts:
        # Engine invariant (M-034): the config validator canonicalises
        # '..'-aliases, but this guard also protects callers that bypass it.
        # It must fire before any staging write — get_mutant_name runs only
        # after the generated module is on disk.
        msg = (
            f"Refusing to mutate through a non-canonical '..'-alias ({filename}) — "
            "paths_to_mutate entries must be canonical project-relative paths."
        )
        raise ValueError(msg)

    if output_path.resolve() == filename.resolve():
        msg = (
            f"Refusing to write mutants into the source file itself "
            f"({filename}) — paths_to_mutate must be relative to the project root."
        )
        raise ValueError(msg)

    mutants_root = _validated_mutants_root()
    safe_output_path = _validated_staging_destination(output_path, mutants_root)
    meta_relative_path = safe_output_path.relative_to(mutants_root)

    # Write guard (issue #75 / A3-CM-001): with absolute paths_to_mutate,
    # ``Path("mutants") / <abs>`` collapses to ``<abs>`` and *output_path*
    # becomes the source file itself.  Refuse loudly instead of destroying
    # the user's code — this also defends callers that bypass the config
    # validator (e.g. CLI overrides via ``model_copy``).
    # Fast-path: if the source is unchanged since we last mutated it, reuse
    # the existing mutant names from the .meta file instead of re-generating.
    # This enables repeated runs: the orchestrator gets the task list even
    # though the mutated file already exists in mutants/.
    # The comparison is against the exact SOURCE hash recorded in .meta at
    # generation time. Legacy stat-only metadata deliberately misses once;
    # same-size/same-mtime edits and backdated restores cannot authorize reuse.
    # The orchestrator passes allow_fast_path=False when the config
    # fingerprint changed (issue #101 / A3-OS-008) — a different mutant
    # universe must be regenerated regardless of file timestamps.
    source_bytes = filename.read_bytes()
    source_hash = hashlib.sha256(source_bytes).hexdigest()
    # Preserve physical newlines throughout the CST roundtrip, including those
    # inside multiline strings and explicit continuations. The generated writer
    # likewise bypasses Windows newline translation.
    source, source_encoding = _decode_python_source(source_bytes)
    generation_payload = json.dumps(
        {
            "source_newline_policy": "preserve-v1",
            "profile": active_profile.to_name(),
            "do_not_mutate_patterns": sorted(do_not_mutate_patterns),
            "covered_lines": sorted(covered_lines) if covered_lines is not None else None,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    generation_fingerprint = hashlib.sha256(generation_payload.encode("utf-8")).hexdigest()

    try:
        if allow_fast_path and output_path.exists():
            source_file_mutation_data = SourceFileMutationData(path=str(meta_relative_path))
            source_file_mutation_data.load()
            fingerprint_ok = (
                source_file_mutation_data.source_hash == source_hash
                and source_file_mutation_data.generation_fingerprint == generation_fingerprint
                and source_file_mutation_data.generated_hash is not None
                and source_file_mutation_data.generated_hash == _content_hash(output_path)
            )
            if not fingerprint_ok:
                raise _FastPathMissError
            # Extract local mutant names from the qualified keys in .meta.
            # Qualified keys look like "module.submod.func__mutmut_1" — the
            # local name is the part containing "__mutmut_" (the mangled name).
            existing_local: list[str] = []
            for key in source_file_mutation_data.exit_code_by_key:
                # Find the mangled method name: everything from the last
                # component that contains __mutmut_
                parts = key.split(".")
                local = next(
                    (p for p in reversed(parts) if "__mutmut_" in p),
                    None,
                )
                if local:
                    existing_local.append(local)
            if existing_local:
                # Tests can read staging sidecars directly.  Remove verdict
                # and timing outputs from the previous run before any phase
                # starts so identical generated code exposes identical bytes.
                source_file_mutation_data.save_generation_metadata()
                return existing_local, collected_warnings, True
            # No names in meta → fall through to regenerate
    except (
        OSError,
        _FastPathMissError,
    ):
        pass

    mutant_names: list[str]
    generated: str
    try:
        buf = StringIO()
        # Record engine-level warnings (e.g. the function-granular
        # mangling-separator skip, issue #121 / MUT-002) so they reach the
        # orchestrator's warning channel like the file-level ones.
        with warnings.catch_warnings(record=True) as engine_warnings:
            warnings.simplefilter("always")
            mutant_names = write_all_mutants_to_file(
                out=buf,
                source=source,
                filename=filename,
                covered_lines=covered_lines,
                active_profile=active_profile,
                do_not_mutate_patterns=do_not_mutate_patterns,
            )
        collected_warnings.extend(engine_warnings)
        generated = buf.getvalue()
    except (cst.ParserSyntaxError, cst.CSTValidationError) as exc:
        # A source file LibCST cannot represent is an expected file-level
        # limitation and stays importable in staging. Engine invariants such
        # as ValueError must propagate to the orchestration transaction;
        # swallowing them would silently publish a partial mutant universe.
        if isinstance(exc, cst.ParserSyntaxError):
            reason = "unsupported_source_syntax"
            text = f"Unsupported syntax in {filename} ({exc!s}), skipping"
        else:
            # CSTValidationError can arise both while parsing and while the
            # engine builds nodes; attribute it neutrally (M-003).
            reason = "cst_validation_error"
            text = f"LibCST rejected the syntax tree for {filename} ({exc!s}), skipping"
        w = warnings.WarningMessage(
            message=MutationSurfaceDegradedWarning(reason, text),
            category=MutationSurfaceDegradedWarning,
            filename=str(filename),
            lineno=0,
        )
        collected_warnings.append(w)
        generated = source
        mutant_names = []

    # Safety net (issue #78): validate BEFORE writing.  A single invalid
    # mutant makes the whole file unimportable and breaks the clean run with
    # a misleading error (the Bug-#68 / BUG-1 class).  Fall back to the
    # unmutated source and warn loudly instead of poisoning the staging.
    if mutant_names:
        try:
            ast.parse(generated)
        except (IndentationError, SyntaxError) as exc:
            lineno = getattr(exc, "lineno", "?")
            w = warnings.WarningMessage(
                message=MutationSurfaceDegradedWarning(
                    "generated_code_invalid",
                    f"Generated mutants for {filename} do not compile "
                    f"(line {lineno}: {exc.msg}) — copying the file unmutated. "
                    "Please report this as a mutmut-win bug.",
                ),
                category=MutationSurfaceDegradedWarning,
                filename=str(filename),
                lineno=0,
            )
            collected_warnings.append(w)
            generated = source
            mutant_names = []

    generated_hash = _atomic_write_generated_python(
        output_path,
        generated,
        source_encoding=source_encoding,
    )

    # Persist the mutation metadata for this file, including the source
    # fingerprint the fast path compares against (issue #101 / A3-FD-004).
    source_file_mutation_data = SourceFileMutationData(path=str(meta_relative_path))
    source_file_mutation_data.exit_code_by_key = {
        get_mutant_name(filename, name): None for name in mutant_names
    }
    try:
        stat = filename.stat()
        source_file_mutation_data.source_mtime = stat.st_mtime
        source_file_mutation_data.source_size = stat.st_size
    except OSError:
        pass
    source_file_mutation_data.source_hash = source_hash
    source_file_mutation_data.generation_fingerprint = generation_fingerprint
    source_file_mutation_data.generated_hash = generated_hash
    # Meta is the transaction commit marker and must be published last.  A
    # crash after the Python file replace leaves missing/old generated_hash
    # authority, so the next run regenerates rather than trusting partial state.
    source_file_mutation_data.save_generation_metadata()

    return mutant_names, collected_warnings, False
