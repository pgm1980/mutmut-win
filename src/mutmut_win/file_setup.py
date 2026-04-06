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
import warnings
from io import StringIO
from pathlib import Path
from typing import IO, TYPE_CHECKING

import libcst as cst

from mutmut_win.models import SourceFileMutationData

if TYPE_CHECKING:
    from collections.abc import Iterator

    from mutmut_win.config import MutmutConfig


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


def copy_src_dir(config: MutmutConfig) -> None:
    """Copy source files to the mutants/ staging directory.

    Preserves the directory structure relative to the project root.
    Updates files whose source has been modified since the last copy
    (mtime comparison).  Uses ``shutil.copy2`` to preserve modification
    times so subsequent runs can detect changes.

    Args:
        config: Active ``MutmutConfig`` instance.
    """
    for root, name in walk_all_files(config):
        source_path = Path(root) / name
        target_path = Path("mutants") / root / name

        if target_path.exists():
            # Update if source is newer than the copy in mutants/.
            if source_path.is_file() and _source_is_newer(source_path, target_path):
                shutil.copy2(source_path, target_path)
                print(f"     updated: {source_path} (source changed since last run)")
                # Invalidate cached mutation results for this file —
                # the .meta file contains exit codes from the previous run
                # which are now stale because the source changed.
                meta_path = Path(str(target_path) + ".meta")
                if meta_path.exists():
                    meta_path.unlink()
            continue

        if source_path.is_dir():
            shutil.copytree(source_path, target_path)
        else:
            target_path.parent.mkdir(exist_ok=True, parents=True)
            # copy2 preserves mtime so create_mutants_for_file can detect
            # whether the source was modified after the mutant was created.
            shutil.copy2(source_path, target_path)


def _source_is_newer(source: Path, target: Path) -> bool:
    """Return True if *source* was modified more recently than *target*."""
    try:
        return source.stat().st_mtime > target.stat().st_mtime
    except OSError:
        return True


def copy_also_copy_files(config: MutmutConfig) -> None:
    """Copy config.also_copy files/directories into the mutants/ directory.

    Skips ``.venv``, ``__pycache__``, and other cache directories to avoid
    copying virtual environments (which contain symlinks that fail on Windows).

    Args:
        config: Active ``MutmutConfig`` instance.
    """
    skip_dirs = {".venv", "venv", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}

    # shutil.copytree ignore callback signature requires (directory, files)
    def _ignore_venvs(
        _directory: str,
        files: list[str],
    ) -> list[str]:
        return [f for f in files if f in skip_dirs]

    for path_str in config.also_copy:
        print("     also copying", path_str)
        path = Path(path_str)
        destination = Path("mutants") / path
        if not path.exists():
            continue
        if path.is_file():
            shutil.copy2(path, destination)
        else:
            shutil.copytree(path, destination, dirs_exist_ok=True, ignore=_ignore_venvs)

    # Sanitise the copied pyproject.toml — remove [tool.uv.sources] entries
    # that contain relative paths. These paths are relative to the original
    # project root and break when resolved from mutants/ (one level deeper).
    _sanitise_mutants_pyproject()


def _sanitise_mutants_pyproject() -> None:
    """Remove [tool.uv.sources] from the copied pyproject.toml in mutants/.

    When mutmut-win copies pyproject.toml into the mutants/ staging directory,
    any ``[tool.uv.sources]`` entries with relative paths (e.g.
    ``../../_deps/my-package``) break because mutants/ is one directory level
    deeper. Removing the entire section is safe — the mutants/ directory uses
    the parent project's venv via sys.executable, not its own.

    This prevents the "Distribution not found at: file:///..." error on
    repeated mutation testing runs.
    """
    pyproject_path = Path("mutants") / "pyproject.toml"
    if not pyproject_path.exists():
        return

    try:
        content = pyproject_path.read_text(encoding="utf-8")
    except OSError:
        return

    # Remove [tool.uv.sources] section (TOML section until next [section] or EOF).
    import re

    # Match [tool.uv.sources] and everything until the next top-level section
    cleaned = re.sub(
        r'\[tool\.uv\.sources\]\s*\n(?:(?!\[)[^\n]*\n)*',
        '',
        content,
    )

    # Also remove [tool.uv] if it only contained sources (now empty)
    cleaned = re.sub(
        r'\[tool\.uv\]\s*\n(?=\[|\Z)',
        '',
        cleaned,
    )

    if cleaned != content:
        pyproject_path.write_text(cleaned, encoding="utf-8")


