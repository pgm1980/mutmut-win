"""Tests for Return Value Replacement and Conditional Expression operators."""

from __future__ import annotations

import libcst as cst

from mutmut_win.node_mutation import (
    operator_conditional_expression,
    operator_return_value,
)


def _return_node(code: str) -> cst.Return:
    """Parse 'return X' and extract the Return node."""
    module = cst.parse_module(code + "\n")
    stmt = module.body[0]
    assert isinstance(stmt, cst.SimpleStatementLine)
    ret = stmt.body[0]
    assert isinstance(ret, cst.Return)
    return ret


def _ifexp_node(code: str) -> cst.IfExp:
    """Parse 'x if c else y' and extract the IfExp node."""
    module = cst.parse_module(code + "\n")
    stmt = module.body[0]
    assert isinstance(stmt, cst.SimpleStatementLine)
    expr = stmt.body[0]
    assert isinstance(expr, cst.Expr)
    assert isinstance(expr.value, cst.IfExp)
    return expr.value


class TestReturnValueReplacement:
    def test_return_call_replaced(self) -> None:
        node = _return_node("return foo()")
        results = list(operator_return_value(node))
        assert len(results) == 1
        assert isinstance(results[0].value, cst.Name)
        assert results[0].value.value == "None"

    def test_return_attribute_replaced(self) -> None:
        node = _return_node("return self.data")
        results = list(operator_return_value(node))
        assert len(results) == 1

    def test_return_comprehension_replaced(self) -> None:
        node = _return_node("return [x for x in items]")
        results = list(operator_return_value(node))
        assert len(results) == 1

    def test_bare_return_skipped(self) -> None:
        node = _return_node("return")
        results = list(operator_return_value(node))
        assert results == []

    def test_return_none_skipped(self) -> None:
        node = _return_node("return None")
        results = list(operator_return_value(node))
        assert results == []

    def test_return_number_skipped(self) -> None:
        node = _return_node("return 42")
        results = list(operator_return_value(node))
        assert results == []

    def test_return_string_skipped(self) -> None:
        node = _return_node("return 'hello'")
        results = list(operator_return_value(node))
        assert results == []

    def test_return_true_skipped(self) -> None:
        node = _return_node("return True")
        results = list(operator_return_value(node))
        assert results == []

    def test_return_false_skipped(self) -> None:
        node = _return_node("return False")
        results = list(operator_return_value(node))
        assert results == []

    def test_return_binary_op_replaced(self) -> None:
        node = _return_node("return a + b")
        results = list(operator_return_value(node))
        assert len(results) == 1


class TestConditionalExpression:
    def test_yields_true_branch(self) -> None:
        node = _ifexp_node("x if condition else y")
        results = list(operator_conditional_expression(node))
        assert len(results) == 2
        # First result should be the true branch (x)
        assert isinstance(results[0], cst.Name)
        assert results[0].value == "x"

    def test_yields_false_branch(self) -> None:
        node = _ifexp_node("x if condition else y")
        results = list(operator_conditional_expression(node))
        assert isinstance(results[1], cst.Name)
        assert results[1].value == "y"

    def test_complex_branches(self) -> None:
        node = _ifexp_node("foo() if bar else baz()")
        results = list(operator_conditional_expression(node))
        assert len(results) == 2

    def test_nested_ternary(self) -> None:
        node = _ifexp_node("a if x else b if y else c")
        results = list(operator_conditional_expression(node))
        assert len(results) == 2
