"""Unit contracts for the TUI foreground launcher (M-057 / issue #158).

``run_foreground_contained`` is the fail-closed launcher every browser TUI
action must use instead of a bare ``subprocess.run``: create a
kill-on-close Job Object, start the child atomically inside it
(``AtomicJobPopen``, no pipes, no creationflags — the shared console is
inherited), wait, and close the job in ``finally`` so the kernel reaps
any surviving descendant.
"""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING, Any

import pytest

from mutmut_win.exceptions import ProcessContainmentError
from mutmut_win.process import foreground

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence


class _FakePopen:
    """Scripted Popen double recording wait/kill calls."""

    def __init__(self, wait_results: list[Any]) -> None:
        self._wait_results = list(wait_results)
        self.wait_calls: list[dict[str, Any]] = []
        self.killed = False

    def wait(self, timeout: float | None = None) -> int:
        self.wait_calls.append({"timeout": timeout})
        assert self._wait_results, "wait() called more often than scripted"
        result = self._wait_results.pop(0)
        if isinstance(result, BaseException):
            raise result
        return int(result)

    def kill(self) -> None:
        self.killed = True


_JOB_HANDLE = 4242


def _install(
    monkeypatch: pytest.MonkeyPatch,
    *,
    create: Callable[[], int] | Callable[[], Any],
    popen: Any,
) -> list[int]:
    """Patch the launcher's module-level collaborators; return close_job log."""
    closed: list[int] = []
    monkeypatch.setattr(foreground, "create_kill_on_close_job", create)
    monkeypatch.setattr(foreground, "AtomicJobPopen", popen)
    monkeypatch.setattr(foreground, "close_job", closed.append)
    return closed


def _job_creator() -> int:
    return _JOB_HANDLE


def test_job_creation_oserror_is_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    """No Job Object -> ProcessContainmentError, nothing is ever started."""

    def failing_create() -> int:
        raise OSError("CreateJobObjectW failed (error 5)")

    def unexpected_popen(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("AtomicJobPopen must not run without a job")

    closed = _install(monkeypatch, create=failing_create, popen=unexpected_popen)

    with pytest.raises(
        ProcessContainmentError,
        match=(
            r"^Could not create a kill-on-close Job Object for the foreground "
            r"child; refusing to start an uncontained process\.$"
        ),
    ):
        foreground.run_foreground_contained(["x"])

    assert closed == []


def test_job_creation_runtimeerror_is_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    """The non-Windows guard RuntimeError maps to the same domain error."""

    def failing_create() -> int:
        raise RuntimeError("Job Objects are only available on Windows")

    def unexpected_popen(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("AtomicJobPopen must not run without a job")

    closed = _install(monkeypatch, create=failing_create, popen=unexpected_popen)

    with pytest.raises(
        ProcessContainmentError,
        match=(
            r"^Could not create a kill-on-close Job Object for the foreground "
            r"child; refusing to start an uncontained process\.$"
        ),
    ):
        foreground.run_foreground_contained(["x"])

    assert closed == []


def test_returns_child_exit_code_and_closes_job(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Happy path: start inside the job, return the raw exit code, close once."""
    fake = _FakePopen(wait_results=[3])
    seen: dict[str, Any] = {}

    def recording_popen(cmd: list[str], *, job_handle: int) -> _FakePopen:
        seen["cmd"] = cmd
        seen["job_handle"] = job_handle
        return fake

    closed = _install(monkeypatch, create=_job_creator, popen=recording_popen)

    # A Sequence (not list) on purpose: the launcher must convert for list2cmdline.
    cmd: Sequence[str] = ("python", "-m", "mutmut_win", "run")
    assert foreground.run_foreground_contained(cmd) == 3

    # Exactly the two documented kwargs reach AtomicJobPopen — no pipes, no
    # creationflags (console must be inherited so Ctrl-C reaches the child).
    assert seen == {"cmd": ["python", "-m", "mutmut_win", "run"], "job_handle": _JOB_HANDLE}
    assert fake.wait_calls == [{"timeout": None}]
    assert not fake.killed
    assert closed == [_JOB_HANDLE]


def test_start_failure_closes_job_exactly_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """CreateProcess failure -> wrapped domain error + close_job exactly once."""

    def failing_popen(_cmd: list[str], *, job_handle: int) -> None:
        assert job_handle == _JOB_HANDLE, "start must target the created job"
        raise FileNotFoundError("no such executable")

    closed = _install(monkeypatch, create=_job_creator, popen=failing_popen)

    with pytest.raises(
        ProcessContainmentError,
        match=(
            r"^Could not start the foreground child inside its Windows "
            r"Job Object; refusing an uncontained launch\.$"
        ),
    ):
        foreground.run_foreground_contained(["x"])

    assert closed == [_JOB_HANDLE]


def test_popen_containment_error_propagates_unwrapped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The launcher never double-wraps the fail-closed domain error."""

    def refusing_popen(_cmd: list[str], *, job_handle: int) -> None:
        assert job_handle == _JOB_HANDLE, "start must target the created job"
        raise ProcessContainmentError("audited runtime only")

    closed = _install(monkeypatch, create=_job_creator, popen=refusing_popen)

    with pytest.raises(ProcessContainmentError, match="audited runtime only"):
        foreground.run_foreground_contained(["x"])

    assert closed == [_JOB_HANDLE]


def test_keyboard_interrupt_gives_bounded_grace_then_kills(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ctrl-C: bounded grace for the child's own shutdown, then kill, then re-raise."""
    fake = _FakePopen(wait_results=[KeyboardInterrupt(), 0])

    def happy_popen(_cmd: list[str], *, job_handle: int) -> _FakePopen:
        assert job_handle == _JOB_HANDLE, "start must target the created job"
        return fake

    closed = _install(monkeypatch, create=_job_creator, popen=happy_popen)

    with pytest.raises(KeyboardInterrupt):
        foreground.run_foreground_contained(["x"])

    assert fake.wait_calls[0] == {"timeout": None}
    assert fake.wait_calls[1] == {"timeout": foreground._CTRL_C_GRACE_SECONDS}
    assert fake.killed
    assert closed == [_JOB_HANDLE]


def test_keyboard_interrupt_grace_expiry_still_kills_and_closes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A child that ignores Ctrl-C past the grace period is hard-killed."""
    fake = _FakePopen(
        wait_results=[KeyboardInterrupt(), subprocess.TimeoutExpired(cmd="x", timeout=0.1)]
    )

    def happy_popen(_cmd: list[str], *, job_handle: int) -> _FakePopen:
        assert job_handle == _JOB_HANDLE, "start must target the created job"
        return fake

    closed = _install(monkeypatch, create=_job_creator, popen=happy_popen)

    with pytest.raises(KeyboardInterrupt):
        foreground.run_foreground_contained(["x"])

    assert fake.killed
    assert closed == [_JOB_HANDLE]
