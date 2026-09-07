"""CST-based diff and apply helpers for mutmut-win mutants.

Ported from mutmut 3.5.0 reference implementation.  All functions operate
on files under the ``mutants/`` staging directory produced by
``file_setup.write_all_mutants_to_file``.
"""

from __future__ import annotations

import codecs
import hashlib
import stat
import tokenize
from difflib import unified_diff
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING, cast

import libcst as cst

from mutmut_win.atomic_file import atomic_write_bytes
from mutmut_win.exceptions import (
    AmbiguousMutantNameError,
    MutationParseError,
    StaleStagingError,
)
from mutmut_win.file_setup import read_verified_generated_bytes, walk_source_files
from mutmut_win.models import SourceFileMutationData
from mutmut_win.test_mapping import (
    function_definition_location_from_key,
    mangled_name_from_mutant_name,
    match_mutant_names,
    orig_function_and_class_names_from_key,
)

if TYPE_CHECKING:
    from mutmut_win.config import MutmutConfig


def _decode_python_bytes(payload: bytes, path: Path | str) -> tuple[str, str]:
    """Decode source bytes under Python's PEP 263 rules."""
    try:
        encoding, _consumed = tokenize.detect_encoding(BytesIO(payload).readline)
        return payload.decode(encoding), encoding
    except (LookupError, SyntaxError, UnicodeDecodeError) as exc:
        msg = f"cannot decode Python source file {path}: {exc}"
        raise MutationParseError(msg) from exc


def _read_source_bytes_matching_staging(
    path: Path | str,
    expected_source_hash: str | None,
) -> bytes:
    """Read source bytes only when they match the generation-time digest."""
    source_path = Path(path)
    source_bytes = source_path.read_bytes()
    current_hash = hashlib.sha256(source_bytes).hexdigest()
    if expected_source_hash is None or current_hash != expected_source_hash:
        msg = (
            f"{source_path} content cannot be proven to match the source used for "
            "mutant generation — re-run 'mutmut-win run' before showing or applying "
            "mutants."
        )
        raise StaleStagingError(msg)
    return source_bytes


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


def resolve_mutant(pattern: str, config: MutmutConfig) -> tuple[str, SourceFileMutationData]:
    """Resolve a mutant name or glob pattern to exactly ONE mutant.

    The ``show``/``apply`` front door (issue #115 / A4-UI-012): exact names
    and glob patterns go through the same matcher as ``run``, but these
    commands operate on a single mutant — an ambiguous pattern fails with
    the candidate list instead of guessing (or applying everything).

    Args:
        pattern: Mutant name or fnmatch pattern supplied by the user.
        config: Active ``MutmutConfig`` instance.

    Returns:
        Tuple of the resolved mutant name and the owning
        ``SourceFileMutationData``.

    Raises:
        FileNotFoundError: If nothing matches *pattern*.
        AmbiguousMutantNameError: If more than one mutant matches.
    """
    matches: list[tuple[str, SourceFileMutationData]] = []
    for path in walk_source_files(config):
        if config.should_ignore_for_mutation(path):
            continue
        m = SourceFileMutationData(path=str(path))
        m.load()
        matches.extend((key, m) for key in match_mutant_names([pattern], m.exit_code_by_key))

    if not matches:
        raise FileNotFoundError(f"Could not find mutant {pattern}")
    if len(matches) > 1:
        shown = [name for name, _ in matches[:10]]
        more = "" if len(matches) <= 10 else f"\n  … and {len(matches) - 10} more"
        msg = (
            f"Pattern {pattern!r} matches {len(matches)} mutants — be specific:\n  "
            + "\n  ".join(shown)
            + more
        )
        raise AmbiguousMutantNameError(msg)
    return matches[0]


