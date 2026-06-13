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
import os
import shutil
import sys
import time
import warnings
from io import StringIO
from pathlib import Path
from typing import IO, TYPE_CHECKING

import libcst as cst

from mutmut_win.constants import SOURCE_ROOT_NAMES
from mutmut_win.models import SourceFileMutationData

if TYPE_CHECKING:
    from collections.abc import Iterator

    from mutmut_win.config import MutmutConfig

#: Directory names excluded from every staging walk (mirror AND also_copy).
#: One list for both passes (issue #129 / 360°-C4): the two sites used to
#: carry diverging literals, and tooling trees (node_modules, .claude, …)
#: were mirrored into mutants/ on every first run.
_STAGING_SKIP_DIRS: frozenset[str] = frozenset(
    {
        ".venv",
        "venv",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".git",
        ".hypothesis",
        "mutants",
        ".mutmut-cache",
        # Tooling/cache trees that have no business inside the staging
        # (issue #129 / 360°-C4).
        "node_modules",
        ".import_linter_cache",
        ".benchmarks",
        ".serena",
        ".claude",
        ".idea",
        ".vscode",
    }
)


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
            for root, _dirs, files in os.walk(path):
                for filename in files:
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
    for attempt in range(max_attempts):
        try:
            if is_tree:
                shutil.copytree(src, dst, **kwargs)  # type: ignore[arg-type]
            else:
                shutil.copy2(src, dst)
            return
        except OSError:
            if attempt < max_attempts - 1:
                time.sleep(0.1 * (2**attempt))
    # Final attempt — let the exception propagate if it still fails.
    if is_tree:
        shutil.copytree(src, dst, **kwargs)  # type: ignore[arg-type]
    else:
        shutil.copy2(src, dst)


def copy_src_dir(config: MutmutConfig) -> None:  # noqa: ARG001 — config kept for API compatibility; source dirs are auto-detected
    """Copy the ENTIRE source tree to the mutants/ staging directory.

    Copies ALL files from standard source directories (the
    ``SOURCE_ROOT_NAMES`` roots plus the project root) — not just the files
    in ``paths_to_mutate``.  This ensures that non-mutated modules are
    available for import when pytest runs inside ``mutants/``.  Without
    this, cross-package imports in conftest.py fail.

    ``paths_to_mutate`` only controls which files get **mutated**, not
    which files get **copied**.

    Updates files whose source has been modified since the last copy —
    equality fingerprint (mtime AND size) for plain mirror copies, strictly
    newer for generator-owned files with a ``.meta`` sibling (see
    :func:`_mirror_is_stale`, issue #129 / 360°-B6a).

    Args:
        config: Active ``MutmutConfig`` instance.
    """
    expected_targets: set[Path] = set()
    synced_roots: list[Path] = []

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
            dirs[:] = [d for d in dirs if d not in _STAGING_SKIP_DIRS]
            if source_root_name == "." and root_str == ".":
                # The explicit roots above already mirrored src/source —
                # walking them again from "." doubled the largest trees
                # (issue #129 / 360°-C4). Top level only: a NESTED foo/src
                # is not covered by the explicit roots and must stay.
                dirs[:] = [d for d in dirs if d not in SOURCE_ROOT_NAMES]

            for name in files:
                source_path = Path(root_str) / name
                target_path = Path("mutants") / root_str / name
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


def _mirror_is_stale(source: Path, target: Path) -> bool:
    """Return True if the staged mirror *target* must be refreshed.

    Two regimes (issue #129 / 360°-B6a):

    * Files WITH a ``.meta`` sibling are (or were) mutation targets — their
      staged content is the trampolined GENERATOR output (newer and bigger
      than the source by construction) and the ``.meta`` source fingerprint
      is the staleness truth there. The mirror refreshes them only when the
      source is strictly NEWER (the pre-#129 rule): an equality rule would
      overwrite the trampoline with the plain source on every run and break
      the forced-fail gate.
    * Plain mirror copies (no ``.meta``) were created by ``copy2`` and
      therefore carry the SOURCE's mtime/size — any inequality means the
      source changed, including a git restore with an OLDER timestamp,
      which the previous ``>`` comparison silently served stale.
    """
    try:
        src_stat = source.stat()
        dst_stat = target.stat()
    except OSError:
        return True
    if target.with_name(target.name + ".meta").exists():
        return src_stat.st_mtime > dst_stat.st_mtime
    return src_stat.st_mtime != dst_stat.st_mtime or src_stat.st_size != dst_stat.st_size


