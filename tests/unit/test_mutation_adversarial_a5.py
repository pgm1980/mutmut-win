"""Adversarial regressions for mutation-codegen hardening wave A5."""

from __future__ import annotations

import asyncio
import inspect
import os
from typing import Any

import libcst as cst

from mutmut_win.constants import Profile
from mutmut_win.mutation import mutate_file_contents, pragma_no_mutate_lines
from mutmut_win.node_mutation import operator_regex


def _exec_clean(
    source: str, namespace: dict[str, Any] | None = None
) -> tuple[str, list[str], dict[str, Any]]:
    generated, names = mutate_file_contents("m.py", source)
    execution_namespace: dict[str, Any] = {"__name__": "m"}
    if namespace:
        execution_namespace.update(namespace)
    old_mutant = os.environ.pop("MUTANT_UNDER_TEST", None)
    try:
        # The generated string derives solely from the literal test fixture.
        exec(  # noqa: S102  # nosec B102  # nosemgrep
            compile(generated, "m", "exec", dont_inherit=True), execution_namespace
        )
    finally:
        if old_mutant is not None:
            os.environ["MUTANT_UNDER_TEST"] = old_mutant
    return generated, list(names), execution_namespace


def _regex_mutant_patterns(expression_source: str) -> set[str]:
    expression = cst.parse_expression(expression_source)
    assert isinstance(expression, cst.Call)
    patterns: set[str] = set()
    for mutation in operator_regex(expression):
        pattern_node = mutation.args[0].value
        assert isinstance(pattern_node, cst.SimpleString)
        pattern = pattern_node.evaluated_value
        assert isinstance(pattern, str)
        patterns.add(pattern)
    return patterns


class TestDefinitionTimeSemantics:
    def test_defaults_annotations_and_docstring_exist_only_on_public_wrapper(self) -> None:
        events: list[str] = []

        def record(label: str, value: Any) -> Any:
            events.append(label)
            return value

        source = '''\
def f(
    x: record("annotation", int) = record("default", 1),
) -> record("return", int):
    """public documentation"""
    return x + 1
'''
        generated, names, namespace = _exec_clean(source, {"record": record})
        function = namespace["f"]

        assert names
        assert events == ["default", "annotation", "return"]
        assert generated.count("record(") == 3
        assert function.__doc__ == "public documentation"
        assert function.__defaults__ == (1,)
        assert function.__annotations__ == {"x": int, "return": int}
        assert str(inspect.signature(function)) == "(x: int = 1) -> int"
        assert function() == 2

    def test_staticmethod_decorator_is_emitted_once(self) -> None:
        source = '''\
class C:
    @staticmethod
    def add(value: int = 1) -> int:
        """add one"""
        return value + 1
'''
        generated, names, namespace = _exec_clean(source)

        assert names
        assert generated.count("@staticmethod") == 1
        assert namespace["C"].add() == 2
        assert namespace["C"].add.__doc__ == "add one"
        assert str(inspect.signature(namespace["C"].add)) == "(value: int = 1) -> int"


class TestWrapperProtocols:
    def test_reserved_looking_parameter_names_do_not_collide_with_locals(self) -> None:
        source = """\
def add(*, _mutmut_args, _mutmut_kwargs):
    return _mutmut_args + _mutmut_kwargs + 1


class C:
    def method(_mutmut_args, *, _mutmut_kwargs):
        return _mutmut_args.base + _mutmut_kwargs + 1
"""
        _generated, names, namespace = _exec_clean(source)
        instance = namespace["C"]()
        instance.base = 10

        assert names
        assert namespace["add"](_mutmut_args=2, _mutmut_kwargs=3) == 6
        assert instance.method(_mutmut_kwargs=4) == 15

    def test_sync_generator_keeps_identity_and_send_protocol(self) -> None:
        source = """\
def gen():
    received = yield 1 + 1
    yield received
"""
        _generated, names, namespace = _exec_clean(source)
        function = namespace["gen"]

        assert names
        assert inspect.isgeneratorfunction(function)
        generator = function()
        assert next(generator) == 2
        assert generator.send(41) == 41

    def test_async_generator_is_conservatively_left_unmutated(self) -> None:
        source = """\
async def agen():
    received = yield 1 + 1
    yield received
"""
        _generated, names, namespace = _exec_clean(source)
        function = namespace["agen"]

        assert not any("agen" in name for name in names)
        assert inspect.isasyncgenfunction(function)

        async def drive() -> tuple[int, int]:
            generator = function()
            return await generator.asend(None), await generator.asend(41)

        assert asyncio.run(drive()) == (2, 41)

    def test_pep695_generic_function_is_conservatively_left_unmutated(self) -> None:
        source = """\
def type_parameter[T]():
    marker = 1 + 1
    return T
"""
        _generated, names, namespace = _exec_clean(source)
        function = namespace["type_parameter"]

        assert not any("type_parameter" in name for name in names)
        assert function() is function.__type_params__[0]


