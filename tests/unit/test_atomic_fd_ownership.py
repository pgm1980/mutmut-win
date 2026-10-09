"""fd-ownership contracts for the sibling-exhaustion path of atomic writes.

``_open_random_sibling`` closes a rejected sibling fd *before* deciding
whether to retry or fail.  Until the ownership fix, the surrounding
``BaseException`` handler closed the same descriptor NUMBER a second time
(M-066): on Windows the CRT reassigns closed descriptor numbers
immediately, so the second close could hit a descriptor a concurrent user
thread had just received — corrupting unrelated I/O instead of surfacing
the ``UnsafeAtomicWriteError``.  Every sibling descriptor must be closed
exactly once on every exit route.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import BaseModel, Field

import mutmut_win.atomic_file as atomic_module
from mutmut_win.atomic_file import UnsafeAtomicWriteError, atomic_write_bytes


def _doctored_nlink(result: os.stat_result, nlink: int) -> os.stat_result:
    """Rebuild *result* with an overridden ``st_nlink`` (path-view doctoring).

    ``os.stat_result`` cannot be mutated; the extras dictionary is the only
    supported way to carry the Windows-only attributes through a rebuild
    (same technique as ``TestHandleLinkCountDivergence._doctored`` in
    ``test_atomic_transient_retry.py``).
    """
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


class SiblingFdRecorder:
    """Record sibling-descriptor opens/closes; refuse double closes.

    ``os.open`` wrappers let every non-sibling call pass through.  A
    descriptor obtained for a path containing ``.mutmut-atomic-`` is
    tracked; closing it once performs the real close, closing it again is
    recorded as a double close and NOT executed — a real second close
    would hit whatever foreign descriptor inherited the recycled number.
    """

    def __init__(self) -> None:
        self.open_fds: set[int] = set()
        self.seen_fds: set[int] = set()
        self.double_closes: list[int] = []
        self._real_open = os.open
        self._real_close = os.close

    def open_sibling(
        self,
        path: str | os.PathLike[str],
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        fd = self._real_open(path, flags, mode, dir_fd=dir_fd)
        if ".mutmut-atomic-" in str(path):
            self.open_fds.add(fd)
            self.seen_fds.add(fd)
        return fd

    def close_sibling(self, fd: int) -> None:
        if fd in self.seen_fds:
            if fd in self.open_fds:
                self.open_fds.discard(fd)
                self._real_close(fd)
                return
            self.double_closes.append(fd)
            return
        self._real_close(fd)


class _RejectedSiblingState(BaseModel):
    """Keep injected validation failures stable across cleanup observations."""

    observed_names: set[Path] = Field(default_factory=set)
    rejected_names: set[Path] = Field(default_factory=set)


def _reject_sibling_path_view(
    monkeypatch: pytest.MonkeyPatch,
    *,
    failures: int = 10_000,
) -> _RejectedSiblingState:
    """Make the path-view ``lstat`` report an extra link for N siblings."""
    real_lstat = Path.lstat
    state = _RejectedSiblingState()

    def atomic_twins(self: Path) -> os.stat_result:
        result = real_lstat(self)
        if ".mutmut-atomic-" in self.name:
            if self not in state.observed_names:
                state.observed_names.add(self)
                if len(state.rejected_names) < failures:
                    state.rejected_names.add(self)
            if self in state.rejected_names:
                return _doctored_nlink(result, nlink=2)
        return result

    monkeypatch.setattr(Path, "lstat", atomic_twins)
    return state


def _install_fd_recorder(
    monkeypatch: pytest.MonkeyPatch,
) -> SiblingFdRecorder:
    recorder = SiblingFdRecorder()
    monkeypatch.setattr(os, "open", recorder.open_sibling)
    monkeypatch.setattr(os, "close", recorder.close_sibling)
    return recorder


class TestSiblingFdClosedExactlyOnce:
    def test_exhausted_sibling_validation_closes_each_fd_exactly_once(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        target = tmp_path / "marker.sentinel"
        recorder = _install_fd_recorder(monkeypatch)
        _reject_sibling_path_view(monkeypatch)
        monkeypatch.setattr(time, "sleep", lambda _seconds: None)
        # The diagnostics sink is removed by M-067; ``raising=False`` keeps
        # this patch valid before and after that change.
        monkeypatch.setattr(
            atomic_module,
            "_dump_sibling_diagnostics",
            lambda *_args, **_kwargs: None,
            raising=False,
        )

        with pytest.raises(UnsafeAtomicWriteError):
            atomic_write_bytes(target, b"x")
        monkeypatch.undo()

        assert recorder.double_closes == []
        assert recorder.open_fds == set()

    def test_interrupt_during_validation_retry_sleep_closes_fd_once(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        target = tmp_path / "marker.sentinel"
        recorder = _install_fd_recorder(monkeypatch)
        _reject_sibling_path_view(monkeypatch)

        def interrupting_sleep(_seconds: float) -> None:
            raise KeyboardInterrupt

        monkeypatch.setattr(time, "sleep", interrupting_sleep)

        with pytest.raises(KeyboardInterrupt):
            atomic_write_bytes(target, b"x")
        monkeypatch.undo()

        assert recorder.double_closes == []
        assert recorder.open_fds == set()

    def test_fstat_failure_before_validation_closes_fd_once(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        target = tmp_path / "marker.sentinel"
        recorder = _install_fd_recorder(monkeypatch)

        def refusing_fstat(_fd: int) -> os.stat_result:
            raise OSError(5, "Access is denied (simulated filter lock)")

        monkeypatch.setattr(os, "fstat", refusing_fstat)

        with pytest.raises(OSError, match="simulated filter lock"):
            atomic_write_bytes(target, b"x")
        monkeypatch.undo()

        # This route always closed exactly once — the guard pins the
        # ownership-flag placement (owned from open until first close).
        assert recorder.double_closes == []
        assert recorder.open_fds == set()


class TestSiblingFdOwnershipProperty:
    @given(failures=st.integers(min_value=1, max_value=5), interrupt_in_sleep=st.booleans())
    def test_every_sibling_fd_is_closed_exactly_once(
        self,
        failures: int,
        interrupt_in_sleep: bool,
    ) -> None:
        import tempfile

        with (
            tempfile.TemporaryDirectory() as tmp,
            pytest.MonkeyPatch.context() as monkeypatch,
        ):
            recorder = _install_fd_recorder(monkeypatch)
            state = _reject_sibling_path_view(monkeypatch, failures=failures)

            def sleep(_seconds: float) -> None:
                if interrupt_in_sleep:
                    raise KeyboardInterrupt

            monkeypatch.setattr(time, "sleep", sleep)

            target = Path(tmp) / "marker.sentinel"
            if interrupt_in_sleep:
                with pytest.raises(KeyboardInterrupt):
                    atomic_write_bytes(target, b"x")
            elif failures >= 5:
                with pytest.raises(UnsafeAtomicWriteError):
                    atomic_write_bytes(target, b"x")
            else:
                atomic_write_bytes(target, b"x")
            monkeypatch.undo()

            assert recorder.double_closes == []
            assert recorder.open_fds == set()
            assert len(state.observed_names) == (1 if interrupt_in_sleep else min(failures + 1, 5))
            if not interrupt_in_sleep and failures < 5:
                assert target.read_bytes() == b"x"
                assert set(Path(tmp).iterdir()) == {target}
            else:
                assert set(Path(tmp).iterdir()) == set()
