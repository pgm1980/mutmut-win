"""Owned CAS sibling cleanup on preparation failures (AR-07, M-005).

COR-005 / PERF-001: after ``_open_random_sibling`` the first try/finally
only closed the file descriptor.  Errors from ``fchmod``, ``_write_all``,
``fsync`` and the subsequent temp/parent revalidation left the private
sibling behind while the target stayed byte-identical.  These tests fail
every preparation seam and require: source unchanged, the OWN sibling gone,
a FOREIGN replacement at the temp name untouched, the original error
primary, and the descriptor closed exactly once.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

import mutmut_win.atomic_file as af
from mutmut_win.atomic_file import FileIdentity, atomic_replace_if_unchanged

_EXPECTED = b"old = 1\n"
_PAYLOAD = b"old = 2\n"


def _fault(*_args: object, **_kwargs: object) -> object:
    raise OSError(28, "injected preparation failure")


class TestCasSiblingCleanupOnPreparationFailure:
    def _observing_sibling(self, seen: list[tuple[int, Path]]) -> object:
        real_open_sibling = af._open_random_sibling

        def observing_sibling(path: Path) -> tuple[int, Path, FileIdentity]:
            fd, temp_path, identity = real_open_sibling(path)
            seen.append((fd, temp_path))
            return fd, temp_path, identity

        return observing_sibling

    @pytest.mark.parametrize(
        "seam",
        ["write", "fsync", "checked_temp", "checked_parent"],
    )
    def test_preparation_failure_cleans_owned_sibling(self, tmp_path: Path, seam: str) -> None:
        """Write/flush/temp/parent failures release the owned sibling."""
        source = tmp_path / "source.py"
        source.write_bytes(_EXPECTED)
        seen: list[tuple[int, Path]] = []
        real_checked_parent = af._checked_parent

        def parent_fault(path: Path, *_args: object, **_kwargs: object) -> FileIdentity:
            # Only the POST-write recheck fails; the pre-write capture inside
            # _capture_parent_identity stays healthy (no sibling seen yet).
            if seen and Path(path) == source:
                raise OSError(28, "injected post-write parent recheck failure")
            return real_checked_parent(path)

        owner, name = {
            "write": (af, "_write_all"),
            "fsync": (os, "fsync"),
            "checked_temp": (af, "_checked_temp"),
            "checked_parent": (af, "_checked_parent"),
        }[seam]
        wrapper = parent_fault if seam == "checked_parent" else _fault

        with (
            patch.object(af, "_open_random_sibling", side_effect=self._observing_sibling(seen)),
            patch.object(owner, name, side_effect=wrapper),
            pytest.raises(OSError, match="injected"),
        ):
            atomic_replace_if_unchanged(source, _PAYLOAD, expected=_EXPECTED)

        assert source.read_bytes() == _EXPECTED
        assert len(seen) == 1
        assert not seen[0][1].exists(), "owned private sibling must be released"
        assert list(tmp_path.glob(".*.mutmut-atomic-*.tmp")) == []
        assert list(tmp_path.glob(".*.mutmut-displaced")) == []

    def test_foreign_replaced_temp_is_not_removed(self, tmp_path: Path) -> None:
        """A foreign inode at the temp name survives the cleanup."""
        source = tmp_path / "source.py"
        source.write_bytes(_EXPECTED)
        seen: list[tuple[int, Path]] = []

        def foreign_then_fail(path: Path, *_args: object, **_kwargs: object) -> None:
            # The fd is already closed here: swap the temp ENTRY for a
            # foreign inode, then fail the preparation.
            donor = tmp_path / "foreign-donor.bin"
            donor.write_bytes(b"foreign replacement inode")
            donor.replace(Path(path))
            raise OSError(28, "injected preparation failure after foreign replacement")

        with (
            patch.object(af, "_open_random_sibling", side_effect=self._observing_sibling(seen)),
            patch.object(af, "_checked_temp", side_effect=foreign_then_fail),
            pytest.raises(OSError, match="injected preparation failure"),
        ):
            atomic_replace_if_unchanged(source, _PAYLOAD, expected=_EXPECTED)

        assert source.read_bytes() == _EXPECTED
        assert len(seen) == 1
        # The foreign replacement stays (identity-bound cleanup) while the
        # donor name is gone.
        assert seen[0][1].read_bytes() == b"foreign replacement inode"
        assert not (tmp_path / "foreign-donor.bin").exists()

    def test_fd_closed_exactly_once_on_write_failure(self, tmp_path: Path) -> None:
        """The owned descriptor is closed exactly once (fd ownership, M-066)."""
        source = tmp_path / "source.py"
        source.write_bytes(_EXPECTED)
        seen: list[tuple[int, Path]] = []
        real_close = os.close
        closed: list[int] = []

        def counting_close(fd: int) -> None:
            closed.append(fd)
            real_close(fd)

        with (
            patch.object(af, "_open_random_sibling", side_effect=self._observing_sibling(seen)),
            patch.object(os, "close", side_effect=counting_close),
            patch.object(af, "_write_all", side_effect=_fault),
            pytest.raises(OSError, match="injected preparation failure"),
        ):
            atomic_replace_if_unchanged(source, _PAYLOAD, expected=_EXPECTED)

        assert len(seen) == 1
        owned_fd, _temp_path = seen[0]
        assert closed.count(owned_fd) == 1
        assert source.read_bytes() == _EXPECTED
