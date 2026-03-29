"""Simple library for E2E mutation testing tests."""

from __future__ import annotations


def add(a: int, b: int) -> int:
    """Return the sum of two integers.

    Args:
        a: First operand.
        b: Second operand.

    Returns:
        Sum of a and b.
    """
    return a + b


def subtract(a: int, b: int) -> int:
    """Return the difference of two integers.

    Args:
        a: Minuend.
        b: Subtrahend.

    Returns:
        Difference a - b.
    """
    return a - b


def multiply(a: int, b: int) -> int:
    """Return the product of two integers.

    Args:
        a: First factor.
        b: Second factor.

    Returns:
        Product of a and b.
    """
    return a * b


def is_positive(n: int) -> bool:
    """Check whether an integer is strictly positive.

    Args:
        n: Integer to check.

    Returns:
        True if n > 0, False otherwise.
    """
    return n > 0
