"""Phase 4 of the nextgen-operator roadmap: the aggressive all-tier operators
(AOD, exception-swap, member/statement-removal, UOI). All tagged Profile.ALL.

opmatrix-style — one construct + one strong assertion per operator, checking the
EXACT mutant set the operator yields. The acceptance_harness all-profile table is
the end-to-end counterpart.
"""

from __future__ import annotations

import libcst as cst


def _aod(src: str) -> list[str]:
    from mutmut_win.node_mutation import operator_aod

    binop = cst.parse_expression(src)
    assert isinstance(binop, cst.BinaryOperation)
    module = cst.Module(body=[])
    return [module.code_for_node(m) for m in operator_aod(binop)]


class TestAod:
    """#2: arithmetic operand deletion — a binary op yields each operand alone."""

    def test_add(self) -> None:
        assert _aod("a + b") == ["a", "b"]

    def test_subtract(self) -> None:
        assert _aod("x - y") == ["x", "y"]

    def test_multiply(self) -> None:
        assert _aod("p * q") == ["p", "q"]

    def test_parenthesizes_non_atomic_operand(self) -> None:
        # _safe_unwrap parenthesises a lower-precedence operand
        assert _aod("a + (b or c)") == ["a", "(b or c)"]


def _exc_swap(src: str) -> list[str]:
    from mutmut_win.node_mutation import operator_exception_swap

    raise_node = cst.parse_module(src).body[0].body[0]
    assert isinstance(raise_node, cst.Raise)
    module = cst.Module(body=[])
    return [module.code_for_node(m) for m in operator_exception_swap(raise_node)]


class TestExceptionSwap:
    """#44: raise ExcA(...) -> raise ExcB(...) via a fixed exception-pair table."""

    def test_value_to_type(self) -> None:
        assert _exc_swap('raise ValueError("x")\n') == ['raise TypeError("x")']

    def test_type_to_value(self) -> None:
        assert _exc_swap('raise TypeError("x")\n') == ['raise ValueError("x")']

    def test_key_to_index(self) -> None:
        assert _exc_swap('raise KeyError("k")\n') == ['raise IndexError("k")']

    def test_unknown_exception_skipped(self) -> None:
        assert _exc_swap('raise CustomError("x")\n') == []

    def test_bare_raise_name_skipped(self) -> None:
        # `raise x` has a Name exc, not a Call -> nothing to swap
        assert _exc_swap("raise x\n") == []

    def test_reraise_skipped(self) -> None:
        # bare `raise` (re-raise) has no exc
        assert _exc_swap("raise\n") == []

    def test_call_returning_callable_skipped(self) -> None:
        # exc.func is itself a Call (no `.value`) -> the Name guard must
        # short-circuit before `.func.value`, leaving the raise untouched (no crash)
        assert _exc_swap('raise make_error()("boom")\n') == []
