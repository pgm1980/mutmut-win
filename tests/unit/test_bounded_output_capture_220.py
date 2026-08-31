"""Regression tests for bounded subprocess output capture (MW220-024)."""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
from typing import TYPE_CHECKING

import mutmut_win.process.output_capture as output_capture_module
from mutmut_win.process.output_capture import BoundedOutputCapture

if TYPE_CHECKING:
    import pytest


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
