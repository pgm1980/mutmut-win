"""Tests for mutmut_win.regex_mutation — Regex pattern mutation engine."""

from __future__ import annotations

import re

import pytest
from hypothesis import given
from hypothesis import strategies as st

from mutmut_win.regex_mutation import (
    MAX_MUTATIONS_PER_PATTERN,
    _is_valid_regex,
    _mutate_anchors,
    _mutate_char_classes,
    _mutate_quantifiers,
    mutate_regex_pattern,
)


class TestMutateQuantifiers:
    def test_plus_removed(self) -> None:
        results = _mutate_quantifiers(r"\d+")
        assert r"\d" in results

    def test_star_to_plus(self) -> None:
        results = _mutate_quantifiers(r"\d*")
        assert r"\d+" in results

    def test_question_mark_removed(self) -> None:
        results = _mutate_quantifiers(r"\d?")
        assert r"\d" in results

    def test_exact_count_plus_minus(self) -> None:
        results = _mutate_quantifiers(r"\d{3}")
        assert r"\d{2}" in results
        assert r"\d{4}" in results

    def test_exact_count_one_no_zero(self) -> None:
        results = _mutate_quantifiers(r"\d{1}")
        # {0} would be pointless but {2} should be there
        assert r"\d{2}" in results

    def test_range_quantifier(self) -> None:
        results = _mutate_quantifiers(r"\d{2,5}")
        assert r"\d{3,5}" in results
        assert r"\d{2,4}" in results

    def test_open_range(self) -> None:
        results = _mutate_quantifiers(r"\d{2,}")
        assert r"\d{3,}" in results

    def test_no_quantifiers(self) -> None:
        results = _mutate_quantifiers(r"abc")
        assert results == []

    def test_escaped_plus_not_mutated(self) -> None:
        results = _mutate_quantifiers(r"a\+b")
        # \+ is an escaped literal plus — should NOT be mutated
        assert results == []


class TestMutateCharClasses:
    def test_digit_to_non_digit(self) -> None:
        results = _mutate_char_classes(r"\d+")
        assert r"\D+" in results

    def test_word_to_non_word(self) -> None:
        results = _mutate_char_classes(r"\w+")
        assert r"\W+" in results

    def test_space_to_non_space(self) -> None:
        results = _mutate_char_classes(r"\s+")
        assert r"\S+" in results

    def test_non_digit_to_digit(self) -> None:
        results = _mutate_char_classes(r"\D")
        assert r"\d" in results

    def test_no_char_classes(self) -> None:
        results = _mutate_char_classes(r"abc")
        assert results == []

    def test_multiple_classes_first_only(self) -> None:
        results = _mutate_char_classes(r"\d\w")
        # Should find at least \d→\D and \w→\W
        assert any(r"\D" in r for r in results)
        assert any(r"\W" in r for r in results)


class TestMutateAnchors:
    def test_caret_removed(self) -> None:
        results = _mutate_anchors(r"^test")
        assert "test" in results

    def test_dollar_removed(self) -> None:
        results = _mutate_anchors(r"test$")
        assert "test" in results

    def test_both_anchors(self) -> None:
        results = _mutate_anchors(r"^test$")
        assert "test$" in results  # ^ removed
        assert "^test" in results  # $ removed

    def test_no_anchors(self) -> None:
        results = _mutate_anchors(r"test")
        assert results == []

    def test_escaped_dollar_not_removed(self) -> None:
        results = _mutate_anchors(r"test\$")
        # \$ is an escaped literal — should NOT be removed
        assert results == []

    def test_caret_in_char_class_not_removed(self) -> None:
        # ^[a-z] — the ^ IS a start anchor here
        results = _mutate_anchors(r"^[a-z]")
        assert "[a-z]" in results


class TestMutateRegexPattern:
    def test_simple_digit_pattern(self) -> None:
        results = mutate_regex_pattern(r"\d+")
        assert len(results) > 0
        # Should include quantifier removal and char class swap
        assert r"\d" in results or r"\D+" in results

    def test_empty_pattern(self) -> None:
        results = mutate_regex_pattern(r"")
        assert results == []

    def test_complex_pattern(self) -> None:
        results = mutate_regex_pattern(r"^\d{3}-\d{4}$")
        assert len(results) > 0
        # All results must be valid regex
        for r in results:
            re.compile(r)  # should not raise

    def test_max_mutations_enforced(self) -> None:
        # A pattern with many quantifiers should still be capped
        results = mutate_regex_pattern(r"\d+\w+\s+\d{3,5}")
        assert len(results) <= MAX_MUTATIONS_PER_PATTERN

    def test_no_op_mutations_filtered(self) -> None:
        results = mutate_regex_pattern(r"abc")
        # "abc" has no quantifiers, no char classes, no anchors
        assert results == []

    def test_all_results_are_valid_regex(self) -> None:
        patterns = [
            r"\d+",
            r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}$",
            r"\w{3,10}",
            r"^\s*#",
        ]
        for pattern in patterns:
            for mutated in mutate_regex_pattern(pattern):
                try:
                    re.compile(mutated)
                except re.error:
                    pytest.fail(f"Invalid regex generated: {mutated!r} from {pattern!r}")

    def test_results_differ_from_original(self) -> None:
        pattern = r"\d+"
        for mutated in mutate_regex_pattern(pattern):
            assert mutated != pattern


class TestIsValidRegex:
    def test_valid(self) -> None:
        assert _is_valid_regex(r"\d+") is True

    def test_invalid(self) -> None:
        assert _is_valid_regex(r"[") is False

    def test_empty_is_valid(self) -> None:
        assert _is_valid_regex(r"") is True


class TestHypothesisProperties:
    @given(st.from_regex(r"[a-zA-Z0-9\\dDwWsS+*?.^${}()\[\]|]+", fullmatch=True))
    def test_all_mutations_are_valid_or_filtered(self, pattern: str) -> None:
        """Property: mutate_regex_pattern never returns an invalid regex."""
        results = mutate_regex_pattern(pattern)
        for mutated in results:
            assert _is_valid_regex(mutated), f"Invalid regex: {mutated!r} from {pattern!r}"

    @given(st.from_regex(r"[a-zA-Z0-9\\dDwWsS+*?.^${}()\[\]|]+", fullmatch=True))
    def test_max_mutations_never_exceeded(self, pattern: str) -> None:
        """Property: never more than MAX_MUTATIONS_PER_PATTERN results."""
        results = mutate_regex_pattern(pattern)
        assert len(results) <= MAX_MUTATIONS_PER_PATTERN
