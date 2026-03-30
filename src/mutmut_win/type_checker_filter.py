"""CST-based type-checker filter helpers for mutmut-win.

Ports the mutated-method collection and grouping utilities from mutmut 3.5.0
``__main__.py``.  These classes allow the orchestrator to map type-checker
errors back to specific mutated method locations so that mutants can be
precisely filtered rather than by file-path prefix only.

Classes:
    MutatedMethodLocation: Position of a mutated method inside a source file.
    FailedTypeCheckMutant: A mutant that was caught by the type checker.
    MutatedMethodsCollector: CST visitor that collects mutated function defs.

Functions:
    group_by_path: Group ``TypeCheckingError`` instances by file path.
    is_mutated_method_name: Predicate for trampoline-generated names.
"""

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import libcst as cst
from libcst.metadata import PositionProvider

from mutmut_win.type_checking import TypeCheckingError


def is_mutated_method_name(name: str) -> bool:
    """Return ``True`` if *name* is a trampoline-generated mutated method name.

    Trampoline-generated names start with ``x_`` (module-level) or ``xǁ``
    (class methods) and contain the ``__mutmut`` marker.

    Args:
        name: The function or method name to inspect.

    Returns:
        ``True`` if *name* matches a trampoline-generated pattern.
    """
    return name.startswith(("x_", "xǁ")) and "__mutmut" in name


@dataclass
class MutatedMethodLocation:
    """Position of a trampoline-generated mutated method in a source file.

    Attributes:
        file: Absolute path to the (mutated) source file.
        function_name: The trampoline function name (e.g. ``x_my_func__mutmut_1``).
        line_number_start: First line of the function definition (1-based).
        line_number_end: Last line of the function definition (1-based).
    """

    file: Path
    function_name: str
    line_number_start: int
    line_number_end: int


@dataclass
class FailedTypeCheckMutant:
    """A mutant caught by the type checker.

    Attributes:
        method_location: The CST position of the mutated function.
        name: Fully qualified mutant name (e.g. ``pkg.module.x_func__mutmut_1``).
        error: The ``TypeCheckingError`` that caused this mutant to be caught.
    """

    method_location: MutatedMethodLocation
    name: str
    error: TypeCheckingError


class MutatedMethodsCollector(cst.CSTVisitor):
    """CST visitor that collects all trampoline-generated function definitions.

    Ported from mutmut 3.5.0 ``__main__.py``.  Visits top-level and nested
    ``FunctionDef`` nodes; for each whose name matches
    :func:`is_mutated_method_name`, records a :class:`MutatedMethodLocation`
    with the source range from ``PositionProvider`` metadata.

    Args:
        file: Path to the source file being visited (stored for reference).

    Attributes:
        found_mutants: Populated by ``visit_FunctionDef`` with all discovered
            mutated method locations.
    """

    METADATA_DEPENDENCIES = (PositionProvider,)

    def __init__(self, file: Path) -> None:
        self.file = file
        self.found_mutants: list[MutatedMethodLocation] = []

    def visit_FunctionDef(self, node: cst.FunctionDef) -> bool:  # noqa: N802 — libcst visitor protocol requires CamelCase method names
        """Visit a function definition and record it if it is a mutated method.

        Args:
            node: The CST ``FunctionDef`` node being visited.

        Returns:
            ``False`` to stop visiting children (mutated methods are never
            nested within other mutated methods).
        """
        name = node.name.value
        if is_mutated_method_name(name):
            position = self.get_metadata(PositionProvider, node)
            self.found_mutants.append(
                MutatedMethodLocation(
                    file=self.file,
                    function_name=name,
                    line_number_start=position.start.line,
                    line_number_end=position.end.line,
                )
            )
        # Do not recurse — mutated methods are never nested inside other methods.
        return False


def group_by_path(
    errors: list[TypeCheckingError],
) -> dict[Path, list[TypeCheckingError]]:
    """Group a list of ``TypeCheckingError`` instances by their file path.

    Ported from mutmut 3.5.0 ``__main__.py``.

    Args:
        errors: List of type-checker errors to group.

    Returns:
        A ``defaultdict``-backed mapping from file path to the list of errors
        that occurred in that file.
    """
    grouped: dict[Path, list[TypeCheckingError]] = defaultdict(list)
    for error in errors:
        grouped[error.file_path].append(error)
    return grouped
