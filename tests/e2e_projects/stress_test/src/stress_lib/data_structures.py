"""Custom data structures.

Designed to trigger mutations on: class attributes, `is`/`is not`,
`in`/`not in`, `True`/`False`, `break`/`continue`, augmented assignments,
and assignment-to-None mutations.
"""

from __future__ import annotations

from typing import Generic, Iterator, TypeVar

T = TypeVar("T")


class Stack(Generic[T]):
    """A LIFO stack backed by a list."""

    def __init__(self) -> None:
        """Initialise empty stack."""
        self._data: list[T] = []

    def push(self, item: T) -> None:
        """Push item onto the top of the stack."""
        self._data.append(item)

    def pop(self) -> T:
        """Remove and return the top item. Raises IndexError if empty."""
        if self.is_empty():
            raise IndexError("pop from empty stack")
        return self._data.pop()

    def peek(self) -> T:
        """Return the top item without removing it. Raises IndexError if empty."""
        if self.is_empty():
            raise IndexError("peek at empty stack")
        return self._data[-1]

    def is_empty(self) -> bool:
        """Return True if the stack is empty."""
        return len(self._data) == 0

    @property
    def size(self) -> int:
        """Return the number of items in the stack."""
        return len(self._data)

    def __contains__(self, item: object) -> bool:
        """Return True if item is in the stack."""
        return item in self._data

    def __iter__(self) -> Iterator[T]:
        """Iterate from bottom to top."""
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def __repr__(self) -> str:
        return f"Stack({self._data!r})"


class Queue(Generic[T]):
    """A FIFO queue backed by a list."""

    def __init__(self) -> None:
        """Initialise empty queue."""
        self._data: list[T] = []

    def enqueue(self, item: T) -> None:
        """Add item to the back of the queue."""
        self._data.append(item)

    def dequeue(self) -> T:
        """Remove and return the front item. Raises IndexError if empty."""
        if self.is_empty():
            raise IndexError("dequeue from empty queue")
        return self._data.pop(0)

    def front(self) -> T:
        """Return the front item without removing it."""
        if self.is_empty():
            raise IndexError("front of empty queue")
        return self._data[0]

    def is_empty(self) -> bool:
        """Return True if the queue is empty."""
        return len(self._data) == 0

    @property
    def size(self) -> int:
        """Return the number of items in the queue."""
        return len(self._data)

    def __contains__(self, item: object) -> bool:
        return item in self._data

    def __len__(self) -> int:
        return len(self._data)

    def __repr__(self) -> str:
        return f"Queue({self._data!r})"


class BoundedList(Generic[T]):
    """A list with a maximum capacity. Oldest items are evicted when full."""

    def __init__(self, capacity: int) -> None:
        """Initialise with given capacity (must be > 0)."""
        if capacity <= 0:
            raise ValueError("capacity must be > 0")
        self._capacity = capacity
        self._data: list[T] = []

    def append(self, item: T) -> bool:
        """Append item. If full, evict oldest. Return True if eviction occurred."""
        evicted = False
        if len(self._data) >= self._capacity:
            self._data.pop(0)
            evicted = True
        self._data.append(item)
        return evicted

    def __getitem__(self, index: int) -> T:
        return self._data[index]

    def __len__(self) -> int:
        return len(self._data)

    def __contains__(self, item: object) -> bool:
        return item in self._data

    @property
    def is_full(self) -> bool:
        """Return True when capacity is reached."""
        return len(self._data) >= self._capacity

    @property
    def capacity(self) -> int:
        """Return maximum capacity."""
        return self._capacity

    def clear(self) -> None:
        """Remove all items."""
        self._data = []

    def to_list(self) -> list[T]:
        """Return a copy of the internal list."""
        return list(self._data)

    def __repr__(self) -> str:
        return f"BoundedList(capacity={self._capacity}, data={self._data!r})"


class Pair(Generic[T]):
    """An immutable pair of two values of the same type."""

    def __init__(self, first: T, second: T) -> None:
        """Initialise the pair."""
        self._first = first
        self._second = second

    @property
    def first(self) -> T:
        """Return the first element."""
        return self._first

    @property
    def second(self) -> T:
        """Return the second element."""
        return self._second

    def swap(self) -> "Pair[T]":
        """Return a new Pair with first and second swapped."""
        return Pair(self._second, self._first)

    def to_tuple(self) -> tuple[T, T]:
        """Return the pair as a tuple."""
        return (self._first, self._second)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Pair):
            return NotImplemented
        return self._first == other._first and self._second == other._second

    def __hash__(self) -> int:
        return hash((self._first, self._second))

    def __repr__(self) -> str:
        return f"Pair({self._first!r}, {self._second!r})"


def find_in_stack(stack: Stack[T], predicate: object) -> T | None:
    """Return the first item in stack (bottom-to-top) matching predicate, or None."""
    for item in stack:
        if callable(predicate) and predicate(item):  # type: ignore[operator]
            return item
    return None


def transfer(source: Stack[T], target: Stack[T], count: int) -> int:
    """Transfer at most count items from source to target. Returns items moved."""
    moved = 0
    while moved < count and not source.is_empty():
        target.push(source.pop())
        moved += 1
    return moved
