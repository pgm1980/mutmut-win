"""CST-based diff and apply helpers for mutmut-win mutants.

Ported from mutmut 3.5.0 reference implementation.  All functions operate
on files under the ``mutants/`` staging directory produced by
``file_setup.write_all_mutants_to_file``.
"""

from __future__ import annotations

import shutil
from difflib import unified_diff
from pathlib import Path
from typing import TYPE_CHECKING, cast

import libcst as cst

from mutmut_win.exceptions import MutationParseError
from mutmut_win.file_setup import walk_source_files
from mutmut_win.models import SourceFileMutationData
from mutmut_win.test_mapping import (
    mangled_name_from_mutant_name,
    orig_function_and_class_names_from_key,
)

if TYPE_CHECKING:
    from mutmut_win.config import MutmutConfig


def find_mutant(mutant_name: str, config: MutmutConfig) -> SourceFileMutationData:
    """Find which source file contains the given mutant name.

    Walks all source files declared in *config* and returns the
    ``SourceFileMutationData`` whose ``exit_code_by_key`` contains
    *mutant_name*.

    Args:
        mutant_name: Fully qualified mutant identifier (e.g.
            ``src.pkg.mod.x_func__mutmut_1``).
        config: Active ``MutmutConfig`` instance (provides ``paths_to_mutate``
            and ``should_ignore_for_mutation``).

    Returns:
        The ``SourceFileMutationData`` for the source file that owns
        *mutant_name*.

    Raises:
        FileNotFoundError: If no source file contains *mutant_name*.
    """
    for path in walk_source_files(config):
        if config.should_ignore_for_mutation(path):
            continue
        m = SourceFileMutationData(path=str(path))
        m.load()
        if mutant_name in m.exit_code_by_key:
            return m

    raise FileNotFoundError(f"Could not find mutant {mutant_name}")


def read_mutants_module(path: Path | str) -> cst.Module:
    """Read and parse the mutated file from the ``mutants/`` directory.

    Args:
        path: Relative path to the source file (e.g. ``src/pkg/mod.py``).

    Returns:
        Parsed ``libcst.Module`` for the corresponding mutants file.

    Raises:
        MutationParseError: If the staged file is not parseable Python
            (issue #114 / A4-QX-006 — used to leak raw libcst errors).
    """
    target = Path("mutants") / path
    with target.open(encoding="utf-8") as f:
        source = f.read()
    try:
        return cst.parse_module(source)
    except cst.ParserSyntaxError as exc:
        msg = f"cannot parse staged file {target}: {exc}"
        raise MutationParseError(msg) from exc


def read_orig_module(path: Path | str) -> cst.Module:
    """Read and parse the original source file.

    Args:
        path: Relative path to the source file.

    Returns:
        Parsed ``libcst.Module`` for the original (un-mutated) source.

    Raises:
        MutationParseError: If the source file is not parseable Python
            (issue #114 / A4-QX-006).
    """
    with Path(path).open(encoding="utf-8") as f:
        source = f.read()
    try:
        return cst.parse_module(source)
    except cst.ParserSyntaxError as exc:
        msg = f"cannot parse source file {path}: {exc}"
        raise MutationParseError(msg) from exc


def find_top_level_function_or_method(module: cst.Module, name: str) -> cst.FunctionDef | None:
    """Find a function or method by name in a CST module.

    Searches top-level functions and methods of top-level classes.
    Only the trailing component after the last ``.`` is used for matching.

    Args:
        module: Parsed ``libcst.Module`` to search.
        name: Fully-qualified or simple name of the function/method.

    Returns:
        The matching ``cst.FunctionDef`` node, or ``None`` if not found.
    """
    name = name.split(".")[-1]
    for child in module.body:
        if isinstance(child, cst.SimpleStatementLine):
            continue
        if isinstance(child, cst.FunctionDef) and child.name.value == name:
            return child
        if isinstance(child, cst.ClassDef) and isinstance(child.body, cst.IndentedBlock):
            for method in child.body.body:
                if isinstance(method, cst.FunctionDef) and method.name.value == name:
                    return method
    return None