# ---------------------------------------------------------------------------
# sys.path manipulation
# ---------------------------------------------------------------------------


def setup_source_paths() -> None:
    """Insert mutants/ into sys.path and remove the original source paths.

    Ensures that test processes import the *mutated* source code rather than
    the originals.  The following well-known source roots are considered:
    the current directory, ``src``, and ``source``.
    """
    source_code_paths = [Path(), Path("src"), Path("source")]

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

    Converts a relative source file path to a dotted module name, strips any
    leading ``src.`` prefix, and appends the mangled method name.

    For example::

        get_mutant_name(Path("src/my_lib/utils.py"), "add__mutmut_1")
        # -> "my_lib.utils.add__mutmut_1"

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
    module_name = strip_prefix(module_name, prefix="src.")
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


def create_mutants_for_file(
    filename: Path,
    output_path: Path,
    covered_lines: set[int] | None = None,
) -> tuple[list[str], list[warnings.WarningMessage]]:
    """Generate mutants for a single source file and write to *output_path*.

    Reads the source, runs the mutation engine, writes the mutated code to
    *output_path*, validates the generated syntax, and saves a
    ``SourceFileMutationData`` meta file.

    If the source file is unmodified since the last mutant generation (detected
    via mtime comparison) the function returns early with an empty list.

    Args:
        filename: Path to the original source file.
        output_path: Path where the mutated file should be written.
        covered_lines: Optional set of line numbers to restrict mutations to.

    Returns:
        A tuple of (mutant_names, warnings) where *mutant_names* is a list of
        mangled method names and *warnings* is a list of any parse warnings.
    """
    collected_warnings: list[warnings.WarningMessage] = []

    # Fast-path: if the source is unchanged since we last mutated it, reuse
    # the existing mutant names from the .meta file instead of re-generating.
    # This enables repeated runs: the orchestrator gets the task list even
    # though the mutated file already exists in mutants/.
    try:
        source_mtime = filename.stat().st_mtime
        mutant_mtime = output_path.stat().st_mtime
        if source_mtime < mutant_mtime:
            source_file_mutation_data = SourceFileMutationData(path=str(filename))
            source_file_mutation_data.load()
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
                return existing_local, collected_warnings
            # No names in meta → fall through to regenerate
    except OSError:
        pass

    source = filename.read_text(encoding="utf-8")

    mutant_names: list[str]
    with output_path.open("w", encoding="utf-8") as out:
        try:
            buf = StringIO()
            mutant_names = write_all_mutants_to_file(
                out=buf,
                source=source,
                filename=filename,
                covered_lines=covered_lines,
            )
            out.write(buf.getvalue())
        except cst.ParserSyntaxError as exc:
            # libcst cannot parse this file — copy unchanged so tests still run.
            w = warnings.WarningMessage(
                message=SyntaxWarning(f"Unsupported syntax in {filename} ({exc!s}), skipping"),
                category=SyntaxWarning,
                filename=str(filename),
                lineno=0,
            )
            collected_warnings.append(w)
            out.write(source)
            mutant_names = []

    # Validate that the generated output has no syntax errors.
    try:
        ast.parse(output_path.read_text(encoding="utf-8"))
    except (IndentationError, SyntaxError):
        # Return empty names so the caller skips this file gracefully.
        return [], collected_warnings

    # Persist the mutation metadata for this file.
    source_file_mutation_data = SourceFileMutationData(path=str(filename))
    source_file_mutation_data.exit_code_by_key = {
        get_mutant_name(filename, name): None for name in mutant_names
    }
    source_file_mutation_data.save()

    return mutant_names, collected_warnings
