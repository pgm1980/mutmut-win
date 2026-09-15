"""Contract tests for the hierarchical .gitignore walk boundary.

Pins the MBR-2026-09-14-01 fix semantics: staging and basis walks must be
able to prune git-ignored subtrees (e.g. ``tests/test_project/.lake`` with
120k files) without ever excluding a file that Git itself would track.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from mutmut_win.gitignore_boundary import GitignoreBoundary

if TYPE_CHECKING:
    import pytest


def _make_project(tmp_path: Path, *files: tuple[str, str | bytes]) -> Path:
    for relative, payload in files:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(payload, bytes):
            target.write_bytes(payload)
        else:
            target.write_text(payload, encoding="utf-8")
    return tmp_path


class TestRootIgnoreFile:
    def test_ignored_directory_is_excluded(self, tmp_path: Path) -> None:
        project = _make_project(tmp_path, (".gitignore", ".lake/\n"))
        boundary = GitignoreBoundary.load(project)
        assert boundary.excludes_directory("tests") is False
        tests = boundary.enter("tests")
        assert tests.excludes_directory("test_project") is False
        project_level = tests.enter("test_project")
        assert project_level.excludes_directory(".lake") is True

    def test_ignored_file_is_excluded(self, tmp_path: Path) -> None:
        project = _make_project(tmp_path, (".gitignore", "*.log\n"))
        boundary = GitignoreBoundary.load(project)
        assert boundary.excludes_file("debug.log") is True
        assert boundary.excludes_file("keep.txt") is False

    def test_missing_gitignore_excludes_nothing(self, tmp_path: Path) -> None:
        boundary = GitignoreBoundary.load(tmp_path)
        assert boundary.excludes_directory("anything") is False
        assert boundary.excludes_file("anything.txt") is False


class TestNestedIgnoreFiles:
    def test_nested_file_only_governs_its_subtree(self, tmp_path: Path) -> None:
        project = _make_project(
            tmp_path,
            ("tests/test_project/.gitignore", "build/\n"),
        )
        boundary = GitignoreBoundary.load(project)
        # Root level: a "build" directory is NOT ignored there.
        assert boundary.excludes_directory("build") is False
        tests = boundary.enter("tests")
        project_level = tests.enter("test_project")
        assert project_level.excludes_directory("build") is True
        deeper = project_level.enter("build")
        assert deeper.excludes_file("artifact.bin") is True

    def test_deeper_ignore_overrides_shallower_ignore(self, tmp_path: Path) -> None:
        project = _make_project(
            tmp_path,
            (".gitignore", "*.log\n"),
            ("logs/.gitignore", "!important.log\n"),
        )
        boundary = GitignoreBoundary.load(project)
        assert boundary.excludes_file("debug.log") is True
        logs = boundary.enter("logs")
        # The deeper file re-includes what the root ignores.
        assert logs.excludes_file("important.log") is False
        assert logs.excludes_file("other.log") is True

    def test_deeper_negation_does_not_reinclude_when_root_deeper_wins(
        self,
        tmp_path: Path,
    ) -> None:
        """Only-negation deeper files must still count as an opinion.

        ``logs/.gitignore`` containing only ``!keep.log`` must make the root
        ``*.log`` ignore lose for ``keep.log`` — Git tracks that file.
        """
        project = _make_project(
            tmp_path,
            (".gitignore", "*.log\n"),
            ("logs/.gitignore", "!keep.log\n"),
        )
        boundary = GitignoreBoundary.load(project)
        logs = boundary.enter("logs")
        assert logs.excludes_file("keep.log") is False
        assert logs.excludes_file("drop.log") is True


class TestPatternSemantics:
    def test_anchored_pattern_only_matches_at_root(self, tmp_path: Path) -> None:
        project = _make_project(tmp_path, (".gitignore", "/dist/\n"))
        boundary = GitignoreBoundary.load(project)
        assert boundary.excludes_directory("dist") is True
        tests = boundary.enter("tests")
        assert tests.excludes_directory("dist") is False

    def test_unanchored_directory_pattern_matches_at_any_depth(
        self,
        tmp_path: Path,
    ) -> None:
        project = _make_project(tmp_path, (".gitignore", "build/\n"))
        boundary = GitignoreBoundary.load(project)
        assert boundary.excludes_directory("build") is True
        nested = boundary.enter("src").enter("pkg")
        assert nested.excludes_directory("build") is True

    def test_negation_within_one_file(self, tmp_path: Path) -> None:
        project = _make_project(tmp_path, (".gitignore", "*.log\n!keep.log\n"))
        boundary = GitignoreBoundary.load(project)
        assert boundary.excludes_file("drop.log") is True
        assert boundary.excludes_file("keep.log") is False

    def test_excluded_parent_directory_prunes_subtree(self, tmp_path: Path) -> None:
        """Git semantics: files under an excluded directory stay excluded."""
        project = _make_project(tmp_path, (".gitignore", ".lake/\n!keep.json\n"))
        boundary = GitignoreBoundary.load(project)
        lake = boundary.enter("tests").enter("test_project").enter(".lake")
        assert lake.excludes_file("keep.json") is True


class TestFailClosedBehaviour:
    def test_undecodable_gitignore_excludes_nothing(
        self,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        (tmp_path / ".gitignore").write_bytes(b"\xff\xfe\x00bad\n.lake/\n")
        with caplog.at_level(logging.WARNING, logger="mutmut_win.gitignore_boundary"):
            boundary = GitignoreBoundary.load(tmp_path)
        assert boundary.excludes_directory(".lake") is False
        assert any("gitignore" in record.message.lower() for record in caplog.records)

    def test_unreadable_gitignore_excludes_nothing(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        project = tmp_path
        (project / ".gitignore").write_text(".lake/\n", encoding="utf-8")

        real_read_bytes = Path.read_bytes

        def refuse_gitignore_read(self: Path) -> bytes:
            if self.name == ".gitignore":
                raise PermissionError(13, "Permission denied")
            return real_read_bytes(self)

        monkeypatch.setattr(Path, "read_bytes", refuse_gitignore_read)
        boundary = GitignoreBoundary.load(project)
        assert boundary.excludes_directory(".lake") is False

    def test_enter_of_directory_with_broken_gitignore_still_walks(
        self,
        tmp_path: Path,
    ) -> None:
        project = _make_project(
            tmp_path,
            ("src/.gitignore", b"\xff\xfe\x00broken\nsecret/\n"),
        )
        boundary = GitignoreBoundary.load(project)
        src = boundary.enter("src")
        assert src.excludes_directory("secret") is False


class TestBoundaryImmutability:
    def test_enter_returns_new_boundary(self, tmp_path: Path) -> None:
        project = _make_project(tmp_path, (".gitignore", "logs/\n"))
        boundary = GitignoreBoundary.load(project)
        child = boundary.enter("src")
        assert child is not boundary
        # The parent boundary is unchanged by descending.
        assert boundary.excludes_directory("logs") is True