def _find_function_in_scope(
    module: cst.Module, name: str, class_name: str | None
) -> cst.FunctionDef | None:
    """Scope-exact lookup for ``apply`` (issue #75 / A4-UI-001).

    Unlike :func:`find_top_level_function_or_method` (first match in ANY
    scope — fine for the unique mangled names inside the mutants file), this
    matches exactly the scope encoded in the mutant name: a top-level
    function when *class_name* is ``None``, otherwise a method of the
    top-level class named *class_name*.  Without this, applying
    ``xǁBǁgreet__mutmut_1`` patched ``A.greet`` when class ``A`` came first.

    Args:
        module: Parsed ``libcst.Module`` to search.
        name: Simple function/method name.
        class_name: Owning class name from the mutant key, or ``None`` for a
            top-level function.

    Returns:
        The matching ``cst.FunctionDef`` node, or ``None`` if not found.
    """
    for child in module.body:
        if class_name is None:
            if isinstance(child, cst.FunctionDef) and child.name.value == name:
                return child
            continue
        if (
            isinstance(child, cst.ClassDef)
            and child.name.value == class_name
            and isinstance(child.body, cst.IndentedBlock)
        ):
            for method in child.body.body:
                if isinstance(method, cst.FunctionDef) and method.name.value == name:
                    return method
    return None


def read_original_function(module: cst.Module, mutant_name: str) -> cst.FunctionDef:
    """Extract the original function from a mutated module (the ``_orig`` copy).

    The mutated module contains both ``<func>__mutmut_orig`` (the original
    body) and numbered variants ``<func>__mutmut_N``.  This function locates
    the ``_orig`` copy and returns it renamed to the un-mangled function name.

    Args:
        module: Parsed ``libcst.Module`` of the mutants file.
        mutant_name: Fully qualified mutant identifier used to derive the
            original function name and ``_orig`` copy name.

    Returns:
        The ``cst.FunctionDef`` node with the original name restored.

    Raises:
        FileNotFoundError: If the ``_orig`` copy cannot be found in *module*.
    """
    orig_function_name, _ = orig_function_and_class_names_from_key(mutant_name)
    orig_name = mangled_name_from_mutant_name(mutant_name) + "__mutmut_orig"

    result = find_top_level_function_or_method(module, orig_name)
    if not result:
        raise FileNotFoundError(f'Could not find original function "{orig_function_name}"')
    return result.with_changes(name=cst.Name(orig_function_name))


def read_mutant_function(module: cst.Module, mutant_name: str) -> cst.FunctionDef:
    """Extract a specific mutant function from a mutated module.

    Args:
        module: Parsed ``libcst.Module`` of the mutants file.
        mutant_name: Fully qualified mutant identifier (e.g.
            ``src.pkg.mod.x_func__mutmut_1``).

    Returns:
        The ``cst.FunctionDef`` node for this mutant, renamed to the
        original function name.

    Raises:
        FileNotFoundError: If the mutant function cannot be found in *module*.
    """
    orig_function_name, _ = orig_function_and_class_names_from_key(mutant_name)

    result = find_top_level_function_or_method(module, mutant_name)
    if not result:
        raise FileNotFoundError(f'Could not find mutant function "{orig_function_name}"')
    return result.with_changes(name=cst.Name(orig_function_name))


