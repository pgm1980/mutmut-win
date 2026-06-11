"""Tests for the safe-unwrap helper across the parenless-yield operator class
(Issue #73 — closes downstream BUG-1 from the W4.11 report).

Five operators yield a sub-expression in place of its parent node.  The child
loses the parent's parentheses, which broke in three ways (audit
A1-NM-001…006): sole-argument generator expressions became bare (SyntaxError),
multi-line operands stranded their continuation lines (SyntaxError), and
lower-precedence expressions rebound in the surrounding context (wrong
semantics).  The fix wraps the yielded child in its own parentheses where
needed — producing MORE valid mutants instead of skipping (improvement over
the Bug-#68 skip guard).
"""

from __future__ import annotations

import ast

from mutmut_win.mutation import mutate_file_contents


def _mutate(source: str) -> tuple[str, list[str]]:
    code, names = mutate_file_contents("m.py", source)
    # Hard gate: whatever the operators produce must compile.
    ast.parse(code)
    return code, list(names)


# ---------------------------------------------------------------------------
# BUG-1 (W4.11 §1.2/§1.3): sole-argument generator expressions
# ---------------------------------------------------------------------------


class TestSoleGenexpForms:
    def test_single_line_assignment(self) -> None:
        _code, names = _mutate("def f(items):\n    return tuple(x for x in items if x)\n")
        assert names, "fallback engaged — expected real mutants for tuple(<genexp>)"

    def test_multiline_assignment(self) -> None:
        source = (
            "def f(cross_hits, n):\n"
            "    pair_samples = tuple(\n"
            "        (url, sq) for url, sq in list(cross_hits.items())[:n]\n"
            "    )\n"
            "    return pair_samples\n"
        )
        _code, names = _mutate(source)
        assert names

    def test_multiline_assignment_with_filter(self) -> None:
        source = (
            "def f(items):\n"
            "    non_public = tuple(\n"
            "        (term, kind) for term, kind in items if term\n"
            "    )\n"
            "    return non_public\n"
        )
        _code, names = _mutate(source)
        assert names

    def test_inline_kwarg(self) -> None:
        source = "def f(rs, g):\n    return g(counts=tuple(p for p, _x, _y in rs))\n"
        _code, names = _mutate(source)
        assert names

    def test_neutralized_mutant_is_parenthesized_generator(self) -> None:
        code, _names = _mutate("def f(items):\n    return tuple(x for x in items)\n")
        # The neutralised variant keeps generator semantics, parenthesized.
        assert "return (x for x in items)" in code


# ---------------------------------------------------------------------------
# Multi-line operands across the operator class (NM-001…005)
# ---------------------------------------------------------------------------


class TestMultilineOperands:
    def test_or_default_with_multiline_binary_left(self) -> None:
        # A1-NM-001: the old guard only looked at the operator whitespace.
        source = "def f(a, b, c):\n    x = (a +\n         b or c)\n    return x\n"
        _code, names = _mutate(source)
        assert names

    def test_remove_unary_with_multiline_operand(self) -> None:
        # A1-NM-002
        source = "def f(aaa, bbb):\n    x = (not aaa\n         == bbb)\n    return x\n"
        _code, names = _mutate(source)
        assert names

    def test_conditional_expression_with_multiline_body(self) -> None:
        # A1-NM-003
        source = (
            "def f(a, b, c, d):\n"
            "    x = (\n"
            "        a\n"
            "        or b\n"
            "        if c\n"
            "        else d\n"
            "    )\n"
            "    return x\n"
        )
        _code, names = _mutate(source)
        assert names

    def test_math_neutralize_with_multiline_arg(self) -> None:
        # A1-NM-004
        source = "def f(a, b):\n    x = abs(a\n            - b)\n    return x\n"
        _code, names = _mutate(source)
        assert names

    def test_collection_neutralize_with_multiline_arg(self) -> None:
        # A1-NM-005
        source = "def f(a, b):\n    x = sorted(a\n               or b)\n    return x\n"
        _code, names = _mutate(source)
        assert names

    def test_bug68_multiline_if_now_produces_mutants(self) -> None:
        # Improvement over the Bug-#68 skip guard: the or-mutants exist now
        # (parenthesized) instead of being suppressed.
        source = (
            "def parse(a, b, c):\n"
            "    if (\n"
            "        a\n"
            "        or b\n"
            "        or c\n"
            "    ):\n"
            "        return 1\n"
            "    return 0\n"
        )
        code, _names = _mutate(source)
        # The left-operand variant carries its own parens now and renders as
        # ``if (a\n        or b):`` — the original only ever has ``if (\n``
        # (newline right after the paren), so ``if (a`` proves the mutant
        # exists instead of being suppressed.
        assert "if (a" in code


# ---------------------------------------------------------------------------
# Precedence preservation (NM-006)
# ---------------------------------------------------------------------------


class TestPrecedencePreserved:
    def test_collection_unwrap_keeps_binding(self) -> None:
        code, _names = _mutate("def f(a, b):\n    y = list(a or b)[0]\n    return y\n")
        # Must NOT be ``y = a or b[0]`` (rebinding); the original line is
        # ``y = list(a or b)[0]``, so match the mutant line exactly.
        assert "y = (a or b)[0]" in code
        assert "y = a or b[0]" not in code

    def test_math_unwrap_keeps_binding(self) -> None:
        code, _names = _mutate("def f(a, b):\n    z = abs(a - b) * 2\n    return z\n")
        assert "z = (a - b) * 2" in code
        assert "z = a - b * 2" not in code


# ---------------------------------------------------------------------------
# Atoms stay bare — no diff noise on the common cases
# ---------------------------------------------------------------------------


class TestAtomsStayBare:
    def test_simple_name_arg_not_parenthesized(self) -> None:
        code, _names = _mutate("def f(x):\n    return abs(x)\n")
        assert "return (x)" not in code

    def test_single_line_or_default_unparenthesized(self) -> None:
        code, _names = _mutate("def f(a, b):\n    return a or b\n")
        assert "return (a)" not in code
        assert "return (b)" not in code

    def test_single_line_conditional_unparenthesized(self) -> None:
        code, _names = _mutate("def f(a, b, c):\n    return a if c else b\n")
        assert "return (a)" not in code
