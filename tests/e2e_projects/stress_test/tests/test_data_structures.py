"""Tests for data_structures — ~70% well covered."""

from __future__ import annotations

import pytest

from stress_lib.data_structures import Stack, Queue, BoundedList, Pair, transfer


class TestStack:
    def test_push_and_pop(self) -> None:
        s: Stack[int] = Stack()
        s.push(1)
        s.push(2)
        assert s.pop() == 2
        assert s.pop() == 1

    def test_peek(self) -> None:
        s: Stack[int] = Stack()
        s.push(42)
        assert s.peek() == 42
        assert s.size == 1  # peek doesn't remove

    def test_is_empty_initially(self) -> None:
        s: Stack[int] = Stack()
        assert s.is_empty() is True

    def test_not_empty_after_push(self) -> None:
        s: Stack[int] = Stack()
        s.push(1)
        assert s.is_empty() is False

    def test_empty_after_pop(self) -> None:
        s: Stack[int] = Stack()
        s.push(1)
        s.pop()
        assert s.is_empty() is True

    def test_pop_empty_raises(self) -> None:
        s: Stack[int] = Stack()
        with pytest.raises(IndexError):
            s.pop()

    def test_peek_empty_raises(self) -> None:
        s: Stack[int] = Stack()
        with pytest.raises(IndexError):
            s.peek()

    def test_size(self) -> None:
        s: Stack[int] = Stack()
        for i in range(5):
            s.push(i)
        assert s.size == 5

    def test_contains(self) -> None:
        s: Stack[int] = Stack()
        s.push(10)
        s.push(20)
        assert 10 in s
        assert 30 not in s

    def test_len(self) -> None:
        s: Stack[int] = Stack()
        s.push(1)
        s.push(2)
        assert len(s) == 2

    def test_iter(self) -> None:
        s: Stack[int] = Stack()
        s.push(1)
        s.push(2)
        s.push(3)
        assert list(s) == [1, 2, 3]

    def test_repr(self) -> None:
        s: Stack[int] = Stack()
        s.push(1)
        assert "Stack" in repr(s)


class TestQueue:
    def test_enqueue_dequeue(self) -> None:
        q: Queue[int] = Queue()
        q.enqueue(1)
        q.enqueue(2)
        assert q.dequeue() == 1
        assert q.dequeue() == 2

    def test_front(self) -> None:
        q: Queue[int] = Queue()
        q.enqueue(99)
        assert q.front() == 99

    def test_is_empty(self) -> None:
        q: Queue[int] = Queue()
        assert q.is_empty() is True
        q.enqueue(1)
        assert q.is_empty() is False

    def test_dequeue_empty_raises(self) -> None:
        q: Queue[int] = Queue()
        with pytest.raises(IndexError):
            q.dequeue()

    def test_front_empty_raises(self) -> None:
        q: Queue[int] = Queue()
        with pytest.raises(IndexError):
            q.front()

    def test_size(self) -> None:
        q: Queue[int] = Queue()
        q.enqueue(1)
        q.enqueue(2)
        q.enqueue(3)
        assert q.size == 3

    def test_fifo_order(self) -> None:
        q: Queue[str] = Queue()
        for item in ["a", "b", "c"]:
            q.enqueue(item)
        assert q.dequeue() == "a"
        assert q.dequeue() == "b"
        assert q.dequeue() == "c"

    def test_contains(self) -> None:
        q: Queue[int] = Queue()
        q.enqueue(5)
        assert 5 in q
        assert 6 not in q

    def test_len(self) -> None:
        q: Queue[int] = Queue()
        q.enqueue(10)
        assert len(q) == 1


class TestBoundedList:
    def test_append_within_capacity(self) -> None:
        bl: BoundedList[int] = BoundedList(3)
        evicted = bl.append(1)
        assert evicted is False
        assert len(bl) == 1

    def test_eviction_when_full(self) -> None:
        bl: BoundedList[int] = BoundedList(2)
        bl.append(1)
        bl.append(2)
        evicted = bl.append(3)
        assert evicted is True
        assert len(bl) == 2
        assert bl[0] == 2
        assert bl[1] == 3

    def test_is_full(self) -> None:
        bl: BoundedList[int] = BoundedList(2)
        assert bl.is_full is False
        bl.append(1)
        bl.append(2)
        assert bl.is_full is True

    def test_capacity_property(self) -> None:
        bl: BoundedList[int] = BoundedList(5)
        assert bl.capacity == 5

    def test_zero_capacity_raises(self) -> None:
        with pytest.raises(ValueError):
            BoundedList(0)

    def test_negative_capacity_raises(self) -> None:
        with pytest.raises(ValueError):
            BoundedList(-1)

    def test_clear(self) -> None:
        bl: BoundedList[int] = BoundedList(3)
        bl.append(1)
        bl.append(2)
        bl.clear()
        assert len(bl) == 0

    def test_contains(self) -> None:
        bl: BoundedList[int] = BoundedList(3)
        bl.append(42)
        assert 42 in bl
        assert 99 not in bl

    def test_to_list(self) -> None:
        bl: BoundedList[int] = BoundedList(3)
        bl.append(1)
        bl.append(2)
        result = bl.to_list()
        assert result == [1, 2]

    def test_repr(self) -> None:
        bl: BoundedList[int] = BoundedList(3)
        assert "BoundedList" in repr(bl)


class TestPair:
    def test_first_second(self) -> None:
        p: Pair[int] = Pair(1, 2)
        assert p.first == 1
        assert p.second == 2

    def test_swap(self) -> None:
        p: Pair[int] = Pair(1, 2)
        swapped = p.swap()
        assert swapped.first == 2
        assert swapped.second == 1

    def test_to_tuple(self) -> None:
        p: Pair[str] = Pair("a", "b")
        assert p.to_tuple() == ("a", "b")

    def test_equality(self) -> None:
        p1: Pair[int] = Pair(1, 2)
        p2: Pair[int] = Pair(1, 2)
        assert p1 == p2

    def test_inequality(self) -> None:
        p1: Pair[int] = Pair(1, 2)
        p2: Pair[int] = Pair(2, 1)
        assert p1 != p2

    def test_hash(self) -> None:
        p: Pair[int] = Pair(1, 2)
        assert hash(p) == hash((1, 2))

    def test_repr(self) -> None:
        p: Pair[int] = Pair(3, 4)
        assert "Pair" in repr(p)


class TestTransfer:
    def test_transfer_all(self) -> None:
        source: Stack[int] = Stack()
        target: Stack[int] = Stack()
        for i in range(3):
            source.push(i)
        moved = transfer(source, target, 10)
        assert moved == 3
        assert source.is_empty()
        assert target.size == 3

    def test_transfer_partial(self) -> None:
        source: Stack[int] = Stack()
        target: Stack[int] = Stack()
        for i in range(5):
            source.push(i)
        moved = transfer(source, target, 2)
        assert moved == 2
        assert source.size == 3
        assert target.size == 2

    def test_transfer_from_empty(self) -> None:
        source: Stack[int] = Stack()
        target: Stack[int] = Stack()
        moved = transfer(source, target, 5)
        assert moved == 0
