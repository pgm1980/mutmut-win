"""Unit tests for mutmut_win.node_mutation."""

import libcst as cst

from mutmut_win.node_mutation import (
    NON_ESCAPE_SEQUENCE,
    _simple_mutation_mapping,
    mutation_operators,
    operator_assignment,
    operator_augmented_assignment,
    operator_keywords,
    operator_lambda,
    operator_match,
    operator_name,
    operator_number,
    operator_remove_unary_ops,
    operator_string,
)

# --- Helper: parse a small expression ------------------------------------------

def _parse_expr(code: str) -> cst.BaseExpression:
    """Parse a single expression from source code."""
    module = cst.parse_module(code)
    stmt = module.body[0]
    assert isinstance(stmt, cst.SimpleStatementLine)
    assert isinstance(stmt.body[0], cst.Expr)
    return stmt.body[0].value


def _parse_stmt(code: str) -> cst.BaseSmallStatement:
    """Parse a single small statement."""
    module = cst.parse_module(code)
    stmt = module.body[0]
    assert isinstance(stmt, cst.SimpleStatementLine)
    return stmt.body[0]


# --- operator_number -----------------------------------------------------------

class TestOperatorNumber:
    def test_integer_incremented(self) -> None:
        node = cst.Integer("5")
        results = list(operator_number(node))
        assert len(results) == 1
        assert isinstance(results[0], cst.Integer)
        assert results[0].value == "6"

    def test_float_incremented(self) -> None:
        node = cst.Float("3.14")
        results = list(operator_number(node))
        assert len(results) == 1
        assert isinstance(results[0], cst.Float)

    def test_imaginary_incremented(self) -> None:
        node = cst.Imaginary("2j")
        results = list(operator_number(node))
        assert len(results) == 1


# --- operator_string -----------------------------------------------------------

class TestOperatorString:
    def test_simple_string_produces_mutations(self) -> None:
        node = cst.SimpleString('"hello"')
        results = list(operator_string(node))
        # expect: XX prefix, lower, upper variants
        assert len(results) >= 1

    def test_triple_quoted_string_not_mutated(self) -> None:
        node = cst.SimpleString('"""docstring"""')
        results = list(operator_string(node))
        assert len(results) == 0

    def test_triple_single_quoted_string_not_mutated(self) -> None:
        node = cst.SimpleString("'''doc'''")
        results = list(operator_string(node))
        assert len(results) == 0

    def test_already_uppercase_string_skips_upper_variant(self) -> None:
        node = cst.SimpleString('"HELLO"')
        results = list(operator_string(node))
        # upper variant should be skipped since it's identical
        values = [r.value for r in results]
        assert all(v != '"HELLO"' or v == '"XXHELLOXX"' for v in values)


# --- operator_lambda -----------------------------------------------------------

class TestOperatorLambda:
    def test_lambda_none_becomes_zero(self) -> None:
        node = cst.parse_expression("lambda: None")
        assert isinstance(node, cst.Lambda)
        results = list(operator_lambda(node))
        assert len(results) == 1
        assert isinstance(results[0].body, cst.Integer)
        assert results[0].body.value == "0"

    def test_lambda_non_none_becomes_none(self) -> None:
        node = cst.parse_expression("lambda x: x + 1")
        assert isinstance(node, cst.Lambda)
        results = list(operator_lambda(node))
        assert len(results) == 1
        assert isinstance(results[0].body, cst.Name)
        assert results[0].body.value == "None"


# --- operator_name -------------------------------------------------------------

class TestOperatorName:
    def test_true_becomes_false(self) -> None:
        node = cst.Name("True")
        results = list(operator_name(node))
        assert len(results) == 1
        assert results[0].value == "False"  # type: ignore[union-attr]

    def test_false_becomes_true(self) -> None:
        node = cst.Name("False")
        results = list(operator_name(node))
        assert len(results) == 1
        assert results[0].value == "True"  # type: ignore[union-attr]

    def test_deepcopy_becomes_copy(self) -> None:
        node = cst.Name("deepcopy")
        results = list(operator_name(node))
        assert len(results) == 1
        assert results[0].value == "copy"  # type: ignore[union-attr]

    def test_unknown_name_not_mutated(self) -> None:
        node = cst.Name("my_variable")
        results = list(operator_name(node))
        assert len(results) == 0


# --- operator_keywords ---------------------------------------------------------

class TestOperatorKeywords:
    def test_is_becomes_is_not(self) -> None:
        node = cst.Is()
        results = list(operator_keywords(node))
        assert len(results) == 1
        assert isinstance(results[0], cst.IsNot)

    def test_in_becomes_not_in(self) -> None:
        node = cst.In()
        results = list(operator_keywords(node))
        assert len(results) == 1
        assert isinstance(results[0], cst.NotIn)

    def test_break_becomes_return(self) -> None:
        node = cst.Break()
        results = list(operator_keywords(node))
        assert len(results) == 1
        assert isinstance(results[0], cst.Return)

    def test_continue_becomes_break(self) -> None:
        node = cst.Continue()
        results = list(operator_keywords(node))
        assert len(results) == 1
        assert isinstance(results[0], cst.Break)


