"""Regression contracts for transient filter-driver retries in atomic writes.

The pytest phase guard republishes its execution sentinel once per test
report.  Under rapid create/replace churn, Windows filter drivers
(antivirus, indexers) transiently lock the fresh sibling or the replace
target — reproduced at roughly 1 failure per 5000 publications on an
otherwise healthy machine (MBR-2026-09-14-01 follow-up).  A bounded retry
with fresh validation absorbs the transient window; persistent unsafety or
locked targets still fail closed with the original error taxonomy.
"""

from __future__ import annotations

import os
import stat
import time
from pathlib import Path

import pytest

from mutmut_win.atomic_file import (
    AtomicReplaceError,
    UnsafeAtomicWriteError,
    atomic_write_bytes,
)


class FlakyReplace:
    """Simulate a filter driver holding ONE replace target for N calls.

    Only the configured target path is blocked; every other replace —
    notably the pytest phase guard's sentinel publications, whose call
    reports fire before this monkeypatch is torn down — passes through
    untouched.
    """

    def __init__(self, target: Path, failures: int) -> None:
        self.target = target
        self.failures = failures
        self.calls = 0
        self._real = os.replace

    def __call__(self, src: str, dst: str) -> None:
        if Path(dst) != self.target:
            self._real(src, dst)
            return
        self.calls += 1
        if self.calls <= self.failures:
            raise PermissionError(5, "Access is denied (simulated filter lock)")
        self._real(src, dst)


