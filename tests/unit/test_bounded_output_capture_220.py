"""Regression tests for bounded subprocess output capture (MW220-024)."""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import time

import pytest

import mutmut_win.process.output_capture as output_capture_module
from mutmut_win.process.output_capture import BoundedOutputCapture


def test_capture_counts_all_bytes_but_retains_only_bounded_tail() -> None:
    capture = BoundedOutputCapture(max_tail_bytes=32)
    payload = b"discard-me\n" + b"x" * 64 + b"\nlast-line\n"

    os.write(capture.writer_fd, payload)
    capture.close_writer()
    capture.close()

    assert capture.total_bytes == len(payload)
    tail = capture.last_lines(10)
    assert tail is not None
    assert tail.endswith("last-line")
    assert "discard-me" not in tail
    assert len(tail.encode("utf-8")) <= 32


def test_large_real_subprocess_cannot_fill_a_pipe_or_grow_a_log_file() -> None:
    size = 5 * 1024 * 1024
    capture = BoundedOutputCapture(max_tail_bytes=4096)
    process = subprocess.Popen(  # noqa: S603 - fixed interpreter command
        [sys.executable, "-c", f"import sys; sys.stdout.buffer.write(b'x' * {size})"],
        stdout=capture.writer_fd,
        stderr=subprocess.STDOUT,
    )
    capture.close_writer()

    assert process.wait(timeout=15) == 0
    capture.close()

    assert capture.total_bytes == size
    tail = capture.last_lines(1)
    assert tail is not None
    assert len(tail) == 4096


def test_close_is_bounded_even_if_an_escaped_writer_never_reaches_eof() -> None:
    capture = BoundedOutputCapture(max_tail_bytes=64)
    escaped_writer = os.dup(capture.writer_fd)
    capture.close_writer()

    started = time.monotonic()
    capture.close(timeout=0.2)
    elapsed = time.monotonic() - started
    os.close(escaped_writer)

    assert elapsed < 1.0


def test_close_drains_bytes_written_after_an_empty_read_before_stop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A close racing an empty reader pass must not discard phase output.

    The old drain loop checked ``stop`` after its non-blocking read.  If the
    child wrote its final diagnostic between those operations, the reader
    exited without making another read and forced-fail attribution became
    intermittently false.  Hold that exact interleaving deterministically.
    """
    real_start = threading.Thread.start
    monkeypatch.setattr(threading.Thread, "start", lambda _thread: None)
    capture = BoundedOutputCapture(max_tail_bytes=128)
    monkeypatch.setattr(threading.Thread, "start", real_start)

    real_read = os.read
    empty_read_observed = threading.Event()
    release_empty_read = threading.Event()
    first_capture_read = True

    def controlled_read(fd: int, size: int) -> bytes:
        nonlocal first_capture_read
        if fd == capture._read_fd and first_capture_read:
            first_capture_read = False
            try:
                return real_read(fd, size)
            except BlockingIOError:
                empty_read_observed.set()
                assert release_empty_read.wait(timeout=2)
                raise
        return real_read(fd, size)

    monkeypatch.setattr(output_capture_module.os, "read", controlled_read)
    capture._reader.start()
    assert empty_read_observed.wait(timeout=2)

    payload = b"MutmutProgrammaticFailException: Forced fail\n"
    os.write(capture.writer_fd, payload)
    capture.close_writer()
    capture._stop.set()  # force the historical race window
    release_empty_read.set()
    capture.close()

    assert capture.text() == payload.decode()


# ---------------------------------------------------------------------------
# M-109: exception-safe construction — no pipe-descriptor leaks on failure
# ---------------------------------------------------------------------------


def _recording_pipe(monkeypatch: pytest.MonkeyPatch) -> list[tuple[int, int]]:
    """Record the fd pairs created by output_capture's os.pipe calls."""
    created: list[tuple[int, int]] = []
    real_pipe = os.pipe

    def wrapper() -> tuple[int, int]:
        fds = real_pipe()
        created.append(fds)
        return fds

    monkeypatch.setattr(output_capture_module.os, "pipe", wrapper)
    return created


def _recording_close(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """Record every os.close issued through output_capture's os module."""
    closed: list[int] = []
    real_close = os.close

    def wrapper(fd: int) -> None:
        closed.append(fd)
        real_close(fd)

    monkeypatch.setattr(output_capture_module.os, "close", wrapper)
    return closed


def test_failed_reader_start_closes_both_pipe_fds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Thread/handle exhaustion during start() must not leak either fd."""
    created = _recording_pipe(monkeypatch)
    closed = _recording_close(monkeypatch)

    class _StartFailsThread(threading.Thread):
        def start(self) -> None:
            raise RuntimeError("can't start new thread")

    monkeypatch.setattr(threading, "Thread", _StartFailsThread)

    with pytest.raises(RuntimeError, match="can't start new thread"):
        BoundedOutputCapture()

    read_fd, write_fd = created[0]
    assert closed.count(read_fd) == 1
    assert closed.count(write_fd) == 1


def test_failed_set_blocking_closes_both_pipe_fds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created = _recording_pipe(monkeypatch)
    closed = _recording_close(monkeypatch)

    def failing_set_blocking(_fd: int, _blocking: bool) -> None:
        raise OSError("simulated set_blocking failure")

    monkeypatch.setattr(output_capture_module.os, "set_blocking", failing_set_blocking)

    with pytest.raises(OSError, match="set_blocking"):
        BoundedOutputCapture()

    read_fd, write_fd = created[0]
    assert closed.count(read_fd) == 1
    assert closed.count(write_fd) == 1


def test_interrupt_after_reader_start_leaves_read_fd_to_the_reader(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """KeyboardInterrupt racing a genuinely started reader must not double-close.

    The ownership handshake decides under the lock: once the reader took
    ``read_fd``, the abort path only closes the writer and lets the reader see
    EOF and close ``read_fd`` exactly once in its finally."""
    created = _recording_pipe(monkeypatch)
    closed = _recording_close(monkeypatch)

    class _InterruptAfterOwnershipThread(threading.Thread):
        def start(self) -> None:
            super().start()
            capture = self._target.__self__  # type: ignore[union-attr]
            deadline = time.monotonic() + 2.0
            while not capture._reader_owns_fd and time.monotonic() < deadline:
                time.sleep(0.005)
            raise KeyboardInterrupt

    monkeypatch.setattr(threading, "Thread", _InterruptAfterOwnershipThread)

    with pytest.raises(KeyboardInterrupt):
        BoundedOutputCapture()

    read_fd, write_fd = created[0]
    assert closed.count(write_fd) == 1  # closed once by the abort path
    assert closed.count(read_fd) == 1  # closed once, by the reader's finally
