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


def _stmt_removal(src: str) -> list[str]:
    from mutmut_win.node_mutation import operator_statement_removal

    line = cst.parse_module(src).body[0]
    assert isinstance(line, cst.SimpleStatementLine)
    module = cst.Module(body=[])
    return [module.code_for_node(m).strip() for m in operator_statement_removal(line)]


class TestStatementRemoval:
    """#27: drop an effectful expression statement -> pass. Only Await / Yield /
    Subscript / walrus are removed; Calls (advanced owns them), docstrings,
    ``...`` stubs and pure-value statements are deliberately left alone.
    """

    def test_await_removed(self) -> None:
        assert _stmt_removal("await coro()\n") == ["pass"]

    def test_yield_removed(self) -> None:
        assert _stmt_removal("yield value\n") == ["pass"]

    def test_subscript_removed(self) -> None:
        assert _stmt_removal("buffer[0]\n") == ["pass"]

    def test_walrus_removed(self) -> None:
        assert _stmt_removal("(total := compute())\n") == ["pass"]

    def test_plain_call_skipped(self) -> None:
        # bare Call statements belong to operator_void_call_removal (advanced)
        assert _stmt_removal("do_work()\n") == []

    def test_docstring_skipped(self) -> None:
        # a string-literal statement is a docstring -> removal is always equivalent
        assert _stmt_removal('"""module docstring"""\n') == []

    def test_ellipsis_stub_skipped(self) -> None:
        # `...` stub body -> removal is always equivalent
        assert _stmt_removal("...\n") == []

    def test_pure_value_skipped(self) -> None:
        # a side-effect-free comparison statement -> removal is always equivalent
        assert _stmt_removal("a == b\n") == []

    def test_multi_statement_line_skipped(self) -> None:
        assert _stmt_removal("await a(); await b()\n") == []

    def test_non_expr_statement_with_allowlisted_value_skipped(self) -> None:
        # `x = data[0]` is an Assign (value=Subscript), NOT an Expr statement;
        # the cst.Expr guard must exclude it even though Subscript is allow-listed
        assert _stmt_removal("x = data[0]\n") == []


def _member_assign_removal(src: str) -> list[str]:
    from mutmut_win.node_mutation import operator_member_assignment_removal

    line = cst.parse_module(src).body[0]
    assert isinstance(line, cst.SimpleStatementLine)
    module = cst.Module(body=[])
    return [module.code_for_node(m).strip() for m in operator_member_assignment_removal(line)]


class TestMemberAssignRemoval:
    """#29: drop a single-target attribute assignment -> pass. Plain-name,
    tuple-target, chained and annotated assignments are left to other operators.
    """

    def test_self_attribute_removed(self) -> None:
        assert _member_assign_removal("self.x = 1\n") == ["pass"]

    def test_nested_attribute_removed(self) -> None:
        assert _member_assign_removal("obj.a.b = value\n") == ["pass"]

    def test_plain_name_skipped(self) -> None:
        # a bare-name assignment is the base operator_assignment's domain
        assert _member_assign_removal("x = 1\n") == []

    def test_tuple_target_skipped(self) -> None:
        assert _member_assign_removal("self.x, self.y = pair\n") == []

    def test_chained_target_skipped(self) -> None:
        assert _member_assign_removal("self.x = self.y = value\n") == []

    def test_annotated_assignment_skipped(self) -> None:
        # `self.x: int = 1` is a cst.AnnAssign, not a cst.Assign
        assert _member_assign_removal("self.x: int = 1\n") == []

    def test_multi_statement_line_skipped(self) -> None:
        # two attribute assignments on one line -> the len(body) != 1 guard skips it
        assert _member_assign_removal("self.x = 1; self.y = 2\n") == []


def _uoi_while(src: str) -> list[str]:
    from mutmut_win.node_mutation import operator_uoi_negate_while

    node = cst.parse_module(src).body[0]
    assert isinstance(node, cst.While)
    module = cst.Module(body=[])
    return [module.code_for_node(m.test).strip() for m in operator_uoi_negate_while(node)]


