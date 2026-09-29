"""Tests for the pattern-local syntax gate in match statements (M-048 / issue #168).

Unary mutations produce invalid POSITIVE signs inside match patterns —
``case +1`` and ``case --1`` are SyntaxErrors even though ``+1``/``--1`` are
perfectly fine expressions. One such mutant made the file-wide safety net
drop every mutant of the file with a SyntaxWarning. The visitor now probes
each candidate inside its enclosing pattern and silently discards
syntactically invalid ones (precedent: operator_regex's serialisation gate).
"""

from __future__ import annotations

import ast
import warnings

from hypothesis import given
from hypothesis import strategies as st

from mutmut_win.constants import Profile
from mutmut_win.mutation import mutate_file_contents


def _mutate(source: str, active_profile: Profile = Profile.ADVANCED) -> tuple[str, list[str]]:
    code, names = mutate_file_contents("m.py", source, active_profile=active_profile)
    ast.parse(code)  # hard gate: the generated file must compile
    return code, list(names)


class TestNegativeLiteralCases:
    def test_case_minus_one(self) -> None:
        source = (
            "def f(x):\n"
            "    match x:\n"
            "        case -1:\n"
            "            return 1\n"
            "        case _:\n"
            "            return 0\n"
        )
        code, names = _mutate(source)
        assert "case -2:" in code  # operator_number still mutates the literal
        assert "case +1:" not in code  # swap_op: invalid positive sign
        assert "case --1:" not in code  # CRCR -orig: double minus
        assert names

    def test_mapping_key_with_negative_value(self) -> None:
        source = (
            "def f(x):\n"
            "    match x:\n"
            "        case {-1: _}:\n"
            "            return 1\n"
            "        case _:\n"
            "            return 0\n"
        )
        code, _names = _mutate(source)
        assert "case +1:" not in code
        assert "case --1:" not in code

    def test_complex_literal_case(self) -> None:
        source = (
            "def f(x):\n"
            "    match x:\n"
            "        case -1+2j:\n"
            "            return 1\n"
            "        case _:\n"
            "            return 0\n"
        )
        code, _names = _mutate(source)
        assert "case +1+2j:" not in code
        assert "case --1+2j:" not in code


class TestValidPatternMutantsPreserved:
    def test_int_case_still_incremented(self) -> None:
        source = (
            "def f(x):\n"
            "    match x:\n"
            "        case 1:\n"
            "            return 1\n"
            "        case _:\n"
            "            return 0\n"
        )
        code, names = _mutate(source)
        assert "case 2:" in code
        assert names

    def test_bool_case_still_swapped(self) -> None:
        source = (
            "def f(x):\n"
            "    match x:\n"
            "        case True:\n"
            "            return 1\n"
            "        case _:\n"
            "            return 0\n"
        )
        code, _names = _mutate(source)
        assert "case False:" in code

    def test_string_case_still_xx_mutated(self) -> None:
        source = (
            "def f(x):\n"
            "    match x:\n"
            '        case "abc":\n'
            "            return 1\n"
            "        case _:\n"
            "            return 0\n"
        )
        code, _names = _mutate(source)
        assert 'case "XXabcXX":' in code

    def test_class_pattern_attribute_still_mutated(self) -> None:
        source = (
            "def f(x):\n"
            "    match x:\n"
            "        case Point(x=-1):\n"
            "            return 1\n"
            "        case _:\n"
            "            return 0\n"
        )
        code, _names = _mutate(source)
        assert "case Point(x=+1):" not in code
        assert "case Point(x=-2):" in code

    def test_parenthesized_case_value_keeps_parens(self) -> None:
        # M-046 interplay: libcst keeps the parens on the Integer, and the
        # gate accepts '(-1)' as a valid pattern.
        source = (
            "def f(x):\n"
            "    match x:\n"
            "        case (1):\n"
            "            return 1\n"
            "        case _:\n"
            "            return 0\n"
        )
        code, _names = _mutate(source)
        assert "case (-1):" in code


class TestNoWarningLeak:
    def test_invalid_escape_string_pattern_emits_no_syntax_warning(self) -> None:
        # A string pattern with an invalid escape ('\d') triggers a
        # SyntaxWarning from the ast.parse machinery when the gate probes
        # candidates. create_mutants_for_file records every warning
        # ('always') and forwards it to the user, so the gate must suppress
        # SyntaxWarning locally. Scope: the generation call itself — the
        # compile check of the generated source happens outside the
        # recording block because the USER's invalid escape legitimately
        # warns there (pre-existing file-wide-net behaviour).
        source = (
            "def f(x):\n"
            "    match x:\n"
            '        case "' + "\\" + 'd\\x4A":\n'
            "            return 1\n"
            "        case _:\n"
            "            return 0\n"
        )
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            code, _names = mutate_file_contents("m.py", source)
        assert not [w for w in caught if issubclass(w.category, SyntaxWarning)]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)
            ast.parse(code)


class TestProfileAllMappingKeys:
    def test_aod_complex_mapping_key_stays_parseable(self) -> None:
        # operator_aod (Profile.ALL) on '{-1+2j: _}' yields '{(-1): _}',
        # an invalid mapping key — the gate drops that candidate instead of
        # sacrificing the whole file.
        source = (
            "def f(x):\n"
            "    match x:\n"
            "        case {-1+2j: _}:\n"
            "            return 1\n"
            "        case _:\n"
            "            return 0\n"
        )
        code, _names = _mutate(source, active_profile=Profile.ALL)
        assert "case {(-1): _}:" not in code

    def test_aod_int_mapping_key_survives(self) -> None:
        source = (
            "def f(x):\n"
            "    match x:\n"
            "        case {1+2j: _}:\n"
            "            return 1\n"
            "        case _:\n"
            "            return 0\n"
        )
        code, names = _mutate(source, active_profile=Profile.ALL)
        assert "case {1: _}:" in code
        assert names


class TestPatternProperty:
    @given(
        n=st.integers(min_value=0, max_value=10**6),
        sign=st.sampled_from(["", "-"]),
        shape=st.sampled_from(["{v}", "[{v}, _]", "{{{v}: _}}", "{v}+2j"]),
    )
    def test_generated_code_always_parses_and_mutates(self, n: int, sign: str, shape: str) -> None:
        value = sign + str(n)
        source = (
            "def f(x):\n"
            "    match x:\n"
            "        case " + shape.format(v=value) + ":\n"
            "            return 1\n"
            "        case _:\n"
            "            return 0\n"
        )
        _code, names = _mutate(source)
        assert names
