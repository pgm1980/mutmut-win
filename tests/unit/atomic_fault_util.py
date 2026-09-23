"""Fault-injection harness for atomic write paths (remediation AP-00 / Q-01).

Targeted, scoped fault injection for the atomic publication machinery and its
operating-system seams (``os.replace``, ``os.open``, ``os.fsync``,
``os.lstat``) plus a pass-through call recorder for release/close paths.

Design rules (from the remediation handover, AP-00):

- Injection is always scoped: every helper is a context manager built on
  ``unittest.mock.patch``, so patches cannot leak past the ``with`` block.
  This also satisfies the phase-guard monkeypatch hygiene convention without
  requiring a ``monkeypatch`` fixture (no ``os``/``Path``/``time`` patch
  survives the context manager, so no explicit ``monkeypatch.undo()`` call is
  needed by callers).
- Failure modes are narrow by construction: fail only the first call, only
  the n-th call, or every call of the target. All other calls delegate to the
  real implementation.
- The injected exception is re-raised as-is, preserving the production
  taxonomy (``UnsafeAtomicWriteError``, ``AtomicReplaceError``,
  ``AtomicPublicationRaceError``, plain ``OSError`` subclasses, ...).

Consumers are the remediation regression tests for M-005, M-008, M-010,
M-011, M-012, M-013, M-066, M-067, M-068, M-069, M-070, M-091 and M-092.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal
from unittest.mock import patch

if TYPE_CHECKING:
    from types import TracebackType

__all__ = ["CallRecord", "CallSpy", "FaultRecorder", "inject_call_fault", "record_calls"]

#: Selectable failure policy for :func:`inject_call_fault`.
FaultMode = Literal["first", "nth", "always"]


@dataclass(frozen=True)
class CallRecord:
    """One observed call: positional and keyword arguments."""

    args: tuple[Any, ...]
    kwargs: dict[str, Any]


@dataclass
class FaultRecorder:
    """Observation log of an injected fault harness.

    Attributes:
        calls: Every call made to the target, in order.
        injected_failures: Number of calls that were failed by injection.
    """

    calls: list[CallRecord] = field(default_factory=list)
    injected_failures: int = 0

    @property
    def call_count(self) -> int:
        """Return how often the target was called."""
        return len(self.calls)


def _validate_dotted_target(target: str) -> None:
    """Reject targets that are not a dotted ``module.attribute`` path."""

    module_name, separator, attribute = target.rpartition(".")
    if not separator or not module_name or not attribute:
        msg = f"fault target must be a dotted 'module.attribute' path, got {target!r}"
        raise ValueError(msg)


def _resolve_target(target: str) -> tuple[Any, str]:
    """Resolve a dotted ``module.attribute`` path to (module, attribute)."""

    _validate_dotted_target(target)
    module_name, _, attribute = target.rpartition(".")
    module = importlib.import_module(module_name)
    return module, attribute


def inject_call_fault(
    target: str,
    *,
    mode: FaultMode,
    exception: BaseException,
    n: int = 1,
) -> _FaultInjector:
    """Return a context manager that fails selected calls of ``target``.

    Args:
        target: Dotted path of the callable to patch, e.g.
            ``"os.replace"`` or ``"mutmut_win.atomic_file.atomic_write_bytes"``.
        mode: ``"first"`` fails only call #1, ``"nth"`` only call ``n``,
            ``"always"`` every call.
        exception: Exception instance raised for each failed call.
        n: The one-based index used by ``mode="nth"``.

    Returns:
        Context manager yielding a :class:`FaultRecorder`.
    """

    if mode not in ("first", "nth", "always"):
        msg = f"unknown fault mode {mode!r}"
        raise ValueError(msg)
    if n < 1:
        msg = f"n must be >= 1, got {n}"
        raise ValueError(msg)
    _validate_dotted_target(target)
    return _FaultInjector(target, mode, exception, n)


class _FaultInjector:
    """Scoped patch that fails selected calls and records every call."""

    def __init__(self, target: str, mode: FaultMode, exception: BaseException, n: int) -> None:
        self._target = target
        self._mode = mode
        self._exception = exception
        self._n = n
        self.recorder = FaultRecorder()

    def __enter__(self) -> FaultRecorder:
        module, attribute = _resolve_target(self._target)
        real = getattr(module, attribute)
        if not callable(real):
            msg = f"fault target {self._target!r} is not callable"
            raise TypeError(msg)
        recorder = self.recorder

        def faulting_call(*args: Any, **kwargs: Any) -> Any:
            index = recorder.call_count + 1
            recorder.calls.append(CallRecord(args=args, kwargs=kwargs))
            should_fail = (
                self._mode == "always"
                or (self._mode == "first" and index == 1)
                or (self._mode == "nth" and index == self._n)
            )
            if should_fail:
                recorder.injected_failures += 1
                raise self._exception
            return real(*args, **kwargs)

        self._patcher = patch(self._target, new=faulting_call)
        self._patcher.start()
        return recorder

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self._patcher.stop()


class CallSpy:
    """Scoped pass-through recorder that never changes behaviour."""

    def __init__(self, target: str) -> None:
        self._target = target
        self.recorder = FaultRecorder()

    def __enter__(self) -> FaultRecorder:
        module, attribute = _resolve_target(self._target)
        real = getattr(module, attribute)
        if not callable(real):
            msg = f"spy target {self._target!r} is not callable"
            raise TypeError(msg)
        recorder = self.recorder

        def spying_call(*args: Any, **kwargs: Any) -> Any:
            recorder.calls.append(CallRecord(args=args, kwargs=kwargs))
            return real(*args, **kwargs)

        self._patcher = patch(self._target, new=spying_call)
        self._patcher.start()
        return recorder

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self._patcher.stop()


def record_calls(target: str) -> CallSpy:
    """Return a context manager recording every call of ``target``.

    Unlike :func:`inject_call_fault` this never raises: it observes release,
    close, and cleanup paths (e.g. ``CloseHandle``-like seam functions) while
    the real implementation keeps running.
    """

    _validate_dotted_target(target)
    return CallSpy(target)
