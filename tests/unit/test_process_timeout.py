"""Unit tests for mutmut_win.process.timeout (WallClockTimeout)."""

from __future__ import annotations

import time
from queue import Queue
from typing import Any
from unittest.mock import patch

from mutmut_win.models import TaskTimedOut
from mutmut_win.process.timeout import WallClockTimeout, _kill_process

# ---------------------------------------------------------------------------
# Queue stub — avoids multiprocessing overhead in unit tests
# ---------------------------------------------------------------------------


class _SimpleQueue:
    """Minimal queue stub that matches the put/get interface."""

    def __init__(self) -> None:
        self._q: Queue[Any] = Queue()

    def put(self, item: Any) -> None:
        self._q.put(item)

    def get(self) -> Any:
        return self._q.get()

    def empty(self) -> bool:
        return self._q.empty()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestWallClockTimeoutRegisterUnregister:
    """Tests for register / unregister mechanics (no thread involved)."""

    def test_register_and_unregister(self) -> None:
        eq: _SimpleQueue = _SimpleQueue()
        wct = WallClockTimeout(eq)  # type: ignore[arg-type]

        wct.register("m1", 1001, time.monotonic() + 60.0)
        with wct._lock:
            assert "m1" in wct._entries

        wct.unregister("m1")
        with wct._lock:
            assert "m1" not in wct._entries

    def test_unregister_nonexistent_is_silent(self) -> None:
        eq: _SimpleQueue = _SimpleQueue()
        wct = WallClockTimeout(eq)  # type: ignore[arg-type]
        wct.unregister("does_not_exist")  # must not raise

    def test_multiple_entries(self) -> None:
        eq: _SimpleQueue = _SimpleQueue()
        wct = WallClockTimeout(eq)  # type: ignore[arg-type]

        for i in range(5):
            wct.register(f"m{i}", 1000 + i, time.monotonic() + 60.0)

        with wct._lock:
            assert len(wct._entries) == 5

        wct.unregister("m2")
        with wct._lock:
            assert len(wct._entries) == 4
            assert "m2" not in wct._entries


class TestWallClockTimeoutDeadlineExpiry:
    """Tests that check deadline detection emits the right events."""

    def test_expired_deadline_emits_timed_out_event(self) -> None:
        """An already-expired deadline must produce a TaskTimedOut event."""
        eq: _SimpleQueue = _SimpleQueue()
        wct = WallClockTimeout(eq)  # type: ignore[arg-type]

        past_deadline = time.monotonic() - 1.0  # already passed
        wct.register("mutant_x", 9999, past_deadline)

        with patch("mutmut_win.process.timeout._kill_process"):
            wct._check_deadlines()

        assert not eq.empty()
        raw = eq.get()
        event = TaskTimedOut.model_validate(raw)
        assert event.mutant_name == "mutant_x"
        assert event.worker_pid == 9999

    def test_future_deadline_not_triggered(self) -> None:
        """A deadline in the future must NOT produce any event."""
        eq: _SimpleQueue = _SimpleQueue()
        wct = WallClockTimeout(eq)  # type: ignore[arg-type]

        future_deadline = time.monotonic() + 60.0
        wct.register("mutant_y", 1234, future_deadline)

        with patch("mutmut_win.process.timeout._kill_process"):
            wct._check_deadlines()

        assert eq.empty()
        with wct._lock:
            assert "mutant_y" in wct._entries  # still registered

    def test_expired_entry_removed_from_registry(self) -> None:
        """Timed-out entries must be removed from _entries."""
        eq: _SimpleQueue = _SimpleQueue()
        wct = WallClockTimeout(eq)  # type: ignore[arg-type]

        wct.register("expired", 42, time.monotonic() - 0.1)

        with patch("mutmut_win.process.timeout._kill_process"):
            wct._check_deadlines()

        with wct._lock:
            assert "expired" not in wct._entries

    def test_mixed_deadlines(self) -> None:
        """Expired entries trigger events; future entries survive."""
        eq: _SimpleQueue = _SimpleQueue()
        wct = WallClockTimeout(eq)  # type: ignore[arg-type]

        wct.register("past", 1, time.monotonic() - 1.0)
        wct.register("future", 2, time.monotonic() + 60.0)

        with patch("mutmut_win.process.timeout._kill_process"):
            wct._check_deadlines()

        assert not eq.empty()
        raw = eq.get()
        event = TaskTimedOut.model_validate(raw)
        assert event.mutant_name == "past"

        with wct._lock:
            assert "future" in wct._entries
            assert "past" not in wct._entries


