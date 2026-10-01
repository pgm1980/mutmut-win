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

from mutmut_win import gitignore_boundary
from mutmut_win.config import MutmutConfig
from mutmut_win.file_setup import copy_src_dir, walk_source_files
from mutmut_win.gitignore_boundary import GitignoreBoundary

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


class TestTrackedGitlinkDirectory:
    """AR-03 (COR-003): tracked gitlink entries (mode 160000) are directories.

    ``git ls-files`` reports a submodule as ONE path with mode 160000; the
    tracked override must treat that path as a tracked directory root so the
    ignore rule cannot prune it, without guessing directory-ness for normal
    file entries.
    """

    def _init_with_gitlink(self, root: Path, path: str = "vendor") -> None:
        _init_repo(root)
        (root / ".gitignore").write_text(f"{path}/\n", encoding="utf-8")
        vendor = root / path
        vendor.mkdir(parents=True)
        (vendor / "api.py").write_text("def answer(): return 42\n", encoding="utf-8")
        _git(root, "update-index", "--add", "--cacheinfo", f"160000,{'1' * 40},{path}")

    def test_gitlink_directory_is_not_excluded(self, tmp_path: Path) -> None:
        """The gitlink itself is a tracked directory root (M-001 override)."""
        self._init_with_gitlink(tmp_path)
        boundary = GitignoreBoundary.load(tmp_path)
        assert boundary.excludes_directory("vendor") is False

    def test_gitlink_nested_directory_is_not_excluded(self, tmp_path: Path) -> None:
        """A gitlink below the root covers all its ancestor components too."""
        self._init_with_gitlink(tmp_path, path="third_party/vendor")
        boundary = GitignoreBoundary.load(tmp_path)
        assert boundary.excludes_directory("third_party") is False
        assert boundary.enter("third_party").excludes_directory("vendor") is False

    def test_gitlink_source_content_stays_reachable_through_configured_root(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._init_with_gitlink(tmp_path)
        monkeypatch.chdir(tmp_path)
        config = MutmutConfig(paths_to_mutate=["vendor"], max_children=1)
        sources = [str(s).replace("\\", "/") for s in walk_source_files(config)]
        assert "vendor/api.py" in sources

    def test_tracked_plain_file_does_not_act_as_directory_override(self, tmp_path: Path) -> None:
        """Normal index entries keep their file identity: a tracked FILE
        named like the ignored directory does not un-exclude the directory."""
        _init_repo(tmp_path)
        (tmp_path / ".gitignore").write_text("vendor\n", encoding="utf-8")
        (tmp_path / "vendor").write_text("i am a file\n", encoding="utf-8")
        _git(tmp_path, "add", "-f", "vendor")
        boundary = GitignoreBoundary.load(tmp_path)
        assert boundary.excludes_file("vendor") is False
        assert boundary.excludes_directory("vendor") is True

    def test_full_submodule_end_to_end(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A real ``git submodule add`` gitlink survives ignore pruning.

        Git refuses the file protocol by default since 2.38, so the probe
        allows it explicitly for the local inner repository.
        """
        inner = tmp_path / "inner"
        inner.mkdir()
        _init_repo(inner)
        (inner / "api.py").write_text("def answer(): return 42\n", encoding="utf-8")
        _git(inner, "add", "api.py")
        _git(inner, "commit", "-q", "-m", "inner")

        outer = tmp_path / "outer"
        outer.mkdir()
        _init_repo(outer)
        subprocess.run(  # noqa: S603  # full path via shutil.which; argv list, no shell
            [
                _GIT,
                "-C",
                str(outer),
                "-c",
                "protocol.file.allow=always",
                "submodule",
                "add",
                "--quiet",
                str(inner),
                "vendor",
            ],
            check=True,
            capture_output=True,
            timeout=120,
        )
        _git(outer, "commit", "-q", "-m", "submodule")
        # The ignore rule arrives AFTER the submodule is tracked — the M-001
        # scenario (git itself refuses submodule-add onto an ignored path).
        (outer / ".gitignore").write_text("vendor/\ncache/\n", encoding="utf-8")
        stage = _git(outer, "ls-files", "--stage").stdout.decode("utf-8")
        assert "160000" in stage
        assert "vendor" in stage

        boundary = GitignoreBoundary.load(outer)
        # The gitlink directory is entered despite the ignore rule ...
        assert boundary.excludes_directory("vendor") is False
        # ... its configured source content stays reachable ...
        monkeypatch.chdir(outer)
        config = MutmutConfig(paths_to_mutate=["vendor"], max_children=1)
        sources = [str(s).replace("\\", "/") for s in walk_source_files(config)]
        assert "vendor/api.py" in sources
        # ... and normal ignored untracked directories stay excluded.
        cache = outer / "cache"
        cache.mkdir()
        (cache / "dropped.py").write_text("x = 1\n", encoding="utf-8")
        assert boundary.excludes_directory("cache") is True


class TestWorktreeTrackedCacheInvalidation:
    """AR-04 (COR-004/SEC-002): .git files must invalidate the tracked cache.

    A linked worktree carries a ``.git`` FILE; without an index path the
    cache key used to collapse to ``(root, 0, 0)`` and never changed again,
    so every later boundary in the same process kept the FIRST tracked set.
    """

    def _make_worktree(self, tmp_path: Path) -> Path:
        main = tmp_path / "main"
        main.mkdir()
        _init_repo(main)
        (main / ".gitignore").write_text("hidden.py\n", encoding="utf-8")
        _git(main, "add", ".gitignore")
        _git(main, "commit", "-q", "-m", "init")
        _git(main, "worktree", "add", "--quiet", str(tmp_path / "wt"))
        worktree = tmp_path / "wt"
        (worktree / "hidden.py").write_text("SECRET = 1\n", encoding="utf-8")
        return worktree

    @staticmethod
    def _counting_git(monkeypatch: pytest.MonkeyPatch) -> list[int]:
        """Wrap the boundary's git invocation with a call counter."""
        real_run = gitignore_boundary.subprocess.run
        calls = [0]

        def counting_run(*args: object, **kwargs: object) -> object:
            calls[0] += 1
            return real_run(*args, **kwargs)  # type: ignore[arg-type]

        monkeypatch.setattr(gitignore_boundary.subprocess, "run", counting_run)
        return calls

    def test_worktree_index_change_invalidates_tracked_cache(self, tmp_path: Path) -> None:
        """The acceptance probe: ``git add -f`` between two loads in one
        process must become visible without any private cache reset."""
        worktree = self._make_worktree(tmp_path)
        before = GitignoreBoundary.load(worktree).excludes_file("hidden.py")
        _git(worktree, "add", "-f", "hidden.py")
        after = GitignoreBoundary.load(worktree).excludes_file("hidden.py")
        assert before is True
        assert after is False

    def test_unchanged_worktree_index_reuses_the_cache(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        worktree = self._make_worktree(tmp_path)
        calls = self._counting_git(monkeypatch)
        first = GitignoreBoundary.load(worktree).excludes_file("hidden.py")
        second = GitignoreBoundary.load(worktree).excludes_file("hidden.py")
        assert first is True
        assert second is True
        assert calls[0] == 1

    def test_worktree_index_replacement_invalidates_the_cache(self, tmp_path: Path) -> None:
        """Taking the forced add back out rewrites the index; the next load
        must observe the removal."""
        worktree = self._make_worktree(tmp_path)
        _git(worktree, "add", "-f", "hidden.py")
        tracked = GitignoreBoundary.load(worktree).excludes_file("hidden.py")
        _git(worktree, "rm", "--quiet", "--cached", "hidden.py")
        reverted = GitignoreBoundary.load(worktree).excludes_file("hidden.py")
        assert tracked is False
        assert reverted is True

    def test_unresolvable_gitdir_marker_does_not_reuse_any_cache(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Without a trustworthy index identity there is no cache reuse:
        every load re-observes git and stays fail-open on failure."""
        (tmp_path / ".gitignore").write_text("*_gen.py\n", encoding="utf-8")
        (tmp_path / ".git").write_text("gitdir: ../missing-gitdir\n", encoding="utf-8")
        (tmp_path / "x_gen.py").write_text("x = 1\n", encoding="utf-8")
        calls = self._counting_git(monkeypatch)
        first = GitignoreBoundary.load(tmp_path)
        second = GitignoreBoundary.load(tmp_path)
        assert first.excludes_file("x_gen.py") is False
        assert second.excludes_file("x_gen.py") is False
        assert calls[0] == 2
