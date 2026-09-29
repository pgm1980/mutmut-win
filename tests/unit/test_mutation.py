"""Unit tests for mutmut_win.mutation."""

import ast

import libcst as cst
from hypothesis import given, settings
from hypothesis import strategies as st

from mutmut_win.mutation import (
    ChildReplacementTransformer,
    Mutation,
    _is_generator,
    _pragma_block_range,
    _pragma_no_mutate_suffix,
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

    def test_start_end_range_inclusive(self) -> None:
        source = "a = 1\n# pragma: no mutate start\nb = 2\nc = 3\n# pragma: no mutate end\nd = 4\n"
        result = pragma_no_mutate_lines(source)
        assert result == {2, 3, 4, 5}  # the two markers and everything between
        assert 1 not in result
        assert 6 not in result

    def test_dangling_start_skips_to_end_of_file(self) -> None:
        source = "a = 1\n# pragma: no mutate start\nb = 2\nc = 3\n"
        result = pragma_no_mutate_lines(source)
        assert 1 not in result
        assert {2, 3, 4}.issubset(result)  # from the start marker to EOF

    def test_block_covers_indented_suite(self) -> None:
        source = "def f():  # pragma: no mutate block\n    a = 1\n    b = 2\nc = 3\n"
        result = pragma_no_mutate_lines(source)
        assert result == {1, 2, 3}  # header + the two body lines, not the dedent
        assert 4 not in result

    def test_block_includes_interior_blank_lines(self) -> None:
        source = "def f():  # pragma: no mutate block\n    a = 1\n\n    b = 2\nc = 3\n"
        result = pragma_no_mutate_lines(source)
        assert result == {1, 2, 3, 4}  # blank line between body lines stays inside
        assert 5 not in result

    def test_plain_pragma_excludes_only_its_line(self) -> None:
        # exact-set pin (kills superset / off-by-one mutants on the plain branch)
        assert pragma_no_mutate_lines("a = 1\nb = 2  # pragma: no mutate\nc = 3\n") == {2}

    def test_pragma_without_no_mutate_marker_ignored(self) -> None:
        # `# pragma:` present but NOT the `no mutate` marker -> nothing excluded
        assert pragma_no_mutate_lines("x = 1  # pragma: allowlist\n") == set()

    def test_unknown_suffix_word_degrades_to_plain(self) -> None:
        # an unrecognised word after `no mutate` falls back to the single line
        assert pragma_no_mutate_lines("x = 1  # pragma: no mutate later\n") == {1}

    def test_suffix_word_is_case_insensitive(self) -> None:
        src = "# pragma: no mutate START\nx = 1\n# pragma: no mutate END\n"
        assert pragma_no_mutate_lines(src) == {1, 2, 3}

    def test_block_suffix_uses_only_the_first_word(self) -> None:
        # trailing words after `block` are ignored; block extent still applies
        src = "def f():  # pragma: no mutate block now\n    a = 1\nb = 2\n"
        assert pragma_no_mutate_lines(src) == {1, 2}

    def test_block_on_simple_statement_is_just_its_line(self) -> None:
        # no indented suite below -> block degenerates to the single line
        assert pragma_no_mutate_lines("x = 1  # pragma: no mutate block\ny = 2\n") == {1}

    def test_deeper_indent_block_extent(self) -> None:
        src = "    if x:  # pragma: no mutate block\n        a = 1\n    b = 2\n"
        assert pragma_no_mutate_lines(src) == {1, 2}

    def test_two_independent_start_end_ranges(self) -> None:
        src = (
            "# pragma: no mutate start\na = 1\n# pragma: no mutate end\n"
            "b = 2\n"
            "# pragma: no mutate start\nc = 3\n# pragma: no mutate end\n"
        )
        # open_start must reset after the first `end`, so the two ranges are distinct
        assert pragma_no_mutate_lines(src) == {1, 2, 3, 5, 6, 7}

    def test_duplicate_start_keeps_the_first(self) -> None:
        src = (
            "# pragma: no mutate start\na = 1\n"
            "# pragma: no mutate start\nb = 2\n# pragma: no mutate end\n"
        )
        # the first open start wins (the second is ignored until the end)
        assert pragma_no_mutate_lines(src) == {1, 2, 3, 4, 5}

    def test_block_pragma_below_first_line(self) -> None:
        # block not on line 1 -> the scan must start at pragma_index + 1
        src = "x = 1\ndef f():  # pragma: no mutate block\n    a = 1\nb = 2\n"
        assert pragma_no_mutate_lines(src) == {2, 3}

    def test_block_extending_to_end_of_file(self) -> None:
        # the suite runs to EOF -> the `cursor < len(lines)` bound must not overrun
        src = "def f():  # pragma: no mutate block\n    a = 1\n    b = 2\n"
        assert pragma_no_mutate_lines(src) == {1, 2, 3}

    def test_lone_end_marker_is_just_its_line(self) -> None:
        # an `end` with no open `start` falls back to its own line
        assert pragma_no_mutate_lines("x = 1\n# pragma: no mutate end\ny = 2\n") == {2}

    def test_plain_pragma_on_block_header_skips_only_header(self) -> None:
        # plain (not block) on a def header -> only the header line, body still mutable
        assert pragma_no_mutate_lines("def f():  # pragma: no mutate\n    a = 1\nb = 2\n") == {1}

    def test_dangling_start_without_trailing_newline(self) -> None:
        # exact set, no trailing newline -> pins the to-EOF range bound
        assert pragma_no_mutate_lines("a = 1\n# pragma: no mutate start\nb = 2\nc = 3") == {2, 3, 4}

    def test_block_breaks_on_lesser_indent(self) -> None:
        # a line dedented BELOW the header indent ends the block (<= base, not == base)
        src = "    if x:  # pragma: no mutate block\n        a = 1\nb = 2\n"
        assert pragma_no_mutate_lines(src) == {1, 2}

    def test_block_survives_column0_comment_inside_suite(self) -> None:
        # M-043 regression: a column-0 comment line is NOT a statement and must
        # not end the block - the suite continues with ` b = 2` below it.
        src = "def f():  # pragma: no mutate block\n    a = 1\n# note\n    b = 2\nc = 3\n"
        assert pragma_no_mutate_lines(src) == {1, 2, 3, 4}

    def test_block_survives_multiline_string_content_at_column0(self) -> None:
        # M-043 regression: the STRING token spans several physical lines; its
        # column-0 content lines are not suite boundaries.
        src = 'def f():  # pragma: no mutate block\n    s = """\nx\n"""\n    b = 2\nc = 3\n'
        assert pragma_no_mutate_lines(src) == {1, 2, 3, 4, 5}

    def test_block_survives_multiline_fstring_content_at_column0(self) -> None:
        # f-strings tokenise as FSTRING_START/MIDDLE/END; same rule as plain
        # multi-line strings (guard for the token-based extent).
        src = 'def g(v):  # pragma: no mutate block\n    s = f"""{v}\nx\n"""\n    b = 2\nc = 3\n'
        assert pragma_no_mutate_lines(src) == {1, 2, 3, 4, 5}

    def test_block_excludes_trailing_comment_after_last_statement(self) -> None:
        # pinned new semantic: the extent ends at the last NEWLINE inside the
        # suite, so a trailing comment line after the last statement drops out
        # (it cannot carry a mutation target anyway).
        src = "def f():  # pragma: no mutate block\n    a = 1\n    # tail\nc = 3\n"
        assert pragma_no_mutate_lines(src) == {1, 2}

    def test_comment_only_block_pragma_as_first_suite_line_stays_single_line(self) -> None:
        # guard against silent widening: for a comment-only pragma the next
        # significant token is the INDENT of the ENCLOSING header, which must
        # not swallow the whole body - comment-only pragmas keep the legacy
        # physical-indent extent.
        src = "def f():\n    # pragma: no mutate block\n    if x:\n        a = 1\nc = 3\n"
        assert pragma_no_mutate_lines(src) == {2}

    def test_comment_only_block_pragma_before_header_stays_single_line(self) -> None:
        src = "x = 1\n# pragma: no mutate block\ndef f():\n    a = 1\n"
        assert pragma_no_mutate_lines(src) == {2}

    def test_block_pragma_on_bracket_continuation_line_stays_legacy(self) -> None:
        # pinned conservative decision: the token-based extent only applies to
        # pragmas on a code line that CLOSES its logical line (NEWLINE on the
        # same physical line). A pragma inside a bracketed multi-line header
        # keeps the physical-indent extent instead of widening to the suite.
        src = "def f(\n    a,  # pragma: no mutate block\n):\n    x = 1\n"
        assert pragma_no_mutate_lines(src) == {2}

    def test_block_pragma_over_multiline_string_prevents_all_mutants(self) -> None:
        # end to end: nothing inside the block pragma's suite may produce a
        # mutant name (`c = 3` is a module statement and never mutated).
        source = 'def f():  # pragma: no mutate block\n    s = """\nx\n"""\n    b = 2\nc = 3\n'
        _code, names = mutate_file_contents("m.py", source)
        assert list(names) == []

    @given(
        st.lists(st.sampled_from(["assign", "comment", "string", "blank"]), min_size=1, max_size=6)
    )
    @settings(deadline=None)
    def test_block_extent_matches_ast_suite_property(self, parts: list[str]) -> None:
        """A code-line block pragma covers at least the whole ast function suite."""
        lines = ["def f():  # pragma: no mutate block", "    v0 = 0"]
        for part in parts:
            if part == "assign":
                lines.append(f"    v{len(lines)} = {len(lines)}")
            elif part == "comment":
                lines.append("# col0 comment")
            elif part == "string":
                lines += ['    s = """', "col0 string content", '    """']
            else:
                lines.append("")
        lines.append("z = 1")
        source = "\n".join(lines) + "\n"
        tree = ast.parse(source)
        function = tree.body[0]
        assert isinstance(function, ast.FunctionDef)
        result = pragma_no_mutate_lines(source)
        assert set(range(function.lineno, (function.end_lineno or 0) + 1)) <= result
        assert tree.body[1].lineno not in result

    @given(
        st.lists(st.sampled_from(["assign", "comment", "string", "blank"]), min_size=1, max_size=6)
    )
    @settings(deadline=None)
    def test_comment_only_block_pragma_keeps_legacy_extent_property(self, parts: list[str]) -> None:
        """A comment-only block pragma keeps exactly the legacy indent-based extent."""
        lines = ["def g():", "    w0 = 0", "    # pragma: no mutate block"]
        for part in parts:
            if part == "assign":
                lines.append(f"    w{len(lines)} = {len(lines)}")
            elif part == "comment":
                lines.append("# col0 comment")
            elif part == "string":
                lines += ['    t = """', "col0 string content", '    """']
            else:
                lines.append("")
        lines.append("y = 1")
        source = "\n".join(lines) + "\n"
        legacy = _pragma_block_range(source.split("\n"), 2)
        assert pragma_no_mutate_lines(source) == set(legacy)

    def test_block_starts_suite_after_blank_line_between_header_and_body(self) -> None:
        # the NL/COMMENT skip between the header's NEWLINE and the suite's
        # INDENT must not end the block (token-path boundary).
        src = "def f():  # pragma: no mutate block\n\n    a = 1\nb = 2\n"
        assert pragma_no_mutate_lines(src) == {1, 2, 3}

    def test_block_starts_suite_after_comment_line_between_header_and_body(self) -> None:
        src = "def f():  # pragma: no mutate block\n# lead\n    a = 1\nb = 2\n"
        assert pragma_no_mutate_lines(src) == {1, 2, 3}

    def test_block_pragma_on_final_line_without_newline_or_suite(self) -> None:
        # EOF right after the pragma's logical line: no suite, no crash.
        assert pragma_no_mutate_lines("x = 1  # pragma: no mutate block") == {1}

    def test_block_pragma_with_trailing_blank_line_after_simple_statement(self) -> None:
        # trailing NL tokens after the pragma's NEWLINE must be skipped and
        # still yield no suite (the next significant token is code, not INDENT).
        assert pragma_no_mutate_lines("x = 1  # pragma: no mutate block\n\ny = 2\n") == {1}

    def test_block_covers_nested_indented_suite_completely(self) -> None:
        # nested INDENT/DEDENT inside the suite must not end the block at the
        # FIRST inner DEDENT - the block only ends when the pragma header's own
        # suite dedents (INDENT/DEDENT depth counting).
        src = "if x:  # pragma: no mutate block\n    if y:\n        a = 1\n    b = 2\nc = 3\n"
        assert pragma_no_mutate_lines(src) == {1, 2, 3, 4}

    def test_suffix_helper_return_values(self) -> None:
        # direct probe of the classifier: pins the exact return value so the
        # caller-equivalent mutants (unknown / empty -> a non-"" sentinel) die
        assert _pragma_no_mutate_suffix("x = 1") is None
        assert _pragma_no_mutate_suffix("x  # pragma: lint") is None
        assert _pragma_no_mutate_suffix("x  # pragma: no mutate") == ""
        assert _pragma_no_mutate_suffix("x  # pragma: no mutate start") == "start"
        assert _pragma_no_mutate_suffix("x  # pragma: no mutate end") == "end"
        assert _pragma_no_mutate_suffix("x  # pragma: no mutate block") == "block"
        assert _pragma_no_mutate_suffix("x  # pragma: no mutate other") == ""


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
        # exact bool: the API contract is a bool return, not any falsy value
        assert _is_generator(func) is False

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

    def test_lambda_yield_not_counted(self) -> None:
        # M-044: a lambda body is its own scope — a yield there makes only
        # the LAMBDA a generator, not the surrounding function.
        code = "def foo():\n    g = lambda: (yield)\n    return g\n"
        module = cst.parse_module(code)
        func = module.body[0]
        assert isinstance(func, cst.FunctionDef)
        assert not _is_generator(func)

    def test_lambda_default_yield_still_counted(self) -> None:
        # guard against over-fixing (M-044 review): parameter defaults are
        # evaluated in the ENCLOSING scope, so this foo IS a generator.
        code = "def foo():\n    g = lambda x=(yield): x\n    return g\n"
        module = cst.parse_module(code)
        func = module.body[0]
        assert isinstance(func, cst.FunctionDef)
        assert _is_generator(func)

    def test_nested_lambda_default_body_yield_not_counted(self) -> None:
        # the inner lambda's BODY yield must not leak through the outer
        # lambda's default expression
        code = "def foo():\n    g = lambda x=(lambda: (yield)): x\n    return g\n"
        module = cst.parse_module(code)
        func = module.body[0]
        assert isinstance(func, cst.FunctionDef)
        assert not _is_generator(func)

    def test_lambda_param_without_default_and_body_yield_not_counted(self) -> None:
        # a default-less lambda parameter plus a yield only in the lambda
        # BODY: foo is not a generator, and the default visit loop must skip
        # the parameter instead of dereferencing its absent default.
        code = "def foo():\n    g = lambda x: (yield)\n    return g\n"
        module = cst.parse_module(code)
        func = module.body[0]
        assert isinstance(func, cst.FunctionDef)
        assert not _is_generator(func)

    def test_lambda_posonly_and_kwonly_defaults_counted(self) -> None:
        # the default visit loop covers every ordinary parameter group:
        # positional-only (with a default) and keyword-only defaults are
        # evaluated in the enclosing scope as well.
        code = "def foo():\n    g = lambda x=1, /, *, k=(yield): x\n    return g\n"
        module = cst.parse_module(code)
        func = module.body[0]
        assert isinstance(func, cst.FunctionDef)
        assert _is_generator(func)

    def test_yield_in_outermost_comprehension_iterable_counted(self) -> None:
        # guard (M-044 review): the outermost for-iterable is evaluated in
        # the enclosing scope — this foo IS a generator and must not be
        # excluded by any scope boundary the visitor adds.
        code = "def foo():\n    return [x for x in (yield)]\n"
        module = cst.parse_module(code)
        func = module.body[0]
        assert isinstance(func, cst.FunctionDef)
        assert _is_generator(func)


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
        assert all(not isinstance(m.original_node, cst.Annotation) for m in mutations)

    def test_single_quoted_docstrings_are_not_mutation_targets(self) -> None:
        code = """\
'module docs'

class C:
    'class docs'

    def method(self):
        'method docs'
        return 'runtime payload'

def outer():
    def inner():
        'nested docs'
        return 'nested payload'
    return inner()
"""
        _module, mutations = create_mutations(code)
        mutated_strings = {
            node.evaluated_value
            for mutation in mutations
            if isinstance((node := mutation.original_node), cst.SimpleString)
        }

        assert (
            not {
                "module docs",
                "class docs",
                "method docs",
                "nested docs",
            }
            & mutated_strings
        )
        assert {"runtime payload", "nested payload"} <= mutated_strings

    def test_concatenated_constant_str_docstring_is_not_a_mutation_target(self) -> None:
        code = """\
def f():
    "constant " "docs"
    return "runtime payload"
"""
        _module, mutations = create_mutations(code)
        mutated_strings = {
            node.evaluated_value
            for mutation in mutations
            if isinstance((node := mutation.original_node), cst.SimpleString)
        }

        assert not {"constant ", "docs"} & mutated_strings
        assert "runtime payload" in mutated_strings

    def test_semicolon_docstring_is_not_a_mutation_target(self) -> None:
        code = """\
def f():
    "real docs"; payload = "runtime payload"
    return payload
"""
        _module, mutations = create_mutations(code)
        mutated_strings = {
            node.evaluated_value
            for mutation in mutations
            if isinstance((node := mutation.original_node), cst.SimpleString)
        }

        assert "real docs" not in mutated_strings
        assert "runtime payload" in mutated_strings

    def test_leading_bytes_expression_remains_a_mutation_target(self) -> None:
        code = """\
def f():
    b"runtime bytes"
    return "runtime payload"
"""
        _module, mutations = create_mutations(code)
        mutated_strings = {
            node.evaluated_value
            for mutation in mutations
            if isinstance((node := mutation.original_node), cst.SimpleString)
        }

        assert b"runtime bytes" in mutated_strings
        assert "runtime payload" in mutated_strings

    def test_leading_f_string_concatenation_remains_a_mutation_target(self) -> None:
        code = """\
def f(value):
    f"{value}" "runtime tail"
    return "runtime payload"
"""
        _module, mutations = create_mutations(code)
        mutated_strings = {
            node.evaluated_value
            for mutation in mutations
            if isinstance((node := mutation.original_node), cst.SimpleString)
        }

        assert "runtime tail" in mutated_strings
        assert "runtime payload" in mutated_strings


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
