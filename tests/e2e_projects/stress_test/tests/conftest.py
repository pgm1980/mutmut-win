"""Shared fixtures for stress_lib tests."""

from __future__ import annotations

import pytest


@pytest.fixture
def sample_ints() -> list[int]:
    """A varied list of integers for sorting/searching tests."""
    return [5, 2, 8, 1, 9, 3, 7, 4, 6, 0]


@pytest.fixture
def sorted_ints() -> list[int]:
    """A sorted list of integers."""
    return [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]


@pytest.fixture
def small_stack() -> list[int]:
    """Values to push onto a Stack."""
    return [10, 20, 30]
