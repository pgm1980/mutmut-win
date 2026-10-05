"""Bounded, deadlock-safe subprocess output capture.

``subprocess.PIPE`` without a concurrent reader can deadlock once the kernel
buffer fills; an ordinary temporary file cannot deadlock but lets a runaway
test exhaust the disk.  ``BoundedOutputCapture`` combines a pipe with a
dedicated non-blocking drain thread. It retains only a fixed-size byte tail
while counting all bytes monotonically for the infinite-loop classifier.
"""

from __future__ import annotations

import contextlib
import os
import threading
from typing import Final

_READ_CHUNK_BYTES: Final[int] = 64 * 1024
_POLL_SECONDS: Final[float] = 0.01
DEFAULT_TAIL_BYTES: Final[int] = 1024 * 1024


class BoundedOutputCapture:
    """Continuously drain one OS pipe into a bounded in-memory tail.

    The write descriptor is suitable for ``Popen(stdout=...)``. Call
    :meth:`close_writer` immediately after the child is created so EOF reflects
    only handles inherited by the subprocess tree. :meth:`close` is bounded;
    the daemon reader never participates in interpreter shutdown waits.

    Construction is exception-safe: if anything fails after ``os.pipe()``
    (non-blocking setup, thread start), both descriptors are released before
    the original exception is re-raised.  Ownership of the read side is
    decided under the state lock, so a reader that already started observes
    EOF and closes its own descriptor — a failed construction can never leak
    or double-close a descriptor.
    """

    def __init__(self, *, max_tail_bytes: int = DEFAULT_TAIL_BYTES) -> None:
        if max_tail_bytes <= 0:
            raise ValueError("max_tail_bytes must be positive")
        self._max_tail_bytes = max_tail_bytes
        # fd-independent state comes FIRST: nothing below can observe a
        # half-initialised object, and the constructor/reader ownership
        # handshake (see _drain/_abort_construction) already owns its lock
        # before the pipe exists.
        self._state_lock = threading.Lock()
        self._tail = bytearray()
        self._total_bytes = 0
        self._stop = threading.Event()
        self._closed = False
        self._construction_aborted = False
        self._reader_owns_fd = False
        self._reader = threading.Thread(
            target=self._drain,
            name="mutmut-output-capture",
            daemon=True,
        )
        self._read_fd, self._write_fd = os.pipe()
        try:
            os.set_blocking(self._read_fd, False)
            self._reader.start()
        except BaseException:
            self._abort_construction()
            raise

    def _abort_construction(self) -> None:
        """Roll back a failed construction without leaking pipe descriptors.

        Runs for every exception between ``os.pipe()`` and a successfully
        started reader.  Ownership of ``read_fd`` is decided under the state
        lock: if the reader already took it, it observes EOF after the writer
        close and closes ``read_fd`` itself in its finally; otherwise this
        method closes it here — exactly once either way.  Nothing in here may
        raise: the original constructor exception propagates unchanged
        (M-109).
        """
        self._closed = True
        with self._state_lock:
            self._construction_aborted = True
            reader_owns_fd = self._reader_owns_fd
        self.close_writer()
        if not reader_owns_fd:
            read_fd = self._read_fd
            self._read_fd = -1
            with contextlib.suppress(OSError):
                os.close(read_fd)
            return
        self._stop.set()
        self._reader.join(timeout=1.0)

    @property
    def writer_fd(self) -> int:
        """Return the still-open descriptor to pass to ``subprocess.Popen``."""
        if self._write_fd < 0:
            raise RuntimeError("output-capture writer is already closed")
        return self._write_fd

    @property
    def total_bytes(self) -> int:
        """Return the monotonic number of bytes drained from the whole tree."""
        with self._state_lock:
            return self._total_bytes

    @property
    def truncated(self) -> bool:
        """Whether bytes were discarded from the retained output tail."""
        with self._state_lock:
            return self._total_bytes > self._max_tail_bytes

    def text(self) -> str:
        """Decode and return the retained output tail."""
        with self._state_lock:
            payload = bytes(self._tail)
        return payload.decode("utf-8", errors="replace")

    def close_writer(self) -> None:
        """Close the parent's writer copy without affecting inherited copies."""
        writer_fd = self._write_fd
        if writer_fd < 0:
            return
        self._write_fd = -1
        with contextlib.suppress(OSError):
            os.close(writer_fd)

    def close(self, timeout: float = 1.0) -> None:
        """Stop after draining currently available data; never wait unboundedly."""
        if self._closed:
            return
        self.close_writer()
        self._stop.set()
        self._reader.join(max(0.0, timeout))
        self._closed = True

    def last_lines(self, count: int) -> str | None:
        """Decode and return at most the last *count* captured text lines."""
        if count <= 0:
            return None
        text = self.text()
        if not text:
            return None
        lines = text.splitlines()
        return "\n".join(lines[-count:]) if lines else None

    def _drain(self) -> None:
        # Construction handshake (M-109): the constructor's abort path and
        # the reader race for the ownership of read_fd.  Whoever acquires
        # the state lock first decides — an aborted construction keeps the
        # fd for the constructor, and the reader must then never touch it,
        # not even in the finally below.
        with self._state_lock:
            if self._construction_aborted:
                return
            self._reader_owns_fd = True
        try:
            while True:
                # Snapshot before reading.  If ``close()`` sets the event
                # after a non-blocking read found no data, this iteration
                # must not exit: bytes written just before the parent's
                # writer was closed may already be in the pipe.  The next
                # iteration observes ``stop`` at its start and performs one
                # final, post-stop drain pass before returning.  This also
                # remains bounded when an escaped descendant keeps a writer
                # open, because that final pass is non-blocking.
                stop_was_set = self._stop.is_set()
                while True:
                    try:
                        chunk = os.read(self._read_fd, _READ_CHUNK_BYTES)
                    except BlockingIOError:
                        break
                    except OSError:
                        return
                    if not chunk:
                        return
                    self._record(chunk)

                if stop_was_set:
                    return
                self._stop.wait(_POLL_SECONDS)
        finally:
            with contextlib.suppress(OSError):
                os.close(self._read_fd)

    def _record(self, chunk: bytes) -> None:
        with self._state_lock:
            self._total_bytes += len(chunk)
            self._tail.extend(chunk)
            overflow = len(self._tail) - self._max_tail_bytes
            if overflow > 0:
                del self._tail[:overflow]

    def __enter__(self) -> BoundedOutputCapture:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()
