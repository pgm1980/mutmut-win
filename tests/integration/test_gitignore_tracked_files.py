"""Integration: tracked files survive gitignore pruning in real repos (M-001, #146).

Uses a real ``git init`` + ``git add -f`` in a temporary directory to prove
that a tracked-ignored file appears in the mutation selection and staging.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from typing import TYPE_CHECKING

import pytest

from mutmut_win.config import MutmutConfig
from mutmut_win.file_setup import copy_src_dir, walk_source_files

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(sys.platform != "win32", reason="Windows-native git behaviour"),
]

_GIT = shutil.which("git")


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    """Run a git command in *root*; full path avoids S607 partial-path findings."""
    assert _GIT is not None, "git must be available for integration tests"
    return subprocess.run(  # noqa: S603  # full path via shutil.which; argv list, no shell
        [_GIT, "-C", str(root), *args],
        check=True,
        capture_output=True,
        timeout=30,
    )


def _init_repo(root: Path) -> None:
    """Initialize a git repo with explicit settings for determinism."""
    for args in (
        ("init",),
        ("config", "core.ignorecase", "true"),
        ("config", "user.email", "test@test.local"),
        ("config", "user.name", "Test"),
    ):
        _git(root, *args)


class TestTrackedIgnoredSourceInSelection:
    def test_tracked_ignored_file_appears_in_mutation_selection(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A tracked (git add -f) file matching an ignore pattern is selected."""
        _init_repo(tmp_path)
        (tmp_path / ".gitignore").write_text("*_gen.py\n", encoding="utf-8")
        pkg = tmp_path / "src" / "pkg"
        pkg.mkdir(parents=True)
        (pkg / "api_gen.py").write_text("def f():\n    return 1\n", encoding="utf-8")
        (pkg / "other_gen.py").write_text("def g():\n    return 2\n", encoding="utf-8")

        _git(tmp_path, "add", "-f", "src/pkg/api_gen.py")

        monkeypatch.chdir(tmp_path)
        config = MutmutConfig(paths_to_mutate=["src"], max_children=1)
        sources = [str(s).replace("\\", "/") for s in walk_source_files(config)]

        assert "src/pkg/api_gen.py" in sources
        assert "src/pkg/other_gen.py" not in sources

    def test_tracked_ignored_file_is_staged(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A tracked-ignored file is copied into mutants/ staging."""
        _init_repo(tmp_path)
        (tmp_path / ".gitignore").write_text("generated/\n", encoding="utf-8")
        gen = tmp_path / "src" / "generated"
        gen.mkdir(parents=True)
        (gen / "tracked.py").write_text("def f():\n    return 1\n", encoding="utf-8")

        _git(tmp_path, "add", "-f", "src/generated/tracked.py")

        monkeypatch.chdir(tmp_path)
        config = MutmutConfig(paths_to_mutate=["src"], max_children=1)
        copy_src_dir(config)

        staged = tmp_path / "mutants" / "src" / "generated" / "tracked.py"
        assert staged.is_file()
        assert staged.read_text(encoding="utf-8") == "def f():\n    return 1\n"

    def test_git_failure_disables_pruning(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A git failure with .git present disables pruning (fail-open)."""
        _init_repo(tmp_path)
        (tmp_path / ".gitignore").write_text("*_gen.py\n", encoding="utf-8")
        src = tmp_path / "src"
        src.mkdir()
        (src / "x_gen.py").write_text("x = 1\n", encoding="utf-8")

        monkeypatch.setenv("PATH", str(tmp_path / "no-git"))

        monkeypatch.chdir(tmp_path)
        config = MutmutConfig(paths_to_mutate=["src"], max_children=1)
        sources = [str(s).replace("\\", "/") for s in walk_source_files(config)]

        assert "src/x_gen.py" in sources

    def test_no_repo_keeps_pure_patterns(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Without .git, pure pattern behaviour is unchanged."""
        (tmp_path / ".gitignore").write_text("*_gen.py\n", encoding="utf-8")
        src = tmp_path / "src"
        src.mkdir()
        (src / "x_gen.py").write_text("x = 1\n", encoding="utf-8")
        (src / "ok.py").write_text("x = 2\n", encoding="utf-8")

        monkeypatch.chdir(tmp_path)
        config = MutmutConfig(paths_to_mutate=["src"], max_children=1)
        sources = [str(s).replace("\\", "/") for s in walk_source_files(config)]

        assert "src/x_gen.py" not in sources
        assert "src/ok.py" in sources


class TestNestedExplicitRootInRealRepo:
    """AR-02: nested explicit roots survive in a real git repo (M-001/M-032).

    ``pkg/.gitignore`` excludes the configured root ``pkg/sub``; tracked and
    untracked content below it must both stay reachable.
    """

    def _make_nested_root(self, root: Path) -> None:
        (root / ".gitignore").write_text("nothing/\n", encoding="utf-8")
        nested = root / "pkg" / "sub"
        nested.mkdir(parents=True)
        (root / "pkg" / ".gitignore").write_text("sub/\nsibling/\n", encoding="utf-8")
        (nested / "api.py").write_text("def f():\n    return 1\n", encoding="utf-8")
        (nested / "other.py").write_text("def g():\n    return 2\n", encoding="utf-8")

    def test_untracked_nested_explicit_root_appears_in_mutation_selection(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Untracked (not force-added) sources below the nested ignored root
        are selected — the forced reset, not the tracked override, keeps
        them."""
        _init_repo(tmp_path)
        self._make_nested_root(tmp_path)
        monkeypatch.chdir(tmp_path)
        config = MutmutConfig(paths_to_mutate=["pkg/sub"], max_children=1)
        sources = [str(s).replace("\\", "/") for s in walk_source_files(config)]

        assert "pkg/sub/api.py" in sources
        assert "pkg/sub/other.py" in sources

    def test_tracked_and_untracked_mix_in_nested_explicit_root(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A force-added file below the nested root is selected via the
        tracked override AND its untracked sibling via the forced reset."""
        _init_repo(tmp_path)
        self._make_nested_root(tmp_path)
        _git(tmp_path, "add", "-f", "pkg/sub/api.py")
        monkeypatch.chdir(tmp_path)
        config = MutmutConfig(paths_to_mutate=["pkg/sub"], max_children=1)
        sources = [str(s).replace("\\", "/") for s in walk_source_files(config)]

        assert "pkg/sub/api.py" in sources
        assert "pkg/sub/other.py" in sources

    def test_nested_explicit_root_is_staged(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _init_repo(tmp_path)
        self._make_nested_root(tmp_path)
        (tmp_path / "pkg" / "sibling").mkdir()
        (tmp_path / "pkg" / "sibling" / "keep.txt").write_text("no\n", encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        config = MutmutConfig(paths_to_mutate=["pkg/sub"], max_children=1)
        copy_src_dir(config)

        assert (tmp_path / "mutants" / "pkg" / "sub" / "api.py").is_file()
        assert (tmp_path / "mutants" / "pkg" / "sub" / "other.py").is_file()
        # The unconfigured ignored sibling stays out of staging.
        assert not (tmp_path / "mutants" / "pkg" / "sibling").exists()
