"""Phase 2 of the nextgen-operator roadmap: the advanced operators (ROR matrix,
number CRCR, negate/force condition, collection-empty, match-guard).

opmatrix-style — one construct + one strong assertion per operator, checking the
EXACT mutant set the operator yields. The acceptance_harness is the end-to-end
counterpart; these are the fine-grained TDD pins. All operators are tagged
Profile.ADVANCED.
"""

from __future__ import annotations

import libcst as cst
from hypothesis import given
from hypothesis import strategies as st

from mutmut_win.node_mutation import operator_relational_matrix


def _comparison_target(src: str) -> cst.ComparisonTarget:
    comp = cst.parse_expression(src)
    assert isinstance(comp, cst.Comparison)
    return comp.comparisons[0]


def _ror_ops(src: str) -> set[str]:
    target = _comparison_target(src)
    return {type(m.operator).__name__ for m in operator_relational_matrix(target)}


class TestRorFullMatrix:
    """#3: each ordering operator yields the 4 alternatives that swap_op does
    NOT cover, so swap_op + ROR together span all 5 relations without a
    duplicate (there is no visitor-level dedup). ==/!= are left to swap_op.
    """

    def test_less_than_yields_four_non_swap_alternatives(self) -> None:
        # swap_op gives <= ; ROR gives the other four
        assert _ror_ops("a < b") == {"GreaterThan", "GreaterThanEqual", "Equal", "NotEqual"}

    def test_less_than_equal(self) -> None:
        # swap_op gives < ; ROR gives the other four
        assert _ror_ops("a <= b") == {"GreaterThan", "GreaterThanEqual", "Equal", "NotEqual"}

    def test_greater_than(self) -> None:
        # swap_op gives >= ; ROR gives the other four
        assert _ror_ops("a > b") == {"LessThan", "LessThanEqual", "Equal", "NotEqual"}

    def test_greater_than_equal(self) -> None:
        # swap_op gives > ; ROR gives the other four
        assert _ror_ops("a >= b") == {"LessThan", "LessThanEqual", "Equal", "NotEqual"}

    def test_equality_ops_left_to_swap_op(self) -> None:
        # ==/!= are fully covered by base swap_op; ROR yields nothing for them
        assert _ror_ops("a == b") == set()
        assert _ror_ops("a != b") == set()

    def test_mutated_node_keeps_the_comparator(self) -> None:
        # the yielded node is a ComparisonTarget with the SAME comparator,
        # only the operator changes
        target = _comparison_target("a < b")
        for mutated in operator_relational_matrix(target):
            assert isinstance(mutated, cst.ComparisonTarget)
            assert cst.Module(body=[]).code_for_node(mutated.comparator) == "b"


def _crcr_rendered(src: str) -> set[str]:
    from mutmut_win.node_mutation import operator_number_crcr

    num = cst.parse_expression(src)
    assert isinstance(num, cst.BaseNumber)
    module = cst.Module(body=[])
    return {module.code_for_node(m) for m in operator_number_crcr(num)}


def _crcr_sequence(src: str) -> list[str]:
    """Like :func:`_crcr_rendered` but preserves order and duplicates.

    The set view hides duplicate yields; the sequence view pins them, which is
    what kills the ``seen``-dedup and self-skip mutants — the visitor has no
    dedup of its own, so a duplicate yield is a real defect.
    """
    from mutmut_win.node_mutation import operator_number_crcr

    num = cst.parse_expression(src)
    assert isinstance(num, cst.BaseNumber)
    module = cst.Module(body=[])
    return [module.code_for_node(m) for m in operator_number_crcr(num)]


