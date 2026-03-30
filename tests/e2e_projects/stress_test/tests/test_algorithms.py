"""Tests for algorithms — ~70% well covered."""

from __future__ import annotations

import pytest

from stress_lib.algorithms import (
    binary_search,
    insertion_sort,
    merge_sort,
    quicksort,
    fibonacci,
    flatten,
    group_by,
    count_inversions,
    rotate_left,
    rotate_right,
    find_peak,
    longest_increasing_subsequence,
    two_sum,
)


class TestBinarySearch:
    def test_found_middle(self) -> None:
        assert binary_search([1, 2, 3, 4, 5], 3) == 2

    def test_found_first(self) -> None:
        assert binary_search([1, 2, 3], 1) == 0

    def test_found_last(self) -> None:
        assert binary_search([1, 2, 3], 3) == 2

    def test_not_found(self) -> None:
        assert binary_search([1, 2, 3], 99) == -1

    def test_empty(self) -> None:
        assert binary_search([], 1) == -1

    def test_single_element_found(self) -> None:
        assert binary_search([42], 42) == 0

    def test_single_element_not_found(self) -> None:
        assert binary_search([42], 1) == -1


class TestInsertionSort:
    def test_basic(self) -> None:
        assert insertion_sort([3, 1, 2]) == [1, 2, 3]

    def test_already_sorted(self) -> None:
        assert insertion_sort([1, 2, 3]) == [1, 2, 3]

    def test_reverse_sorted(self) -> None:
        assert insertion_sort([5, 4, 3, 2, 1]) == [1, 2, 3, 4, 5]

    def test_single(self) -> None:
        assert insertion_sort([7]) == [7]

    def test_empty(self) -> None:
        assert insertion_sort([]) == []

    def test_duplicates(self) -> None:
        assert insertion_sort([3, 1, 2, 1]) == [1, 1, 2, 3]

    def test_does_not_modify_original(self) -> None:
        original = [3, 1, 2]
        insertion_sort(original)
        assert original == [3, 1, 2]


class TestMergeSort:
    def test_basic(self) -> None:
        assert merge_sort([5, 2, 8, 1]) == [1, 2, 5, 8]

    def test_empty(self) -> None:
        assert merge_sort([]) == []

    def test_single(self) -> None:
        assert merge_sort([3]) == [3]

    def test_two_elements(self) -> None:
        assert merge_sort([2, 1]) == [1, 2]

    def test_already_sorted(self) -> None:
        assert merge_sort([1, 2, 3, 4]) == [1, 2, 3, 4]

    def test_all_same(self) -> None:
        assert merge_sort([2, 2, 2]) == [2, 2, 2]


class TestQuicksort:
    def test_basic(self) -> None:
        assert quicksort([3, 6, 8, 10, 1, 2]) == [1, 2, 3, 6, 8, 10]

    def test_empty(self) -> None:
        assert quicksort([]) == []

    def test_single(self) -> None:
        assert quicksort([1]) == [1]

    def test_duplicates(self) -> None:
        assert quicksort([3, 1, 2, 1]) == [1, 1, 2, 3]

    def test_reverse(self) -> None:
        assert quicksort([5, 4, 3, 2, 1]) == [1, 2, 3, 4, 5]


class TestFibonacci:
    def test_zero(self) -> None:
        assert fibonacci(0) == 0

    def test_one(self) -> None:
        assert fibonacci(1) == 1

    def test_two(self) -> None:
        assert fibonacci(2) == 1

    def test_ten(self) -> None:
        assert fibonacci(10) == 55

    def test_negative_raises(self) -> None:
        with pytest.raises(ValueError):
            fibonacci(-1)

    def test_sequence(self) -> None:
        expected = [0, 1, 1, 2, 3, 5, 8, 13, 21, 34]
        for i, val in enumerate(expected):
            assert fibonacci(i) == val


class TestFlatten:
    def test_already_flat(self) -> None:
        assert flatten([1, 2, 3]) == [1, 2, 3]

    def test_nested(self) -> None:
        assert flatten([1, [2, 3], [4, [5, 6]]]) == [1, 2, 3, 4, 5, 6]

    def test_empty(self) -> None:
        assert flatten([]) == []

    def test_deep(self) -> None:
        assert flatten([[[1]], [[2]]]) == [1, 2]


class TestGroupBy:
    def test_basic(self) -> None:
        items = [
            {"type": "a", "val": 1},
            {"type": "b", "val": 2},
            {"type": "a", "val": 3},
        ]
        result = group_by(items, "type")
        assert len(result["a"]) == 2
        assert len(result["b"]) == 1

    def test_missing_key(self) -> None:
        items = [{"x": 1}, {"x": 2}]
        result = group_by(items, "missing")
        assert None in result
        assert len(result[None]) == 2

    def test_empty(self) -> None:
        assert group_by([], "key") == {}


class TestCountInversions:
    def test_sorted(self) -> None:
        assert count_inversions([1, 2, 3, 4]) == 0

    def test_reverse_sorted(self) -> None:
        # [4,3,2,1] has 6 inversions
        assert count_inversions([4, 3, 2, 1]) == 6

    def test_single(self) -> None:
        assert count_inversions([5]) == 0

    def test_basic(self) -> None:
        assert count_inversions([2, 1, 3]) == 1


class TestRotate:
    def test_left_basic(self) -> None:
        assert rotate_left([1, 2, 3, 4, 5], 2) == [3, 4, 5, 1, 2]

    def test_left_zero(self) -> None:
        assert rotate_left([1, 2, 3], 0) == [1, 2, 3]

    def test_left_empty(self) -> None:
        assert rotate_left([], 3) == []

    def test_right_basic(self) -> None:
        assert rotate_right([1, 2, 3, 4, 5], 2) == [4, 5, 1, 2, 3]

    def test_right_zero(self) -> None:
        assert rotate_right([1, 2, 3], 0) == [1, 2, 3]

    def test_right_empty(self) -> None:
        assert rotate_right([], 3) == []


class TestFindPeak:
    def test_single(self) -> None:
        assert find_peak([5]) == 0

    def test_ascending(self) -> None:
        idx = find_peak([1, 2, 3, 4, 5])
        assert idx == 4

    def test_middle_peak(self) -> None:
        idx = find_peak([1, 3, 2])
        assert idx == 1

    def test_empty_raises(self) -> None:
        with pytest.raises(ValueError):
            find_peak([])


class TestLIS:
    def test_empty(self) -> None:
        assert longest_increasing_subsequence([]) == 0

    def test_sorted(self) -> None:
        assert longest_increasing_subsequence([1, 2, 3, 4, 5]) == 5

    def test_reverse(self) -> None:
        assert longest_increasing_subsequence([5, 4, 3, 2, 1]) == 1

    def test_mixed(self) -> None:
        assert longest_increasing_subsequence([3, 1, 4, 1, 5, 9, 2, 6]) == 4


class TestTwoSum:
    def test_found(self) -> None:
        result = two_sum([2, 7, 11, 15], 9)
        assert result == (0, 1)

    def test_not_found(self) -> None:
        assert two_sum([1, 2, 3], 100) is None

    def test_multiple_pairs(self) -> None:
        result = two_sum([3, 2, 4], 6)
        assert result is not None
        i, j = result
        assert [3, 2, 4][i] + [3, 2, 4][j] == 6
