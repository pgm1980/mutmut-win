"""Faulthandler watchdog reporting Python stacks when prelude progress stalls.

MBR-2026-09-14-01 (Abschnitt 8): run startup could sit silently for 15-60
minutes with zero diagnostics.  The watchdog dumps the current Python stack
to stderr whenever no observable progress happened for the stall interval,
turning an undiagnosable hang into an immediate one-look diagnosis.

The watchdog never kills the process: legitimately slow phases (a large
dependency walk, for example) keep running and simply re-arm on progress, so
the report is evidence, not a verdict.
"""

from __future__ import annotations

import faulthandler
import io
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from types import TracebackType
    from typing import TextIO

#: Default no-progress interval before a stack is dumped.
DEFAULT_STALL_TIMEOUT_SECONDS = 60.0


def _stream_with_fileno(stream: TextIO | None) -> TextIO | None:
    """Return *stream* when faulthandler can dump into it, else a fallback.

    ``faulthandler`` writes through a real file descriptor.  Capturing
    harnesses (pytest, some CI wrappers) replace ``sys.stderr`` with an
    object that has none; fall back to the interpreter's original stderr so
    watchdog evidence still reaches a real stream, and give up silently
    when even that is unavailable.
    """
    for candidate in (stream, sys.__stderr__):
        if candidate is None:
            continue
        try:
            candidate.fileno()
        except (io.UnsupportedOperation, AttributeError, OSError, ValueError):  # fmt: skip
            continue
        return candidate
    return None


class StallWatchdog:
    """Dump the Python stack to stderr after a no-progress interval.

    ``arm`` starts a repeating faulthandler timer; ``progress`` cancels and
    re-arms it at every observable step; ``close`` disarms it.  The timer is
    process-global (one live watchdog at a time), which matches the
    single-run-per-process prelude it guards.
    """

    __slots__ = ("_armed", "_target", "_timeout")

    def __init__(
        self,
        timeout: float = DEFAULT_STALL_TIMEOUT_SECONDS,
        *,
        file: TextIO | None = None,
    ) -> None:
        self._timeout = timeout
        self._target = _stream_with_fileno(file if file is not None else sys.stderr)
        self._armed = False

    @property
    def armed(self) -> bool:
        """Whether the stall timer is currently active."""
        return self._armed

    @property
    def timeout(self) -> float:
        """The configured no-progress interval in seconds."""
        return self._timeout

    def arm(self) -> None:
        """Start the repeating stall timer.

        A no-op when no stream with a real file descriptor is available:
        missing diagnostics must never break the guarded phase itself.
        """
        if self._target is None:
            return
        faulthandler.dump_traceback_later(self._timeout, repeat=True, file=self._target)
        self._armed = True

    def progress(self) -> None:
        """Report observable progress and restart the stall timer.

        A no-op while disarmed, so call sites do not need their own state.
        """
        if not self._armed or self._target is None:
            return
        faulthandler.cancel_dump_traceback_later()
        faulthandler.dump_traceback_later(self._timeout, repeat=True, file=self._target)

    def close(self) -> None:
        """Disarm the stall timer; safe to call repeatedly."""
        if self._armed:
            faulthandler.cancel_dump_traceback_later()
            self._armed = False

    def __enter__(self) -> StallWatchdog:
        self.arm()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()