def _sync_tree(source_root: Path, destination_root: Path) -> None:
    """Mirror *source_root* into *destination_root* (issue #129 / B6b+C2).

    mtime-aware per-file sync replacing the previous ``copytree``:

    * copy a file only when missing or stale (:func:`_mirror_is_stale`
      equality regime — ``copy2`` preserves mtimes, so any inequality means
      the source changed, including backdated restores);
    * DELETE staged files whose source disappeared — under ``copytree`` a
      removed test file kept RUNNING inside the staging forever;
    * the deletion pass never leaves *destination_root* (containment of the
      root itself is guard 4's job in :func:`copy_also_copy_files`).
    """
    import contextlib

    for root_str, dirs, files in os.walk(source_root):
        dirs[:] = [d for d in dirs if d not in _STAGING_SKIP_DIRS]
        rel_root = Path(root_str).relative_to(source_root)
        for name in files:
            src_file = Path(root_str) / name
            dst_file = destination_root / rel_root / name
            if dst_file.exists() and not _mirror_is_stale(src_file, dst_file):
                continue
            dst_file.parent.mkdir(parents=True, exist_ok=True)
            _copy_with_retry(src_file, dst_file)

    if not destination_root.is_dir():
        return
    for root_str, dirs, files in os.walk(destination_root):
        dirs[:] = [d for d in dirs if d not in _STAGING_SKIP_DIRS]
        rel_root = Path(root_str).relative_to(destination_root)
        for name in files:
            if (source_root / rel_root / name).exists():
                continue
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
    for source_root in synced_roots:
        staged_root = Path("mutants") / source_root
        if not staged_root.is_dir():
            continue
        for root_str, dirs, files in os.walk(staged_root):
            dirs[:] = [d for d in dirs if d not in skip_dirs and d != "mutants"]
            for name in files:
                if not name.endswith(".py"):
                    continue
                staged = Path(root_str) / name
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

    mutants_root = Path("mutants").resolve()
    for path_str in paths_to_copy:
        path = Path(path_str)
        # Guard 1 (Bug #67): top-level virtualenv / cache directories must not
        # be mirrored into mutants/ even when the user lists them explicitly.
        # The walk filter inside _sync_tree only skips *children*, so a
        # top-level entry like ``also_copy = [".venv"]`` would otherwise be
        # mirrored wholesale — slow at best, broken on Windows because of
        # symlinked Scripts/python.exe.
        if path.name in _STAGING_SKIP_DIRS:
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
        try:
            destination.resolve().relative_to(mutants_root)
        except ValueError:
            print(f"     skipping {path_str} (destination escapes the staging directory)")
            continue
        if not path.exists():
            continue
        print("     also copying", path_str)
        if path.is_file():
            if not destination.exists() or _mirror_is_stale(path, destination):
                destination.parent.mkdir(parents=True, exist_ok=True)
                _copy_with_retry(path, destination)
        else:
            _sync_tree(path, destination)

    # Sanitise the copied pyproject.toml — remove [tool.uv.sources] entries
    # that contain relative paths. These paths are relative to the original
    # project root and break when resolved from mutants/ (one level deeper).
    _sanitise_mutants_pyproject()