def render_function_diff(path: Path | str, mutant_name: str) -> str:
    """Render the per-mutant function diff from a known mutants file.

    The single diff renderer (issue #108 / A4-UI-007): ``show`` reaches it
    via :func:`get_diff_for_mutant`, the TUI browser calls it directly —
    only the path DISCOVERY differs between the two consumers.

    Args:
        path: Source file path relative to the project root (the mutants
            copy is read from ``mutants/<path>``).
        mutant_name: Fully qualified mutant identifier.

    Returns:
        A unified diff string (possibly empty if no difference is detected).

    Raises:
        FileNotFoundError: If the ``_orig`` copy or the mutant function is
            missing from the mutants file.
        OSError: If the mutants file cannot be read.
    """
    module = read_mutants_module(path)
    orig_code = cst.Module([read_original_function(module, mutant_name)]).code.strip()
    mutant_code = cst.Module([read_mutant_function(module, mutant_name)]).code.strip()

    path_str = str(path)  # difflib requires str, not Path
    return "\n".join(
        line
        for line in unified_diff(
            orig_code.split("\n"),
            mutant_code.split("\n"),
            fromfile=path_str,
            tofile=path_str,
            lineterm="",
        )
    )


def get_diff_for_mutant(mutant_name: str, config: MutmutConfig) -> str:
    """Generate unified diff between original and mutant function.

    Reads the mutants file, extracts both the ``_orig`` copy and the numbered
    mutant variant, and returns a unified diff string suitable for display.

    Args:
        mutant_name: Fully qualified mutant identifier.
        config: Active ``MutmutConfig`` instance.

    Returns:
        A unified diff string (possibly empty if no difference is detected).
    """
    m = find_mutant(mutant_name, config)
    return render_function_diff(m.path, mutant_name)


def apply_mutant(mutant_name: str, config: MutmutConfig) -> None:
    """Apply a mutant's code to the original source file using CST deep_replace.

    Reads the mutants file to find the mutant function body, then patches the
    original source file so the named function contains the mutated code.

    Safety (issue #75): the lookup is scope-exact (the mutant's class name is
    honoured, A4-UI-001), reads/writes are byte-exact so the original line
    endings survive (A4-UI-002), the previous content is backed up next to
    the source as ``<name>.mutmut-orig.bak`` (overwritten on repeated apply),
    the write is atomic (temp file + ``os.replace``), and the call refuses to
    run when the source changed after its mutants were generated (A4-UI-003).

    Args:
        mutant_name: Fully qualified mutant identifier.
        config: Active ``MutmutConfig`` instance.

    Raises:
        FileNotFoundError: If the mutant or the original function cannot be
            found.
        RuntimeError: If the source file is newer than its ``mutants/`` copy
            (stale staging — re-run ``mutmut-win run`` first).
    """
    path = find_mutant(mutant_name, config).path
    source_path = Path(path)
    mutants_path = Path("mutants") / path

    if source_path.stat().st_mtime > mutants_path.stat().st_mtime:
        msg = (
            f"{source_path} changed after its mutants were generated — "
            "re-run 'mutmut-win run' before applying mutants."
        )
        raise RuntimeError(msg)

    orig_function_name, class_name = orig_function_and_class_names_from_key(mutant_name)
    orig_function_name = orig_function_name.rpartition(".")[-1]

    # Byte-exact reads: no universal-newline translation, so the patched file
    # keeps the original line endings.
    orig_module = cst.parse_module(source_path.read_bytes().decode("utf-8"))
    mutants_module = cst.parse_module(mutants_path.read_bytes().decode("utf-8"))

    mutant_function = read_mutant_function(mutants_module, mutant_name)
    mutant_function = mutant_function.with_changes(name=cst.Name(orig_function_name))

    original_function = _find_function_in_scope(orig_module, orig_function_name, class_name)
    if not original_function:
        raise FileNotFoundError(f"Could not apply mutant {mutant_name}")

    # libcst.deep_replace is typed to return CSTNode; we know the result is Module.
    new_module = cast("cst.Module", orig_module.deep_replace(original_function, mutant_function))

    backup_path = source_path.with_name(source_path.name + ".mutmut-orig.bak")
    shutil.copy2(source_path, backup_path)

    tmp_file = source_path.with_name(source_path.name + ".mutmut-apply.tmp")
    tmp_file.write_bytes(new_module.bytes)
    tmp_file.replace(source_path)