class TestUoiNegateWhile:
    """#12: negate a while test (the while-analogue of operator_negate_condition)."""

    def test_simple(self) -> None:
        assert _uoi_while("while x:\n    pass\n") == ["not x"]

    def test_boolean_test_parenthesized(self) -> None:
        # `not` binds weakly -> _safe_unwrap parenthesises the boolean operand
        assert _uoi_while("while a or b:\n    pass\n") == ["not (a or b)"]

    def test_comparison_test_skipped(self) -> None:
        # a Comparison test is left to swap_op / relational_matrix
        assert _uoi_while("while a < b:\n    pass\n") == []

    def test_existing_not_skipped(self) -> None:
        # an existing `not` is left to operator_remove_unary_ops
        assert _uoi_while("while not x:\n    pass\n") == []


def _uoi_minus(src: str) -> list[str]:
    from mutmut_win.node_mutation import operator_uoi_minus_operand

    node = cst.parse_expression(src)
    assert isinstance(node, cst.BinaryOperation)
    module = cst.Module(body=[])
    return [module.code_for_node(m) for m in operator_uoi_minus_operand(node)]


class TestUoiMinusOperand:
    """#12: insert a parenthesised unary minus on a Name operand of an arithmetic op."""

    def test_both_names(self) -> None:
        assert _uoi_minus("x + y") == ["(-x) + y", "x + (-y)"]

    def test_literal_operand_skipped(self) -> None:
        # the literal 5 is owned by operator_number_crcr (-orig); only x is touched
        assert _uoi_minus("x + 5") == ["(-x) + 5"]

    def test_power_precedence_safe(self) -> None:
        # the explicit parens keep the minus on the operand under ** (not -(x**y))
        assert _uoi_minus("x ** y") == ["(-x) ** y", "x ** (-y)"]

    def test_non_arithmetic_skipped(self) -> None:
        # `&` is BitAnd, not an arithmetic operator
        assert _uoi_minus("x & y") == []

    def test_both_literals_skipped(self) -> None:
        assert _uoi_minus("3 * 4") == []


def _uoi_bool(src: str) -> list[str]:
    from mutmut_win.node_mutation import operator_uoi_negate_boolean_operand

    node = cst.parse_expression(src)
    assert isinstance(node, cst.BooleanOperation)
    module = cst.Module(body=[])
    return [module.code_for_node(m) for m in operator_uoi_negate_boolean_operand(node)]


class TestUoiNegateBooleanOperand:
    """#12: insert `not` on each operand of an and/or chain."""

    def test_and(self) -> None:
        assert _uoi_bool("a and b") == ["not a and b", "a and not b"]

    def test_or(self) -> None:
        assert _uoi_bool("a or b") == ["not a or b", "a or not b"]

    def test_nested_operand_parenthesized(self) -> None:
        # the left operand `a and b` is itself lower-precedence -> _safe_unwrap parens it
        assert _uoi_bool("a and b and c") == ["not (a and b) and c", "a and b and not c"]

    def test_existing_not_left_operand_skipped(self) -> None:
        # the already-negated left operand is skipped (not not a ~ bool(a))
        assert _uoi_bool("not a and b") == ["not a and not b"]

    def test_existing_not_right_operand_skipped(self) -> None:
        # symmetric: the already-negated RIGHT operand is skipped too
        assert _uoi_bool("a and not b") == ["not a and not b"]


def test_no_duplicate_mutants_across_overlapping_operators() -> None:
    """Regression guard (external QA v2.19.0): the operators avoid duplicate
    mutants by construction (e.g. ROR excludes the base boundary swap; the
    all-tier ops are disjoint by node kind). There is NO visitor-level dedup, so
    a future overlapping operator that re-emitted an existing mutant would
    silently add a redundant one for the same node — caught here.
    """
    from mutmut_win.constants import Profile
    from mutmut_win.mutation import create_mutations

    source = (
        "def f(a, b):\n    total = a + b\n    if a < b:\n        return a and b\n    return 7\n"
    )
    _module, mutations = create_mutations(source, active_profile=Profile.ALL)
    renderer = cst.Module(body=[])
    seen: set[tuple[int, str]] = set()
    for mutation in mutations:
        key = (id(mutation.original_node), renderer.code_for_node(mutation.mutated_node))
        assert key not in seen, f"duplicate mutant for one node: {key[1]!r}"
        seen.add(key)
