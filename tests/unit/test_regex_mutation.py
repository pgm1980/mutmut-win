"""Tests for mutmut_win.regex_mutation — Regex pattern mutation engine."""

from __future__ import annotations

import re

import pytest
from hypothesis import given
from hypothesis import strategies as st

from mutmut_win.regex_mutation import (
    MAX_MUTATIONS_PER_PATTERN,
    _class_spans,
    _in_class,
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

    def test_star_removed(self) -> None:
        # #2 removal now applies to * too (in addition to the *->+ swap)
        assert r"\d" in _mutate_quantifiers(r"\d*")

    def test_brace_removed(self) -> None:
        # #2 removal applies to {n,m} as well
        assert r"\d" in _mutate_quantifiers(r"\d{2,4}")

    def test_plus_to_star_swap(self) -> None:
        # require-at-least-one -> require-zero-or-more
        assert r"\d*" in _mutate_quantifiers(r"\d+")

    def test_reluctant_plus(self) -> None:
        # #6 greedy -> lazy
        assert r"\d+?" in _mutate_quantifiers(r"\d+")

    def test_reluctant_star_question_range(self) -> None:
        assert r"\d*?" in _mutate_quantifiers(r"\d*")
        assert r"\d??" in _mutate_quantifiers(r"\d?")
        assert r"\d{2,4}?" in _mutate_quantifiers(r"\d{2,4}")

    def test_reluctant_skips_exact_count(self) -> None:
        # {n}? is legal but semantically identical -> not generated
        assert r"\d{3}?" not in _mutate_quantifiers(r"\d{3}")

    def test_reluctant_skips_already_lazy(self) -> None:
        # \d+? must not become \d+?? (invalid)
        assert r"\d+??" not in _mutate_quantifiers(r"\d+?")

    def test_lazy_quantifier_removed_as_unit(self) -> None:
        # the whole lazy quantifier is removed together
        assert r"\d" in _mutate_quantifiers(r"\d+?")

    def test_short_to_range_question(self) -> None:
        # #5 ? ({0,1}) -> {1} (exactly one, a real tightening)
        assert r"\d{1}" in _mutate_quantifiers(r"\d?")

    def test_short_to_range_plus(self) -> None:
        # #5 + ({1,}) -> {2,} (at least two)
        assert r"\d{2,}" in _mutate_quantifiers(r"\d+")

    def test_range_lo_minus(self) -> None:
        # #3 lo-1
        assert r"\d{1,5}" in _mutate_quantifiers(r"\d{2,5}")

    def test_range_hi_plus(self) -> None:
        # #3 hi+1
        assert r"\d{2,6}" in _mutate_quantifiers(r"\d{2,5}")

    def test_open_range_lo_minus(self) -> None:
        # #4 {n,} lo-1
        assert r"\d{1,}" in _mutate_quantifiers(r"\d{2,}")

    def test_brace_lo_minus_guarded_against_negative(self) -> None:
        # {0,5}: lo-1 would be {-1,5} — the lo>0 guard must suppress it
        assert r"\d{-1,5}" not in _mutate_quantifiers(r"\d{0,5}")
        # {1,5}: lo-1 = {0,5} IS generated
        assert r"\d{0,5}" in _mutate_quantifiers(r"\d{1,5}")

    def test_exact_count_minus_guarded_against_zero(self) -> None:
        # {1}: n-1 would be {0} — the n>1 guard must suppress it
        assert r"\d{0}" not in _mutate_quantifiers(r"\d{1}")
        # {2}: n-1 = {1} IS generated
        assert r"\d{1}" in _mutate_quantifiers(r"\d{2}")

    def test_lazy_input_base_swap(self) -> None:
        # group(1) is the base even for lazy input: \d+? still swaps + -> *
        assert r"\d*" in _mutate_quantifiers(r"\d+?")


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

    def test_nullify_digit(self) -> None:
        # #12 \d -> d (drop the backslash -> a literal 'd')
        assert r"d" in _mutate_char_classes(r"\d")

    def test_nullify_in_pattern(self) -> None:
        assert r"ad+" in _mutate_char_classes(r"a\d+")

    def test_to_any_digit(self) -> None:
        # #13 \d -> [\d\D] (matches any character)
        assert r"[\d\D]" in _mutate_char_classes(r"\d")

    def test_to_any_skipped_inside_class(self) -> None:
        # \d inside [...] must NOT become a nested class [[\d\D]]
        results = _mutate_char_classes(r"[\d]")
        assert not any("[[" in r for r in results)

    def test_in_class_negation_and_nullify_still_apply(self) -> None:
        # inside a class #11 (\D) and #12 (d) still apply; only #13 is skipped
        results = _mutate_char_classes(r"[\d]")
        assert r"[\D]" in results
        assert r"[d]" in results

    def test_negation_all_occurrences(self) -> None:
        # every \d gets its own negation mutant, not just the first
        results = _mutate_char_classes(r"\d-\d")
        assert r"\D-\d" in results
        assert r"\d-\D" in results

    def test_escaped_backslash_not_shorthand(self) -> None:
        # \\d is a literal backslash + d, not a \d shorthand
        assert _mutate_char_classes(r"\\d") == []

    def test_trailing_backslash_no_shorthand(self) -> None:
        # a trailing backslash has no next char -> no shorthand, no IndexError
        # (kills `while i != n` and the i+1 boundary arithmetic)
        assert _mutate_char_classes("a\\") == []


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

    def test_backslash_a_removed(self) -> None:
        # \A start-of-string anchor
        assert r"foo" in _mutate_anchors(r"\Afoo")

    def test_backslash_z_removed(self) -> None:
        # \Z end-of-string anchor
        assert r"foo" in _mutate_anchors(r"foo\Z")

    def test_word_boundary_removed(self) -> None:
        results = _mutate_anchors(r"\bfoo\b")
        assert r"foo\b" in results  # leading \b removed
        assert r"\bfoo" in results  # trailing \b removed

    def test_non_word_boundary_removed(self) -> None:
        assert r"foo" in _mutate_anchors(r"\Bfoo")

    def test_backspace_in_class_not_an_anchor(self) -> None:
        # [\b] is a backspace literal, not a word boundary — no anchor mutation
        assert _mutate_anchors(r"[\b]x") == []

    def test_anchor_exact_set(self) -> None:
        # exact removal set + order kills index arithmetic in the scan
        assert _mutate_anchors(r"\Afoo\Z") == [r"foo\Z", r"\Afoo"]

    def test_multiple_escaped_anchors_exact(self) -> None:
        # repeated escape-skip path (kills the i+=2 arithmetic / infinite loop)
        assert _mutate_anchors(r"\A\Bx") == [r"\Bx", r"\Ax"]

    def test_only_real_escape_anchors_match(self) -> None:
        # exactly \A \Z \b \B are anchors; \X must not be (pins the "AZbB" set)
        assert _mutate_anchors(r"\Xq") == []

    def test_plain_letter_is_not_an_anchor(self) -> None:
        # 'X' is a literal; the "^$" membership must be exact (kills the XX pad)
        assert _mutate_anchors(r"Xfoo") == []

    def test_caret_mid_pattern_is_scanned(self) -> None:
        # the fallthrough index must reach a '^' that is not at position 0
        assert _mutate_anchors(r"ab^c") == ["abc"]

    def test_trailing_backslash_left_alone(self) -> None:
        # "" is a substring of "AZbB"; the frozenset check must reject the
        # missing next char so a trailing backslash is not treated as an anchor
        assert _mutate_anchors("a\\") == []


class TestClassSpans:
    """Structural tokenizer foundation: locate unescaped [...] class spans so
    context-sensitive sub-mutators (anchors, shorthands) never fire inside a
    character class. Each span is (start_of_'[', index_past_']').
    """

    def test_simple_class(self) -> None:
        assert _class_spans(r"a[bc]d") == [(1, 5)]

    def test_negated_class(self) -> None:
        assert _class_spans(r"[^a-z]") == [(0, 6)]

    def test_literal_close_bracket_first(self) -> None:
        # a ] right after [ (or [^) is a literal member, not the class end
        assert _class_spans(r"[]a]") == [(0, 4)]
        assert _class_spans(r"[^]a]") == [(0, 5)]

    def test_escaped_bracket_not_class(self) -> None:
        assert _class_spans(r"\[abc\]") == []

    def test_escaped_close_inside_class(self) -> None:
        # \] inside a class does not close it
        assert _class_spans(r"[a\]b]") == [(0, 6)]

    def test_two_classes(self) -> None:
        assert _class_spans(r"[ab]x[cd]") == [(0, 4), (5, 9)]

    def test_no_class(self) -> None:
        assert _class_spans(r"\d+foo") == []

    def test_escape_before_class(self) -> None:
        # the escape-skip index must land exactly on the '['
        assert _class_spans(r"\.[ab]") == [(2, 6)]

    def test_multiple_escapes_then_class(self) -> None:
        # exercises the escape-skip index repeatedly (kills i+=2 arithmetic)
        assert _class_spans(r"\d\w[ab]") == [(4, 8)]

    def test_long_class_content(self) -> None:
        # exercises the inner content-scan index (kills j+=1 / j+=2 arithmetic)
        assert _class_spans(r"[abcdef]") == [(0, 8)]

    def test_text_then_class(self) -> None:
        # exercises the fallthrough index (kills i+=1 arithmetic)
        assert _class_spans(r"xx[ab]y") == [(2, 6)]

    def test_unterminated_class_runs_to_end(self) -> None:
        # no closing ] — the span extends to end of string (kills min(j+1, n))
        assert _class_spans(r"a[bc") == [(1, 4)]

    def test_trailing_backslash(self) -> None:
        # an escape with no next char must not run the index past the end
        # (kills `while i != n`, which would IndexError here)
        assert _class_spans("a\\") == []

    def test_spans_are_well_formed(self) -> None:
        # every reported span must bracket a real '[' .. ']' pair
        patterns = (
            r"[abc]",
            r"a[bc]d[ef]",
            r"[a\]b]",
            r"[]x]",
            r"[^]y]",
            r"\[no[yes]",
            r"[0-9][a-z]",
        )
        for p in patterns:
            for s, e in _class_spans(p):
                assert p[s] == "[", f"{p!r} span {(s, e)} start not ["
                assert p[e - 1] == "]", f"{p!r} span {(s, e)} end not ]"


class TestInClass:
    """`_in_class` is a half-open membership test over ``[start, end)`` spans."""

    def test_membership_boundaries(self) -> None:
        spans = [(2, 5)]  # covers indices 2, 3, 4
        assert _in_class(2, spans) is True  # start is inside (kills <= -> <)
        assert _in_class(4, spans) is True
        assert _in_class(5, spans) is False  # end is exclusive (kills < -> <=)
        assert _in_class(6, spans) is False  # beyond end (kills < -> !=)
        assert _in_class(1, spans) is False  # before start

    def test_no_spans(self) -> None:
        assert _in_class(3, []) is False

    def test_multiple_spans(self) -> None:
        spans = [(0, 2), (5, 8)]
        assert _in_class(1, spans) is True
        assert _in_class(3, spans) is False
        assert _in_class(6, spans) is True


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
