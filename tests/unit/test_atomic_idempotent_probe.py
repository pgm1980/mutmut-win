"""Contract tests for the idempotent probe's transient-error taxonomy (Q-30).

The idempotency probe of :func:`mutmut_win.atomic_file.ensure_atomic_bytes`
runs once per task, phase and stats publication against the frozen staging
tree.  Before M-012 its parent inspection ran without any retry: a single
transient Windows filter-driver failure escaped as ``UnsafeAtomicWriteError``
and aborted the whole run through the fatal ``PytestBoundaryError`` channel.

These tests pin the taxonomy agreed in the AP-31 handover:

- the parent identity of the probe is captured through the bounded retry
  ladder (:func:`_capture_parent_identity`), so transient resolve failures
  are absorbed without republishing byte-identical frozen leaves;
- exhausting the ladder still fails closed with ``UnsafeAtomicWriteError``;
- structural rejections (link/reparse/missing parents) stay immediate.
"""

from __future__ import annotations

import tempfile
import time
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from mutmut_win.atomic_file import (
    _PARENT_CAPTURE_RETRY_DELAYS,
    UnsafeAtomicWriteError,
    ensure_atomic_bytes,
)
from mutmut_win.process.worker import prepare_pytest_phase_guard


def test_transient_parent_resolve_failure_in_idempotent_probe_is_absorbed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "mutants" / "_mutmut_phase_guard.py"
    payload = b"# frozen staging sentinel\n"
    target.parent.mkdir(parents=True)
    ensure_atomic_bytes(target, payload)
    before = target.stat()

    real_resolve = Path.resolve
    state = {"failed": False}

    def flaky_resolve(self: Path, strict: bool = False) -> Path:
        if self == tmp_path and not state["failed"]:
            state["failed"] = True
            raise OSError(5, "Access is denied (simulated filter lock)")
        return real_resolve(self, strict=strict)

    monkeypatch.setattr(Path, "resolve", flaky_resolve)
    monkeypatch.setattr(time, "sleep", lambda _seconds: None)

    ensure_atomic_bytes(target, payload)
    monkeypatch.undo()

    after = target.stat()
    assert (after.st_dev, after.st_ino) == (before.st_dev, before.st_ino)


def test_transient_parent_resolve_failure_in_phase_guard_publish_is_absorbed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    staging = tmp_path / "mutants"
    staging.mkdir()
    prepare_pytest_phase_guard({}, staging)

    real_resolve = Path.resolve
    state = {"failed": False}

    def flaky_resolve(self: Path, strict: bool = False) -> Path:
        if self == staging and not state["failed"]:
            state["failed"] = True
            raise OSError(5, "Access is denied (simulated filter lock)")
        return real_resolve(self, strict=strict)

    monkeypatch.setattr(Path, "resolve", flaky_resolve)
    monkeypatch.setattr(time, "sleep", lambda _seconds: None)

    marker_path, _token = prepare_pytest_phase_guard({}, staging)
    monkeypatch.undo()

    assert (staging / "_mutmut_phase_guard.py").is_file()
    assert marker_path.is_absolute()


@given(k=st.integers(min_value=0, max_value=len(_PARENT_CAPTURE_RETRY_DELAYS)))
@settings(deadline=None)
def test_up_to_ladder_length_transient_parent_failures_are_absorbed(k: int) -> None:
    with (
        tempfile.TemporaryDirectory() as name,
        pytest.MonkeyPatch.context() as monkeypatch,
    ):
        root = Path(name)
        target = root / "marker.sentinel"
        payload = b"payload"
        ensure_atomic_bytes(target, payload)
        before = target.stat()

        real_resolve = Path.resolve
        remaining = {"count": k}

        def flaky_resolve(self: Path, strict: bool = False) -> Path:
            if self == root and remaining["count"] > 0:
                remaining["count"] -= 1
                raise OSError(5, "Access is denied (simulated filter lock)")
            return real_resolve(self, strict=strict)

        monkeypatch.setattr(Path, "resolve", flaky_resolve)
        monkeypatch.setattr(time, "sleep", lambda _seconds: None)

        ensure_atomic_bytes(target, payload)

        after = target.stat()
        assert (after.st_dev, after.st_ino) == (before.st_dev, before.st_ino)


def test_beyond_ladder_transient_parent_failures_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "marker.sentinel"
    payload = b"payload"
    ensure_atomic_bytes(target, payload)
    before = target.stat()

    def refusing_resolve(self: Path, strict: bool = False) -> Path:  # noqa: ARG001 - signature parity with Path.resolve
        if self == tmp_path:
            raise OSError(5, "Access is denied (simulated filter lock)")
        return self

    monkeypatch.setattr(Path, "resolve", refusing_resolve)
    monkeypatch.setattr(time, "sleep", lambda _seconds: None)

    with pytest.raises(UnsafeAtomicWriteError, match="cannot resolve atomic-write parent"):
        ensure_atomic_bytes(target, payload)
    monkeypatch.undo()

    after = target.stat()
    assert (after.st_dev, after.st_ino) == (before.st_dev, before.st_ino)