def read_mutants_module(
    path: Path | str,
    *,
    expected_generated_hash: str | None = None,
    require_verified: bool = False,
) -> cst.Module:
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
    payload = (
        read_verified_generated_bytes(path, expected_generated_hash)
        if require_verified
        else target.read_bytes()
    )
    source, _encoding = _decode_python_bytes(payload, target)
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
    source, _encoding = _decode_python_bytes(Path(path).read_bytes(), path)
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
    module: cst.Module,
    name: str,
    class_name: str | None,
    definition_ordinal: int = 1,
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
        definition_ordinal: One-based occurrence among same-named definitions
            in the encoded scope. Method occurrences span repeated top-level
            class definitions with the same class name in module order.

    Returns:
        The matching ``cst.FunctionDef`` node, or ``None`` if not found.
    """
    if definition_ordinal < 1:
        return None
    matches_seen = 0
    for child in module.body:
        if class_name is None:
            if isinstance(child, cst.FunctionDef) and child.name.value == name:
                matches_seen += 1
                if matches_seen == definition_ordinal:
                    return child
            continue
        if (
            isinstance(child, cst.ClassDef)
            and child.name.value == class_name
            and isinstance(child.body, cst.IndentedBlock)
        ):
            for method in child.body.body:
                if isinstance(method, cst.FunctionDef) and method.name.value == name:
                    matches_seen += 1
                    if matches_seen == definition_ordinal:
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


def _public_mutant_function(
    original_function: cst.FunctionDef,
    mutants_module: cst.Module,
    mutant_name: str,
) -> cst.FunctionDef:
    """Rebuild a mutant on the original public function declaration.

    Private implementations in ``mutants/`` intentionally omit defaults,
    annotations, decorators, return annotations, type parameters and leading
    lines so importing the staged module cannot repeat user definition-time
    side effects.  Those implementation-only normalisations must never leak
    into ``show`` or ``apply``.  Only the mutated body belongs to the selected
    mutant; the public declaration remains byte-for-byte CST-equivalent to the
    current source definition.
    """
    private_mutant = read_mutant_function(mutants_module, mutant_name)
    return original_function.with_changes(body=private_mutant.body)


def _source_modules_for_mutant(
    path: Path | str,
    source_bytes: bytes,
    mutants_module: cst.Module,
    mutant_name: str,
) -> tuple[cst.Module, cst.Module, str]:
    """Return a verified source module and its one-function mutant variant."""
    source, encoding = _decode_python_bytes(source_bytes, path)
    try:
        original_module = cst.parse_module(source)
    except cst.ParserSyntaxError as exc:
        msg = f"cannot parse source file {path}: {exc}"
        raise MutationParseError(msg) from exc

    location = function_definition_location_from_key(mutant_name)
    original_function = _find_function_in_scope(
        original_module,
        location.function_name,
        location.class_name,
        location.definition_ordinal,
    )
    if original_function is None:
        location_text = (
            f"{location.class_name}.{location.function_name}"
            if location.class_name is not None
            else location.function_name
        )
        raise FileNotFoundError(
            f"Could not find source function {location_text!r} for mutant {mutant_name}"
        )

    public_mutant = _public_mutant_function(
        original_function,
        mutants_module,
        mutant_name,
    )
    mutated_module = cast(
        "cst.Module",
        original_module.deep_replace(original_function, public_mutant),
    )
    return original_module, mutated_module, encoding


def _physical_source_lines(text: str) -> list[str]:
    """Split only at LF, preserving CRLF and every other Unicode character."""
    if not text:
        return []
    parts = text.split("\n")
    lines = [part + "\n" for part in parts[:-1]]
    if parts[-1]:
        lines.append(parts[-1])
    return lines


def _git_unified_diff(original: str, mutated: str, *, label: str) -> str:
    """Return a byte-stable, Git-applicable unified diff.

    A plain ``splitlines()`` loses CRLF/EOF distinctions, while even its
    ``keepends`` form treats NEL, VT, FF and Unicode separators as lines that
    Git does not recognise.  Preserve only physical LF-delimited source lines
    and add Git's explicit ``No newline`` marker for every affected side that
    lacks one. Diff metadata always uses LF so redirection is deterministic.
    """
    raw_lines = unified_diff(
        _physical_source_lines(original),
        _physical_source_lines(mutated),
        fromfile=f"a/{label}",
        tofile=f"b/{label}",
        n=1,
        lineterm="\n",
    )
    rendered: list[str] = []
    for line in raw_lines:
        if line.endswith("\n"):
            rendered.append(line)
            continue
        rendered.extend((line, "\n\\ No newline at end of file\n"))
    return "".join(rendered)


def _encode_git_patch(diff: str, source_encoding: str) -> bytes:
    """Encode metadata as UTF-8 and hunk payload in the source encoding."""
    try:
        canonical_encoding = codecs.lookup(source_encoding).name
    except LookupError as exc:  # pragma: no cover - tokenize already validated it
        raise MutationParseError(f"unknown Python source encoding: {source_encoding}") from exc
    payload_encoding = "utf-8" if canonical_encoding == "utf-8-sig" else canonical_encoding
    output = bytearray()
    for index, line in enumerate(_physical_source_lines(diff)):
        if index < 2 or line.startswith(("@@", "\\ ")):
            output.extend(line.encode("utf-8"))
            continue
        if not line.startswith((" ", "+", "-")):
            raise MutationParseError("generated unified diff contains an invalid hunk line")
        output.extend(line[0].encode("ascii"))
        try:
            output.extend(line[1:].encode(payload_encoding))
        except UnicodeEncodeError as exc:
            msg = f"mutant diff cannot be represented in source encoding {source_encoding}: {exc}"
            raise MutationParseError(msg) from exc
    return bytes(output)


def _render_function_diff(path: Path | str, mutant_name: str) -> tuple[str, str]:
    """Render one diff and return its verified Python source encoding."""
    metadata = SourceFileMutationData(path=str(path))
    metadata.load()
    source_bytes = _read_source_bytes_matching_staging(path, metadata.source_hash)
    module = read_mutants_module(
        path,
        expected_generated_hash=metadata.generated_hash,
        require_verified=True,
    )
    original_module, mutated_module, source_encoding = _source_modules_for_mutant(
        path,
        source_bytes,
        module,
        mutant_name,
    )
    orig_code = original_module.code
    mutant_code = mutated_module.code
    if codecs.lookup(source_encoding).name == "utf-8-sig":
        # ``decode('utf-8-sig')`` removes the BOM. Git patches model it as the
        # first content byte, not as a BOM in front of the diff header.
        orig_code = "\ufeff" + orig_code
        mutant_code = "\ufeff" + mutant_code

    label = str(path).replace("\\", "/")
    return _git_unified_diff(orig_code, mutant_code, label=label), source_encoding


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

    Patch-capability (issue #115 / A4-UI-014): the diff is rendered from the
    generation-time source module with only the selected body changed. It
    therefore retains the public signature, decorators, comments and
    indentation and applies to methods as well as top-level functions. A
    missing source or missing/mismatched generation hash fails closed instead
    of emitting a patch against unverifiable bytes.

    Raises:
        FileNotFoundError: If the ``_orig`` copy or the mutant function is
            missing from the mutants file.
        OSError: If the mutants file cannot be read.
        StaleStagingError: If the current source bytes do not match the source
            hash recorded when the mutants were generated.
    """
    diff, _source_encoding = _render_function_diff(path, mutant_name)
    return diff


