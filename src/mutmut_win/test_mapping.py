"""Test mapping utilities for mutmut-win.

Maps mutant names to the test node IDs that exercise them, by extracting
mangled function names from mutant identifiers and looking them up in the
stats-collected mapping.

Ported from mutmut 3.5.0 ``__main__.py`` with the following adaptations:
- No global state: ``tests_by_mangled_function_name`` is passed explicitly.
- ``fnmatch`` wildcard support retained from the original.
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from typing import TYPE_CHECKING

from mutmut_win.trampoline import CLASS_NAME_SEPARATOR, COLLISION_SAFE_NAME_PREFIX

if TYPE_CHECKING:
    from collections.abc import Iterable


@dataclass(frozen=True, slots=True)
class FunctionDefinitionLocation:
    """Decoded source location carried by a mangled mutant identifier."""

    function_name: str
    class_name: str | None
    definition_ordinal: int


def _decode_collision_safe_component(encoded: str, mutant_name: str) -> str:
    """Decode one UTF-8 hex identifier from the collision-safe namespace."""
    if not encoded or len(encoded) % 2:
        raise ValueError(f"Malformed collision-safe mutant name: {mutant_name!r}")
    try:
        decoded = bytes.fromhex(encoded).decode("utf-8")
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError(f"Malformed collision-safe mutant name: {mutant_name!r}") from exc
    if not decoded.isidentifier() or CLASS_NAME_SEPARATOR in decoded:
        raise ValueError(f"Malformed collision-safe mutant name: {mutant_name!r}")
    return decoded


def _split_definition_ordinal(component: str, mutant_name: str) -> tuple[str, int]:
    """Split and validate the optional canonical ``ǁ<ordinal>`` suffix."""
    function_name, separator, ordinal_text = component.rpartition(CLASS_NAME_SEPARATOR)
    if not separator:
        return component, 1
    if (
        not function_name
        or CLASS_NAME_SEPARATOR in function_name
        or not ordinal_text.isascii()
        or not ordinal_text.isdecimal()
        or int(ordinal_text) < 2
        or str(int(ordinal_text)) != ordinal_text
    ):
        raise ValueError(f"Malformed definition ordinal in mutant name: {mutant_name!r}")
    return function_name, int(ordinal_text)


def match_mutant_names(patterns: Iterable[str], candidates: Iterable[str]) -> list[str]:
    """Return the candidates matching any pattern — exact or fnmatch glob.

    THE matching rule for user-supplied mutant names (issue #115 /
    A4-UI-012): ``run``, ``show``, ``apply`` and ``time-estimates`` all
    resolve names through this function. An exact name matches itself;
    ``*``/``?``/``[...]`` patterns match via :func:`fnmatch.fnmatch`.
    Candidate order is preserved, each candidate appears at most once.

    Args:
        patterns: User-supplied names and/or glob patterns.
        candidates: Known mutant names to match against.

    Returns:
        The matching candidates in their original order (possibly empty).
    """
    pattern_list = list(patterns)
    return [
        candidate
        for candidate in candidates
        if candidate in pattern_list
        or any(fnmatch.fnmatch(candidate, pattern) for pattern in pattern_list)
    ]


def _is_numeric_mutant_suffix(value: str) -> bool:
    """Return whether *value* is a non-empty ASCII decimal suffix."""
    return value.isascii() and value.isdecimal()


def mangled_name_from_mutant_name(mutant_name: str) -> str:
    """Extract the mangled function name before the ``__mutmut_`` suffix.

    Args:
        mutant_name: Fully qualified mutant identifier containing ``__mutmut_``.

    Returns:
        The portion of the mutant name up to (and not including) ``__mutmut_``.

    Raises:
        ValueError: If the final dotted name segment has no numeric
            ``__mutmut_`` suffix.
    """
    marker = "__mutmut_"
    marker_index = mutant_name.rfind(marker)
    last_dot = mutant_name.rfind(".")
    if marker_index <= last_dot:
        msg = f"Not a mutant name (missing local '__mutmut_' suffix): {mutant_name!r}"
        raise ValueError(msg)
    mangled_name, separator, suffix = mutant_name.rpartition(marker)
    if not separator or not _is_numeric_mutant_suffix(suffix):
        msg = f"Not a mutant name (malformed '__mutmut_' suffix): {mutant_name!r}"
        raise ValueError(msg)
    return mangled_name


def function_definition_location_from_key(mutant_name: str) -> FunctionDefinitionLocation:
    """Decode function, class and same-name definition ordinal from a mutant key.

    Definition occurrence 1 uses the historical encoding.  Occurrences 2+
    end in ``ǁ<ordinal>``; the separator cannot occur in source function or
    class names accepted by the mutation engine, so decoding is unambiguous.

    Given a mutant name such as ``src.module.xǁMyClassǁmy_func__mutmut_1``,
    returns location ``("my_func", "MyClass", 1)``.  A second top-level
    definition ``src.module.x_my_funcǁ2__mutmut_1`` decodes to
    ``("my_func", None, 2)``.

    Args:
        mutant_name: Fully qualified mutant identifier.

    Returns:
        Frozen decoded source location.

    Raises:
        ValueError: If the name does not start with the expected prefix
            (``x_`` or ``xǁ…ǁ``).
    """
    r = mangled_name_from_mutant_name(mutant_name)
    _, _, r = r.rpartition(".")
    class_name: str | None = None
    collision_safe = False
    class_prefix = f"x{CLASS_NAME_SEPARATOR}"
    encoded_class_prefix = f"{COLLISION_SAFE_NAME_PREFIX}{CLASS_NAME_SEPARATOR}"
    if r.startswith(encoded_class_prefix):
        encoded_class_and_function = r[len(encoded_class_prefix) :]
        encoded_class, separator, r = encoded_class_and_function.partition(CLASS_NAME_SEPARATOR)
        if not separator or not encoded_class or not r:
            msg = f"Malformed collision-safe class-method mutant name: {mutant_name!r}"
            raise ValueError(msg)
        class_name = _decode_collision_safe_component(encoded_class, mutant_name)
        collision_safe = True
    elif r.startswith(f"{COLLISION_SAFE_NAME_PREFIX}_"):
        r = r[len(COLLISION_SAFE_NAME_PREFIX) + 1 :]
        if not r:
            msg = f"Malformed collision-safe mutant function prefix: {mutant_name!r}"
            raise ValueError(msg)
        collision_safe = True
    elif r.startswith(class_prefix):
        class_and_function = r[len(class_prefix) :]
        class_name, separator, r = class_and_function.partition(CLASS_NAME_SEPARATOR)
        if not separator or not class_name or not r:
            msg = f"Malformed class-method mutant name: {mutant_name!r}"
            raise ValueError(msg)
    elif r.startswith("x_") and len(r) > 2:
        r = r[2:]
    else:
        msg = f"Malformed mutant function prefix: {mutant_name!r}"
        raise ValueError(msg)
    r, definition_ordinal = _split_definition_ordinal(r, mutant_name)
    if collision_safe:
        r = _decode_collision_safe_component(r, mutant_name)
    return FunctionDefinitionLocation(
        function_name=r,
        class_name=class_name,
        definition_ordinal=definition_ordinal,
    )


def orig_function_and_class_names_from_key(mutant_name: str) -> tuple[str, str | None]:
    """Extract the source function and optional class name from a mutant key.

    This compatibility API intentionally retains its historical two-tuple.
    Consumers that must distinguish repeated definitions use
    :func:`function_definition_location_from_key`.

    Args:
        mutant_name: Fully qualified mutant identifier.

    Returns:
        Tuple of ``(function_name, class_name)`` with any definition ordinal
        decoded and removed from the source function name.
    """
    location = function_definition_location_from_key(mutant_name)
    return location.function_name, location.class_name


def is_mutated_method_name(name: str) -> bool:
    """Check if *name* looks like a trampoline-generated method name.

    A trampoline method name starts with ``x_`` (for module-level functions)
    or ``xǁ`` (for class methods) and contains ``__mutmut``.

    Args:
        name: The attribute or method name to inspect.

    Returns:
        ``True`` if *name* matches a trampoline-generated pattern.
    """
    return (
        name.startswith(
            (
                "x_",
                f"x{CLASS_NAME_SEPARATOR}",
                f"{COLLISION_SAFE_NAME_PREFIX}_",
                f"{COLLISION_SAFE_NAME_PREFIX}{CLASS_NAME_SEPARATOR}",
            )
        )
        and "__mutmut" in name
    )


def tests_for_mutant_names(
    mutant_names: list[str],
    tests_by_mangled_function_name: dict[str, set[str]],
) -> set[str]:
    """Map mutant names to the specific test node IDs that should run.

    Supports all fnmatch patterns (``*``, ``?`` and ``[...]``).  Patterns may
    name a mangled function directly or include a ``__mutmut_`` suffix; the
    suffix is intentionally removed because stats map tests at function, not
    individual-mutant, granularity.  Malformed/unknown user input simply has no
    matching tests instead of surfacing an optimization-dependent assertion.

    Args:
        mutant_names: List of mutant identifiers to resolve.  May contain
            fnmatch wildcards, with or without a ``__mutmut_`` suffix.
        tests_by_mangled_function_name: Mapping produced by stats collection —
            keys are mangled function names, values are sets of pytest node IDs.

    Returns:
        Union of all test node IDs for the given mutant names.
    """
    tests: set[str] = set()
    for mutant_name in mutant_names:
        # Exact mangled function keys without a mutant suffix are useful API
        # input too.  Split only a valid selector in the final dotted segment:
        # package/module components may legally contain the reserved text.
        marker = "__mutmut_"
        marker_index = mutant_name.rfind(marker)
        last_dot = mutant_name.rfind(".")
        mangled_pattern, separator, suffix = mutant_name.rpartition(marker)
        suffix_is_selector = _is_numeric_mutant_suffix(suffix)
        suffix_is_selector = suffix_is_selector or any(magic in suffix for magic in "*?[")
        if marker_index <= last_dot or not separator or not suffix_is_selector:
            mangled_pattern = mutant_name

        if any(magic in mangled_pattern for magic in "*?["):
            for name, tests_of_this_name in tests_by_mangled_function_name.items():
                if fnmatch.fnmatchcase(name, mangled_pattern):
                    tests |= set(tests_of_this_name)
        else:
            tests |= set(tests_by_mangled_function_name.get(mangled_pattern, ()))
    return tests
