"""Unit regressions for bounded generation-supervisor teardown."""

from __future__ import annotations

import inspect

import pytest

from mutmut_win.process.generation_supervisor import (
    _SUCCESS_JOIN_TIMEOUT_SECONDS,
    GenerationSupervisorCrashedError,
    _join_completed_supervisor,
    run_generation_supervised,
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


class _StuckAfterDoneProcess:
    """Minimal process fake that ignores the DONE join and stays alive."""

    exitcode = 0

    def __init__(self) -> None:
        self.join_timeout: float | None = None

    def join(self, *, timeout: float) -> None:
        self.join_timeout = timeout

    def is_alive(self) -> bool:
        return True


class _UncleanExitProcess:
    """Minimal process fake that exits immediately after DONE with code 3."""

    exitcode = 3

    def __init__(self) -> None:
        self.join_timeout: float | None = None

    def join(self, *, timeout: float) -> None:
        self.join_timeout = timeout

    def is_alive(self) -> bool:
        return False


def test_done_teardown_uses_its_own_generous_bounded_timeout() -> None:
    process = _DelayedSuccessfulProcess()

    _join_completed_supervisor(process)  # type: ignore[arg-type]

    assert process.join_timeout == _SUCCESS_JOIN_TIMEOUT_SECONDS
    assert process.is_alive() is False


def test_done_teardown_still_alive_discards_results_fail_closed() -> None:
    process = _StuckAfterDoneProcess()

    with pytest.raises(
        GenerationSupervisorCrashedError,
        match="did not exit after reporting completion",
    ):
        _join_completed_supervisor(process)  # type: ignore[arg-type]

    assert process.join_timeout == _SUCCESS_JOIN_TIMEOUT_SECONDS


def test_done_teardown_nonzero_exit_discards_results_fail_closed() -> None:
    process = _UncleanExitProcess()

    with pytest.raises(
        GenerationSupervisorCrashedError,
        match=r"exited with code 3 after completion",
    ):
        _join_completed_supervisor(process)  # type: ignore[arg-type]

    assert process.join_timeout == _SUCCESS_JOIN_TIMEOUT_SECONDS


def test_crashed_error_docstring_documents_post_done_teardown() -> None:
    """The exported crash class must cover post-DONE teardown failures (M-111)."""
    doc = inspect.getdoc(GenerationSupervisorCrashedError)

    assert doc is not None
    assert "after reporting completion" in doc


def test_run_generation_supervised_raises_doc_covers_post_done_teardown() -> None:
    """The Raises section must name the post-DONE crash causes (M-111)."""
    raw_doc = inspect.getdoc(run_generation_supervised)
    assert raw_doc is not None
    doc = " ".join(raw_doc.split())

    assert "after reporting completion" in doc
