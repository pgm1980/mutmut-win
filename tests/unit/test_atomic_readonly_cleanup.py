"""M-068: failed publications must not leave read-only temp siblings behind.

A read-only source produces a read-only private sibling; when the replace
then fails, ``unlink`` on the read-only leaf raises ``PermissionError``
(proven for CPython 3.14.7/Windows, winerror 5) and every retry left
another hidden ``.mutmut-atomic-*.tmp`` corpse.  The cleanup may lift the
read-only attribute only on a provably own, regular, singly-linked,
non-reparse leaf (the DOS attribute applies to every hardlink).
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from mutmut_win.atomic_file import AtomicReplaceError, atomic_copy_file


class FlakyReplace:
    """Block every replace onto ONE target path (simulated filter lock)."""

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


class TestReadonlyCleanup:
    def test_failed_readonly_copy_leaves_no_private_siblings(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        source = tmp_path / "src" / "data.txt"
        source.parent.mkdir()
        source.write_text("payload", encoding="utf-8")
        source.chmod(stat.S_IREAD)
        target = tmp_path / "dst" / "data.txt"
        target.parent.mkdir()

        flaky = FlakyReplace(target=target, failures=100)
        monkeypatch.setattr(os, "replace", flaky)
        monkeypatch.setattr("mutmut_win.atomic_file.time.sleep", lambda _delay: None)

        try:
            with pytest.raises(AtomicReplaceError):
                atomic_copy_file(source, target)
            monkeypatch.undo()
            leftovers = list(target.parent.glob(".data.txt.mutmut-atomic-*.tmp"))
            assert leftovers == [], f"read-only siblings survived: {leftovers}"
            assert not target.exists()
        finally:
            source.chmod(stat.S_IWRITE)

    def test_cleanup_never_chmods_a_multiply_linked_sibling(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The DOS read-only attribute applies to every hardlink: a leaf with
        path-view nlink == 2 must never be chmod'ed (foreign-file hazard)."""
        from mutmut_win.atomic_file import _cleanup_owned_temp, _identity

        leaf = tmp_path / ".data.txt.mutmut-atomic-deadbeef.tmp"
        leaf.write_text("x", encoding="utf-8")
        leaf.chmod(stat.S_IREAD)
        hardlink = tmp_path / "hardlink.txt"
        os.link(leaf, hardlink)
        assert leaf.lstat().st_nlink == 2
        identity = _identity(leaf.lstat())

        chmod_calls: list[Path] = []
        real_chmod = Path.chmod

        def spying_chmod(self: Path, mode: int, **kwargs: object) -> None:
            chmod_calls.append(self)
            real_chmod(self, mode, **kwargs)  # type: ignore[call-arg]

        try:
            monkeypatch.setattr(Path, "chmod", spying_chmod)
            _cleanup_owned_temp(leaf, identity)
            monkeypatch.undo()

            assert leaf not in chmod_calls, "cleanup chmod'ed a multiply-linked leaf"
            assert leaf.exists(), "multiply-linked leaf must be left alone"
        finally:
            monkeypatch.undo()
            hardlink.chmod(stat.S_IWRITE)
            hardlink.unlink()

    def test_cleanup_removes_own_readonly_sibling(self, tmp_path: Path) -> None:
        """The provably own, singly-linked, read-only sibling is released."""
        from mutmut_win.atomic_file import _cleanup_owned_temp, _identity

        leaf = tmp_path / ".data.txt.mutmut-atomic-cafebabe.tmp"
        leaf.write_text("x", encoding="utf-8")
        leaf.chmod(stat.S_IREAD)
        identity = _identity(leaf.lstat())

        try:
            _cleanup_owned_temp(leaf, identity)
            assert not leaf.exists(), "own read-only sibling should be removed"
        finally:
            if leaf.exists():
                leaf.chmod(stat.S_IWRITE)

    def test_cleanup_ignores_foreign_identity(self, tmp_path: Path) -> None:
        """A leaf whose identity no longer matches is never touched."""
        from mutmut_win.atomic_file import _cleanup_owned_temp

        leaf = tmp_path / ".data.txt.mutmut-atomic-abcdef01.tmp"
        leaf.write_text("x", encoding="utf-8")
        leaf.chmod(stat.S_IREAD)

        try:
            _cleanup_owned_temp(leaf, (999, 999))
            assert leaf.exists(), "foreign leaf must not be unlinked"
            assert leaf.stat().st_mode & stat.S_IWRITE == 0, "foreign leaf must stay read-only"
        finally:
            leaf.chmod(stat.S_IWRITE)
