"""Regression tests for Bug #68 — multi-line ``if A or B or C:`` produces an
unimportable mutant file with SyntaxError.

The original ``operator_or_default`` rewrites ``x or default`` to ``x`` or
``default``. For single-line expressions that is fine. For multi-line
expressions with hanging continuation operands, like

::

    if (
        _RE_A.match(line)
        or _RE_B.match(line)
    ):
        ...

dropping the ``or`` leaves the second operand stranded on its own line without
a binding operator, so the resulting mutant is no longer valid Python — the
entire mutant file fails to import and pytest exits with code 2 during test
collection, blocking the entire mutation run.

The fix: skip the mutation when the ``BooleanOperation`` spans multiple lines
(detected by newline characters inside its whitespace nodes).

See critique-model-service ``_misc/mutmut-win-bugs.md`` Bug #1 (this repo's
issue #68) for the original repro.
"""

from __future__ import annotations

import ast

from mutmut_win.mutation import mutate_file_contents


def _assert_all_mutants_parse(mutated_code: str, source: str) -> None:
    """Every line in the mutated file plus the trampoline must form valid Python."""
    try:
        ast.parse(mutated_code)
    except SyntaxError as exc:
        raise AssertionError(
            f"Mutated file does not parse — Bug #68 regression.\n"
            f"Source:\n{source}\n"
            f"Error: {exc}\n"
            f"Mutated code:\n{mutated_code}"
        ) from exc


def test_single_line_or_default_still_mutated() -> None:
    """The fix must not regress single-line ``or`` mutations — they are safe."""
    source = """\
def pick(a, b):
    return a or b
"""
    mutated_code, _names = mutate_file_contents("m.py", source)

    _assert_all_mutants_parse(mutated_code, source)
    # operator_or_default should still produce two mutants: ``return a`` and ``return b``
    assert "return a\n" in mutated_code or "return a " in mutated_code, (
        "Single-line or-default mutation ``return a`` missing — "
        f"the fix must not over-suppress. Mutated code:\n{mutated_code}"
    )


def test_multiline_if_or_does_not_produce_syntax_error_mutant() -> None:
    """Repro from the bug report: multi-line ``if A or B or C:`` must not crash
    the mutant file."""
    source = """\
import re

_RE_A = re.compile(r"a")
_RE_B = re.compile(r"b")
_RE_C = re.compile(r"c")


def parse(lines: list[str]) -> int:
    count = 0
    for line in lines:
        if (
            _RE_A.match(line)
            or _RE_B.match(line)
            or _RE_C.match(line)
        ):
            count += 1
    return count
"""
    mutated_code, _ = mutate_file_contents("m.py", source)

    _assert_all_mutants_parse(mutated_code, source)


def test_multiline_or_in_return_does_not_produce_syntax_error_mutant() -> None:
    """Similar repro on a multi-line ``return`` expression."""
    source = """\
def pick(a, b, c):
    return (
        a
        or b
        or c
    )
"""
    mutated_code, _ = mutate_file_contents("m.py", source)

    _assert_all_mutants_parse(mutated_code, source)


def test_multiline_or_in_assignment_does_not_produce_syntax_error_mutant() -> None:
    """Multi-line ``x = (\\n  long_expr1\\n  or long_expr2\\n)`` assignment."""
    source = """\
def resolve(env, fallback):
    result = (
        env.get("URL")
        or fallback
    )
    return result
"""
    mutated_code, _ = mutate_file_contents("m.py", source)

    _assert_all_mutants_parse(mutated_code, source)
