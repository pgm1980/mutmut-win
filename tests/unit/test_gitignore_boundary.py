"""Contract tests for the hierarchical .gitignore walk boundary.

Pins the MBR-2026-09-14-01 fix semantics: staging and basis walks must be
able to prune git-ignored subtrees (e.g. ``tests/test_project/.lake`` with
120k files) without ever excluding a file that Git itself would track.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

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

        class _ExplodingRegex:
            pattern = "(?:.+/)?\\.lake(?P<ps_d>/)"
            flags = 0
            groupindex: ClassVar[dict[str, int]] = {"ps_d": 1}

            def search(self, _probe: str) -> object:
                raise RuntimeError("pattern engine failure")

        class _ExplodingPattern:
            include = True
            regex = _ExplodingRegex()

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


# ---------------------------------------------------------------------------
# Tracked-index override (M-001, issue #146): tracked files are never pruned
# ---------------------------------------------------------------------------


def _tracked_index(
    files: set[str] | None = None, *, unknown: bool = False
) -> gitignore_boundary._TrackedIndex:
    """Build a _TrackedIndex for testing."""
    file_set = frozenset(f.casefold() for f in (files or set()))
    dirs: set[str] = set()
    for f in files or set():
        parts = f.split("/")
        for i in range(1, len(parts)):
            dirs.add("/".join(parts[:i]).casefold())
    return gitignore_boundary._TrackedIndex(
        files=file_set,
        directories=frozenset(dirs),
        unknown=unknown,
    )


class TestTrackedIndexOverride:
    """M-001: tracked files are never excluded by gitignore patterns."""

    def test_tracked_file_ignored_by_pattern_is_included(self, tmp_path: Path) -> None:
        """A tracked file matching an ignore pattern is NOT excluded."""
        project = _make_project(tmp_path, (".gitignore", "*_gen.py\n"))
        (project / "src" / "pkg").mkdir(parents=True)
        (project / "src" / "pkg" / "api_gen.py").write_text("x = 1\n", encoding="utf-8")
        (project / "src" / "pkg" / "other_gen.py").write_text("x = 2\n", encoding="utf-8")

        original_load = gitignore_boundary._load_tracked_index
        gitignore_boundary._load_tracked_index = lambda _root: _tracked_index(
            {"src/pkg/api_gen.py"}
        )
        try:
            boundary = GitignoreBoundary.load(project).descend_forced("src").enter("pkg")
            assert boundary.excludes_file("api_gen.py") is False
            assert boundary.excludes_file("other_gen.py") is True
        finally:
            gitignore_boundary._load_tracked_index = original_load

    def test_tracked_directory_not_excluded(self, tmp_path: Path) -> None:
        """A directory containing tracked files is never excluded."""
        project = _make_project(tmp_path, (".gitignore", "build/\n"))
        (project / "build").mkdir()
        (project / "build" / "generated.py").write_text("x = 1\n", encoding="utf-8")

        original_load = gitignore_boundary._load_tracked_index
        gitignore_boundary._load_tracked_index = lambda _root: _tracked_index(
            {"build/generated.py"}
        )
        try:
            boundary = GitignoreBoundary.load(project)
            assert boundary.excludes_directory("build") is False
        finally:
            gitignore_boundary._load_tracked_index = original_load

    def test_unknown_tracked_index_excludes_nothing(self, tmp_path: Path) -> None:
        """Git failure (unknown) disables pruning entirely for safety."""
        project = _make_project(tmp_path, (".gitignore", "*_gen.py\nlogs/\n"))
        original_load = gitignore_boundary._load_tracked_index
        gitignore_boundary._load_tracked_index = lambda _root: _tracked_index(unknown=True)
        try:
            boundary = GitignoreBoundary.load(project)
            assert boundary.excludes_file("x_gen.py") is False
            assert boundary.excludes_directory("logs") is False
        finally:
            gitignore_boundary._load_tracked_index = original_load

    def test_no_repo_keeps_pure_pattern_verdict(self, tmp_path: Path) -> None:
        """Without .git, the tracked index is empty and patterns apply."""
        project = _make_project(tmp_path, (".gitignore", "*_gen.py\n"))
        original_load = gitignore_boundary._load_tracked_index
        gitignore_boundary._load_tracked_index = lambda _root: _tracked_index()
        try:
            boundary = GitignoreBoundary.load(project)
            assert boundary.excludes_file("x_gen.py") is True
        finally:
            gitignore_boundary._load_tracked_index = original_load

    def test_descend_forced_keeps_git_add_f_semantics_for_untracked(self, tmp_path: Path) -> None:
        """Counter-review correction 1: the branch decision in descend_forced
        must use the PURE pattern verdict, not the tracked override.

        An ignored configured entry with tracked content must keep the
        git-add-f reset branch (ancestral patterns discarded), so untracked
        files underneath are NOT accidentally pruned by ancestor rules.
        """
        project = _make_project(tmp_path, (".gitignore", "generated/\n"))
        (project / "generated").mkdir()
        (project / "generated" / "tracked_file.py").write_text("x = 1\n", encoding="utf-8")
        (project / "generated" / "untracked_ignored.py").write_text("x = 2\n", encoding="utf-8")
        (project / "generated" / ".gitignore").write_text(
            "untracked_ignored.py\n", encoding="utf-8"
        )

        original_load = gitignore_boundary._load_tracked_index
        gitignore_boundary._load_tracked_index = lambda _root: _tracked_index(
            {"generated/tracked_file.py"}
        )
        try:
            # 'generated' is ignored by the root .gitignore; descend_forced
            # must take the RESET branch (ancestral patterns discarded).
            boundary = GitignoreBoundary.load(project).descend_forced("generated")
            # The tracked file is included by the local .gitignore override.
            assert boundary.excludes_file("tracked_file.py") is False
            # The local .gitignore still prunes its own patterns.
            assert boundary.excludes_file("untracked_ignored.py") is True
        finally:
            gitignore_boundary._load_tracked_index = original_load

    def test_tracked_boundary_propagates_through_enter(self, tmp_path: Path) -> None:
        """The tracked index propagates through enter/descend chains."""
        project = _make_project(tmp_path, (".gitignore", "*.pyc\n"))
        original_load = gitignore_boundary._load_tracked_index
        gitignore_boundary._load_tracked_index = lambda _root: _tracked_index(
            {"src/deep/module.pyc"}
        )
        try:
            boundary = GitignoreBoundary.load(project)
            deep = boundary.enter("src").enter("deep")
            assert deep.excludes_file("module.pyc") is False
            assert deep.excludes_file("other.pyc") is True
        finally:
            gitignore_boundary._load_tracked_index = original_load


class TestForcedRootAtNestedBoundary:
    """AR-02 (COR-002/C-003): the forced-root reset must be decided at the
    boundary the descent actually reached, not at the walk root.

    ``pkg/.gitignore`` rules load only while descending; a ``descend_forced``
    branch decision taken on the root boundary never sees them, so the
    explicit root was pinned as an excluded subtree instead of being reset.
    """

    def test_nested_gitignore_exclusion_triggers_forced_reset(self, tmp_path: Path) -> None:
        """An explicit root excluded by a nested ignore file is force-reset."""
        project = _make_project(
            tmp_path,
            ("pkg/.gitignore", "sub/\n"),
            ("pkg/sub/api.py", "def answer(): return 42\n"),
        )
        boundary = GitignoreBoundary.load(project).descend_forced("pkg", "sub")
        assert boundary.excludes_file("api.py") is False

    def test_forced_root_below_nested_ignore_keeps_its_own_deeper_rules(
        self,
        tmp_path: Path,
    ) -> None:
        """Only rules AT or BELOW the forced entry restart governance."""
        project = _make_project(
            tmp_path,
            ("pkg/.gitignore", "sub/\n"),
            ("pkg/sub/.gitignore", "tmp/\n*.log\n"),
            ("pkg/sub/api.py", "x = 1\n"),
        )
        boundary = GitignoreBoundary.load(project).descend_forced("pkg", "sub")
        assert boundary.excludes_file("api.py") is False
        assert boundary.excludes_directory("tmp") is True
        assert boundary.excludes_file("drop.log") is True

    def test_deeply_nested_forced_root_through_two_ignored_levels(
        self,
        tmp_path: Path,
    ) -> None:
        """The reset also covers rules pinned by an excluded ancestor chain."""
        project = _make_project(
            tmp_path,
            ("a/.gitignore", "b/\n"),
            ("a/b/c/api.py", "x = 1\n"),
        )
        boundary = GitignoreBoundary.load(project).descend_forced("a", "b", "c")
        assert boundary.excludes_file("api.py") is False

    def test_forced_reset_discards_ancestral_negation_like_git_add_f(
        self,
        tmp_path: Path,
    ) -> None:
        """``git add -f`` force-adds the whole entry; ancestral negations
        below an excluded directory cannot re-govern it after the reset."""
        project = _make_project(
            tmp_path,
            ("pkg/.gitignore", "sub/\n!sub/keep.py\n"),
            ("pkg/sub/keep.py", "x = 1\n"),
        )
        boundary = GitignoreBoundary.load(project).descend_forced("pkg", "sub")
        assert boundary.excludes_file("keep.py") is False

    def test_visible_entry_below_nested_ignore_still_descends_normally(
        self,
        tmp_path: Path,
    ) -> None:
        """An entry NOT excluded by the nested rules keeps normal descent, so
        file patterns from intermediate ignore files still prune inside it."""
        project = _make_project(
            tmp_path,
            ("pkg/.gitignore", "*.log\n"),
            ("pkg/sub/api.py", "x = 1\n"),
        )
        boundary = GitignoreBoundary.load(project).descend_forced("pkg", "sub")
        assert boundary.excludes_file("api.py") is False
        assert boundary.excludes_file("drop.log") is True

    def test_unconfigured_nested_ignored_sibling_stays_excluded(
        self,
        tmp_path: Path,
    ) -> None:
        """The forced reset applies to the configured entry only: a sibling
        excluded by the same nested ignore file stays pruned for walks that
        descend normally."""
        project = _make_project(
            tmp_path,
            ("pkg/.gitignore", "sub/\nsibling/\n"),
            ("pkg/sub/api.py", "x = 1\n"),
            ("pkg/sibling/keep.txt", "keep\n"),
        )
        pkg = GitignoreBoundary.load(project).enter("pkg")
        assert pkg.excludes_directory("sub") is True
        assert pkg.excludes_directory("sibling") is True


class TestTrackedIndexStageParsing:
    """AR-03 (COR-003): gitlink records land in the directory override set.

    The loader consumes ``git ls-files -z --cached --stage`` records
    (``<mode> <object> <stage><SEP><path>``, SEP is a tab on current git and
    a space on some versions) and must classify gitlinks (mode 160000) as
    tracked directories without guessing directory-ness for normal files.
    """

    @staticmethod
    def _fake_ls_files(monkeypatch: pytest.MonkeyPatch, stdout: bytes) -> None:
        completed = subprocess.CompletedProcess([], 0, stdout=stdout, stderr=b"")
        monkeypatch.setattr(
            gitignore_boundary.subprocess,
            "run",
            lambda *_args, **_kwargs: completed,
        )

    def test_gitlink_record_lands_in_directories(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_path / ".git").mkdir()
        payload = (
            b"160000 1111111111111111111111111111111111111111 0\tvendor\x00"
            b"100644 2222222222222222222222222222222222222222 0\tsrc/x.py\x00"
        )
        self._fake_ls_files(monkeypatch, payload)
        index = gitignore_boundary._load_tracked_index(tmp_path)
        assert "vendor" in index.files
        assert "vendor" in index.directories
        assert "src/x.py" in index.files
        assert "src" in index.directories
        assert "src/x.py" not in index.directories

    def test_space_separated_stage_records_parse_too(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Some git versions emit a space separator with ``-z``."""
        (tmp_path / ".git").mkdir()
        payload = b"160000 1111111111111111111111111111111111111111 0 sub/deps/vendor\x00"
        self._fake_ls_files(monkeypatch, payload)
        index = gitignore_boundary._load_tracked_index(tmp_path)
        assert {"sub", "sub/deps", "sub/deps/vendor"} <= index.directories

    def test_unparseable_record_keeps_plain_path_behaviour(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A record without stage metadata degrades to the old file-path
        treatment instead of dropping the entry."""
        (tmp_path / ".git").mkdir()
        self._fake_ls_files(monkeypatch, b"plain/odd\x00")
        index = gitignore_boundary._load_tracked_index(tmp_path)
        assert "plain/odd" in index.files
        assert "plain" in index.directories
        assert "plain/odd" not in index.directories


class TestUnknownLevelsAndBom:
    """M-015/M-014: broken child levels suspend inherited rules; BOM honoured."""

    def test_unreadable_child_level_suspends_inherited_exclusions(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        project = _make_project(
            tmp_path,
            (".gitignore", "*.py\n"),
            ("src/.gitignore", "!keep.py\n"),
        )
        broken = project / "src" / ".gitignore"
        real_read_bytes = Path.read_bytes

        def failing_read_bytes(self: Path) -> bytes:
            if self == broken:
                raise PermissionError(5, "Access is denied")
            return real_read_bytes(self)

        monkeypatch.setattr(Path, "read_bytes", failing_read_bytes)
        boundary = GitignoreBoundary.load(project).enter("src")
        assert boundary.excludes_file("keep.py") is False

    def test_invalid_pattern_child_level_suspends_inherited_exclusions(
        self,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        project = _make_project(
            tmp_path,
            (".gitignore", "*.py\n"),
            ("src/.gitignore", "!keep.py\n!\n"),
        )
        with caplog.at_level(logging.WARNING, logger="mutmut_win.gitignore_boundary"):
            boundary = GitignoreBoundary.load(project).enter("src")
        assert boundary.excludes_file("keep.py") is False
        text = " ".join(
            record.getMessage() for record in caplog.records if record.levelno == logging.WARNING
        )
        assert ".gitignore" in text
        assert "excludes nothing" in text

    def test_deeper_readable_level_below_unknown_still_decides(
        self,
        tmp_path: Path,
    ) -> None:
        project = _make_project(
            tmp_path,
            (".gitignore", "*.py\n"),
            ("src/.gitignore", "!\n"),
            ("src/sub/.gitignore", "x.log\n"),
        )
        boundary = GitignoreBoundary.load(project).enter("src").enter("sub")
        assert boundary.excludes_file("x.log") is True
        assert boundary.excludes_file("other.py") is False

    def test_descend_forced_reset_with_unknown_level_excludes_nothing(
        self,
        tmp_path: Path,
    ) -> None:
        project = _make_project(
            tmp_path,
            (".gitignore", "src/\n*.py\n"),
            ("src/.gitignore", "!\n"),
        )
        boundary = GitignoreBoundary.load(project).descend_forced("src")
        assert boundary.excludes_file("a.py") is False

    def test_bom_first_pattern_is_honoured(self, tmp_path: Path) -> None:
        project = _make_project(
            tmp_path,
            (".gitignore", b"\xef\xbb\xbf.lake/\n*.log\n"),
        )
        boundary = GitignoreBoundary.load(project)
        assert boundary.excludes_directory(".lake") is True
        assert boundary.excludes_file("a.log") is True

    def test_bom_in_child_level_is_honoured(self, tmp_path: Path) -> None:
        project = _make_project(
            tmp_path,
            (".gitignore", "*.py\n"),
            ("src/.gitignore", b"\xef\xbb\xbfsecret/\n"),
        )
        boundary = GitignoreBoundary.load(project).enter("src")
        assert boundary.excludes_directory("secret") is True

    def test_bom_reinclusion_in_child_level(self, tmp_path: Path) -> None:
        project = _make_project(
            tmp_path,
            (".gitignore", "*.py\n"),
            ("src/.gitignore", b"\xef\xbb\xbf!keep.py\n"),
        )
        boundary = GitignoreBoundary.load(project).enter("src")
        assert boundary.excludes_file("keep.py") is False

    def test_bom_only_file_carries_no_rules(self, tmp_path: Path) -> None:
        project = _make_project(tmp_path, (".gitignore", b"\xef\xbb\xbf"))
        boundary = GitignoreBoundary.load(project)
        assert boundary.excludes_file("anything.py") is False

    def test_bom_before_comment_then_rule(self, tmp_path: Path) -> None:
        project = _make_project(tmp_path, (".gitignore", b"\xef\xbb\xbf# c\n.lake/\n"))
        boundary = GitignoreBoundary.load(project)
        assert boundary.excludes_directory(".lake") is True


class TestDirMarkerPrecedence:
    """M-017: directory-marker precedence must mirror Git within one level.

    A negation that hits the candidate only through an ANCESTOR directory
    marker cannot override an earlier real path match; an end-anchored own
    marker is a path match.  Derived against ``git check-ignore`` (see the
    integration oracle test).
    """

    def test_negated_dir_cannot_reinstate_files_under_path_match(self, tmp_path: Path) -> None:
        project = _make_project(
            tmp_path,
            (".gitignore", "*.pyc\n!vendor/\n"),
            ("vendor/x.pyc", ""),
        )
        boundary = GitignoreBoundary.load(project).enter("vendor")
        assert boundary.excludes_file("x.pyc") is True

    def test_whitelist_idiom_keeps_directories_but_files_stay_excluded(
        self,
        tmp_path: Path,
    ) -> None:
        project = _make_project(
            tmp_path,
            (".gitignore", "*\n!*/\n"),
            ("a/b.txt", ""),
        )
        boundary = GitignoreBoundary.load(project)
        assert boundary.excludes_directory("a") is False
        assert boundary.enter("a").excludes_file("b.txt") is True

    def test_negated_parent_dir_does_not_reinstate_subdirectories(
        self,
        tmp_path: Path,
    ) -> None:
        project = _make_project(
            tmp_path,
            (".gitignore", "*\n!a/\n"),
        )
        boundary = GitignoreBoundary.load(project).enter("a")
        assert boundary.excludes_directory("sub") is True

    def test_nested_directories_stay_reincluded_under_whitelist(
        self,
        tmp_path: Path,
    ) -> None:
        # Regression guard for the rejected first design: a/sub is NOT
        # excluded under ['*', '!*/'].
        project = _make_project(tmp_path, (".gitignore", "*\n!*/\n"))
        boundary = GitignoreBoundary.load(project).enter("a")
        assert boundary.excludes_directory("sub") is False

    def test_whitelist_file_negation_reinstates_nested_files(self, tmp_path: Path) -> None:
        project = _make_project(
            tmp_path,
            (".gitignore", "*\n!*/\n!x.pyc\n"),
        )
        boundary = GitignoreBoundary.load(project).enter("a").enter("sub")
        assert boundary.excludes_file("x.pyc") is False

    def test_globstar_dir_negation_excludes_files_and_subtrees(self, tmp_path: Path) -> None:
        project = _make_project(
            tmp_path,
            (".gitignore", "a/**\n!a/\n"),
        )
        boundary = GitignoreBoundary.load(project).enter("a")
        assert boundary.excludes_file("x.pyc") is True
        assert boundary.excludes_directory("sub") is True

    def test_equal_patterns_last_match_wins_for_files(self, tmp_path: Path) -> None:
        project = _make_project(
            tmp_path,
            (".gitignore", "vendor/\n!vendor/\n"),
            ("vendor/x.pyc", ""),
        )
        boundary = GitignoreBoundary.load(project).enter("vendor")
        # The directory is re-included (own end marker, equal priority, last
        # match wins); the FILE matches no pattern itself and stays kept -
        # exactly what git check-ignore reports.
        assert boundary.excludes_file("x.pyc") is False

    def test_root_whitelist_idiom(self, tmp_path: Path) -> None:
        project = _make_project(
            tmp_path,
            (".gitignore", "/*\n!/src/\n!*.pyc\n"),
        )
        boundary = GitignoreBoundary.load(project)
        assert boundary.excludes_directory("src") is False
        assert boundary.enter("src").excludes_directory("sub") is False
