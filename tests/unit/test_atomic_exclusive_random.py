"""Validation-retry contracts for ``create_exclusive_random_bytes`` (M-013).

The helper used to reject its freshly created ``O_EXCL`` file on the
handle-derived ``st_nlink`` — the exact signal the module documents as
unreliable on Windows (CX221-071 / MBR-2026-09-14-01: transient zero or
two links for a fresh inode under filter-driver enumeration) — and it did
so without any retry, while the sister function ``_open_random_sibling``
tolerates the same divergence and retries the remaining validation
conditions.  The handle-view link count is gone from the rejection
condition and validation failures are retried through
``_SIBLING_VALIDATION_RETRY_DELAYS`` with a budget strictly separate from
the 32-attempt collision budget (which still ends in ``FileExistsError``).
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
from mutmut_win.atomic_file import UnsafeAtomicWriteError, create_exclusive_random_bytes

PREFIX = "mutmut-empty-"
SUFFIX = ".ini"


def _doctored_nlink(result: os.stat_result, nlink: int) -> os.stat_result:
    """Rebuild *result* with an overridden ``st_nlink`` (doctoring helper).

    ``os.stat_result`` cannot be mutated; the extras dictionary is the only
    supported way to carry the Windows-only attributes through a rebuild
    (same technique as ``test_atomic_transient_retry.py``).
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


class _ValidationState(BaseModel):
    """Count rejected creation attempts independently of cleanup observations."""

    flaps_left: int
    observed_names: set[Path] = Field(default_factory=set)
    rejected_names: set[Path] = Field(default_factory=set)


def _flap_prefix_lstat(
    monkeypatch: pytest.MonkeyPatch,
    *,
    flaps: int = 10_000,
) -> _ValidationState:
    """Reject the first *flaps* distinct creations, including their cleanup reads."""
    real_lstat = Path.lstat
    state = _ValidationState(flaps_left=flaps)

    def flapping(self: Path) -> os.stat_result:
        result = real_lstat(self)
        if self.name.startswith(PREFIX):
            if self not in state.observed_names:
                state.observed_names.add(self)
                if state.flaps_left > 0:
                    state.flaps_left -= 1
                    state.rejected_names.add(self)
            if self in state.rejected_names:
                return _doctored_nlink(result, nlink=2)
        return result

    monkeypatch.setattr(Path, "lstat", flapping)
    return state


class TestHandleLinkCountDivergenceTolerated:
    def test_handle_view_extra_link_is_tolerated_for_exclusive_random_file(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        real_fstat = os.fstat

        def two_links(fd: int) -> os.stat_result:
            return _doctored_nlink(real_fstat(fd), nlink=2)

        monkeypatch.setattr(os, "fstat", two_links)

        path, identity = create_exclusive_random_bytes(
            tmp_path, b"cfg", prefix=PREFIX, suffix=SUFFIX
        )
        monkeypatch.undo()

        assert path.read_bytes() == b"cfg"
        leaf = path.lstat()
        assert identity == (leaf.st_dev, leaf.st_ino)


class TestValidationRetry:
    def test_transient_path_view_link_flap_is_retried(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        state = _flap_prefix_lstat(monkeypatch, flaps=1)
        monkeypatch.setattr(time, "sleep", lambda _seconds: None)

        path, _identity = create_exclusive_random_bytes(
            tmp_path, b"cfg", prefix=PREFIX, suffix=SUFFIX
        )
        monkeypatch.undo()

        assert path.read_bytes() == b"cfg"
        # Cleanup and post-write observations cannot consume creation retries.
        assert len(state.observed_names) == 2
        assert list(tmp_path.iterdir()) == [path]

    def test_persistent_path_view_extra_link_fails_closed_without_leftovers(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _flap_prefix_lstat(monkeypatch, flaps=10_000)
        monkeypatch.setattr(time, "sleep", lambda _seconds: None)

        with pytest.raises(UnsafeAtomicWriteError):
            create_exclusive_random_bytes(tmp_path, b"cfg", prefix=PREFIX, suffix=SUFFIX)
        monkeypatch.undo()

        assert list(tmp_path.iterdir()) == []

    def test_transient_identity_flap_is_retried_without_leftovers(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        real_identity = atomic_module._identity

        class OnceFlapping:
            def __init__(self) -> None:
                self.calls = 0

            def __call__(self, file_stat: os.stat_result) -> tuple[int, int]:
                self.calls += 1
                real = real_identity(file_stat)
                # Skip the three parent-capture identity calls in
                # _checked_parent so the flap hits the first sibling
                # validation (handle identity of the first attempt).
                if self.calls == 4:
                    return (real[0], real[1] + 1)
                return real

        flapping = OnceFlapping()
        monkeypatch.setattr(atomic_module, "_identity", flapping)
        monkeypatch.setattr(time, "sleep", lambda _seconds: None)

        path, _identity = create_exclusive_random_bytes(
            tmp_path, b"cfg", prefix=PREFIX, suffix=SUFFIX
        )
        monkeypatch.undo()

        assert path.read_bytes() == b"cfg"
        assert list(tmp_path.iterdir()) == [path]

    def test_collision_budget_and_validation_budget_are_separate(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        real_open = os.open
        collisions_left = {"count": 31}

        def colliding_open(
            path: str | os.PathLike[str],
            flags: int,
            mode: int = 0o777,
            *,
            dir_fd: int | None = None,
        ) -> int:
            if Path(str(path)).name.startswith(PREFIX) and collisions_left["count"] > 0:
                collisions_left["count"] -= 1
                raise FileExistsError(17, "File exists (simulated)", str(path))
            return real_open(path, flags, mode, dir_fd=dir_fd)

        _flap_prefix_lstat(monkeypatch, flaps=1)
        monkeypatch.setattr(os, "open", colliding_open)
        monkeypatch.setattr(time, "sleep", lambda _seconds: None)

        # 31 simulated collisions plus one validation flap must still
        # succeed: the validation retry never eats into the collision
        # budget (and vice versa).
        path, _identity = create_exclusive_random_bytes(
            tmp_path, b"cfg", prefix=PREFIX, suffix=SUFFIX
        )
        monkeypatch.undo()

        assert path.read_bytes() == b"cfg"
        assert list(tmp_path.iterdir()) == [path]


class TestValidationRetryProperty:
    @given(flaps=st.integers(min_value=0, max_value=6))
    def test_flap_budget_bounds_success_and_exhaustion(self, flaps: int) -> None:
        import tempfile

        with (
            tempfile.TemporaryDirectory() as tmp,
            pytest.MonkeyPatch.context() as monkeypatch,
        ):
            state = _flap_prefix_lstat(monkeypatch, flaps=flaps)
            monkeypatch.setattr(time, "sleep", lambda _seconds: None)

            directory = Path(tmp)
            budget = len(atomic_module._SIBLING_VALIDATION_RETRY_DELAYS) + 1
            if flaps >= budget:
                with pytest.raises(UnsafeAtomicWriteError):
                    create_exclusive_random_bytes(directory, b"cfg", prefix=PREFIX, suffix=SUFFIX)
            else:
                path, _identity = create_exclusive_random_bytes(
                    directory, b"cfg", prefix=PREFIX, suffix=SUFFIX
                )
                assert path.read_bytes() == b"cfg"
            monkeypatch.undo()

            # Exactly the published payload file remains — never leftover
            # attempts from the validation retries.
            files = list(directory.iterdir())
            assert len(files) == (0 if flaps >= budget else 1)
            assert len(state.observed_names) == min(flaps + 1, budget)
