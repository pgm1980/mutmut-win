"""Templates and helpers for generating mutation trampoline functions."""

CLASS_NAME_SEPARATOR = "ǁ"
#: Prefix for the collision-safe encoding used only when a source function or
#: class name itself contains the reserved ``__mutmut_`` delimiter.  Ordinary
#: names retain their historical ``x_`` / ``xǁ`` IDs byte-for-byte.
COLLISION_SAFE_NAME_PREFIX = "xq"


def _encoded_source_name(name: str) -> str:
    """Encode one Python identifier without using the mutant delimiter."""
    return name.encode("utf-8").hex()


def create_trampoline_lookup(
    *,
    orig_name: str,
    mutants: list[str],
    class_name: str | None,
    definition_ordinal: int = 1,
) -> str:
    """Generate source code for the mutants dict and __name__ assignment.

    The generated statements live at MODULE level (issue #77): a dict inside
    a class body is no descriptor, so ``enum.Enum`` turned it into a phantom
    member, and the former ``ClassVar[...]`` annotation crashed ``NamedTuple``
    creation (audit A1-MT-004/005).  For methods the dict values and the
    ``__name__`` target are therefore qualified with ``<ClassName>.``.

    Args:
        orig_name: The original (unmangled) function name.
        mutants: List of mangled mutant function names.
        class_name: Class name if this is a method, None for top-level functions.
        definition_ordinal: One-based occurrence of this same-named definition
            in its module scope.  The first occurrence stays byte-for-byte
            backward compatible; later occurrences carry a reserved suffix.

    Returns:
        Python source code string for the trampoline lookup table.
    """
    mangled_name = mangle_function_name(
        name=orig_name,
        class_name=class_name,
        definition_ordinal=definition_ordinal,
    )
    qualifier = f"{class_name}." if class_name else ""

    mutants_dict = (
        f"{mangled_name}__mutmut_mutants : MutantDict = {{ # type: ignore\n"
        + ", \n    ".join(f"{m!r}: {qualifier}{m}" for m in mutants)
        + "\n}"
    )
    return f"""
{mutants_dict}
{qualifier}{mangled_name}__mutmut_orig.__name__ = '{mangled_name}'
"""


def mangle_function_name(
    *,
    name: str,
    class_name: str | None,
    definition_ordinal: int = 1,
) -> str:
    """Generate a unique mangled name for the original function.

    Args:
        name: The function name to mangle.
        class_name: Class name if this is a method, None for top-level functions.
        definition_ordinal: One-based occurrence of the same function name in
            the same encoded scope.  ``1`` deliberately has no suffix so all
            existing non-colliding IDs remain stable.  Occurrences 2+ use the
            reserved class-name separator, which source function/class names
            are already forbidden to contain, making the encoding reversible.

    Returns:
        Mangled function name string.
    """
    if CLASS_NAME_SEPARATOR in name:
        msg = f"Function name must not contain '{CLASS_NAME_SEPARATOR}': {name!r}"
        raise ValueError(msg)
    if class_name and CLASS_NAME_SEPARATOR in class_name:
        msg = f"Class name must not contain '{CLASS_NAME_SEPARATOR}': {class_name!r}"
        raise ValueError(msg)
    if (
        not isinstance(definition_ordinal, int)
        or isinstance(definition_ordinal, bool)
        or definition_ordinal < 1
    ):
        msg = f"Definition ordinal must be a positive integer: {definition_ordinal!r}"
        raise ValueError(msg)
    # Decide from the complete legacy prefix plus the generated delimiter, not
    # only from the raw source component.  A valid identifier can contain the
    # delimiter, end in ``__mutmut`` and complete it when the suffix is added,
    # or start in ``_mutmut_`` and complete it across the top-level ``x_``
    # prefix.  Any of those forms makes the first delimiter ambiguous and can
    # route apply/show to another source definition (MW221-025 / CX221-005).
    legacy_mangled_base = (
        f"x{CLASS_NAME_SEPARATOR}{class_name}{CLASS_NAME_SEPARATOR}{name}"
        if class_name
        else f"x_{name}"
    )
    needs_collision_safe_encoding = (
        "__mutmut_" in legacy_mangled_base or legacy_mangled_base.endswith("__mutmut")
    )
    if needs_collision_safe_encoding:
        encoded_name = _encoded_source_name(name)
        if class_name:
            encoded_class = _encoded_source_name(class_name)
            prefix = (
                f"{COLLISION_SAFE_NAME_PREFIX}{CLASS_NAME_SEPARATOR}"
                f"{encoded_class}{CLASS_NAME_SEPARATOR}"
            )
        else:
            prefix = f"{COLLISION_SAFE_NAME_PREFIX}_"
        mangled = f"{prefix}{encoded_name}"
    elif class_name:
        prefix = f"x{CLASS_NAME_SEPARATOR}{class_name}{CLASS_NAME_SEPARATOR}"
        mangled = f"{prefix}{name}"
    else:
        prefix = "x_"
        mangled = f"{prefix}{name}"
    if definition_ordinal > 1:
        mangled += f"{CLASS_NAME_SEPARATOR}{definition_ordinal}"
    return mangled


# noinspection PyUnresolvedReferences
# language=python
trampoline_impl = """
from typing import Annotated
from typing import Callable
from typing import ClassVar

MutantDict = Annotated[dict[str, Callable], "Mutant"] # type: ignore


def _mutmut_trampoline(orig, mutants, call_args, call_kwargs): # type: ignore
    \"""Forward call to original or mutated function, depending on the environment\"""
    import os # type: ignore
    mutant_under_test = os.environ.get('MUTANT_UNDER_TEST') # type: ignore
    if mutant_under_test is None: # type: ignore
        result = orig(*call_args, **call_kwargs) # type: ignore
        return result # type: ignore
    if mutant_under_test == 'fail': # type: ignore
        from mutmut_win.exceptions import MutmutProgrammaticFailException # type: ignore
        raise MutmutProgrammaticFailException('Failed programmatically')       # type: ignore
    elif mutant_under_test == 'stats': # type: ignore
        from mutmut_win.hit_recording import record_trampoline_hit # type: ignore
        record_trampoline_hit(orig.__module__ + '.' + orig.__name__) # type: ignore
        result = orig(*call_args, **call_kwargs) # type: ignore
        return result # type: ignore
    prefix = orig.__module__ + '.' + orig.__name__ + '__mutmut_' # type: ignore
    if not mutant_under_test.startswith(prefix): # type: ignore
        result = orig(*call_args, **call_kwargs) # type: ignore
        return result # type: ignore
    mutant_name = mutant_under_test.rpartition('.')[-1] # type: ignore
    result = mutants[mutant_name](*call_args, **call_kwargs) # type: ignore
    return result # type: ignore

"""