def config_fingerprint_matches(config: MutmutConfig) -> bool:
    """Check (and persist) the mutant-universe fingerprint of *config*.

    The generation fast path reuses ``.meta`` mutant names when the source
    is unchanged — but the UNIVERSE also depends on configuration:
    ``paths_to_mutate``, ``do_not_mutate``, ``mutate_only_covered_lines``,
    ``also_copy``/``extra_paths``. Editing any of these used to leave a
    stale mutant universe in place without warning (issue #101 /
    A3-OS-008). The orchestrator calls this once per run and disables the
    fast path when the fingerprint changed.

    Args:
        config: Active ``MutmutConfig``.

    Returns:
        ``True`` if the persisted fingerprint matches *config* (fast path
        allowed); ``False`` on first run or after a universe-relevant
        change — the new fingerprint is persisted either way.
    """
    import hashlib
    import json

    import mutmut_win

    payload = json.dumps(
        {
            # Issue #129 / 360°-A8: an engine upgrade changes the mutant
            # universe (new/changed operators) — without the version in the
            # fingerprint the fast path kept the OLD universe and its reuse
            # candidates alive until an unrelated source edit or --force.
            "engine_version": mutmut_win.__version__,
            "paths_to_mutate": sorted(config.paths_to_mutate),
            "do_not_mutate": sorted(config.do_not_mutate),
            "mutate_only_covered_lines": config.mutate_only_covered_lines,
            "also_copy": sorted(config.also_copy),
            "extra_paths": sorted(config.extra_paths),
        },
        sort_keys=True,
    )
    fingerprint = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    fingerprint_path = Path("mutants") / ".mutmut-config-fingerprint"

    try:
        stored = fingerprint_path.read_text(encoding="utf-8").strip()
    except OSError:
        stored = None

    if stored == fingerprint:
        return True
    fingerprint_path.parent.mkdir(parents=True, exist_ok=True)
    fingerprint_path.write_text(fingerprint, encoding="utf-8")
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
                pyproject_path.write_text(cleaned, encoding="utf-8")
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
) -> list[str]:
    """Generate mutated code and write it to *out*.

    Args:
        out: Writable text stream to receive the mutated source.
        source: Original Python source code.
        filename: Path to the source file (used by the mutation engine for
            context; the file is not re-read).
        covered_lines: Optional set of line numbers to restrict mutations to.

    Returns:
        List of mangled mutant method names (e.g. ``["add__mutmut_1", ...]``).
    """
    from mutmut_win.mutation import mutate_file_contents

    result, mutant_names = mutate_file_contents(str(filename), source, covered_lines)
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

    # Write guard (issue #75 / A3-CM-001): with absolute paths_to_mutate,
    # ``Path("mutants") / <abs>`` collapses to ``<abs>`` and *output_path*
    # becomes the source file itself.  Refuse loudly instead of destroying
    # the user's code — this also defends callers that bypass the config
    # validator (e.g. CLI overrides via ``model_copy``).
    if output_path.resolve() == filename.resolve():
        msg = (
            f"Refusing to write mutants into the source file itself "
            f"({filename}) — paths_to_mutate must be relative to the project "
            "root (issue #75)."
        )
        raise ValueError(msg)

    # Fast-path: if the source is unchanged since we last mutated it, reuse
    # the existing mutant names from the .meta file instead of re-generating.
    # This enables repeated runs: the orchestrator gets the task list even
    # though the mutated file already exists in mutants/.
    # The comparison is against the SOURCE fingerprint recorded in .meta at
    # generation time (mtime AND size, equality not ordering) — the old
    # `source_mtime < target_mtime` check missed restores with OLD
    # timestamps (issue #101 / A3-FD-004, sandbox-confirmed).
    # The orchestrator passes allow_fast_path=False when the config
    # fingerprint changed (issue #101 / A3-OS-008) — a different mutant
    # universe must be regenerated regardless of file timestamps.
    try:
        source_stat = filename.stat()
        if allow_fast_path and output_path.exists():
            source_file_mutation_data = SourceFileMutationData(path=str(filename))
            source_file_mutation_data.load()
            fingerprint_ok = (
                source_file_mutation_data.source_mtime == source_stat.st_mtime
                and source_file_mutation_data.source_size == source_stat.st_size
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

    source = filename.read_text(encoding="utf-8")

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
            )
        collected_warnings.extend(engine_warnings)
        generated = buf.getvalue()
    except (cst.ParserSyntaxError, cst.CSTValidationError, ValueError) as exc:
        # libcst cannot parse this file, or the engine hit an unmutatable
        # construct (e.g. an identifier containing the U+01C1 mangling
        # separator) — copy unchanged so tests still run (issue #78).
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

    output_path.write_text(generated, encoding="utf-8")

    # Persist the mutation metadata for this file, including the source
    # fingerprint the fast path compares against (issue #101 / A3-FD-004).
    source_file_mutation_data = SourceFileMutationData(path=str(filename))
    source_file_mutation_data.exit_code_by_key = {
        get_mutant_name(filename, name): None for name in mutant_names
    }
    try:
        stat = filename.stat()
        source_file_mutation_data.source_mtime = stat.st_mtime
        source_file_mutation_data.source_size = stat.st_size
    except OSError:
        pass
    source_file_mutation_data.save()

    return mutant_names, collected_warnings, False
