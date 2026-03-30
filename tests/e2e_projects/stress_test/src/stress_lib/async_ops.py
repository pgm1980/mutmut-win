"""Async operations and generators.

Designed to trigger mutations on: async def, await expressions, async for,
yield expressions, and generator logic.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, AsyncIterator, Generator


async def async_add(a: int, b: int) -> int:
    """Asynchronously return a + b."""
    await asyncio.sleep(0)
    return a + b


async def async_multiply(a: int, b: int) -> int:
    """Asynchronously return a * b."""
    await asyncio.sleep(0)
    return a * b


async def async_sum(values: list[int]) -> int:
    """Asynchronously sum a list of integers."""
    total = 0
    for v in values:
        await asyncio.sleep(0)
        total += v
    return total


async def gather_results(tasks: list[int]) -> list[int]:
    """Return doubled values of each task item (simulates async processing)."""
    async def process(x: int) -> int:
        await asyncio.sleep(0)
        return x * 2

    results = await asyncio.gather(*[process(t) for t in tasks])
    return list(results)


async def async_filter(values: list[int], threshold: int) -> list[int]:
    """Return values greater than threshold, processed asynchronously."""
    result: list[int] = []
    for v in values:
        await asyncio.sleep(0)
        if v > threshold:
            result.append(v)
    return result


async def countdown(start: int) -> AsyncGenerator[int, None]:
    """Async generator that yields integers from start down to 0."""
    n = start
    while n >= 0:
        yield n
        n -= 1
        await asyncio.sleep(0)


async def async_range(start: int, stop: int, step: int = 1) -> AsyncIterator[int]:
    """Async generator equivalent of range(start, stop, step)."""
    if step == 0:
        raise ValueError("step must not be zero")
    current = start
    if step > 0:
        while current < stop:
            yield current
            current += step
            await asyncio.sleep(0)
    else:
        while current > stop:
            yield current
            current += step
            await asyncio.sleep(0)


async def async_map(values: list[int], multiplier: int) -> list[int]:
    """Multiply each value by multiplier asynchronously."""
    result: list[int] = []
    async for v in _async_iter(values):
        result.append(v * multiplier)
    return result


async def _async_iter(values: list[int]) -> AsyncGenerator[int, None]:
    """Yield each value from a list asynchronously."""
    for v in values:
        await asyncio.sleep(0)
        yield v


async def async_max(values: list[int]) -> int:
    """Return the maximum value asynchronously. Raises ValueError on empty."""
    if not values:
        raise ValueError("values must not be empty")
    result = values[0]
    for v in values[1:]:
        await asyncio.sleep(0)
        if v > result:
            result = v
    return result


async def retry(coro_fn: object, attempts: int, delay: float = 0.0) -> object:
    """Call coro_fn() up to attempts times; return first success or raise last error."""
    last_exc: Exception | None = None
    for i in range(attempts):
        try:
            if callable(coro_fn):
                return await coro_fn()  # type: ignore[operator]
        except Exception as exc:
            last_exc = exc
            if i < attempts - 1:
                await asyncio.sleep(delay)
    raise last_exc or RuntimeError("no attempts made")


def sync_generator(start: int, end: int) -> Generator[int, None, None]:
    """Yield integers from start to end (inclusive)."""
    current = start
    while current <= end:
        yield current
        current += 1


def infinite_counter(start: int = 0, step: int = 1) -> Generator[int, None, None]:
    """Infinite generator yielding start, start+step, start+2*step, ..."""
    current = start
    while True:
        yield current
        current += step


def take(gen: Generator[int, None, None], n: int) -> list[int]:
    """Take the first n values from a generator."""
    result: list[int] = []
    for _ in range(n):
        try:
            result.append(next(gen))
        except StopIteration:
            break
    return result
