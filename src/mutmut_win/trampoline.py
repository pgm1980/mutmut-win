"""Templates and helpers for generating mutation trampoline functions."""

CLASS_NAME_SEPARATOR = "ǁ"


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
    if (
        not isinstance(definition_ordinal, int)
        or isinstance(definition_ordinal, bool)
        or definition_ordinal < 1
    ):
        msg = f"Definition ordinal must be a positive integer: {definition_ordinal!r}"
        raise ValueError(msg)
    if class_name:
        if CLASS_NAME_SEPARATOR in class_name:
            msg = f"Class name must not contain '{CLASS_NAME_SEPARATOR}': {class_name!r}"
            raise ValueError(msg)
        prefix = f"x{CLASS_NAME_SEPARATOR}{class_name}{CLASS_NAME_SEPARATOR}"
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


def _mutmut_trampoline(orig, mutants, call_args, call_kwargs, self_arg = None): # type: ignore
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
        # (for class methods, orig is bound and thus does not need the explicit self argument)
        result = orig(*call_args, **call_kwargs) # type: ignore
        return result # type: ignore
    prefix = orig.__module__ + '.' + orig.__name__ + '__mutmut_' # type: ignore
    if not mutant_under_test.startswith(prefix): # type: ignore
        result = orig(*call_args, **call_kwargs) # type: ignore
        return result # type: ignore
    mutant_name = mutant_under_test.rpartition('.')[-1] # type: ignore
    if self_arg is not None: # type: ignore
        # call to a class method where self is not bound
        result = mutants[mutant_name](self_arg, *call_args, **call_kwargs) # type: ignore
    else:
        result = mutants[mutant_name](*call_args, **call_kwargs) # type: ignore
    return result # type: ignore

"""
