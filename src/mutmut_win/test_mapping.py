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

from mutmut_win.trampoline import CLASS_NAME_SEPARATOR


def mangled_name_from_mutant_name(mutant_name: str) -> str:
    """Extract the mangled function name before the ``__mutmut_`` suffix.

    Args:
        mutant_name: Fully qualified mutant identifier containing ``__mutmut_``.

    Returns:
        The portion of the mutant name up to (and not including) ``__mutmut_``.

    Raises:
        AssertionError: If ``__mutmut_`` is not present in *mutant_name*.
    """
    assert "__mutmut_" in mutant_name, mutant_name  # noqa: S101
    return mutant_name.partition("__mutmut_")[0]


def orig_function_and_class_names_from_key(mutant_name: str) -> tuple[str, str | None]:
    """Extract the original function name and optional class name from a mutant key.

    Given a mutant name such as ``src.module.xǁMyClassǁmy_func__mutmut_1``,
    returns ``("my_func", "MyClass")``.  For a top-level function like
    ``src.module.x_my_func__mutmut_1`` returns ``("my_func", None)``.

    Args:
        mutant_name: Fully qualified mutant identifier.

    Returns:
        A tuple of ``(function_name, class_name)`` where ``class_name`` is
        ``None`` for module-level functions.

    Raises:
        AssertionError: If the name does not start with the expected prefix
            (``x_`` or ``xǁ…ǁ``).
    """
    r = mangled_name_from_mutant_name(mutant_name)
    _, _, r = r.rpartition(".")
    class_name: str | None = None
    if CLASS_NAME_SEPARATOR in r:
        class_name = r[r.index(CLASS_NAME_SEPARATOR) + 1 : r.rindex(CLASS_NAME_SEPARATOR)]
        r = r[r.rindex(CLASS_NAME_SEPARATOR) + 1 :]
    else:
        assert r.startswith("x_"), r  # noqa: S101
        r = r[2:]
    return r, class_name


def is_mutated_method_name(name: str) -> bool:
    """Check if *name* looks like a trampoline-generated method name.

    A trampoline method name starts with ``x_`` (for module-level functions)
    or ``xǁ`` (for class methods) and contains ``__mutmut``.

    Args:
        name: The attribute or method name to inspect.

    Returns:
        ``True`` if *name* matches a trampoline-generated pattern.
    """
    return name.startswith(("x_", f"x{CLASS_NAME_SEPARATOR}")) and "__mutmut" in name


def tests_for_mutant_names(
    mutant_names: list[str],
    tests_by_mangled_function_name: dict[str, set[str]],
) -> set[str]:
    """Map mutant names to the specific test node IDs that should run.

    Supports wildcard patterns (``*``) in *mutant_names* via
    :func:`fnmatch.fnmatch`.  For each wildcard entry every mangled name
    matching the pattern contributes its tests.  For exact names the
    ``__mutmut_``-prefix is stripped and the remainder is looked up directly.

    Args:
        mutant_names: List of mutant identifiers to resolve.  May contain
            ``*`` wildcards.
        tests_by_mangled_function_name: Mapping produced by stats collection —
            keys are mangled function names, values are sets of pytest node IDs.

    Returns:
        Union of all test node IDs for the given mutant names.
    """
    tests: set[str] = set()
    for mutant_name in mutant_names:
        if "*" in mutant_name:
            for name, tests_of_this_name in tests_by_mangled_function_name.items():
                if fnmatch.fnmatch(name, mutant_name):
                    tests |= set(tests_of_this_name)
        else:
            mangled = mangled_name_from_mutant_name(mutant_name)
            if mangled in tests_by_mangled_function_name:
                tests |= set(tests_by_mangled_function_name[mangled])
    return tests
