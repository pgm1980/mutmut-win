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
import json
import os
import shutil
import sys
import time
import warnings
from io import StringIO
from pathlib import Path
from typing import IO, TYPE_CHECKING

import libcst as cst

from mutmut_win.atomic_file import atomic_copy_file, atomic_write_bytes
from mutmut_win.constants import SOURCE_ROOT_NAMES, WORKSPACE_EXCLUDED_DIR_NAMES, Profile
from mutmut_win.exceptions import UnsafeStagingError
from mutmut_win.models import SourceFileMutationData

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

    from mutmut_win.config import MutmutConfig

#: Directory names excluded from every staging walk (mirror AND also_copy).
#: One list for both passes (issue #129 / 360°-C4): the two sites used to
#: carry diverging literals, and tooling trees (node_modules, .claude, …)
#: were mirrored into mutants/ on every first run.
_STAGING_SKIP_DIRS: frozenset[str] = WORKSPACE_EXCLUDED_DIR_NAMES

# Stable workspace coordination artifacts belong beside the project, never in
# the import staging tree. The guard intentionally survives clean releases.
_STAGING_SKIP_FILES: frozenset[str] = frozenset(
    {".mutmut-win.run.lock", ".mutmut-win.run.lock.guard"}
)


def _skip_automatic_root_file(name: str) -> bool:
    """Keep coordination files and dotenv secrets out of automatic staging."""
    folded = name.casefold()
    if folded in _STAGING_SKIP_FILES or (
        folded.startswith(".mutmut-win-") and folded.endswith((".run.lock", ".run.lock.guard"))
    ):
        return True
    return folded == ".env" or (
        folded.startswith(".env.")
        and folded not in {".env.example", ".env.sample", ".env.template"}
    )


def _is_staging_skip_dir(name: str) -> bool:
    """Apply Windows' case-insensitive directory semantics consistently."""
    return name.casefold() in _STAGING_SKIP_DIRS


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


def _validated_staging_destination(destination: Path, mutants_root: Path) -> Path:
    """Return a lexical staging path only when no component redirects it."""
    # ``absolute`` makes the path lexical-absolute without dereferencing
    # symlinks/junctions; comparing it with ``resolve`` below is intentional.
    lexical = destination.absolute()
    try:
        lexical.relative_to(mutants_root)
    except ValueError as exc:
        raise UnsafeStagingError(
            f"Unsafe staging destination {destination}: path escapes {mutants_root}"
        ) from exc
    try:
        resolved = destination.resolve(strict=False)
    except (OSError, RuntimeError) as exc:
        raise UnsafeStagingError(
            f"Cannot resolve staging destination {destination}: {exc}"
        ) from exc
    if resolved != lexical:
        raise UnsafeStagingError(
            f"Unsafe staging destination {destination}: resolves through a "
            f"symlink/junction to {resolved}"
        )
    return lexical


# ---------------------------------------------------------------------------
# Directory walking helpers
# ---------------------------------------------------------------------------


def walk_all_files(config: MutmutConfig) -> Iterator[tuple[str, str]]:
    """Yield (root, filename) for all files in config.paths_to_mutate.

    Args:
        config: Active ``MutmutConfig`` instance.

    Yields:
        Tuples of (root directory string, filename string).
    """
    for path in config.paths_to_mutate:
        p = Path(path)
        if not p.is_dir():
            if p.is_file():
                yield "", str(path)
                continue
        else:
            project_root = Path.cwd().resolve()
            for root, dirs, files in os.walk(path):
                # Never feed staging/cache/tool environments back into the
                # mutation engine. Resolve children as a junction/symlink
                # defence in addition to the fast name filter.
                safe_dirs: list[str] = []
                for directory in dirs:
                    if _is_staging_skip_dir(directory):
                        continue
                    try:
                        (Path(root) / directory).resolve().relative_to(project_root)
                    except (OSError, ValueError):
                        continue
                    safe_dirs.append(directory)
                dirs[:] = safe_dirs
                for filename in files:
                    try:
                        (Path(root) / filename).resolve().relative_to(project_root)
                    except (OSError, ValueError):
                        # A file symlink can escape even when its containing
                        # directory is inside the project. Never feed that
                        # external target to staging/mutation implicitly.
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
        if filename.endswith(".py"):
            yield Path(root) / filename


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

    for attempt in range(max_attempts):
        try:
            copy_once()
            return
        except OSError:
            if attempt < max_attempts - 1:
                time.sleep(0.1 * (2**attempt))
    # Final attempt — let the exception propagate if it still fails.
    copy_once()


