"""Phase 2 of the nextgen-operator roadmap: the advanced operators (ROR matrix,
number CRCR, negate/force condition, collection-empty, match-guard).

opmatrix-style — one construct + one strong assertion per operator, checking the
EXACT mutant set the operator yields. The acceptance_harness is the end-to-end
counterpart; these are the fine-grained TDD pins. All operators are tagged
Profile.ADVANCED.
"""

from __future__ import annotations

import libcst as cst

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
