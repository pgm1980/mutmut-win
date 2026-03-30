"""Sorting, searching, and recursive algorithms.

Designed to trigger mutations on: numeric literals, loop conditions, recursive
base cases, comparison operators, and index arithmetic.
"""

from __future__ import annotations

from typing import TypeVar

T = TypeVar("T")


def binary_search(items: list[int], target: int) -> int:
    """Return the index of target in sorted items, or -1 if not found."""
    low = 0
    high = len(items) - 1
    while low <= high:
        mid = (low + high) // 2
        if items[mid] == target:
            return mid
        if items[mid] < target:
            low = mid + 1
        else:
            high = mid - 1
    return -1


def insertion_sort(items: list[int]) -> list[int]:
    """Return a new list sorted via insertion sort (ascending)."""
    result = list(items)
    for i in range(1, len(result)):
        key = result[i]
        j = i - 1
        while j >= 0 and result[j] > key:
            result[j + 1] = result[j]
            j -= 1
        result[j + 1] = key
    return result


def merge_sort(items: list[int]) -> list[int]:
    """Return a new list sorted via merge sort (ascending)."""
    if len(items) <= 1:
        return list(items)
    mid = len(items) // 2
    left = merge_sort(items[:mid])
    right = merge_sort(items[mid:])
    return _merge(left, right)


def _merge(left: list[int], right: list[int]) -> list[int]:
    """Merge two sorted lists into one sorted list."""
    result: list[int] = []
    i = 0
    j = 0
    while i < len(left) and j < len(right):
        if left[i] <= right[j]:
            result.append(left[i])
            i += 1
        else:
            result.append(right[j])
            j += 1
    result.extend(left[i:])
    result.extend(right[j:])
    return result


def quicksort(items: list[int]) -> list[int]:
    """Return a new list sorted via quicksort (ascending)."""
    if len(items) <= 1:
        return list(items)
    pivot = items[len(items) // 2]
    left = [x for x in items if x < pivot]
    middle = [x for x in items if x == pivot]
    right = [x for x in items if x > pivot]
    return quicksort(left) + middle + quicksort(right)


def fibonacci(n: int) -> int:
    """Return the n-th Fibonacci number (0-indexed). fib(0)=0, fib(1)=1."""
    if n < 0:
        raise ValueError("n must be >= 0")
    if n == 0:
        return 0
    if n == 1:
        return 1
    a, b = 0, 1
    for _ in range(2, n + 1):
        a, b = b, a + b
    return b


def flatten(nested: list[object]) -> list[object]:
    """Recursively flatten a nested list."""
    result: list[object] = []
    for item in nested:
        if isinstance(item, list):
            result.extend(flatten(item))
        else:
            result.append(item)
    return result


def group_by(items: list[dict[str, object]], key: str) -> dict[object, list[dict[str, object]]]:
    """Group a list of dicts by a shared key."""
    groups: dict[object, list[dict[str, object]]] = {}
    for item in items:
        k = item.get(key)
        if k not in groups:
            groups[k] = []
        groups[k].append(item)
    return groups


def count_inversions(items: list[int]) -> int:
    """Count the number of inversions in items (pairs where i < j but items[i] > items[j])."""
    if len(items) <= 1:
        return 0
    mid = len(items) // 2
    left = items[:mid]
    right = items[mid:]
    count = count_inversions(left) + count_inversions(right)
    i = j = k = 0
    merged: list[int] = []
    while i < len(left) and j < len(right):
        if left[i] <= right[j]:
            merged.append(left[i])
            i += 1
        else:
            merged.append(right[j])
            count += len(left) - i
            j += 1
    merged.extend(left[i:])
    merged.extend(right[j:])
    items[:] = merged
    return count


def rotate_left(items: list[int], k: int) -> list[int]:
    """Rotate items left by k positions."""
    if not items:
        return []
    k = k % len(items)
    return items[k:] + items[:k]


def rotate_right(items: list[int], k: int) -> list[int]:
    """Rotate items right by k positions."""
    if not items:
        return []
    k = k % len(items)
    return items[-k:] + items[:-k]


def find_peak(items: list[int]) -> int:
    """Return index of a peak element (element >= both neighbours) via binary search."""
    if not items:
        raise ValueError("items must not be empty")
    low = 0
    high = len(items) - 1
    while low < high:
        mid = (low + high) // 2
        if items[mid] < items[mid + 1]:
            low = mid + 1
        else:
            high = mid
    return low


def longest_increasing_subsequence(items: list[int]) -> int:
    """Return length of the longest strictly increasing subsequence."""
    if not items:
        return 0
    dp = [1] * len(items)
    for i in range(1, len(items)):
        for j in range(i):
            if items[j] < items[i]:
                if dp[j] + 1 > dp[i]:
                    dp[i] = dp[j] + 1
    return max(dp)


def two_sum(items: list[int], target: int) -> tuple[int, int] | None:
    """Return indices (i, j) where items[i] + items[j] == target, or None."""
    seen: dict[int, int] = {}
    for i, val in enumerate(items):
        complement = target - val
        if complement in seen:
            return (seen[complement], i)
        seen[val] = i
    return None