def render_function_diff_bytes(path: Path | str, mutant_name: str) -> bytes:
    """Render a redirect-safe patch whose hunk bytes match the source file."""
    diff, source_encoding = _render_function_diff(path, mutant_name)
    return _encode_git_patch(diff, source_encoding)


def get_diff_for_mutant(mutant_name: str, config: MutmutConfig) -> str:
    """Generate unified diff between original and mutant function.

    Reads the mutants file, extracts both the ``_orig`` copy and the numbered
    mutant variant, and returns a unified diff string suitable for display.

    Args:
        mutant_name: Fully qualified mutant identifier or glob pattern
            matching exactly one mutant (issue #115 / A4-UI-012).
        config: Active ``MutmutConfig`` instance.

    Returns:
        A unified diff string (possibly empty if no difference is detected).
    """
    resolved, m = resolve_mutant(mutant_name, config)
    return render_function_diff(m.path, resolved)


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
        AmbiguousMutantNameError: If a glob pattern matches more than one
            mutant (issue #115 / A4-UI-012 — apply never applies a set).
        StaleStagingError: If the source file is newer than its ``mutants/``
            copy (stale staging — re-run ``mutmut-win run`` first; was a raw
            ``RuntimeError`` traceback until issue #123 / CLI-003).
    """
    mutant_name, data = resolve_mutant(mutant_name, config)
    path = data.path
    source_path = Path(path)
    mutants_path = Path("mutants") / path

    source_bytes = _read_source_bytes_matching_staging(source_path, data.source_hash)
    source_mode = stat.S_IMODE(source_path.stat().st_mode)

    location = function_definition_location_from_key(mutant_name)
    orig_function_name = location.function_name.rpartition(".")[-1]

    # Byte-exact reads: no universal-newline translation, so the patched file
    # keeps the original line endings.
    source, source_encoding = _decode_python_bytes(source_bytes, source_path)
    staged_bytes = read_verified_generated_bytes(path, data.generated_hash)
    staged_source, _staged_encoding = _decode_python_bytes(staged_bytes, mutants_path)
    orig_module = cst.parse_module(source)
    mutants_module = cst.parse_module(staged_source)

    original_function = _find_function_in_scope(
        orig_module,
        orig_function_name,
        location.class_name,
        location.definition_ordinal,
    )
    if not original_function:
        raise FileNotFoundError(f"Could not apply mutant {mutant_name}")

    mutant_function = _public_mutant_function(
        original_function,
        mutants_module,
        mutant_name,
    )

    # libcst.deep_replace is typed to return CSTNode; we know the result is Module.
    new_module = cast("cst.Module", orig_module.deep_replace(original_function, mutant_function))

    backup_path = source_path.with_name(source_path.name + ".mutmut-orig.bak")
    atomic_write_bytes(backup_path, source_bytes, mode=source_mode)
    try:
        applied_bytes = new_module.code.encode(source_encoding)
    except UnicodeEncodeError as exc:
        msg = f"applied mutant cannot be represented in source encoding {source_encoding}: {exc}"
        raise MutationParseError(msg) from exc
    atomic_write_bytes(source_path, applied_bytes, mode=source_mode)
