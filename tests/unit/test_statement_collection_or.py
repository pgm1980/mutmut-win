"""Tests for Statement Removal, Collection Neutralize, and or-Default operators."""

from __future__ import annotations

import libcst as cst

from mutmut_win.node_mutation import (
    operator_collection_neutralize,
    operator_comprehension_filter_removal,
    operator_or_default,
    operator_raise_removal,
    operator_void_call_removal,
)


def _stmt_line(code: str) -> cst.SimpleStatementLine:
    """Parse a single-line statement."""
    module = cst.parse_module(code + "\n")
    stmt = module.body[0]
    assert isinstance(stmt, cst.SimpleStatementLine)
    return stmt


def _call(code: str) -> cst.Call:
    """Parse a call expression."""
    module = cst.parse_module(code + "\n")
    stmt = module.body[0]
    assert isinstance(stmt, cst.SimpleStatementLine)
    expr = stmt.body[0]
    assert isinstance(expr, cst.Expr)
    assert isinstance(expr.value, cst.Call)
    return expr.value


def _listcomp(code: str) -> cst.ListComp:
    """Parse a list comprehension."""
    module = cst.parse_module(code + "\n")
    stmt = module.body[0]
    assert isinstance(stmt, cst.SimpleStatementLine)
    expr = stmt.body[0]
    assert isinstance(expr, cst.Expr)
    assert isinstance(expr.value, cst.ListComp)
    return expr.value


def _boolop(code: str) -> cst.BooleanOperation:
    """Parse a boolean operation."""
    module = cst.parse_module(code + "\n")
    stmt = module.body[0]
    assert isinstance(stmt, cst.SimpleStatementLine)
    expr = stmt.body[0]
    assert isinstance(expr, cst.Expr)
    assert isinstance(expr.value, cst.BooleanOperation)
    return expr.value


# ---- Statement Removal ----


class TestVoidCallRemoval:
    def test_removes_void_call(self) -> None:
        node = _stmt_line("foo()")
        results = list(operator_void_call_removal(node))
        assert len(results) == 1
        assert isinstance(results[0].body[0], cst.Pass)

    def test_removes_method_call(self) -> None:
        node = _stmt_line("self.bar()")
        results = list(operator_void_call_removal(node))
        assert len(results) == 1

    def test_skips_print(self) -> None:
        node = _stmt_line("print('debug')")
        results = list(operator_void_call_removal(node))
        assert results == []

    def test_skips_logger(self) -> None:
        node = _stmt_line("logger.info('msg')")
        results = list(operator_void_call_removal(node))
        assert results == []

    def test_skips_assignment(self) -> None:
        node = _stmt_line("x = foo()")
        results = list(operator_void_call_removal(node))
        assert results == []

    def test_skips_non_call_expr(self) -> None:
        node = _stmt_line("x + y")
        results = list(operator_void_call_removal(node))
        assert results == []


class TestRaiseRemoval:
    def test_removes_raise(self) -> None:
        node = _stmt_line("raise ValueError('bad')")
        results = list(operator_raise_removal(node))
        assert len(results) == 1
        assert isinstance(results[0].body[0], cst.Pass)

    def test_removes_bare_raise(self) -> None:
        node = _stmt_line("raise")
        results = list(operator_raise_removal(node))
        assert len(results) == 1

    def test_skips_non_raise(self) -> None:
        node = _stmt_line("x = 1")
        results = list(operator_raise_removal(node))
        assert results == []


# ---- Collection Methods ----


class TestCollectionNeutralize:
    def test_sorted_to_arg(self) -> None:
        node = _call("sorted(items)")
        results = list(operator_collection_neutralize(node))
        assert len(results) == 1
        assert isinstance(results[0], cst.Name)

    def test_reversed_to_arg(self) -> None:
        node = _call("reversed(items)")
        results = list(operator_collection_neutralize(node))
        assert len(results) == 1

    def test_list_to_arg(self) -> None:
        node = _call("list(items)")
        results = list(operator_collection_neutralize(node))
        assert len(results) == 1

    def test_non_collection_not_mutated(self) -> None:
        node = _call("foo(items)")
        results = list(operator_collection_neutralize(node))
        assert results == []

    def test_empty_args_not_mutated(self) -> None:
        node = _call("sorted()")
        results = list(operator_collection_neutralize(node))
        assert results == []


class TestComprehensionFilterRemoval:
    def test_removes_if_clause(self) -> None:
        node = _listcomp("[x for x in items if x > 0]")
        results = list(operator_comprehension_filter_removal(node))
        assert len(results) == 1
        # The result should have no ifs
        assert not results[0].for_in.ifs

    def test_no_filter_not_mutated(self) -> None:
        node = _listcomp("[x for x in items]")
        results = list(operator_comprehension_filter_removal(node))
        assert results == []


# ---- or-Default ----


class TestOrDefault:
    def test_yields_left(self) -> None:
        node = _boolop("x or default_value")
        results = list(operator_or_default(node))
        assert len(results) == 2
        assert isinstance(results[0], cst.Name)
        assert results[0].value == "x"

    def test_yields_right(self) -> None:
        node = _boolop("x or default_value")
        results = list(operator_or_default(node))
        assert isinstance(results[1], cst.Name)
        assert results[1].value == "default_value"

    def test_and_not_mutated(self) -> None:
        node = _boolop("x and y")
        results = list(operator_or_default(node))
        assert results == []

    def test_complex_or(self) -> None:
        node = _boolop("foo() or bar()")
        results = list(operator_or_default(node))
        assert len(results) == 2