class TestWallClockTimeoutThread:
    """Integration-level tests that exercise the monitor thread."""

    def test_start_stop_no_entries(self) -> None:
        """Start + stop with no entries must not raise."""
        eq: _SimpleQueue = _SimpleQueue()
        wct = WallClockTimeout(eq)  # type: ignore[arg-type]
        wct.start()
        wct.stop()
        assert wct._thread is None

    def test_thread_fires_timed_out_event(self) -> None:
        """Short timeout must produce TaskTimedOut event via the thread."""
        eq: _SimpleQueue = _SimpleQueue()
        wct = WallClockTimeout(eq)  # type: ignore[arg-type]

        wct.start()
        deadline = time.monotonic() + 0.05  # 50 ms from now
        with patch("mutmut_win.process.timeout._kill_process"):
            wct.register("fast_mutant", 7777, deadline)
            # Give the monitor thread time to detect the expiry (max 2 s).
            start = time.monotonic()
            while eq.empty() and time.monotonic() - start < 2.0:
                time.sleep(0.05)

        wct.stop()

        assert not eq.empty(), "Expected a TaskTimedOut event within 2 s"
        event = TaskTimedOut.model_validate(eq.get())
        assert event.mutant_name == "fast_mutant"
        assert event.worker_pid == 7777

    def test_unregistered_before_deadline_no_event(self) -> None:
        """Unregistering before the deadline must suppress the event."""
        eq: _SimpleQueue = _SimpleQueue()
        wct = WallClockTimeout(eq)  # type: ignore[arg-type]

        wct.start()
        wct.register("safe_mutant", 1234, time.monotonic() + 60.0)
        wct.unregister("safe_mutant")
        time.sleep(0.1)  # let thread run at least once
        wct.stop()

        assert eq.empty(), "No event expected for unregistered mutant"

    def test_start_is_idempotent(self) -> None:
        """Calling start() twice must not create a second thread."""
        eq: _SimpleQueue = _SimpleQueue()
        wct = WallClockTimeout(eq)  # type: ignore[arg-type]
        wct.start()
        first_thread = wct._thread
        wct.start()
        assert wct._thread is first_thread
        wct.stop()


class TestKillProcess:
    """Tests for the _kill_process helper."""

    def test_kill_nonexistent_pid_is_silent(self) -> None:
        """Killing a non-existent PID must not raise."""
        # Very large PID is unlikely to exist.
        _kill_process(99999999)  # must not raise

    def test_kill_calls_os_kill(self) -> None:
        """_kill_process must call os.kill with the given PID."""
        import signal

        captured: list[tuple[int, int]] = []

        def fake_os_kill(pid: int, sig: int) -> None:
            captured.append((pid, sig))

        with patch("mutmut_win.process.timeout.os.kill", side_effect=fake_os_kill):
            _kill_process(1234)

        assert len(captured) == 1
        pid_sent, sig_sent = captured[0]
        assert pid_sent == 1234
        assert sig_sent == signal.SIGTERM

    def test_kill_process_lookup_error_is_silent(self) -> None:
        """ProcessLookupError from os.kill must be swallowed silently."""
        with patch("mutmut_win.process.timeout.os.kill", side_effect=ProcessLookupError):
            _kill_process(9999)  # must not raise

    def test_kill_permission_error_is_silent(self) -> None:
        """PermissionError from os.kill must be swallowed silently."""
        with patch("mutmut_win.process.timeout.os.kill", side_effect=PermissionError):
            _kill_process(9999)  # must not raise
