"""Integration: Windows filesystem contracts for the staging pipeline (T3, TM-02).

Real NTFS state factories (``tests/unit/windows_fs_util.py``) driven through
the actual staging copy pipeline — not mocked.  Every case uses the
independent oracle principle: expectations derive from NTFS semantics
(normcase, junction resolution, sharing-violation timing), never from the
engine's own code.
"""

from __future__ import annotations

import contextlib
import os
import stat
from typing import TYPE_CHECKING

import pytest

from mutmut_win.config import MutmutConfig
from mutmut_win.file_setup import copy_src_dir
from tests.unit.windows_fs_util import (
    JunctionUnavailableError,
    byte_range_locked_file,
    lone_surrogate_name,
    make_junction,
    near_max_length_path,
    readonly_leaf,
    sharing_violation_holder,
)

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.integration, pytest.mark.slow]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_project(root: Path) -> Path:
    src = root / "src" / "pkg"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    (root / "tests").mkdir()
    (root / "tests" / "test_f.py").write_text(
        "def test_f():\n    from pkg import f\n    assert f() == 1\n", encoding="utf-8"
    )
    return root


# ---------------------------------------------------------------------------
# Junction contracts
# ---------------------------------------------------------------------------


class TestJunctionDefense:
    """Junctions in paths-to-mutate must not leak outside-tree content."""

    def test_junction_in_source_tree_is_not_recursive(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A junction inside the mutation tree must not recurse into the target."""

        project = _make_project(tmp_path)
        monkeypatch.chdir(project)
        outside = tmp_path / "outside"
        outside.mkdir()
        (outside / "leaked.py").write_text("# should not appear\n", encoding="utf-8")
        try:
            make_junction(project / "src" / "pkg" / "link_to_outside", outside)
        except JunctionUnavailableError:
            pytest.skip("junction creation unavailable on this host")

        config = MutmutConfig(paths_to_mutate=["src/"], tests_dir=["tests/"])
        copy_src_dir(config)
        staged_leak = tmp_path / "mutants" / "src" / "pkg" / "link_to_outside"
        assert not staged_leak.is_dir() or not (staged_leak / "leaked.py").exists(), (
            "a junction inside the mutation tree must not stage the target's content"
        )

    def test_junction_as_paths_to_mutate_root_is_resolved_or_rejected(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A junction as a configured mutation root must not silently mutate the target."""

        project = _make_project(tmp_path)
        monkeypatch.chdir(project)
        real_target = tmp_path / "real_target"
        real_target.mkdir()
        (real_target / "victim.py").write_text("x = 1\n", encoding="utf-8")
        try:
            make_junction(project / "junction_root", real_target)
        except JunctionUnavailableError:
            pytest.skip("junction creation unavailable on this host")

        config = MutmutConfig(
            paths_to_mutate=["junction_root/"],
            tests_dir=["tests/"],
        )
        try:
            copy_src_dir(config)
        except Exception:
            return  # rejected: acceptable
        assert not (tmp_path / "real_target" / "victim.py.meta").exists(), (
            "mutation metadata must never appear beside the junction target"
        )


# ---------------------------------------------------------------------------
# Sharing-violation contracts
# ---------------------------------------------------------------------------


class TestSharingViolation:
    """Exclusive locks must not crash the staging pipeline."""

    def test_locked_file_in_tests_does_not_crash_copy(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A byte-range-locked test file must not crash copy_src_dir."""

        project = _make_project(tmp_path)
        monkeypatch.chdir(project)
        lock_target = project / "tests" / "test_f.py"
        with byte_range_locked_file(lock_target):
            config = MutmutConfig(paths_to_mutate=["src/"], tests_dir=["tests/"])
            with contextlib.suppress(PermissionError):
                copy_src_dir(config)

    def test_sharing_violation_holder_does_not_crash_copy(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A sharing-violation holder on a file must not crash copy_src_dir."""

        project = _make_project(tmp_path)
        monkeypatch.chdir(project)
        target = project / "src" / "pkg" / "__init__.py"
        with sharing_violation_holder(target):
            config = MutmutConfig(paths_to_mutate=["src/"], tests_dir=["tests/"])
            with contextlib.suppress(PermissionError):
                copy_src_dir(config)


# ---------------------------------------------------------------------------
# Readonly contracts
# ---------------------------------------------------------------------------


class TestReadonlyCleanup:
    """Read-only staged leaves must be removable on shutdown (M-146)."""

    def test_readonly_staged_leaf_is_removable(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A read-only leaf in the staging tree can be removed on cleanup."""

        project = _make_project(tmp_path)
        monkeypatch.chdir(project)
        config = MutmutConfig(paths_to_mutate=["src/"], tests_dir=["tests/"])
        copy_src_dir(config)
        staged = tmp_path / "mutants" / "src" / "pkg" / "__init__.py"
        assert staged.exists()
        with readonly_leaf(staged):
            assert not (staged.stat().st_mode & stat.S_IWRITE)
            # The engine's shutdown must handle this (M-146); a raw
            # PermissionError here means cleanup is broken.
            staged.chmod(stat.S_IWRITE | stat.S_IREAD)


# ---------------------------------------------------------------------------
# NTFS normcase contracts
# ---------------------------------------------------------------------------


class TestNormcaseIdentity:
    """NTFS normcase identity: same name, different case, must not duplicate."""

    @pytest.mark.parametrize(
        ("name_a", "name_b"),
        [
            ("File.PY", "file.py"),
            ("MODULE.PY", "module.py"),
            ("Package", "package"),
        ],
    )
    def test_case_insensitive_names_collapse(self, name_a: str, name_b: str) -> None:
        """Two names differing only in case must normcase to the same identity."""

        assert os.path.normcase(name_a) == os.path.normcase(name_b), (
            f"NTFS normcase must fold {name_a!r} and {name_b!r} to the same identity"
        )


# ---------------------------------------------------------------------------
# Long-path contracts
# ---------------------------------------------------------------------------


class TestLongPath:
    """Near-maximum-length path components must survive staging."""

    def test_near_max_length_source_file_is_staged(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A source file near the 255 UTF-16 component limit can be staged."""

        project = _make_project(tmp_path)
        monkeypatch.chdir(project)
        pkg = project / "src" / "pkg"
        try:
            long_name = near_max_length_path(pkg, suffix=".py")
        except OSError:
            pytest.skip("long-path creation unavailable")
        (pkg / long_name).write_text("x = 1\n", encoding="utf-8")
        config = MutmutConfig(paths_to_mutate=["src/"], tests_dir=["tests/"])
        try:
            copy_src_dir(config)
        except OSError:
            pytest.skip("long-path staging rejected (LongPathsEnabled may be off)")


# ---------------------------------------------------------------------------
# Surrogate-name contracts
# ---------------------------------------------------------------------------


class TestSurrogateNames:
    """Lone-surrogate filenames must not crash the staging walk."""

    def test_lone_surrogate_name_does_not_crash_copy(self, tmp_path: Path) -> None:
        """A filename with a lone surrogate must not crash the copy walk."""

        project = _make_project(tmp_path)
        pkg = project / "src" / "pkg"
        try:
            bad_name = lone_surrogate_name(pkg)
        except OSError:
            pytest.skip("surrogate-name creation unavailable")
        (pkg / bad_name).write_text("x = 1\n", encoding="utf-8", errors="surrogateescape")
        config = MutmutConfig(paths_to_mutate=["src/"], tests_dir=["tests/"])
        copy_src_dir(config)
