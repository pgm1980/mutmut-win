"""Tests for simple_lib — used as the E2E target project."""

from __future__ import annotations

from simple_lib import add, is_positive, multiply, subtract


def test_add_two_positives() -> None:
    assert add(2, 3) == 5


def test_add_zero() -> None:
    assert add(0, 0) == 0


def test_subtract() -> None:
    assert subtract(10, 4) == 6


def test_subtract_negative_result() -> None:
    assert subtract(1, 5) == -4


def test_multiply() -> None:
    assert multiply(3, 4) == 12


def test_multiply_by_zero() -> None:
    assert multiply(7, 0) == 0


def test_is_positive_true() -> None:
    assert is_positive(1) is True


def test_is_positive_zero() -> None:
    assert is_positive(0) is False


def test_is_positive_negative() -> None:
    assert is_positive(-5) is False
