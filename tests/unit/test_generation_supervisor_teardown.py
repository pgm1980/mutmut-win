"""Unit regressions for bounded generation-supervisor teardown."""

from __future__ import annotations

from mutmut_win.process.generation_supervisor import (
    _SUCCESS_JOIN_TIMEOUT_SECONDS,
    _join_completed_supervisor,
)


class _DelayedSuccessfulProcess:
    """Minimal process fake that exits only during the generous DONE join."""

    exitcode = 0

    def __init__(self) -> None:
        self.alive = True
        self.join_timeout: float | None = None

    def join(self, *, timeout: float) -> None:
        self.join_timeout = timeout
        self.alive = False

    def is_alive(self) -> bool:
        return self.alive


def test_done_teardown_uses_its_own_generous_bounded_timeout() -> None:
    process = _DelayedSuccessfulProcess()

    _join_completed_supervisor(process)  # type: ignore[arg-type]

    assert process.join_timeout == _SUCCESS_JOIN_TIMEOUT_SECONDS
    assert process.is_alive() is False
