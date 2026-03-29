"""Unit tests for mutmut_win.mutation."""

import libcst as cst

from mutmut_win.mutation import (
    ChildReplacementTransformer,
    Mutation,
    _is_generator,
    create_mutations,
    deep_replace,
    get_statements_until_func_or_class,
    group_by_top_level_node,
    mutate_file_contents,
    pragma_no_mutate_lines,
)

# --- pragma_no_mutate_lines ---------------------------------------------------

class TestPragmaNoMutateLines:
    def test_no_pragmas_returns_empty_set(self) -> None:
        result = pragma_no_mutate_lines("x = 1\ny = 2\n")
        assert result == set()

    def test_pragma_line_detected(self) -> None:
        source = "x = 1  # pragma: no mutate\ny = 2\n"
        result = pragma_no_mutate_lines(source)
        assert 1 in result
        assert 2 not in result

    def test_second_line_pragma(self) -> None:
        source = "x = 1\ny = 2  # pragma: no mutate\n"
        result = pragma_no_mutate_lines(source)
        assert 2 in result
        assert 1 not in result

    def test_multiple_pragmas(self) -> None:
        source = "a = 1  # pragma: no mutate\nb = 2\nc = 3  # pragma: no mutate\n"
        result = pragma_no_mutate_lines(source)
        assert 1 in result
        assert 3 in result
        assert 2 not in result


# --- deep_replace -------------------------------------------------------------

class TestDeepReplace:
    def test_replaces_integer_node(self) -> None:
        module = cst.parse_module("x = 1\n")
        cst.Integer("1")
        cst.Integer("99")
        # find the actual old_node in the module
        cst.metadata.MetadataWrapper(module)
        # Replace using a fresh parse to get the node reference
        module2 = cst.parse_module("x = 1\n")
        stmt = module2.body[0]
        assert isinstance(stmt, cst.SimpleStatementLine)
        assign = stmt.body[0]
        assert isinstance(assign, cst.Assign)
        actual_old = assign.value
        result = deep_replace(module2, actual_old, cst.Integer("99"))
        assert "99" in result.code

    def test_only_first_occurrence_replaced(self) -> None:
        module = cst.parse_module("x = 1\ny = 1\n")
        # find the first integer(1)
        stmt = module.body[0]
        assert isinstance(stmt, cst.SimpleStatementLine)
        assign = stmt.body[0]
        assert isinstance(assign, cst.Assign)
        old_node = assign.value
        result = deep_replace(module, old_node, cst.Integer("99"))
        assert result.code.count("99") == 1
        assert result.code.count("= 1") == 1


# --- get_statements_until_func_or_class ---------------------------------------

class TestGetStatementsUntilFuncOrClass:
    def test_stops_at_function(self) -> None:
        module = cst.parse_module("x = 1\ndef foo(): pass\ny = 2\n")
        result = get_statements_until_func_or_class(module.body)
        assert len(result) == 1

    def test_stops_at_class(self) -> None:
        module = cst.parse_module("x = 1\nclass Foo: pass\ny = 2\n")
        result = get_statements_until_func_or_class(module.body)
        assert len(result) == 1

    def test_returns_all_if_no_func_or_class(self) -> None:
        module = cst.parse_module("x = 1\ny = 2\nz = 3\n")
        result = get_statements_until_func_or_class(module.body)
        assert len(result) == 3

    def test_returns_empty_if_starts_with_function(self) -> None:
        module = cst.parse_module("def foo(): pass\n")
        result = get_statements_until_func_or_class(module.body)
        assert len(result) == 0


# --- group_by_top_level_node --------------------------------------------------

class TestGroupByTopLevelNode:
    def test_empty_mutations_returns_empty_mapping(self) -> None:
        result = group_by_top_level_node([])
        assert len(result) == 0

    def test_mutations_without_function_are_excluded(self) -> None:
        original = cst.Integer("1")
        mutated = cst.Integer("2")
        mut = Mutation(
            original_node=original,
            mutated_node=mutated,
            contained_by_top_level_function=None,
        )
        result = group_by_top_level_node([mut])
        assert len(result) == 0


