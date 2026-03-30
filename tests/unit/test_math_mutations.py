"""Tests for math method mutation operator."""

from __future__ import annotations

import libcst as cst

from mutmut_win.node_mutation import operator_math_methods


def _call(code: str) -> cst.Call:
    """Parse a single expression and return the Call node."""
    module = cst.parse_module(code + "\n")
    stmt = module.body[0]
    assert isinstance(stmt, cst.SimpleStatementLine)
    expr = stmt.body[0]
    assert isinstance(expr, cst.Expr)
    assert isinstance(expr.value, cst.Call)
    return expr.value


def _mutated_codes(code: str) -> list[str]:
    """Return the code strings of all mutations for a call expression."""
    node = _call(code)
    return [cst.parse_module("").code_for_node(m) for m in operator_math_methods(node)]


class TestMathSwaps:
    def test_ceil_to_floor(self) -> None:
        results = _mutated_codes("math.ceil(x)")
        assert any("floor" in r for r in results)

    def test_floor_to_ceil(self) -> None:
        results = _mutated_codes("math.floor(x)")
        assert any("ceil" in r for r in results)

    def test_min_to_max(self) -> None:
        results = _mutated_codes("min(a, b)")
        assert any("max" in r for r in results)

    def test_max_to_min(self) -> None:
        results = _mutated_codes("max(a, b)")
        assert any("min" in r for r in results)

    def test_non_math_call_not_mutated(self) -> None:
        results = _mutated_codes("foo(x)")
        assert results == []


class TestMathNeutralize:
    def test_abs_to_arg(self) -> None:
        results = _mutated_codes("abs(x)")
        assert any(r.strip() == "x" for r in results)

    def test_round_to_arg(self) -> None:
        results = _mutated_codes("round(x)")
        assert any(r.strip() == "x" for r in results)

    def test_sum_to_zero(self) -> None:
        results = _mutated_codes("sum(items)")
        assert any(r.strip() == "0" for r in results)

    def test_abs_no_args_no_crash(self) -> None:
        # abs() with no args — should not crash
        results = _mutated_codes("abs()")
        # No neutralisation (no args), but no crash either
        assert isinstance(results, list)


class TestMathAttributeCalls:
    def test_math_ceil_attribute(self) -> None:
        results = _mutated_codes("math.ceil(x)")
        assert len(results) >= 1

    def test_math_floor_attribute(self) -> None:
        results = _mutated_codes("math.floor(x)")
        assert len(results) >= 1
