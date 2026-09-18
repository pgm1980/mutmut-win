"""Contract tests for the hierarchical .gitignore walk boundary.

Pins the MBR-2026-09-14-01 fix semantics: staging and basis walks must be
able to prune git-ignored subtrees (e.g. ``tests/test_project/.lake`` with
120k files) without ever excluding a file that Git itself would track.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from mutmut_win import gitignore_boundary
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

    def test_anchored_pattern_in_nested_file_anchors_at_that_file(
        self,
        tmp_path: Path,
    ) -> None:
        """A leading slash anchors to the ignore file's own directory.

        Git resolves every pattern relative to the directory holding the
        ``.gitignore``.  ``/build/`` in ``tests/test_project/.gitignore``
        therefore governs ``tests/test_project/build`` — not a ``build``
        directory at the walk root, and not one further down.
        """
        project = _make_project(
            tmp_path,
            ("tests/test_project/.gitignore", "/build/\n"),
        )
        boundary = GitignoreBoundary.load(project)
        assert boundary.excludes_directory("build") is False
        project_level = boundary.enter("tests").enter("test_project")
        assert project_level.excludes_directory("build") is True
        deeper = project_level.enter("src")
        assert deeper.excludes_directory("build") is False

    def test_nested_pattern_never_matches_an_ancestor_component(
        self,
        tmp_path: Path,
    ) -> None:
        """Patterns must not see the path above their own ignore file.

        ``logs/.gitignore`` containing ``logs`` governs entries *inside*
        ``logs/``.  Matching it against the walk-root-relative path lets the
        ancestor component ``logs/`` satisfy the pattern and wrongly drops
        ``logs/app.txt`` from staging and from the execution-basis digest —
        the fail-closed direction this module promises never to take.
        """
        project = _make_project(tmp_path, ("logs/.gitignore", "logs\n"))
        boundary = GitignoreBoundary.load(project)
        logs = boundary.enter("logs")
        assert logs.excludes_file("app.txt") is False
        assert logs.excludes_directory("logs") is True

    def test_slashed_pattern_in_nested_file_is_relative_to_that_file(
        self,
        tmp_path: Path,
    ) -> None:
        """A pattern containing a slash is anchored to its own directory."""
        project = _make_project(tmp_path, ("pkg/.gitignore", "out/cache/\n"))
        boundary = GitignoreBoundary.load(project)
        out = boundary.enter("pkg").enter("out")
        assert out.excludes_directory("cache") is True
        assert boundary.enter("out").excludes_directory("cache") is False


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


class TestDescend:
    def test_descend_applies_every_real_component(self, tmp_path: Path) -> None:
        """Each non-empty part must actually enter, and empty parts must not stop it.

        The anchored ``/dist/`` only holds at the walk root, so the prefix the
        descent produces is observable: a descent that silently stays at the
        root still reports ``dist`` as ignored.
        """
        project = _make_project(tmp_path, (".gitignore", "/dist/\n"))
        boundary = GitignoreBoundary.load(project)
        assert boundary.excludes_directory("dist") is True
        assert boundary.descend("src", "pkg").excludes_directory("dist") is False
        # An empty or "." component is skipped, and the descent continues.
        assert boundary.descend("", "src", ".", "pkg").excludes_directory("dist") is False
        # No components at all is the identity.
        assert boundary.descend().excludes_directory("dist") is True


class TestPatternEngineFailure:
    def test_failing_pattern_degrades_to_no_opinion(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """A third-party pattern crash must never break or bias the walk.

        The documented contract is "no opinion": the walk keeps going and the
        entry stays included.  The diagnostic record has to name the evaluated
        path and carry the traceback, otherwise the failure is invisible.
        """

        class _ExplodingPattern:
            include = True

            def match_file(self, _relative: str) -> object:
                raise RuntimeError("pattern engine failure")

        class _ExplodingSpec:
            patterns = (_ExplodingPattern(),)

            @classmethod
            def from_lines(cls, _lines: list[str]) -> _ExplodingSpec:
                return cls()

        monkeypatch.setattr(gitignore_boundary, "GitIgnoreSpec", _ExplodingSpec)
        project = _make_project(tmp_path, (".gitignore", ".lake/\n"))
        with caplog.at_level(logging.DEBUG, logger="mutmut_win.gitignore_boundary"):
            boundary = GitignoreBoundary.load(project)
            assert boundary.excludes_directory(".lake") is False
            assert boundary.excludes_file("keep.txt") is False
        records = [record for record in caplog.records if record.levelno == logging.DEBUG]
        assert records, "a failing pattern must leave a diagnostic record"
        text = records[0].getMessage()
        assert "gitignore pattern evaluation failed" in text
        assert "'.lake'" in text
        assert records[0].exc_info is not None


class TestFailClosedBehaviour:
    def test_undecodable_gitignore_warning_names_path_and_error(
        self,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """The fail-closed warning must identify the file and the failure."""
        (tmp_path / ".gitignore").write_bytes(b"\xff\xfe\x00bad\n.lake/\n")
        with caplog.at_level(logging.WARNING, logger="mutmut_win.gitignore_boundary"):
            GitignoreBoundary.load(tmp_path)
        warnings = [record for record in caplog.records if record.levelno == logging.WARNING]
        assert len(warnings) == 1
        text = warnings[0].getMessage()
        assert str(tmp_path / ".gitignore") in text
        assert "UnicodeDecodeError" in text
        assert "it excludes nothing" in text

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
