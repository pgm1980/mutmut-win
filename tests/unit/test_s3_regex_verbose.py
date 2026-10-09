"""Semantic controls for global and scoped verbose regex comments."""

from __future__ import annotations

import re

import libcst as cst
import pytest
from hypothesis import given
from hypothesis import strategies as st

from mutmut_win.node_mutation import operator_regex
from mutmut_win.regex_mutation import mutate_regex_pattern


def _operator_patterns(pattern: str, flags: str = "") -> list[str]:
    call = cst.parse_expression(f"re.compile({pattern!r}{flags})")
    assert isinstance(call, cst.Call)
    patterns: list[str] = []
    for candidate in operator_regex(call):
        literal = candidate.args[0].value
        assert isinstance(literal, cst.SimpleString)
        value = literal.evaluated_value
        assert isinstance(value, str)
        patterns.append(value)
    return patterns


@pytest.mark.parametrize("prefix", ["(?x)", "(?ix)", "(?xi)", "(?mx)", "(?x:"])
@pytest.mark.parametrize("route", ["direct", "operator"])
def test_comment_only_patterns_have_no_regex_mutants(prefix: str, route: str) -> None:
    """All operator-bearing tokens in this fixture are ignored comment text."""
    pattern = prefix + "a #\\d+\n b" + (")" if prefix.endswith(":") else "")
    assert re.fullmatch(pattern, "ab") is not None
    candidates = mutate_regex_pattern(pattern) if route == "direct" else _operator_patterns(pattern)
    print(prefix, route, candidates)
    assert candidates == []


@pytest.mark.parametrize(
    ("pattern", "flags", "protected"),
    [
        ("(?x:a # [ ( \\d+\n b)\\w+", 0, "# [ ( \\d+\n"),
        ("(?x)a(?-x:#\\d+) # \\w+\n b", 0, "# \\w+\n"),
        ("a(?-x:#\\d+) # \\w+\n b", re.VERBOSE, "# \\w+\n"),
        ("(?x:a(?-x:b(?x:c #\\d+\n d)e)f)\\w+", 0, "#\\d+\n"),
    ],
)
def test_scoped_flags_keep_comments_and_preserve_real_mutation_surface(
    pattern: str, flags: int, protected: str
) -> None:
    """Nested scope restoration protects comments without erasing real tokens."""
    re.compile(pattern, flags)
    candidates = mutate_regex_pattern(pattern, flags)
    assert candidates
    assert all(protected in candidate for candidate in candidates), candidates
    for candidate in candidates:
        re.compile(candidate, flags)


@pytest.mark.parametrize("pattern", [r"(?x:[#]\d+)", r"(?x:\#\d+)", r"(?x:a)(?-x:#\d+)"])
def test_literal_hashes_keep_distinguishable_mutations(pattern: str) -> None:
    """Class, escaped and disabled-x hashes remain literal regex syntax."""
    candidates = mutate_regex_pattern(pattern)
    assert candidates
    samples = ("#1", "#11", "a#1", "a#11", "a#", "", "#x")
    original = tuple(bool(re.fullmatch(pattern, sample)) for sample in samples)
    assert any(
        tuple(bool(re.fullmatch(candidate, sample)) for sample in samples) != original
        for candidate in candidates
    )


@given(st.text(alphabet="abc[]()?#\\d+*{}", max_size=30))
def test_verbose_comment_payload_cannot_create_mutation_sites(payload: str) -> None:
    """Arbitrary single-line comment syntax is inert in a scoped x group."""
    # A fixed suffix prevents a trailing payload backslash from escaping the
    # newline and making the source pattern itself an unterminated group.
    pattern = f"(?x:a # {payload} end\n b)"
    assert re.fullmatch(pattern, "ab") is not None
    assert mutate_regex_pattern(pattern) == []
