"""Unit regressions for the effective generation worker count (M-055)."""

from __future__ import annotations

import concurrent.futures.process

import pytest
from hypothesis import given
from hypothesis import strategies as st

from mutmut_win.process.generation_supervisor import (
    _WINDOWS_PPE_MAX_WORKERS,
    _effective_generation_workers,
)


def test_windows_ppe_cap_mirrors_cpython_limit() -> None:
    """The mirror constant must track CPython's own ProcessPoolExecutor cap.

    Accessing the private CPython symbol is deliberate here and confined to
    this test: it is the only way to notice that a CPython update moved
    ``_MAX_WINDOWS_WORKERS``, which would silently invalidate our mirror.
    """
    assert _WINDOWS_PPE_MAX_WORKERS == concurrent.futures.process._MAX_WINDOWS_WORKERS


@pytest.mark.parametrize(
    ("max_children", "file_count", "expected"),
    [
        (1, 1, 1),
        (8, 3, 3),
        (61, 61, 61),
        (61, 100, 61),
        (62, 100, 61),
        (64, 100, 61),
        (4, 0, 1),
    ],
)
def test_effective_generation_workers_boundaries(
    max_children: int,
    file_count: int,
    expected: int,
) -> None:
    assert _effective_generation_workers(max_children, file_count) == expected


@given(
    max_children=st.integers(min_value=1, max_value=10_000),
    file_count=st.integers(min_value=0, max_value=10_000),
)
def test_effective_generation_workers_property(max_children: int, file_count: int) -> None:
    effective = _effective_generation_workers(max_children, file_count)

    assert effective == min(max_children, _WINDOWS_PPE_MAX_WORKERS, max(1, file_count))
    assert 1 <= effective <= _WINDOWS_PPE_MAX_WORKERS
    assert effective <= max_children
