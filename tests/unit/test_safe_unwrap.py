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

import libcst as cst
from hypothesis import given
from hypothesis import strategies as st

from mutmut_win.constants import Profile
from mutmut_win.mutation import mutate_file_contents
from mutmut_win.node_mutation import _is_bare_decimal_integer


def _mutate(source: str, active_profile: Profile = Profile.ADVANCED) -> tuple[str, list[str]]:
    code, names = mutate_file_contents("m.py", source, active_profile=active_profile)
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


# ---------------------------------------------------------------------------
# M-047 (issue #168): bare decimal integers as an attribute BASE
# ---------------------------------------------------------------------------


class TestDecimalIntegerAttributeBase:
    """A bare decimal integer is NOT a safe atom where the replaced node was
    the base of an attribute access: '0.bit_length()' is a SyntaxError because
    the dot tokenises as the start of a float. The parenthesisation is
    context-sensitive (only the attribute-base position gets parens), so
    ordinary mutants keep their diff-minimal bare form and mapping keys under
    profile ALL stay valid.
    """

    def test_unary_removal_attribute_base(self) -> None:
        code, names = _mutate("def f():\n    return (~1).bit_length()\n")
        assert "(1).bit_length()" in code
        assert names

    def test_math_neutralize_attribute_base(self) -> None:
        code, names = _mutate("def f():\n    return abs(1).bit_length()\n")
        assert "(1).bit_length()" in code
        assert names

    def test_or_default_attribute_base(self) -> None:
        code, names = _mutate("def f(x):\n    return (x or 0).bit_length()\n")
        assert "(0).bit_length()" in code
        assert names

    def test_conditional_expression_attribute_base(self) -> None:
        code, names = _mutate("def f(c):\n    return (1 if c else 2).to_bytes(2)\n")
        assert "(1).to_bytes(2)" in code
        assert "(2).to_bytes(2)" in code
        assert names

    def test_or_default_without_attribute_stays_bare(self) -> None:
        # Context-sensitive (variant b): outside an attribute base the
        # decimal integer keeps its diff-minimal bare form.
        code, _names = _mutate("def f(x):\n    return x or 0\n")
        assert "return 0" in code
        assert "return (0)" not in code

    def test_hex_attribute_base_stays_bare(self) -> None:
        # Hex (like float/imaginary) bases are valid before the dot.
        code, _names = _mutate("def f():\n    return (~0x1).bit_length()\n")
        assert "0x1.bit_length()" in code
        assert "(0x1).bit_length()" not in code

    def test_name_attribute_base_stays_bare(self) -> None:
        code, _names = _mutate("def f(x, y):\n    return (x or y).bit_length()\n")
        assert "y.bit_length()" in code
        assert "(y).bit_length()" not in code

    def test_profile_all_mapping_key_stays_valid(self) -> None:
        # operator_aod (Profile.ALL) on a complex mapping key yields the bare
        # decimal integer '1' — still a valid mapping key ('case {(1): _}'
        # would be a SyntaxError; the M-048 gate is the second line of
        # defence).
        source = (
            "def f(x):\n"
            "    match x:\n"
            "        case {1+2j: _}:\n"
            "            return 1\n"
            "        case _:\n"
            "            return 0\n"
        )
        code, _names = _mutate(source, active_profile=Profile.ALL)
        assert "case {1: _}:" in code


class TestIsBareDecimalInteger:
    def test_decimal_integer_is_bare_decimal(self) -> None:
        assert _is_bare_decimal_integer(cst.Integer("1"))

    def test_underscored_decimal_is_bare_decimal(self) -> None:
        assert _is_bare_decimal_integer(cst.Integer("1_000"))

    def test_hex_integer_is_not_bare_decimal(self) -> None:
        assert not _is_bare_decimal_integer(cst.Integer("0x1"))

    def test_octal_integer_is_not_bare_decimal(self) -> None:
        assert not _is_bare_decimal_integer(cst.Integer("0o7"))

    def test_binary_integer_is_not_bare_decimal(self) -> None:
        assert not _is_bare_decimal_integer(cst.Integer("0b1"))

    def test_uppercase_prefix_is_not_bare_decimal(self) -> None:
        assert not _is_bare_decimal_integer(cst.Integer("0X1"))

    def test_parenthesized_integer_is_not_bare(self) -> None:
        node = cst.Integer("1", lpar=[cst.LeftParen()], rpar=[cst.RightParen()])
        assert not _is_bare_decimal_integer(node)

    def test_other_atoms_are_not_bare_decimals(self) -> None:
        assert not _is_bare_decimal_integer(cst.Name("x"))
        assert not _is_bare_decimal_integer(cst.Float("1.0"))
        assert not _is_bare_decimal_integer(cst.Imaginary("1j"))
        assert not _is_bare_decimal_integer(cst.SimpleString('"1"'))


class TestAttributeBaseProperty:
    @given(
        n=st.integers(min_value=0, max_value=10**9),
        tpl=st.sampled_from(
            [
                "(~{}).bit_length()",
                "abs({}).bit_length()",
                "(x or {}).bit_length()",
                "({} if x else 2).real",
            ]
        ),
    )
    def test_generated_code_always_parses_and_mutates(self, n: int, tpl: str) -> None:
        _code, names = _mutate(f"def f(x):\n    return {tpl.format(n)}\n")
        assert names
