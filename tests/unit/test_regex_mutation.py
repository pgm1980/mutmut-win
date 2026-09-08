"""Tests for mutmut_win.regex_mutation — Regex pattern mutation engine."""

from __future__ import annotations

import re
import warnings

import pytest
from hypothesis import given
from hypothesis import strategies as st

from mutmut_win.regex_mutation import (
    MAX_MUTATIONS_PER_PATTERN,
    _class_members,
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

    def test_group_extension_question_not_a_quantifier(self) -> None:
        # the ? in (?=...), (?:...), (?<=...) is group syntax, not a quantifier
        assert _mutate_quantifiers(r"(?=bar)") == []
        assert _mutate_quantifiers(r"(?:ab)") == []
        assert _mutate_quantifiers(r"(?<=x)y") == []

    def test_quantifier_glyphs_inside_character_class_are_literals(self) -> None:
        assert _mutate_quantifiers(r"[?+*]") == []
        assert _mutate_quantifiers(r"[a{2}]") == []


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


def _mut_classes(src: str) -> list[str]:
    from mutmut_win.regex_mutation import _mutate_classes

    return _mutate_classes(src)


class TestMutateClasses:
    """#7-#10: character-CLASS mutations (negation toggle, child removal, range
    ±1, to-any). Span-based via _class_spans; #8/#9 parse the class body.
    """

    def test_negate_add(self) -> None:
        # #7: [abc] -> [^abc]
        assert r"[^abc]" in _mut_classes(r"[abc]")

    def test_negate_remove(self) -> None:
        # #7: [^abc] -> [abc]
        assert r"[abc]" in _mut_classes(r"[^abc]")

    def test_to_any(self) -> None:
        # #10: [abc] -> [\w\W]
        assert r"[\w\W]" in _mut_classes(r"[abc]")

    def test_child_removal(self) -> None:
        # #8: each member dropped in turn
        results = _mut_classes(r"[abc]")
        assert r"[bc]" in results
        assert r"[ac]" in results
        assert r"[ab]" in results

    def test_child_removal_keeps_negation(self) -> None:
        assert r"[^bc]" in _mut_classes(r"[^abc]")

    def test_child_removal_skipped_for_single_member(self) -> None:
        # [a] -> [] would be invalid; no child-removal mutant
        assert r"[]" not in _mut_classes(r"[a]")

    def test_child_removal_member_units(self) -> None:
        # \d is one member, a is another
        results = _mut_classes(r"[\da]")
        assert r"[a]" in results  # dropped \d
        assert r"[\d]" in results  # dropped a

    def test_range_lo_plus(self) -> None:
        # #9: [a-z] -> [b-z]
        assert r"[b-z]" in _mut_classes(r"[a-z]")

    def test_range_hi_minus(self) -> None:
        # #9: [a-z] -> [a-y]
        assert r"[a-y]" in _mut_classes(r"[a-z]")

    def test_range_keeps_negation(self) -> None:
        assert r"[^b-z]" in _mut_classes(r"[^a-z]")

    def test_literal_close_bracket_first_negation_still_works(self) -> None:
        # []a] : #7 still toggles ^; member-based #8/#9 are skipped (no crash)
        assert r"[^]a]" in _mut_classes(r"[]a]")

    def test_no_class(self) -> None:
        assert _mut_classes(r"abc") == []

    def test_negate_toggle_is_exact_first_result(self) -> None:
        # the #7 toggle is the first result; pin it exactly so the negation
        # detection (inner.startswith("^")) cannot be silently broken
        assert _mut_classes(r"[ab]")[0] == r"[^ab]"
        assert _mut_classes(r"[^ab]")[0] == r"[ab]"

    def test_child_removal_keeps_negation_marker(self) -> None:
        # #8 in a negated class keeps the ^ mark; dropping it would emit [bc],
        # which is never a legit result here -> pins the mark
        results = _mut_classes(r"[^abc]")
        assert r"[^bc]" in results
        assert r"[bc]" not in results

    def test_range_keeps_negation_marker(self) -> None:
        # #9 in a negated class keeps the ^ mark
        results = _mut_classes(r"[^a-z]")
        assert r"[^b-z]" in results
        assert r"[b-z]" not in results

    def test_literal_bracket_skips_member_mutations(self) -> None:
        # []a] : body starts with a literal ] -> only #7 toggle and #10 to-any,
        # no member-based #8/#9 (pins the body.startswith("]") guard exactly)
        assert _mut_classes(r"[]a]") == [r"[^]a]", r"[\w\W]"]

    def test_literal_bracket_does_not_stop_later_class(self) -> None:
        # break vs continue: a literal-] class must not stop a later class
        results = _mut_classes(r"[]a][bc]")
        assert any("[^bc]" in r for r in results)


class TestClassMembers:
    """Class-body member parser feeding #8 child-removal. Exact (start, end)
    units so any index arithmetic error in the scan is caught.
    """

    def test_literals(self) -> None:
        assert _class_members("abc") == [(0, 1), (1, 2), (2, 3)]

    def test_single_range(self) -> None:
        assert _class_members("a-z") == [(0, 3)]

    def test_range_then_literal(self) -> None:
        assert _class_members("a-z0") == [(0, 3), (3, 4)]

    def test_literal_then_range(self) -> None:
        assert _class_members("0a-z") == [(0, 1), (1, 4)]

    def test_two_ranges(self) -> None:
        assert _class_members("a-z0-9") == [(0, 3), (3, 6)]

    def test_escaped_unit(self) -> None:
        # \d is one 2-char member, a is another
        assert _class_members(r"\da") == [(0, 2), (2, 3)]

    def test_escaped_range_end(self) -> None:
        # a-\d is a single range whose upper end is the escaped \d
        assert _class_members(r"a-\d") == [(0, 4)]

    def test_dash_at_end_is_literal(self) -> None:
        # a trailing '-' has no range partner -> two literals
        assert _class_members("a-") == [(0, 1), (1, 2)]

    def test_dash_at_start_is_literal(self) -> None:
        assert _class_members("-a") == [(0, 1), (1, 2)]

    def test_empty(self) -> None:
        assert _class_members("") == []

    def test_lone_backslash_is_one_member(self) -> None:
        # a trailing/lone backslash has no next char -> a 1-char member
        # (kills the i+1 boundary mutants that would over-consume)
        assert _class_members("\\") == [(0, 1)]

    def test_escaped_unit_at_end(self) -> None:
        # \d at the very end is still one 2-char member (i+1 == n boundary)
        assert _class_members("\\d") == [(0, 2)]

    def test_range_with_trailing_backslash_end(self) -> None:
        # a-\ : the range upper end is a lone backslash (1 char, no pair)
        assert _class_members("a-\\") == [(0, 3)]


def _mut_groups(src: str) -> list[str]:
    from mutmut_win.regex_mutation import _mutate_groups

    return _mutate_groups(src)


class TestMutateGroups:
    """#14 look-around flip and +15 group->non-capturing. Class-aware (a ``(``
    inside ``[...]`` is a literal) and escape-aware (``\\(`` is a literal paren).
    """

    def test_lookahead_positive_to_negative(self) -> None:
        assert r"foo(?!bar)" in _mut_groups(r"foo(?=bar)")

    def test_lookahead_negative_to_positive(self) -> None:
        assert r"foo(?=bar)" in _mut_groups(r"foo(?!bar)")

    def test_lookbehind_positive_to_negative(self) -> None:
        assert r"(?<!a)b" in _mut_groups(r"(?<=a)b")

    def test_lookbehind_negative_to_positive(self) -> None:
        assert r"(?<=a)b" in _mut_groups(r"(?<!a)b")

    def test_capturing_to_non_capturing(self) -> None:
        # +15: (abc) -> (?:abc)
        assert r"(?:abc)" in _mut_groups(r"(abc)")

    def test_non_capturing_not_touched(self) -> None:
        # (?:...) is already non-capturing and not a look-around
        assert _mut_groups(r"(?:abc)") == []

    def test_lookaround_not_made_non_capturing(self) -> None:
        # (?=...) only flips; it never gets ?: inserted
        assert all("(?:" not in r for r in _mut_groups(r"(?=a)"))

    def test_paren_in_class_is_literal(self) -> None:
        # [(] is a literal ( inside a class, not a group opener
        assert _mut_groups(r"[(]abc") == []

    def test_escaped_paren_not_a_group(self) -> None:
        assert _mut_groups(r"\(abc\)") == []

    def test_no_group(self) -> None:
        assert _mut_groups(r"abc") == []

    def test_trailing_backslash_no_crash(self) -> None:
        # trailing backslash: no group, no IndexError (kills `while i != n`)
        assert _mut_groups("a\\") == []

    def test_escaped_paren_then_real_group(self) -> None:
        # \( is escaped; the real (a) after it must still get #15
        # (kills the escaped-skip i+=2 arithmetic and continue->break)
        assert r"\((?:a)" in _mut_groups(r"\((a)")

    def test_capturing_near_end(self) -> None:
        # a(b : the ( opens a group even when its content is the last char
        assert r"a(?:b" in _mut_groups(r"a(b")


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

    def test_ambiguous_warning_is_rechecked_even_after_re_cache_hit(self) -> None:
        re.purge()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", FutureWarning)
            re.compile("[[]")

        assert _is_valid_regex("[[]") is False


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