class TestNumberCrcr:
    """#15: a numeric literal also mutates to 0, 1, -1, and its negation,
    skipping itself (and de-duplicating). Base operator_number (+1) keeps the
    off-by-one mutant. Negatives render as ``-N`` (UnaryOperation, no negative
    literal node in libcst).
    """

    def test_seven(self) -> None:
        assert _crcr_rendered("7") == {"0", "1", "-1", "-7"}

    def test_one_skips_self_and_dedups(self) -> None:
        # {0, 1, -1, -1} \ {1} -> {0, -1}
        assert _crcr_rendered("1") == {"0", "-1"}

    def test_zero(self) -> None:
        # {0, 1, -1, -0} \ {0} -> {1, -1}
        assert _crcr_rendered("0") == {"1", "-1"}

    def test_float(self) -> None:
        # {0.0, 1.0, -2.5} \ {2.5}
        assert _crcr_rendered("2.5") == {"0.0", "1.0", "-2.5"}

    @given(n=st.integers(min_value=0, max_value=10_000))
    def test_crcr_value_set_for_nonneg_int(self, n: int) -> None:
        expected = {v for v in (0, 1, -1, -n) if v != n}
        expected_strs = {str(v) if v >= 0 else f"-{-v}" for v in expected}
        assert _crcr_rendered(str(n)) == expected_strs

    def test_one_yields_each_value_once(self) -> None:
        # (0, 1, -1, -1): -1 and -orig collapse. Without the seen-guard ``-1``
        # would be yielded twice; the visitor has no dedup, so the sequence must
        # be unique. Pins the seen-dedup logic the set view cannot see.
        assert _crcr_sequence("1") == ["0", "-1"]

    def test_seven_sequence_is_ordered_and_unique(self) -> None:
        assert _crcr_sequence("7") == ["0", "1", "-1", "-7"]

    def test_float_one_skips_self_in_sequence(self) -> None:
        # (0.0, 1.0, -1.0): 1.0 is the literal's own value -> skipped. Pins the
        # self-skip and loop control flow on the float path.
        assert _crcr_sequence("1.0") == ["0.0", "-1.0"]


def _if_node(src: str) -> cst.If:
    node = cst.parse_module(src).body[0]
    assert isinstance(node, cst.If)
    return node


def _negate_tests(src: str) -> list[str]:
    from mutmut_win.node_mutation import operator_negate_condition

    module = cst.Module(body=[])
    return [module.code_for_node(m.test) for m in operator_negate_condition(_if_node(src))]


def _force_tests(src: str) -> set[str]:
    from mutmut_win.node_mutation import operator_force_condition

    module = cst.Module(body=[])
    return {module.code_for_node(m.test) for m in operator_force_condition(_if_node(src))}


class TestNegateCondition:
    """#22: negate the WHOLE condition (`if x` -> `if not x`), filling the
    truthy-non-comparison gap that swap_op/ROR (comparisons) and
    operator_remove_unary_ops (existing nots) cannot reach. There is no visitor
    dedup, so those node types are deliberately skipped to avoid redundant
    mutants — the same decoupling as the ROR matrix (#3).
    """

    def test_negates_truthy_name(self) -> None:
        assert _negate_tests("if flag:\n    return 1\n") == ["not flag"]

    def test_negates_call(self) -> None:
        # Call is atomic -> no parens needed
        assert _negate_tests("if check():\n    return 1\n") == ["not check()"]

    def test_parenthesizes_boolean_or(self) -> None:
        # `not a or b` != `not (a or b)`: the paren is mandatory for correctness
        assert _negate_tests("if a or b:\n    return 1\n") == ["not (a or b)"]

    def test_parenthesizes_boolean_and(self) -> None:
        assert _negate_tests("if a and b:\n    return 1\n") == ["not (a and b)"]

    def test_skips_comparison(self) -> None:
        # swap_op / ROR already cover comparison negation
        assert _negate_tests("if x > 0:\n    return 1\n") == []

    def test_skips_existing_not(self) -> None:
        # operator_remove_unary_ops already covers `if not x` -> `if x`
        assert _negate_tests("if not flag:\n    return 1\n") == []


class TestForceCondition:
    """#23: force the condition to a constant (`if c` -> `if True` / `if False`,
    PIT REMOVE_CONDITIONALS), proving both branches are exercised. The value the
    test already is (literal True/False) is skipped as a no-op.
    """

    def test_yields_true_and_false(self) -> None:
        assert _force_tests("if x > 0:\n    return 1\n") == {"True", "False"}

    def test_fires_on_truthy_name(self) -> None:
        assert _force_tests("if flag:\n    return 1\n") == {"True", "False"}

    def test_skips_self_when_already_true(self) -> None:
        assert _force_tests("if True:\n    return 1\n") == {"False"}

    def test_skips_self_when_already_false(self) -> None:
        assert _force_tests("if False:\n    return 1\n") == {"True"}
