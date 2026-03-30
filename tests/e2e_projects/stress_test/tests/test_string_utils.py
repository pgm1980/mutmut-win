"""Tests for string_utils — ~70% well covered."""

from __future__ import annotations

import pytest

from stress_lib.string_utils import (
    normalize_whitespace,
    truncate,
    pad_center,
    count_vowels,
    reverse_words,
    camel_to_snake,
    slug,
    remove_prefix_suffix,
    wrap_text,
    is_palindrome,
    count_occurrences,
    first_non_repeating,
    title_case,
    lpad,
    rpad,
    split_at,
    replace_all,
    interleave,
)


class TestNormalizeWhitespace:
    def test_multiple_spaces(self) -> None:
        assert normalize_whitespace("hello   world") == "hello world"

    def test_leading_trailing(self) -> None:
        assert normalize_whitespace("  hello  ") == "hello"

    def test_tabs_and_newlines(self) -> None:
        assert normalize_whitespace("a\t\nb") == "a b"

    def test_already_normal(self) -> None:
        assert normalize_whitespace("hello world") == "hello world"


class TestTruncate:
    def test_short_string_unchanged(self) -> None:
        assert truncate("hello", 10) == "hello"

    def test_exact_length(self) -> None:
        assert truncate("hello", 5) == "hello"

    def test_truncated(self) -> None:
        assert truncate("hello world", 8) == "hello..."

    def test_custom_suffix(self) -> None:
        # max_length=7, suffix="~" -> 6 chars of text + "~" = "hello ~"
        assert truncate("hello world", 7, "~") == "hello ~"

    def test_zero_length(self) -> None:
        # max_length=0 <= len("..."), so return suffix[:0] = ""
        assert truncate("hello", 0, "...") == ""

    def test_negative_raises(self) -> None:
        with pytest.raises(ValueError):
            truncate("hello", -1)


class TestPadCenter:
    def test_basic(self) -> None:
        assert pad_center("hi", 6) == "  hi  "

    def test_custom_fill(self) -> None:
        assert pad_center("hi", 6, "*") == "**hi**"

    def test_no_padding_needed(self) -> None:
        assert pad_center("hello", 3) == "hello"

    def test_invalid_fillchar(self) -> None:
        with pytest.raises(ValueError):
            pad_center("hi", 6, "ab")


class TestCountVowels:
    def test_basic(self) -> None:
        assert count_vowels("hello") == 2

    def test_case_insensitive(self) -> None:
        assert count_vowels("AEIOU") == 5

    def test_no_vowels(self) -> None:
        assert count_vowels("bcdfg") == 0

    def test_empty(self) -> None:
        assert count_vowels("") == 0


class TestReverseWords:
    def test_basic(self) -> None:
        assert reverse_words("hello world") == "world hello"

    def test_three_words(self) -> None:
        assert reverse_words("one two three") == "three two one"

    def test_single_word(self) -> None:
        assert reverse_words("only") == "only"

    def test_empty(self) -> None:
        assert reverse_words("") == ""


class TestCamelToSnake:
    def test_basic(self) -> None:
        assert camel_to_snake("CamelCase") == "camel_case"

    def test_already_lower(self) -> None:
        assert camel_to_snake("already") == "already"

    def test_multiple_words(self) -> None:
        assert camel_to_snake("MyVariableName") == "my_variable_name"

    def test_acronym(self) -> None:
        # regex-based camel_to_snake treats leading runs as a group
        assert camel_to_snake("HTTPSRequest") == "https_request"


class TestSlug:
    def test_basic(self) -> None:
        assert slug("Hello World") == "hello-world"

    def test_special_chars(self) -> None:
        assert slug("Hello, World!") == "hello-world"

    def test_multiple_spaces(self) -> None:
        assert slug("hello   world") == "hello-world"

    def test_leading_trailing_hyphen(self) -> None:
        result = slug("  hello  ")
        assert not result.startswith("-")
        assert not result.endswith("-")


class TestRemovePrefixSuffix:
    def test_both_present(self) -> None:
        assert remove_prefix_suffix("__hello__", "__", "__") == "hello"

    def test_prefix_only(self) -> None:
        assert remove_prefix_suffix("__hello", "__", "__") == "hello"

    def test_suffix_only(self) -> None:
        assert remove_prefix_suffix("hello__", "__", "__") == "hello"

    def test_neither(self) -> None:
        assert remove_prefix_suffix("hello", "__", "__") == "hello"


class TestWrapText:
    def test_basic(self) -> None:
        lines = wrap_text("hello world foo", 8)
        assert lines == ["hello", "world", "foo"]

    def test_fits_on_one_line(self) -> None:
        assert wrap_text("hi", 10) == ["hi"]

    def test_zero_width_raises(self) -> None:
        with pytest.raises(ValueError):
            wrap_text("hello", 0)

    def test_exact_fit(self) -> None:
        lines = wrap_text("hello world", 11)
        assert lines == ["hello world"]


class TestIsPalindrome:
    def test_true(self) -> None:
        assert is_palindrome("racecar") is True

    def test_false(self) -> None:
        assert is_palindrome("hello") is False

    def test_with_spaces(self) -> None:
        assert is_palindrome("a man a plan a canal panama") is True

    def test_case_insensitive(self) -> None:
        assert is_palindrome("Madam") is True


class TestCountOccurrences:
    def test_basic(self) -> None:
        assert count_occurrences("abcabc", "abc") == 2

    def test_none(self) -> None:
        assert count_occurrences("hello", "xyz") == 0

    def test_empty_sub(self) -> None:
        assert count_occurrences("hello", "") == 0

    def test_overlapping(self) -> None:
        # Non-overlapping: "aaa" contains "aa" once (non-overlapping)
        assert count_occurrences("aaaa", "aa") == 2


class TestFirstNonRepeating:
    def test_basic(self) -> None:
        assert first_non_repeating("aabbcd") == "c"

    def test_all_repeat(self) -> None:
        assert first_non_repeating("aabb") is None

    def test_first_is_unique(self) -> None:
        assert first_non_repeating("abcc") == "a"


class TestTitleCase:
    def test_basic(self) -> None:
        assert title_case("hello world") == "Hello World"

    def test_already_title(self) -> None:
        assert title_case("Hello World") == "Hello World"

    def test_single(self) -> None:
        assert title_case("python") == "Python"


class TestLpadRpad:
    def test_lpad(self) -> None:
        assert lpad("42", 5) == "00042"

    def test_rpad(self) -> None:
        assert rpad("hi", 5) == "hi   "

    def test_lpad_no_change(self) -> None:
        assert lpad("hello", 3) == "hello"


class TestSplitAt:
    def test_basic(self) -> None:
        assert split_at("a,b,c", ",") == ["a", "b", "c"]

    def test_max_parts(self) -> None:
        assert split_at("a,b,c,d", ",", 2) == ["a", "b", "c,d"]

    def test_no_delimiter(self) -> None:
        assert split_at("hello", ",") == ["hello"]


class TestReplaceAll:
    def test_basic(self) -> None:
        result = replace_all("hello world", {"hello": "hi", "world": "earth"})
        assert result == "hi earth"

    def test_empty_replacements(self) -> None:
        assert replace_all("hello", {}) == "hello"


class TestInterleave:
    def test_equal_length(self) -> None:
        assert interleave("abc", "123") == "a1b2c3"

    def test_first_longer(self) -> None:
        assert interleave("abcd", "12") == "a1b2cd"

    def test_second_longer(self) -> None:
        assert interleave("ab", "1234") == "a1b234"
