"""Tests for async_ops — ~70% well covered."""

from __future__ import annotations

import pytest

from stress_lib.async_ops import (
    async_add,
    async_multiply,
    async_sum,
    gather_results,
    async_filter,
    countdown,
    async_range,
    async_map,
    async_max,
    sync_generator,
    infinite_counter,
    take,
)


class TestAsyncAdd:
    async def test_basic(self) -> None:
        assert await async_add(2, 3) == 5

    async def test_zero(self) -> None:
        assert await async_add(0, 0) == 0

    async def test_negative(self) -> None:
        assert await async_add(-1, -4) == -5


class TestAsyncMultiply:
    async def test_basic(self) -> None:
        assert await async_multiply(3, 4) == 12

    async def test_by_zero(self) -> None:
        assert await async_multiply(5, 0) == 0


class TestAsyncSum:
    async def test_basic(self) -> None:
        assert await async_sum([1, 2, 3, 4]) == 10

    async def test_empty(self) -> None:
        assert await async_sum([]) == 0

    async def test_single(self) -> None:
        assert await async_sum([42]) == 42


class TestGatherResults:
    async def test_doubled(self) -> None:
        result = await gather_results([1, 2, 3])
        assert result == [2, 4, 6]

    async def test_empty(self) -> None:
        result = await gather_results([])
        assert result == []


class TestAsyncFilter:
    async def test_basic(self) -> None:
        result = await async_filter([1, 5, 3, 8, 2], 4)
        assert result == [5, 8]

    async def test_none_pass(self) -> None:
        result = await async_filter([1, 2, 3], 10)
        assert result == []

    async def test_all_pass(self) -> None:
        result = await async_filter([5, 6, 7], 4)
        assert result == [5, 6, 7]

    async def test_empty(self) -> None:
        result = await async_filter([], 0)
        assert result == []


class TestCountdown:
    async def test_basic(self) -> None:
        values = []
        async for v in countdown(3):
            values.append(v)
        assert values == [3, 2, 1, 0]

    async def test_zero(self) -> None:
        values = []
        async for v in countdown(0):
            values.append(v)
        assert values == [0]


class TestAsyncRange:
    async def test_basic(self) -> None:
        values = []
        async for v in async_range(0, 5):
            values.append(v)
        assert values == [0, 1, 2, 3, 4]

    async def test_with_step(self) -> None:
        values = []
        async for v in async_range(0, 10, 2):
            values.append(v)
        assert values == [0, 2, 4, 6, 8]

    async def test_descending(self) -> None:
        values = []
        async for v in async_range(5, 0, -1):
            values.append(v)
        assert values == [5, 4, 3, 2, 1]

    async def test_zero_step_raises(self) -> None:
        with pytest.raises(ValueError):
            async for _ in async_range(0, 5, 0):
                pass


class TestAsyncMap:
    async def test_basic(self) -> None:
        result = await async_map([1, 2, 3], 3)
        assert result == [3, 6, 9]

    async def test_empty(self) -> None:
        result = await async_map([], 5)
        assert result == []

    async def test_by_one(self) -> None:
        result = await async_map([1, 2, 3], 1)
        assert result == [1, 2, 3]


class TestAsyncMax:
    async def test_basic(self) -> None:
        assert await async_max([3, 1, 4, 1, 5, 9]) == 9

    async def test_single(self) -> None:
        assert await async_max([42]) == 42

    async def test_empty_raises(self) -> None:
        with pytest.raises(ValueError):
            await async_max([])

    async def test_negative(self) -> None:
        assert await async_max([-5, -1, -3]) == -1


class TestSyncGenerator:
    def test_basic(self) -> None:
        assert list(sync_generator(1, 5)) == [1, 2, 3, 4, 5]

    def test_single(self) -> None:
        assert list(sync_generator(3, 3)) == [3]

    def test_empty(self) -> None:
        assert list(sync_generator(5, 3)) == []


class TestInfiniteCounter:
    def test_default(self) -> None:
        gen = infinite_counter()
        assert take(gen, 5) == [0, 1, 2, 3, 4]

    def test_custom_start(self) -> None:
        gen = infinite_counter(10)
        assert take(gen, 3) == [10, 11, 12]

    def test_custom_step(self) -> None:
        gen = infinite_counter(0, 5)
        assert take(gen, 4) == [0, 5, 10, 15]


class TestTake:
    def test_basic(self) -> None:
        gen = sync_generator(1, 10)
        assert take(gen, 3) == [1, 2, 3]

    def test_fewer_than_n(self) -> None:
        gen = sync_generator(1, 2)
        assert take(gen, 10) == [1, 2]

    def test_zero(self) -> None:
        gen = sync_generator(1, 10)
        assert take(gen, 0) == []