def _atomic_write_text(path: Path, content: str) -> str:
    """Publish UTF-8 text and return the SHA-256 of the exact written bytes."""
    path.parent.mkdir(parents=True, exist_ok=True)
    # Match TextIOWrapper's platform newline translation explicitly, then
    # publish those immutable bytes.  Generation inputs were read in text
    # mode, so they contain normalized LF rather than pre-existing CRLF.
    payload = content.replace("\n", os.linesep).encode("utf-8")
    atomic_write_bytes(path, payload)
    return hashlib.sha256(payload).hexdigest()


def copy_src_dir(
    config: MutmutConfig,  # noqa: ARG001 — kept for API compatibility
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

    Args:
        config: Active ``MutmutConfig`` instance.
        excluded_paths: Exact project files owned by the caller that must not
            enter staging. This is intentionally path-specific: broad suffix
            exclusions would also drop legitimate test fixtures such as
            ``tests/fixture.sqlite``.
    """
    expected_targets: set[Path] = set()
    synced_roots: list[Path] = []
    project_root = Path.cwd().resolve()
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

    for source_root_name in [*SOURCE_ROOT_NAMES, "."]:
        source_root = Path(source_root_name)
        if not source_root.exists() or not source_root.is_dir():
            continue
        if source_root_name != ".":
            # Deletion sync only covers the EXPLICIT mirror roots: under the
            # "." grab-bag the expectation set cannot be cleanly separated
            # from also_copy mirrors and generated artifacts (stats plugin,
            # sitecustomize) — deleting there would be guessing.
            synced_roots.append(source_root)

        for root_str, dirs, files in os.walk(source_root):
            # Skip cache/venv/tooling directories (issue #129 / 360°-C4).
            safe_dirs: list[str] = []
            for directory in dirs:
                if _is_staging_skip_dir(directory):
                    continue
                try:
                    (Path(root_str) / directory).resolve().relative_to(project_root)
                except (OSError, ValueError):
                    continue
                safe_dirs.append(directory)
            dirs[:] = safe_dirs
            if source_root_name == "." and root_str == ".":
                # The explicit roots above already mirrored src/source —
                # walking them again from "." doubled the largest trees
                # (issue #129 / 360°-C4). Top level only: a NESTED foo/src
                # is not covered by the explicit roots and must stay.
                source_root_names = {name.casefold() for name in SOURCE_ROOT_NAMES}
                dirs[:] = [d for d in dirs if d.casefold() not in source_root_names]

            for name in files:
                if _skip_automatic_root_file(name):
                    continue
                source_path = Path(root_str) / name
                try:
                    resolved_source = source_path.resolve(strict=True)
                    resolved_source.relative_to(project_root)
                except (OSError, ValueError):
                    # Automatic staging must never dereference an external or
                    # broken file symlink into the executable mirror.
                    continue
                if resolved_source in excluded_resolved:
                    continue
                target_path = Path("mutants") / root_str / name
                _validated_staging_destination(target_path, mutants_root)
                expected_targets.add(target_path)

                if target_path.exists():
                    if source_path.is_file() and _mirror_is_stale(source_path, target_path):
                        _copy_with_retry(source_path, target_path)
                        print(f"     updated: {source_path} (source changed since last run)")
                        # Invalidate cached mutation results for this file.
                        meta_path = Path(str(target_path) + ".meta")
                        if meta_path.exists():
                            meta_path.unlink()
                    continue

                target_path.parent.mkdir(exist_ok=True, parents=True)
                _copy_with_retry(source_path, target_path)

    _sync_deleted_sources(expected_targets, synced_roots, set(_STAGING_SKIP_DIRS))
    # Heal staging created before run-lock and dotenv files were excluded.
    for candidate in Path("mutants").rglob("*"):
        if _skip_automatic_root_file(candidate.name):
            _validated_staging_destination(candidate, mutants_root)
            with contextlib.suppress(OSError):
                candidate.unlink()


def _mirror_is_stale(source: Path, target: Path) -> bool:
    """Return True if the staged mirror *target* must be refreshed.

    Two regimes (issue #129 / 360°-B6a):

    * Files WITH a ``.meta`` sibling are (or were) mutation targets — their
      staged content is the trampolined GENERATOR output (newer and bigger
      than the source by construction) and the ``.meta`` source fingerprint
      is the staleness truth there. The mirror refreshes only when the live
      source SHA-256 differs; legacy metadata without a hash is invalidated.
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
    if meta_path.exists():
        try:
            raw = json.loads(meta_path.read_text(encoding="utf-8"))
            recorded = raw.get("source_hash") if isinstance(raw, dict) else None
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            return True
        return not isinstance(recorded, str) or recorded != _content_hash(source)
    if src_stat.st_mtime != dst_stat.st_mtime or src_stat.st_size != dst_stat.st_size:
        return True
    # Stat equality is a cheap early check, never proof of content identity.
    return _content_hash(source) != _content_hash(target)


def _content_hash(path: Path) -> str:
    """Return the SHA-256 digest of a file's exact bytes."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sync_tree(source_root: Path, destination_root: Path) -> None:
    """Mirror *source_root* into *destination_root* (issue #129 / B6b+C2).

    content-aware per-file sync replacing the previous ``copytree``:

    * copy a file only when missing or stale (:func:`_mirror_is_stale`
      hash-authoritative regime, including same-size/same-mtime edits and
      backdated restores);
    * DELETE staged files whose source disappeared — under ``copytree`` a
      removed test file kept RUNNING inside the staging forever;
    * the deletion pass never leaves *destination_root* (containment of the
      root itself is guard 4's job in :func:`copy_also_copy_files`).
    """
    mutants_root = _validated_mutants_root()
    _validated_staging_destination(destination_root, mutants_root)
    for root_str, dirs, files in os.walk(source_root):
        dirs[:] = [d for d in dirs if not _is_staging_skip_dir(d)]
        rel_root = Path(root_str).relative_to(source_root)
        for name in files:
            src_file = Path(root_str) / name
            dst_file = destination_root / rel_root / name
            _validated_staging_destination(dst_file, mutants_root)
            if dst_file.exists() and not _mirror_is_stale(src_file, dst_file):
                continue
            dst_file.parent.mkdir(parents=True, exist_ok=True)
            _copy_with_retry(src_file, dst_file)

    if not destination_root.is_dir():
        return
    for root_str, dirs, files in os.walk(destination_root):
        safe_dirs: list[str] = []
        for directory in dirs:
            if _is_staging_skip_dir(directory):
                continue
            _validated_staging_destination(Path(root_str) / directory, mutants_root)
            safe_dirs.append(directory)
        dirs[:] = safe_dirs
        rel_root = Path(root_str).relative_to(destination_root)
        for name in files:
            if (source_root / rel_root / name).exists():
                continue
            _validated_staging_destination(Path(root_str) / name, mutants_root)
            with contextlib.suppress(OSError):
                (Path(root_str) / name).unlink()


def _sync_deleted_sources(
    expected_targets: set[Path], synced_roots: list[Path], skip_dirs: set[str]
) -> None:
    """Remove staged ``.py`` mirrors whose source no longer exists.

    Deleted/renamed sources used to stay in ``mutants/`` forever — tests ran
    green against deleted modules and their ``.meta`` files survived with
    them (issue #101 / A3-FD-003 + the OS-012 remainder). Deliberately
    narrow: only ``*.py`` files (plus their ``.meta``) under the mirror
    roots, using the SAME walk skip set as the copy phase, never anything
    else in the staging tree. Locked files are skipped, never fatal.

    Args:
        expected_targets: Every target path the copy walk produced.
        synced_roots: The source roots that were mirrored this run.
        skip_dirs: Directory names excluded from the copy walk.
    """
    import contextlib

    removed = 0
    mutants_root = _validated_mutants_root()
    folded_skip_dirs = {directory.casefold() for directory in skip_dirs}
    for source_root in synced_roots:
        staged_root = Path("mutants") / source_root
        _validated_staging_destination(staged_root, mutants_root)
        if not staged_root.is_dir():
            continue
        for root_str, dirs, files in os.walk(staged_root):
            safe_dirs: list[str] = []
            for directory in dirs:
                if directory.casefold() in folded_skip_dirs or directory.casefold() == "mutants":
                    continue
                _validated_staging_destination(Path(root_str) / directory, mutants_root)
                safe_dirs.append(directory)
            dirs[:] = safe_dirs
            for name in files:
                if not name.endswith(".py"):
                    continue
                staged = Path(root_str) / name
                _validated_staging_destination(staged, mutants_root)
                if staged in expected_targets:
                    continue
                with contextlib.suppress(OSError):
                    staged.unlink()
                    removed += 1
                meta = Path(str(staged) + ".meta")
                if meta.exists():
                    with contextlib.suppress(OSError):
                        meta.unlink()
    if removed:
        print(f"     removed {removed} stale staged files (sources deleted/renamed)")


def copy_also_copy_files(config: MutmutConfig) -> None:
    """Sync config.also_copy files/directories into the mutants/ directory.

    Trees are mirrored mtime-aware INCLUDING deletions via
    :func:`_sync_tree` (issue #129 / 360°-B6b+C2: ``copytree`` re-copied
    everything on every run and never deleted — removed test files kept
    running inside the staging forever). Cache/venv/tooling directories are
    skipped via the shared ``_STAGING_SKIP_DIRS`` walk filter.

    Args:
        config: Active ``MutmutConfig`` instance.
    """
    # extra_paths (Bug #69) are handled by the same copy mechanism as also_copy.
    # Their distinguishing trait — being added to the worker's PYTHONPATH — is
    # implemented in process/worker.py rather than here.
    paths_to_copy: list[str] = [*config.also_copy, *config.extra_paths]

    mutants_root = _validated_mutants_root()
    for path_str in paths_to_copy:
        path = Path(path_str)
        # Guard 1 (Bug #67): top-level virtualenv / cache directories must not
        # be mirrored into mutants/ even when the user lists them explicitly.
        # The walk filter inside _sync_tree only skips *children*, so a
        # top-level entry like ``also_copy = [".venv"]`` would otherwise be
        # mirrored wholesale — slow at best, broken on Windows because of
        # symlinked Scripts/python.exe.
        if _is_staging_skip_dir(path.name):
            print("     skipping", path_str, "(matches venv/cache skip list)")
            continue
        # Guard 2 (issue #101 / A3-FD-005): "." and mutants/ itself defeat the
        # name-based skip (``Path(".").name == ""``) and would nest the whole
        # project — including mutants/ and .git — into mutants/mutants.
        if path.resolve() in (Path.cwd().resolve(), mutants_root):
            print("     skipping", path_str, "(would nest the project into mutants/)")
            continue
        # Guard 3: absolute paths break Path("mutants") / path because Python
        # discards the left operand when the right is absolute, causing a
        # self-copy (source == destination).  Make them relative to CWD.
        if path.is_absolute():
            try:
                path = path.relative_to(Path.cwd())
            except ValueError:
                continue  # Path outside the project — skip
        # Sibling entries with ".." (the Bug-#69 core use case) are staged
        # under their own name — mutants/<name>, which is exactly where the
        # worker puts them on PYTHONPATH. Without this, "mutants" / "../x"
        # silently wrote OUTSIDE the staging tree (issue #101 / A3-FD-002,
        # sandbox-confirmed).
        destination = Path("mutants") / (path.name if ".." in path.parts else path)
        # Guard 4 (containment, second line of defence): whatever the entry
        # looks like, the destination must stay inside mutants/.
        _validated_staging_destination(destination, mutants_root)
        if not path.exists():
            continue
        print("     also copying", path_str)
        if path.is_file():
            _validated_staging_destination(destination, mutants_root)
            if not destination.exists() or _mirror_is_stale(path, destination):
                destination.parent.mkdir(parents=True, exist_ok=True)
                _copy_with_retry(path, destination)
        else:
            _sync_tree(path, destination)

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
    """Insert mutants/ into sys.path and remove the original source paths.

    Ensures that test processes import the *mutated* source code rather than
    the originals.  The following well-known source roots are considered:
    the current directory, ``src``, and ``source``.
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
    360°-A3), and appends the mangled method name. The result MUST equal
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
    module_name = stem.replace(os.sep, ".").replace("/", ".")
    for root in SOURCE_ROOT_NAMES:
        stripped = strip_prefix(module_name, prefix=root + ".")
        if stripped != module_name:
            # Exactly ONE root strips (src/source/pkg → source.pkg).
            module_name = stripped
            break
    mutant_name = f"{module_name}.{mutant_method_name}"
    # Collapse .__init__. to . for package __init__ modules.
    return mutant_name.replace(".__init__.", ".")


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
    # Text-mode read normalizes CRLF before the generated text is written in
    # text mode again; decoding raw CRLF and then write_text would produce
    # CRCRLF on Windows. The hash above remains byte-exact.
    source = filename.read_text(encoding="utf-8")
    generation_payload = json.dumps(
        {
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
                return existing_local, collected_warnings, True
            # No names in meta → fall through to regenerate
    except (OSError, _FastPathMissError):
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
        w = warnings.WarningMessage(
            message=SyntaxWarning(f"Unsupported syntax in {filename} ({exc!s}), skipping"),
            category=SyntaxWarning,
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
                message=SyntaxWarning(
                    f"Generated mutants for {filename} do not compile "
                    f"(line {lineno}: {exc.msg}) — copying the file unmutated. "
                    "Please report this as a mutmut-win bug."
                ),
                category=SyntaxWarning,
                filename=str(filename),
                lineno=0,
            )
            collected_warnings.append(w)
            generated = source
            mutant_names = []

    generated_hash = _atomic_write_text(output_path, generated)

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
    source_file_mutation_data.save()

    return mutant_names, collected_warnings, False