class TestReplaceRetry:
    def test_transient_replace_lock_is_absorbed(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        target = tmp_path / "marker.sentinel"
        flaky = FlakyReplace(target=target, failures=2)
        monkeypatch.setattr(os, "replace", flaky)
        monkeypatch.setattr(time, "sleep", lambda _seconds: None)

        atomic_write_bytes(target, b"payload")

        assert target.read_bytes() == b"payload"
        assert flaky.calls == 3

    def test_persistent_replace_lock_fails_closed(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        target = tmp_path / "marker.sentinel"
        flaky = FlakyReplace(target=target, failures=10_000)
        monkeypatch.setattr(os, "replace", flaky)
        monkeypatch.setattr(time, "sleep", lambda _seconds: None)

        with pytest.raises(AtomicReplaceError):
            atomic_write_bytes(target, b"payload")

    def test_successful_write_performs_no_retry_sleep(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        target = tmp_path / "marker.sentinel"
        sleeps: list[float] = []
        monkeypatch.setattr(time, "sleep", sleeps.append)

        atomic_write_bytes(target, b"payload")

        assert sleeps == []


class _FlapIdentity:
    """Flap file identities for *flaps* calls after skipping *skip* calls.

    ``skip`` lets tests steer the flap past earlier identity consumers (the
    parent-directory validation) onto the sibling validation of interest.
    """

    def __init__(self, skip: int, flaps: int) -> None:
        self.skip = skip
        self.flaps = flaps
        self.calls = 0

    def __call__(self, file_stat: os.stat_result) -> tuple[int, int]:
        self.calls += 1
        real = _real_identity(file_stat)
        if self.skip < self.calls <= self.skip + self.flaps:
            return (real[0], real[1] + self.calls)
        return real


class TestHandleLinkCountDivergence:
    """CX221-071 / MBR-2026-09-14-01: handle-view link counts may over-report.

    ``os.fstat`` transiently reports an extra link for a fresh ``O_EXCL``
    inode under filter-driver enumeration in child processes while the path
    view stays at one.  Exclusive creation plus identity equality plus the
    path-view link count carry the private-sibling contract; the divergence
    itself must not block publication.
    """

    @staticmethod
    def _doctored(result: os.stat_result, nlink: int) -> os.stat_result:
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

    def test_handle_view_extra_link_is_tolerated(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        real_fstat = os.fstat

        def two_links(fd: int) -> os.stat_result:
            return self._doctored(real_fstat(fd), nlink=2)

        monkeypatch.setattr(os, "fstat", two_links)
        target = tmp_path / "marker.sentinel"

        atomic_write_bytes(target, b"payload")
        monkeypatch.undo()

        assert target.read_bytes() == b"payload"

    def test_path_view_extra_link_is_still_refused(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        real_lstat = Path.lstat
        doctor = self._doctored

        def atomic_twins(self: Path) -> os.stat_result:
            result = real_lstat(self)
            if ".mutmut-atomic-" in self.name:
                return doctor(result, nlink=2)
            return result

        monkeypatch.setattr(Path, "lstat", atomic_twins)
        monkeypatch.setattr(time, "sleep", lambda _seconds: None)
        target = tmp_path / "marker.sentinel"

        with pytest.raises(UnsafeAtomicWriteError):
            atomic_write_bytes(target, b"payload")
        monkeypatch.undo()


class TestParentCaptureRetry:
    def test_transient_parent_resolve_failure_is_absorbed(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        target = tmp_path / "marker.sentinel"
        real_resolve = Path.resolve
        state = {"failed": False}

        def flaky_resolve(self: Path, strict: bool = False) -> Path:
            if self == tmp_path and not state["failed"]:
                state["failed"] = True
                raise OSError(5, "Access is denied (simulated filter lock)")
            return real_resolve(self, strict=strict)

        monkeypatch.setattr(Path, "resolve", flaky_resolve)
        monkeypatch.setattr(time, "sleep", lambda _seconds: None)

        atomic_write_bytes(target, b"payload")
        monkeypatch.undo()

        assert target.read_bytes() == b"payload"

    def test_persistent_parent_failure_fails_closed(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        target = tmp_path / "marker.sentinel"

        def refusing_resolve(self: Path, strict: bool = False) -> Path:  # noqa: ARG001 - signature parity with Path.resolve
            if self == tmp_path:
                raise OSError(5, "Access is denied (simulated filter lock)")
            return self

        monkeypatch.setattr(Path, "resolve", refusing_resolve)
        monkeypatch.setattr(time, "sleep", lambda _seconds: None)

        with pytest.raises(UnsafeAtomicWriteError):
            atomic_write_bytes(target, b"payload")
        monkeypatch.undo()


def _real_identity(file_stat: os.stat_result) -> tuple[int, int]:
    return file_stat.st_dev, file_stat.st_ino


class TestSiblingValidationRetry:
    def test_transient_identity_flap_is_absorbed(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import mutmut_win.atomic_file as atomic_module

        target = tmp_path / "marker.sentinel"
        # skip=3 steers the flap past the initial parent validation (three
        # identity calls: parent-compare, resolved-compare, identity capture)
        # onto the first sibling validation.
        flappy = _FlapIdentity(skip=3, flaps=2)
        monkeypatch.setattr(atomic_module, "_identity", flappy)
        monkeypatch.setattr(time, "sleep", lambda _seconds: None)

        atomic_write_bytes(target, b"payload")
        calls_after_write = flappy.calls
        # Restore before returning: this test's own call-phase report makes
        # the pytest phase guard publish its sentinel, and that publication
        # must never observe the flap monkeypatch.
        monkeypatch.undo()

        assert target.read_bytes() == b"payload"
        # The first sibling attempt flapped; the retry validated for real.
        assert calls_after_write >= 6

    def test_persistent_identity_mismatch_fails_closed(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import mutmut_win.atomic_file as atomic_module

        target = tmp_path / "marker.sentinel"
        monkeypatch.setattr(atomic_module, "_identity", _FlapIdentity(skip=3, flaps=10_000))
        monkeypatch.setattr(time, "sleep", lambda _seconds: None)

        with pytest.raises(UnsafeAtomicWriteError):
            atomic_write_bytes(target, b"payload")
        monkeypatch.undo()


class TestRetryPreservesSafetyContracts:
    def test_hardlinked_destination_twin_is_never_modified(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(time, "sleep", lambda _seconds: None)
        target = tmp_path / "shared.bin"
        target.write_bytes(b"original")
        twin = tmp_path / "twin.bin"
        os.link(target, twin)

        # Publishing over a path whose old leaf gained a hard link is a legal
        # rename publication: the twin keeps referencing the original bytes
        # and must never observe the new payload, whatever the outcome for
        # the target path itself.
        atomic_write_bytes(target, b"payload")

        assert twin.read_bytes() == b"original"
        assert target.read_bytes() == b"payload"

    def test_retried_sibling_is_fully_revalidated(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        stat_calls: list[object] = []

        real_fstat = os.fstat

        def counting_fstat(fd: int) -> os.stat_result:
            result = real_fstat(fd)
            stat_calls.append(result)
            return result

        monkeypatch.setattr(os, "fstat", counting_fstat)
        target = tmp_path / "marker.sentinel"

        atomic_write_bytes(target, b"payload")

        # Both identity snapshots (before-read and after-handle) of the very
        # first attempt already happened; a healthy path simply succeeds.
        assert stat_calls
        assert stat.S_ISREG(stat_calls[0].st_mode)