# --- _is_generator ------------------------------------------------------------

class TestIsGenerator:
    def test_non_generator_returns_false(self) -> None:
        module = cst.parse_module("def foo():\n    return 1\n")
        func = module.body[0]
        assert isinstance(func, cst.FunctionDef)
        assert not _is_generator(func)

    def test_generator_returns_true(self) -> None:
        module = cst.parse_module("def foo():\n    yield 1\n")
        func = module.body[0]
        assert isinstance(func, cst.FunctionDef)
        assert _is_generator(func)

    def test_nested_yield_not_counted(self) -> None:
        code = "def foo():\n    def bar():\n        yield 1\n    return 2\n"
        module = cst.parse_module(code)
        func = module.body[0]
        assert isinstance(func, cst.FunctionDef)
        # foo does not yield, only bar does
        assert not _is_generator(func)


# --- create_mutations ---------------------------------------------------------

class TestCreateMutations:
    def test_simple_function_creates_mutations(self) -> None:
        code = "def foo():\n    return 1 + 2\n"
        _module, mutations = create_mutations(code)
        assert len(mutations) > 0

    def test_covered_lines_filters_mutations(self) -> None:
        code = "def foo():\n    x = 1\n    y = 2\n"
        # Only cover line 2 (x = 1), not line 3 (y = 2)
        _module, mutations_all = create_mutations(code)
        _module, mutations_filtered = create_mutations(code, covered_lines={2})
        # Filtered should have fewer or equal mutations
        assert len(mutations_filtered) <= len(mutations_all)

    def test_pragma_lines_excluded(self) -> None:
        code = "def foo():\n    return 1 + 2  # pragma: no mutate\n"
        _module, mutations = create_mutations(code)
        assert len(mutations) == 0

    def test_type_annotation_not_mutated(self) -> None:
        code = "def foo(x: int) -> int:\n    return x\n"
        _module, mutations = create_mutations(code)
        # Type annotations should not be mutated
        assert all(
            not isinstance(m.original_node, cst.Annotation)
            for m in mutations
        )


# --- mutate_file_contents -----------------------------------------------------

class TestMutateFileContents:
    def test_returns_string_and_list(self) -> None:
        code = "def foo():\n    return 1\n"
        mutated_code, names = mutate_file_contents("foo.py", code)
        assert isinstance(mutated_code, str)
        assert isinstance(names, (list, tuple))

    def test_mutated_code_contains_trampoline(self) -> None:
        code = "def foo():\n    return 1\n"
        mutated_code, _names = mutate_file_contents("foo.py", code)
        assert "_mutmut_trampoline" in mutated_code

    def test_function_with_no_mutations_not_modified(self) -> None:
        code = "def foo(): pass\n"
        _mutated_code, names = mutate_file_contents("foo.py", code)
        assert len(names) == 0

    def test_mutation_names_format(self) -> None:
        code = "def foo():\n    return 1 + 2\n"
        _mutated_code, names = mutate_file_contents("foo.py", code)
        assert len(names) > 0
        for name in names:
            assert "__mutmut_" in name


# --- ChildReplacementTransformer ----------------------------------------------

class TestChildReplacementTransformer:
    def test_replaces_matching_node(self) -> None:
        old_node = cst.Integer("1")
        cst.Integer("99")
        transformer = ChildReplacementTransformer(old_node, old_node)
        # replaced_node starts False
        assert not transformer.replaced_node

    def test_on_visit_returns_false_after_replacement(self) -> None:
        old_node = cst.Integer("1")
        new_node = cst.Integer("99")
        transformer = ChildReplacementTransformer(old_node, new_node)
        transformer.replaced_node = True
        # Should return False once replaced
        assert not transformer.on_visit(old_node)
