"""Tests for validators — ~70% well covered, ~30% medium/weak."""

from __future__ import annotations

import pytest

from stress_lib.validators import (
    is_positive,
    is_non_negative,
    is_in_range,
    is_between_exclusive,
    validate_email,
    validate_password,
    all_truthy,
    any_falsy,
    coerce_bool,
    validate_range,
    is_subset,
    has_duplicates,
    deep_copy_if_mutable,
    validate_username,
    validate_port,
    none_of,
    exactly_one,
)


class TestIsPositive:
    def test_positive(self) -> None:
        assert is_positive(1) is True

    def test_zero(self) -> None:
        assert is_positive(0) is False

    def test_negative(self) -> None:
        assert is_positive(-1) is False

    def test_float(self) -> None:
        assert is_positive(0.001) is True


class TestIsNonNegative:
    def test_positive(self) -> None:
        assert is_non_negative(1) is True

    def test_zero(self) -> None:
        assert is_non_negative(0) is True

    def test_negative(self) -> None:
        assert is_non_negative(-1) is False


class TestIsInRange:
    def test_within(self) -> None:
        assert is_in_range(5, 0, 10) is True

    def test_at_low(self) -> None:
        assert is_in_range(0, 0, 10) is True

    def test_at_high(self) -> None:
        assert is_in_range(10, 0, 10) is True

    def test_below(self) -> None:
        assert is_in_range(-1, 0, 10) is False

    def test_above(self) -> None:
        assert is_in_range(11, 0, 10) is False


class TestIsBetweenExclusive:
    def test_within(self) -> None:
        assert is_between_exclusive(5.0, 0.0, 10.0) is True

    def test_at_low(self) -> None:
        assert is_between_exclusive(0.0, 0.0, 10.0) is False

    def test_at_high(self) -> None:
        assert is_between_exclusive(10.0, 0.0, 10.0) is False


class TestValidateEmail:
    def test_valid(self) -> None:
        assert validate_email("user@example.com") is True

    def test_no_at(self) -> None:
        assert validate_email("userexample.com") is False

    def test_empty(self) -> None:
        assert validate_email("") is False

    def test_subdomain(self) -> None:
        assert validate_email("user@mail.example.co.uk") is True

    def test_plus_addressing(self) -> None:
        assert validate_email("user+tag@example.com") is True


class TestValidatePassword:
    def test_valid(self) -> None:
        assert validate_password("Secure!1Pass") is True

    def test_too_short(self) -> None:
        assert validate_password("Ab1!") is False

    def test_no_uppercase(self) -> None:
        assert validate_password("secure!1pass") is False

    def test_no_lowercase(self) -> None:
        assert validate_password("SECURE!1PASS") is False

    def test_no_digit(self) -> None:
        assert validate_password("Secure!Pass") is False

    def test_no_special(self) -> None:
        assert validate_password("Secure1Pass") is False

    def test_exactly_eight_chars(self) -> None:
        assert validate_password("Abc1!xyz") is True


class TestAllTruthy:
    def test_all_true(self) -> None:
        assert all_truthy([1, "hello", True, [1]]) is True

    def test_one_false(self) -> None:
        assert all_truthy([1, 0, "hi"]) is False

    def test_empty(self) -> None:
        assert all_truthy([]) is True

    def test_with_none(self) -> None:
        assert all_truthy([1, None]) is False


class TestAnyFalsy:
    def test_has_falsy(self) -> None:
        assert any_falsy([1, 0, "hi"]) is True

    def test_all_truthy(self) -> None:
        assert any_falsy([1, "hi", True]) is False

    def test_empty(self) -> None:
        assert any_falsy([]) is False


class TestCoerceBool:
    def test_true_string(self) -> None:
        assert coerce_bool("true") is True
        assert coerce_bool("yes") is True
        assert coerce_bool("1") is True
        assert coerce_bool("on") is True

    def test_false_string(self) -> None:
        assert coerce_bool("false") is False
        assert coerce_bool("no") is False
        assert coerce_bool("0") is False
        assert coerce_bool("off") is False

    def test_bool_passthrough(self) -> None:
        assert coerce_bool(True) is True
        assert coerce_bool(False) is False

    def test_int_nonzero(self) -> None:
        assert coerce_bool(1) is True
        assert coerce_bool(0) is False

    def test_invalid_string_raises(self) -> None:
        with pytest.raises(ValueError):
            coerce_bool("maybe")

    def test_unsupported_type_raises(self) -> None:
        with pytest.raises(TypeError):
            coerce_bool([1, 2])


class TestValidateRange:
    def test_within_inclusive(self) -> None:
        assert validate_range(5.0, min_val=0.0, max_val=10.0) is True

    def test_at_min_inclusive(self) -> None:
        assert validate_range(0.0, min_val=0.0) is True

    def test_at_min_exclusive(self) -> None:
        assert validate_range(0.0, min_val=0.0, inclusive=False) is False

    def test_above_max_inclusive(self) -> None:
        assert validate_range(11.0, max_val=10.0) is False

    def test_no_bounds(self) -> None:
        assert validate_range(999.0) is True


class TestIsSubset:
    def test_is_subset(self) -> None:
        assert is_subset([1, 2], [1, 2, 3, 4]) is True

    def test_not_subset(self) -> None:
        assert is_subset([1, 5], [1, 2, 3, 4]) is False

    def test_empty_is_subset(self) -> None:
        assert is_subset([], [1, 2, 3]) is True

    def test_equal_sets(self) -> None:
        assert is_subset([1, 2], [1, 2]) is True


class TestHasDuplicates:
    def test_no_duplicates(self) -> None:
        assert has_duplicates([1, 2, 3]) is False

    def test_has_duplicates(self) -> None:
        assert has_duplicates([1, 2, 2]) is True

    def test_empty(self) -> None:
        assert has_duplicates([]) is False


class TestDeepCopyIfMutable:
    def test_list_is_copied(self) -> None:
        original = [1, [2, 3]]
        copy = deep_copy_if_mutable(original)
        assert copy == original
        assert copy is not original

    def test_dict_is_copied(self) -> None:
        original = {"a": {"b": 1}}
        copy = deep_copy_if_mutable(original)
        assert copy == original
        assert copy is not original


class TestValidateUsername:
    def test_valid(self) -> None:
        assert validate_username("john_doe99") is True

    def test_too_short(self) -> None:
        assert validate_username("ab") is False

    def test_too_long(self) -> None:
        assert validate_username("a" * 21) is False

    def test_invalid_chars(self) -> None:
        assert validate_username("hello world") is False


class TestValidatePort:
    def test_valid_low(self) -> None:
        assert validate_port(1) is True

    def test_valid_high(self) -> None:
        assert validate_port(65535) is True

    def test_zero(self) -> None:
        assert validate_port(0) is False

    def test_above_max(self) -> None:
        assert validate_port(65536) is False

    def test_http(self) -> None:
        assert validate_port(80) is True


class TestNoneOf:
    def test_all_falsy(self) -> None:
        assert none_of([0, False, None, ""]) is True

    def test_one_truthy(self) -> None:
        assert none_of([0, 1]) is False

    def test_empty(self) -> None:
        assert none_of([]) is True


class TestExactlyOne:
    def test_one_truthy(self) -> None:
        assert exactly_one([0, 1, 0]) is True

    def test_none_truthy(self) -> None:
        assert exactly_one([0, 0]) is False

    def test_two_truthy(self) -> None:
        assert exactly_one([1, 1, 0]) is False

    def test_empty(self) -> None:
        assert exactly_one([]) is False
