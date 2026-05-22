"""Regression tests for Bug #70 — default-parameter mutations are structurally unkillable.

Because of mutmut's trampoline architecture, default parameter values are evaluated
at function-definition time. The trampoline variant captures the *mutated* default at
import time, but every call goes through the original symbol's default — so mutations
of default values can never be observed through behavioural testing.

The mutator must therefore skip every node inside a ``cst.Param.default`` subtree,
including simple Name/Number/String defaults (which the old logic still mutated).
Body mutations and second-class mutations must continue to fire normally.

See critique-model-service ``_misc/mutmut-win-bugs.md`` Bug #3 (this repo's issue #70)
for the original repro and the list of 11 unkillable mutants observed in Sprint 4.
"""

from __future__ import annotations

from mutmut_win.mutation import mutate_file_contents


def test_int_default_is_not_mutated() -> None:
    """``def f(x: int = 30): ...`` must not produce ``x: int = 31`` mutants."""
    source = """\
def configure(timeout_seconds: int = 30) -> int:
    return timeout_seconds
"""
    mutated_code, _ = mutate_file_contents("m.py", source)

    for forbidden in ("timeout_seconds: int = 31", "timeout_seconds: int = 29"):
        assert forbidden not in mutated_code, (
            f"Mutant containing {forbidden!r} found — default-int mutations must be "
            f"skipped (Bug #70). Mutated code:\n{mutated_code}"
        )


def test_str_default_is_not_mutated() -> None:
    """String defaults like ``base_url: str = \"https://...\"`` must not be mutated."""
    source = """\
def connect(base_url: str = "https://api.example.com/v1") -> str:
    return base_url
"""
    mutated_code, _ = mutate_file_contents("m.py", source)

    # operator_string normally produces an XX-wrapped sentinel and case-flipped
    # variants. Neither should appear as a default-value mutation.
    for forbidden in (
        'base_url: str = "XXhttps://api.example.com/v1XX"',
        'base_url: str = "HTTPS://API.EXAMPLE.COM/V1"',
    ):
        assert forbidden not in mutated_code, (
            f"Mutant containing {forbidden!r} found — default-string mutations must be "
            f"skipped (Bug #70). Mutated code:\n{mutated_code}"
        )


def test_name_default_is_not_mutated() -> None:
    """``def f(handler = default_handler): ...`` must not turn the default into None."""
    source = """\
default_handler = object()


def register(handler=default_handler):
    return handler
"""
    mutated_code, _ = mutate_file_contents("m.py", source)

    assert "handler=None" not in mutated_code, (
        "Mutation rewriting a Name default to None found — Name defaults must be "
        f"skipped (Bug #70). Mutated code:\n{mutated_code}"
    )


def test_body_is_still_mutated_when_function_has_defaults() -> None:
    """Body mutations must NOT be suppressed by the default-skip logic."""
    source = """\
def configure(timeout_seconds: int = 30) -> int:
    factor = 2
    return timeout_seconds * factor
"""
    mutated_code, _ = mutate_file_contents("m.py", source)

    # ``factor = 2`` is a body assignment, not a default — it must still be mutated
    # (the number_mutation operator turns ``2`` into ``3``).
    assert "factor = 3" in mutated_code, (
        "Body integer ``factor = 2`` not mutated to ``factor = 3`` — default-skip "
        f"logic must not block body mutations. Mutated code:\n{mutated_code}"
    )


def test_non_default_argument_is_still_mutated() -> None:
    """A function with no defaults at all must still get its body mutated normally."""
    source = """\
def add_one(x: int) -> int:
    return x + 1
"""
    mutated_code, _ = mutate_file_contents("m.py", source)

    # number_mutation turns ``x + 1`` into ``x + 2``
    assert "return x + 2" in mutated_code, (
        "Body number mutation suppressed even though there is no default. "
        f"Mutated code:\n{mutated_code}"
    )