# --- operator_assignment -------------------------------------------------------

class TestOperatorAssignment:
    def test_value_assignment_becomes_none(self) -> None:
        stmt = _parse_stmt("a = 5")
        assert isinstance(stmt, cst.Assign)
        results = list(operator_assignment(stmt))
        assert len(results) == 1
        assert isinstance(results[0].value, cst.Name)  # type: ignore[union-attr]
        assert results[0].value.value == "None"  # type: ignore[union-attr]

    def test_none_assignment_becomes_empty_string(self) -> None:
        stmt = _parse_stmt("a = None")
        assert isinstance(stmt, cst.Assign)
        results = list(operator_assignment(stmt))
        assert len(results) == 1
        assert isinstance(results[0].value, cst.SimpleString)  # type: ignore[union-attr]
        assert results[0].value.value == '""'  # type: ignore[union-attr]


# --- operator_augmented_assignment ---------------------------------------------

class TestOperatorAugmentedAssignment:
    def test_aug_assign_becomes_assign(self) -> None:
        stmt = _parse_stmt("a += 1")
        assert isinstance(stmt, cst.AugAssign)
        results = list(operator_augmented_assignment(stmt))
        assert len(results) == 1
        assert isinstance(results[0], cst.Assign)


# --- operator_remove_unary_ops -------------------------------------------------

class TestOperatorRemoveUnaryOps:
    def test_not_removed(self) -> None:
        expr = cst.parse_expression("not x")
        assert isinstance(expr, cst.UnaryOperation)
        results = list(operator_remove_unary_ops(expr))
        assert len(results) == 1

    def test_bitinvert_removed(self) -> None:
        expr = cst.parse_expression("~x")
        assert isinstance(expr, cst.UnaryOperation)
        results = list(operator_remove_unary_ops(expr))
        assert len(results) == 1

    def test_unary_minus_not_removed(self) -> None:
        expr = cst.parse_expression("-x")
        assert isinstance(expr, cst.UnaryOperation)
        results = list(operator_remove_unary_ops(expr))
        assert len(results) == 0


# --- operator_match ------------------------------------------------------------

class TestOperatorMatch:
    def test_single_case_not_mutated(self) -> None:
        code = "match x:\n    case 1:\n        pass\n"
        module = cst.parse_module(code)
        match_stmt = module.body[0]
        assert isinstance(match_stmt, cst.Match)
        results = list(operator_match(match_stmt))
        assert len(results) == 0

    def test_two_cases_produces_two_mutations(self) -> None:
        code = "match x:\n    case 1:\n        pass\n    case 2:\n        pass\n"
        module = cst.parse_module(code)
        match_stmt = module.body[0]
        assert isinstance(match_stmt, cst.Match)
        results = list(operator_match(match_stmt))
        assert len(results) == 2


# --- mutation_operators list ---------------------------------------------------

class TestMutationOperatorsList:
    def test_mutation_operators_is_sequence(self) -> None:
        assert len(mutation_operators) > 0

    def test_all_entries_are_tuples_of_type_and_callable(self) -> None:
        for node_type, operator in mutation_operators:
            assert issubclass(node_type, cst.CSTNode)
            assert callable(operator)


# --- _simple_mutation_mapping --------------------------------------------------

class TestSimpleMutationMapping:
    def test_known_type_returns_instance(self) -> None:
        mapping: dict[type[cst.CSTNode], type[cst.CSTNode]] = {cst.Plus: cst.Minus}
        results = list(_simple_mutation_mapping(cst.Plus(), mapping))
        assert len(results) == 1
        assert isinstance(results[0], cst.Minus)

    def test_unknown_type_returns_nothing(self) -> None:
        mapping: dict[type[cst.CSTNode], type[cst.CSTNode]] = {cst.Plus: cst.Minus}
        results = list(_simple_mutation_mapping(cst.Multiply(), mapping))
        assert len(results) == 0


# --- NON_ESCAPE_SEQUENCE pattern -----------------------------------------------

class TestNonEscapeSequencePattern:
    def test_matches_normal_chars(self) -> None:
        match = NON_ESCAPE_SEQUENCE.search("hello")
        assert match is not None

    def test_does_not_match_backslash_start(self) -> None:
        # a string that starts with a backslash - the pattern should not match
        matches = NON_ESCAPE_SEQUENCE.findall("\\n")
        assert "\\n" not in matches
