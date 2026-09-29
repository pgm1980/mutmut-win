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
- structural rejections (link/reparse/missing parents) stay immediate;
- the probe itself is three-valued (M-011): transient leaf-observation
  failures (open/lstat/handle-view divergence) are retried through a
  bounded backoff and never republish a byte-identical frozen leaf, while
  verify-only callers fail with the real observation cause instead of a
  blind replacement.
"""

from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from mutmut_win.atomic_file import (
    _IDEMPOTENT_PROBE_RETRY_DELAYS,
    _PARENT_CAPTURE_RETRY_DELAYS,
    UnsafeAtomicWriteError,
    ensure_atomic_bytes,
)
from mutmut_win.exceptions import PytestBoundaryError
from mutmut_win.process.worker import prepare_pytest_phase_guard
from mutmut_win.runner import PytestRunner
from mutmut_win.stats import build_staging_context_evidence

if TYPE_CHECKING:
    from collections.abc import Callable


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


# ---------------------------------------------------------------------------
# M-011: the three-valued probe — transient leaf observations never
# republish a byte-identical frozen leaf.
# ---------------------------------------------------------------------------


def _flaky_read_open(target: Path, failures: int) -> Callable[..., int]:
    """Build an ``os.open`` replacement failing *failures* read-opens of *target*."""
    real_open = os.open
    state = {"count": failures}

    def flaky_open(path: Any, flags: int, *args: Any, **kwargs: Any) -> int:
        if Path(path) == target and not flags & os.O_CREAT and state["count"] > 0:
            state["count"] -= 1
            raise PermissionError(13, "simulated sharing violation")
        return real_open(path, flags, *args, **kwargs)

    return flaky_open


def _doctored_nlink(result: os.stat_result, nlink: int) -> os.stat_result:
    """Rebuild *result* with an overridden ``st_nlink`` (extras-preserving)."""
    values = list(result)
    values[3] = nlink
    extras = {
        "st_atime_ns": result.st_atime_ns,
        "st_mtime_ns": result.st_mtime_ns,
        "st_ctime_ns": result.st_ctime_ns,
    }
    for optional in ("st_birthtime_ns", "st_file_attributes", "st_reparse_tag"):
        value = getattr(result, optional, None)
        if value is not None:
            extras[optional] = value
    return os.stat_result(tuple(values), extras)


def _publish_sentinel(target: Path, payload: bytes) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    ensure_atomic_bytes(target, payload)


def test_transient_probe_open_failure_does_not_republish_identical_leaf(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "mutants" / "_mutmut_phase_guard.py"
    payload = b"# frozen staging sentinel\n"
    _publish_sentinel(target, payload)
    before = target.stat()

    monkeypatch.setattr(os, "open", _flaky_read_open(target, failures=1))
    monkeypatch.setattr(time, "sleep", lambda _seconds: None)

    ensure_atomic_bytes(target, payload)
    monkeypatch.undo()

    after = target.stat()
    assert (after.st_dev, after.st_ino) == (before.st_dev, before.st_ino)
    assert after.st_mtime_ns == before.st_mtime_ns


def test_transient_probe_open_failure_keeps_staging_evidence_stable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "mutants" / "_mutmut_phase_guard.py"
    payload = b"# frozen staging sentinel\n"
    _publish_sentinel(target, payload)
    monkeypatch.chdir(tmp_path)
    before_evidence = build_staging_context_evidence(tmp_path)

    monkeypatch.setattr(os, "open", _flaky_read_open(target, failures=1))
    monkeypatch.setattr(time, "sleep", lambda _seconds: None)

    ensure_atomic_bytes(target, payload)
    monkeypatch.undo()

    assert build_staging_context_evidence(tmp_path) == before_evidence


def test_transient_leaf_lstat_failure_does_not_republish(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "mutants" / "_mutmut_phase_guard.py"
    payload = b"# frozen staging sentinel\n"
    _publish_sentinel(target, payload)
    before = target.stat()

    real_lstat = Path.lstat
    state = {"failed": False}

    def flaky_lstat(self: Path) -> os.stat_result:
        if self == target and not state["failed"]:
            state["failed"] = True
            raise PermissionError(5, "simulated filter lock")
        return real_lstat(self)

    monkeypatch.setattr(Path, "lstat", flaky_lstat)
    monkeypatch.setattr(time, "sleep", lambda _seconds: None)

    ensure_atomic_bytes(target, payload)
    monkeypatch.undo()

    after = target.stat()
    assert (after.st_dev, after.st_ino) == (before.st_dev, before.st_ino)


def test_transient_handle_link_divergence_does_not_republish(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "mutants" / "_mutmut_phase_guard.py"
    payload = b"# frozen staging sentinel\n"
    _publish_sentinel(target, payload)
    before = target.stat()

    real_fstat = os.fstat
    state = {"flapped": False}

    def flapping_fstat(fd: int) -> os.stat_result:
        result = real_fstat(fd)
        if not state["flapped"]:
            # One handle view reports two links while the path view stays
            # at one (MBR-2026-09-14-01 field data): unprovable, retry.
            state["flapped"] = True
            return _doctored_nlink(result, nlink=2)
        return result

    monkeypatch.setattr(os, "fstat", flapping_fstat)
    monkeypatch.setattr(time, "sleep", lambda _seconds: None)

    ensure_atomic_bytes(target, payload)
    monkeypatch.undo()

    after = target.stat()
    assert (after.st_dev, after.st_ino) == (before.st_dev, before.st_ino)


def test_exhausted_unverifiable_raises_in_verify_only_mode_and_keeps_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "mutants" / "_mutmut_phase_guard.py"
    payload = b"# frozen staging sentinel\n"
    _publish_sentinel(target, payload)
    before = target.stat()

    monkeypatch.setattr(os, "open", _flaky_read_open(target, failures=10_000))
    monkeypatch.setattr(time, "sleep", lambda _seconds: None)

    with pytest.raises(PermissionError, match="simulated sharing violation"):
        ensure_atomic_bytes(target, payload, replace_unverifiable=False)
    monkeypatch.undo()

    after = target.stat()
    assert (after.st_dev, after.st_ino) == (before.st_dev, before.st_ino)


def test_verify_only_phase_guard_fails_with_real_cause_without_republishing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    staging = tmp_path / "mutants"
    staging.mkdir()
    prepare_pytest_phase_guard({}, staging)
    plugin = staging / "_mutmut_phase_guard.py"
    before = plugin.stat()

    monkeypatch.setattr(os, "open", _flaky_read_open(plugin, failures=10_000))
    monkeypatch.setattr(time, "sleep", lambda _seconds: None)

    with pytest.raises(PytestBoundaryError, match="simulated sharing violation"):
        prepare_pytest_phase_guard({}, staging, replace_unverifiable=False)
    monkeypatch.undo()

    after = plugin.stat()
    assert (after.st_dev, after.st_ino) == (before.st_dev, before.st_ino)


def test_default_phase_guard_still_republishes_when_probe_stays_unverifiable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    staging = tmp_path / "mutants"
    staging.mkdir()
    prepare_pytest_phase_guard({}, staging)
    plugin = staging / "_mutmut_phase_guard.py"
    before = plugin.stat()

    monkeypatch.setattr(os, "open", _flaky_read_open(plugin, failures=10_000))
    monkeypatch.setattr(time, "sleep", lambda _seconds: None)

    # Pre-snapshot callers keep the publishing default: an unprovable leaf
    # is replaced by the strict writer rather than failing the run.
    prepare_pytest_phase_guard({}, staging)
    monkeypatch.undo()

    after = plugin.stat()
    assert (after.st_dev, after.st_ino) != (before.st_dev, before.st_ino)
    assert plugin.is_file()


def test_persistent_parent_failure_pays_exactly_the_parent_ladder(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    staging = tmp_path / "mutants"
    staging.mkdir()

    def refusing_resolve(self: Path, strict: bool = False) -> Path:  # noqa: ARG001 - signature parity with Path.resolve
        if self == staging:
            raise OSError(5, "Access is denied (simulated filter lock)")
        return self

    sleeps: list[float] = []
    monkeypatch.setattr(Path, "resolve", refusing_resolve)
    monkeypatch.setattr(time, "sleep", sleeps.append)

    with pytest.raises(PytestBoundaryError, match="cannot resolve atomic-write parent"):
        prepare_pytest_phase_guard({}, staging)
    monkeypatch.undo()

    # M-011 latency bound: the parent ladder runs once per probe call, it is
    # never multiplied by the probe loop (7 pauses, not 7 x 7).
    assert sleeps == list(_PARENT_CAPTURE_RETRY_DELAYS)


def test_persistent_unverifiable_probe_pays_probe_ladder_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "mutants" / "_mutmut_phase_guard.py"
    payload = b"# frozen staging sentinel\n"
    _publish_sentinel(target, payload)

    sleeps: list[float] = []
    monkeypatch.setattr(os, "open", _flaky_read_open(target, failures=10_000))
    monkeypatch.setattr(time, "sleep", sleeps.append)

    ensure_atomic_bytes(target, payload)
    monkeypatch.undo()

    # Exactly the probe backoff — the parent ladder succeeded up front and
    # the strict writer's replace went through on the first attempt.
    assert sleeps == list(_IDEMPOTENT_PROBE_RETRY_DELAYS)


def test_unchanged_guard_is_not_republished_per_task(tmp_path: Path) -> None:
    staging = tmp_path / "mutants"
    staging.mkdir()
    prepare_pytest_phase_guard({}, staging)
    plugin = staging / "_mutmut_phase_guard.py"
    before = plugin.stat()

    for _task in range(5):
        prepare_pytest_phase_guard({}, staging)

    after = plugin.stat()
    assert (after.st_dev, after.st_ino) == (before.st_dev, before.st_ino)
    assert after.st_mtime_ns == before.st_mtime_ns
    assert list(staging.glob("._mutmut_phase_guard.py.mutmut-atomic-*.tmp")) == []


def test_stats_plugin_transient_open_failure_does_not_republish(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    staging = tmp_path / "mutants"
    staging.mkdir()
    PytestRunner._write_stats_plugin(staging)
    plugin = staging / "_mutmut_stats_plugin.py"
    before = plugin.stat()

    monkeypatch.setattr(os, "open", _flaky_read_open(plugin, failures=1))
    monkeypatch.setattr(time, "sleep", lambda _seconds: None)

    PytestRunner._write_stats_plugin(staging)
    monkeypatch.undo()

    after = plugin.stat()
    assert (after.st_dev, after.st_ino) == (before.st_dev, before.st_ino)


def test_stats_plugin_verify_only_raises_on_persistent_transience(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    staging = tmp_path / "mutants"
    staging.mkdir()
    PytestRunner._write_stats_plugin(staging)
    plugin = staging / "_mutmut_stats_plugin.py"
    before = plugin.stat()

    monkeypatch.setattr(os, "open", _flaky_read_open(plugin, failures=10_000))
    monkeypatch.setattr(time, "sleep", lambda _seconds: None)

    with pytest.raises(PermissionError, match="simulated sharing violation"):
        PytestRunner._write_stats_plugin(staging, replace_unverifiable=False)
    monkeypatch.undo()

    after = plugin.stat()
    assert (after.st_dev, after.st_ino) == (before.st_dev, before.st_ino)


@given(failures=st.integers(min_value=0, max_value=len(_IDEMPOTENT_PROBE_RETRY_DELAYS)))
@settings(deadline=None)
def test_up_to_probe_ladder_transient_open_failures_are_absorbed(failures: int) -> None:
    with (
        tempfile.TemporaryDirectory() as name,
        pytest.MonkeyPatch.context() as monkeypatch,
    ):
        target = Path(name) / "marker.sentinel"
        payload = b"payload"
        ensure_atomic_bytes(target, payload)
        before = target.stat()

        monkeypatch.setattr(os, "open", _flaky_read_open(target, failures))
        monkeypatch.setattr(time, "sleep", lambda _seconds: None)

        ensure_atomic_bytes(target, payload)

        after = target.stat()
        assert (after.st_dev, after.st_ino) == (before.st_dev, before.st_ino)