class TestRegexLiteralIntegration:
    def test_raw_and_non_raw_spellings_have_the_same_mutation_surface(self) -> None:
        ordinary = _regex_mutant_patterns(r're.fullmatch("\\d+", text)')
        raw = _regex_mutant_patterns(r're.fullmatch(r"\d+", text)')

        assert ordinary
        assert ordinary == raw

    def test_triple_quoted_pattern_has_the_same_mutation_surface(self) -> None:
        simple = _regex_mutant_patterns(r're.fullmatch(r"\d+", text)')
        triple = _regex_mutant_patterns(r'''re.fullmatch(r"""\d+""", text)''')

        assert triple == simple

    def test_quote_introducing_range_candidate_is_individually_serialized(self) -> None:
        expression = cst.parse_expression('re.fullmatch("[!-#]", text)')
        assert isinstance(expression, cst.Call)
        mutations = list(operator_regex(expression))
        patterns = {
            mutation.args[0].value.evaluated_value
            for mutation in mutations
            if isinstance(mutation.args[0].value, cst.SimpleString)
        }

        assert '["-#]' in patterns
        for mutation in mutations:
            rendered = cst.Module(body=[]).code_for_node(mutation)
            compile(rendered, "<regex-mutant>", "eval")

    def test_quote_range_does_not_discard_other_file_mutants(self) -> None:
        source = """\
import re


def matches(text):
    return re.fullmatch("[!-#]", text) is not None


def add_one(value):
    return value + 1
"""
        generated, names = mutate_file_contents("m.py", source)

        compile(generated, "m", "exec")
        assert any("x_matches__mutmut" in name for name in names)
        assert any("x_add_one__mutmut" in name for name in names)


class TestCommentOnlyPragmas:
    def test_incomplete_source_defers_to_the_cst_parser(self) -> None:
        source = "def broken(\n# pragma: no mutate start\n"

        assert pragma_no_mutate_lines(source) == set()

    def test_pragma_lookalikes_in_strings_are_ignored(self) -> None:
        source = """\
plain = "# pragma: no mutate start"
raw = r"# pragma: no mutate block"
formatted = f"# pragma: no mutate end {1}"
value = 1
"""
        assert pragma_no_mutate_lines(source) == set()

    def test_pragma_lookalikes_in_multiline_string_are_ignored(self) -> None:
        source = '''\
text = """# pragma: no mutate start
# pragma: no mutate block
# pragma: no mutate end
"""
value = 1
'''
        assert pragma_no_mutate_lines(source) == set()

    def test_real_comment_after_string_is_still_a_directive(self) -> None:
        source = 'marker = "# pragma: no mutate"  # pragma: no mutate\nvalue = 1\n'
        assert pragma_no_mutate_lines(source) == {1}


class TestRenderedMutantDeduplication:
    def test_cross_operator_duplicates_are_removed(self) -> None:
        source = """\
def f(value):
    if True:
        return 0
    return 1
"""
        generated, names = mutate_file_contents("m.py", source, active_profile=Profile.ADVANCED)
        module = cst.parse_module(generated)
        rendered: list[str] = []
        for statement in module.body:
            if isinstance(statement, cst.FunctionDef) and statement.name.value in names:
                normalized = statement.with_changes(name=cst.Name("candidate"))
                rendered.append(cst.Module(body=[]).code_for_node(normalized))

        assert len(names) == 7
        assert len(rendered) == len(names)
        assert len(set(rendered)) == len(rendered)

    def test_declaration_name_only_mutation_is_not_published(self) -> None:
        generated, names = mutate_file_contents("m.py", "def deepcopy():\n    pass\n")

        assert names == []
        assert "def deepcopy():" in generated
        assert "x_deepcopy__mutmut" not in generated

    def test_no_mutant_renders_like_the_original_implementation(self) -> None:
        generated, names = mutate_file_contents(
            "m.py", "def deepcopy(value):\n    return value + 1\n"
        )
        module = cst.parse_module(generated)
        implementations = {
            statement.name.value: statement
            for statement in module.body
            if isinstance(statement, cst.FunctionDef)
        }
        original = implementations["x_deepcopy__mutmut_orig"]
        original_rendering = cst.Module(body=[]).code_for_node(
            original.with_changes(name=cst.Name("candidate"))
        )

        assert names
        for name in names:
            mutant_rendering = cst.Module(body=[]).code_for_node(
                implementations[name].with_changes(name=cst.Name("candidate"))
            )
            assert mutant_rendering != original_rendering
