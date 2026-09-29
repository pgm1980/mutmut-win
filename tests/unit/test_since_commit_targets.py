"""Target selection for ``--since-commit`` (AP-16 / M-021, M-024).

M-021 (BC-015 / CLI-02): ``git diff`` ran without ``--relative``, so git
emitted repo-root-relative names while the target filter checked
``Path(name).exists()`` against the process CWD.  A run started inside a
repository subproject (monorepo) therefore selected NOTHING and still
exited 0 — a silent no-op instead of the requested incremental run.

M-024 (CLI-03): the tests_dir exclusion compared raw ``Path.parts``, so
absolute entries and ``..``-aliases never matched and changed test files
became mutation targets.  Both sides now canonicalize through
``_project_relative_parts``.

The unit tests use a recording ``subprocess.run`` dispatcher that encodes
git's path semantics: with ``--relative`` in argv the diff reports
CWD-relative names, without it repo-root-relative names.  Real-git
coverage lives in ``tests/integration/test_since_commit_git_subproject.py``.
"""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner
from hypothesis import given
from hypothesis import strategies as st

from mutmut_win.cli import cli
from mutmut_win.models import MutationRunResult

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


class GitDiffRecorder:
    """``subprocess.run`` double encoding git's ``--relative`` semantics.

    Git without ``--relative`` (and without ``diff.relative``) reports
    repo-root-relative paths; with ``--relative`` it reports paths relative
    to the process working directory and limits the diff to that subtree.
    The dispatcher returns different payloads for the two forms so a
    missing ``--relative`` cannot accidentally pass.
    """

    def __init__(self) -> None:
        self.calls: list[list[str]] = []
        self.relative_stdout = b""
        self.root_relative_stdout = b""
        self.returncode = 0

    def __call__(self, argv: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        self.calls.append(list(argv))
        if argv[:2] != ["git", "diff"]:
            raise AssertionError(
                f"unexpected subprocess argv while expecting a git diff call: {argv!r}"
            )
        stdout = self.relative_stdout if "--relative" in argv else self.root_relative_stdout
        return subprocess.CompletedProcess(
            args=argv, returncode=self.returncode, stdout=stdout, stderr=b""
        )


@pytest.fixture
def git_diff(monkeypatch: pytest.MonkeyPatch) -> GitDiffRecorder:
    """Replace ``subprocess.run`` with the recording git-diff dispatcher."""
    recorder = GitDiffRecorder()
    monkeypatch.setattr(subprocess, "run", recorder)
    return recorder


def _capturing_orchestrator(captured: dict[str, Any]) -> Callable[..., MagicMock]:
    """Build an orchestrator double recording the effective ``paths_to_mutate``."""

    def _fake(config: Any, **_kwargs: Any) -> MagicMock:
        captured["paths"] = list(config.paths_to_mutate)
        instance = MagicMock()
        instance.run.return_value = MutationRunResult(total_mutants=1, killed=1)
        return instance

    return _fake


def _invoke_since_commit_run(captured: dict[str, Any], *extra_args: str) -> Any:
    """Invoke ``run --since-commit`` with the heavy collaborators mocked."""
    with (
        patch("mutmut_win.cli.MutationOrchestrator", side_effect=_capturing_orchestrator(captured)),
        patch("mutmut_win.cli.PytestRunner"),
        patch("mutmut_win.cli.SpawnPoolExecutor"),
    ):
        return CliRunner().invoke(cli, ["run", "--since-commit", "HEAD~1", *extra_args])


class TestSubprojectRuns:
    def test_subproject_run_selects_project_relative_targets(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, git_diff: GitDiffRecorder
    ) -> None:
        # M-021: the project lives in <repo>/proj; git reports repo-root
        # names ("proj/src/mod.py") without --relative.  The old filter
        # checked that name against the project CWD, found nothing, and
        # ended the run as a silent exit-0 no-op.
        project = tmp_path / "repo" / "proj"
        (project / "src").mkdir(parents=True)
        (project / "src" / "mod.py").write_text("x = 1\n", encoding="utf-8")
        (project / "pyproject.toml").write_text(
            '[tool.mutmut]\npaths_to_mutate = ["src/"]\ntests_dir = ["tests/"]\n',
            encoding="utf-8",
        )
        monkeypatch.chdir(project)
        git_diff.relative_stdout = b"src/mod.py\0"
        git_diff.root_relative_stdout = b"proj/src/mod.py\0"

        captured: dict[str, Any] = {}
        result = _invoke_since_commit_run(captured)

        assert result.exit_code == 0, result.output
        assert captured["paths"] == ["src/mod.py"]
        # #128 guard, new form: exactly one revision (the ref itself), no
        # range operator — committed AND uncommitted changes count.
        assert git_diff.calls[0] == [
            "git",
            "diff",
            "--name-only",
            "-z",
            "--relative",
            "HEAD~1",
        ]
        assert not any(".." in arg for arg in git_diff.calls[0][1:])

    def test_toplevel_project_run_still_selects_targets(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, git_diff: GitDiffRecorder
    ) -> None:
        # Counter-check: project root == git top level.  --relative must be
        # a no-op there — the fix may not regress the common layout.
        project = tmp_path / "repo"
        (project / "src").mkdir(parents=True)
        (project / "src" / "mod.py").write_text("x = 1\n", encoding="utf-8")
        (project / "pyproject.toml").write_text(
            '[tool.mutmut]\npaths_to_mutate = ["src/"]\ntests_dir = ["tests/"]\n',
            encoding="utf-8",
        )
        monkeypatch.chdir(project)
        git_diff.relative_stdout = b"src/mod.py\0"
        git_diff.root_relative_stdout = b"src/mod.py\0"

        captured: dict[str, Any] = {}
        result = _invoke_since_commit_run(captured)

        assert result.exit_code == 0, result.output
        assert captured["paths"] == ["src/mod.py"]

    def test_invalid_ref_still_fails_with_exit_2(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, git_diff: GitDiffRecorder
    ) -> None:
        # The #102 returncode contract must survive the --relative rebuild.
        monkeypatch.chdir(tmp_path)
        git_diff.returncode = 128
        git_diff.relative_stdout = b""
        git_diff.root_relative_stdout = b""

        captured: dict[str, Any] = {}
        with (
            patch(
                "mutmut_win.cli.MutationOrchestrator",
                side_effect=_capturing_orchestrator(captured),
            ),
            patch("mutmut_win.cli.PytestRunner"),
            patch("mutmut_win.cli.SpawnPoolExecutor"),
        ):
            result = CliRunner().invoke(cli, ["run", "--since-commit", "not-a-ref"])

        assert result.exit_code == 2
        assert "git diff failed" in result.output
        assert "paths" not in captured


class TestTestsDirCanonicalization:
    """M-024 (CLI-03): absolute and ``..``-alias tests_dir entries must exclude.

    The old comparison used raw ``Path.parts``: absolute entries kept their
    drive anchor and ``..``-aliases kept their ``..`` components, so neither
    ever prefix-matched a changed name — changed test files became mutation
    targets and were silently mutated in the staging copy.
    """

    @pytest.mark.parametrize("entry_kind", ["absolute", "dotdot", "upper"])
    def test_absolute_and_alias_entries_exclude_changed_test_files(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        git_diff: GitDiffRecorder,
        entry_kind: str,
    ) -> None:
        project = tmp_path / "proj"
        (project / "src" / "tests").mkdir(parents=True)
        (project / "src" / "mod.py").write_text("x = 1\n", encoding="utf-8")
        (project / "src" / "tests" / "test_mod.py").write_text(
            "def test_x(): pass\n", encoding="utf-8"
        )
        (project / "pyproject.toml").write_text(
            '[tool.mutmut]\npaths_to_mutate = ["src/"]\ntests_dir = ["unused/"]\n',
            encoding="utf-8",
        )
        entries = {
            "absolute": str(project / "src" / "tests"),
            "dotdot": "src/../src/tests",
            "upper": str(project / "src" / "tests").upper(),
        }
        monkeypatch.chdir(project)
        git_diff.relative_stdout = b"src/mod.py\0src/tests/test_mod.py\0"
        git_diff.root_relative_stdout = git_diff.relative_stdout

        captured: dict[str, Any] = {}
        result = _invoke_since_commit_run(captured, "--tests-dir", entries[entry_kind])

        assert result.exit_code == 0, result.output
        assert captured["paths"] == ["src/mod.py"]

    def test_leading_separator_entry_still_excludes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, git_diff: GitDiffRecorder
    ) -> None:
        # Backwards compatibility: '/tests/' (and the backslash variant)
        # worked like 'tests' before because leading separators were
        # stripped — the canonicalization must keep that meaning instead
        # of failing open.
        project = tmp_path / "proj"
        (project / "src").mkdir(parents=True)
        (project / "src" / "mod.py").write_text("x = 1\n", encoding="utf-8")
        (project / "tests").mkdir()
        (project / "tests" / "test_mod.py").write_text("def test_x(): pass\n", encoding="utf-8")
        (project / "pyproject.toml").write_text(
            '[tool.mutmut]\npaths_to_mutate = ["src/"]\ntests_dir = ["unused/"]\n',
            encoding="utf-8",
        )
        monkeypatch.chdir(project)
        git_diff.relative_stdout = b"src/mod.py\0tests/test_mod.py\0"
        git_diff.root_relative_stdout = git_diff.relative_stdout

        captured: dict[str, Any] = {}
        result = _invoke_since_commit_run(captured, "--tests-dir", "\\tests\\")

        assert result.exit_code == 0, result.output
        assert captured["paths"] == ["src/mod.py"]

    def test_drive_anchored_entry_stays_ineffective(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, git_diff: GitDiffRecorder
    ) -> None:
        # 'C:tests' is relative to the DRIVE's current directory — it never
        # matched anything before and is documented as not comparable (None)
        # now.  The changed test file therefore stays a target; the entry
        # must not crash the run either.
        project = tmp_path / "proj"
        (project / "src").mkdir(parents=True)
        (project / "src" / "mod.py").write_text("x = 1\n", encoding="utf-8")
        (project / "tests").mkdir()
        (project / "tests" / "test_mod.py").write_text("def test_x(): pass\n", encoding="utf-8")
        (project / "pyproject.toml").write_text(
            '[tool.mutmut]\npaths_to_mutate = ["src/"]\ntests_dir = ["unused/"]\n',
            encoding="utf-8",
        )
        monkeypatch.chdir(project)
        git_diff.relative_stdout = b"src/mod.py\0tests/test_mod.py\0"
        git_diff.root_relative_stdout = git_diff.relative_stdout
        drive = project.drive
        assert drive, "tmp_path lives on a Windows drive"

        captured: dict[str, Any] = {}
        result = _invoke_since_commit_run(captured, "--tests-dir", f"{drive}tests")

        assert result.exit_code == 0, result.output
        assert captured["paths"] == ["src/mod.py", "tests/test_mod.py"]

    def test_project_root_entry_excludes_everything(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, git_diff: GitDiffRecorder
    ) -> None:
        # tests_dir '.' IS the project root: Path('.').parts == () made the
        # prefix comparison exclude EVERYTHING before — a documented
        # semantic the canonicalization keeps (empty tuple, not None).
        project = tmp_path / "proj"
        (project / "src").mkdir(parents=True)
        (project / "src" / "mod.py").write_text("x = 1\n", encoding="utf-8")
        (project / "pyproject.toml").write_text(
            '[tool.mutmut]\npaths_to_mutate = ["src/"]\ntests_dir = ["unused/"]\n',
            encoding="utf-8",
        )
        monkeypatch.chdir(project)
        git_diff.relative_stdout = b"src/mod.py\0"
        git_diff.root_relative_stdout = git_diff.relative_stdout

        captured: dict[str, Any] = {}
        result = _invoke_since_commit_run(captured, "--tests-dir", ".")

        assert result.exit_code == 0, result.output
        assert "No mutation-target .py files changed" in result.output
        assert "paths" not in captured


class TestProjectRelativeParts:
    """Unit coverage of the shared canonicalization helper (Q-33/M-024)."""

    def test_plain_relative_path(self, tmp_path: Path) -> None:
        from mutmut_win.cli import _project_relative_parts

        assert _project_relative_parts("src/mod.py", tmp_path) == ("src", "mod.py")

    def test_dotdot_alias_collapses(self, tmp_path: Path) -> None:
        from mutmut_win.cli import _project_relative_parts

        assert _project_relative_parts("src/../src/tests", tmp_path) == ("src", "tests")

    def test_absolute_entry_inside_project(self, tmp_path: Path) -> None:
        from mutmut_win.cli import _project_relative_parts

        assert _project_relative_parts(str(tmp_path / "src"), tmp_path) == ("src",)

    def test_absolute_entry_outside_project_is_none(self, tmp_path: Path) -> None:
        from mutmut_win.cli import _project_relative_parts

        project = tmp_path / "proj"
        project.mkdir()
        assert _project_relative_parts(str(tmp_path / "outside"), project) is None

    def test_drive_anchored_relative_form_is_none(self, tmp_path: Path) -> None:
        from mutmut_win.cli import _project_relative_parts

        assert _project_relative_parts("C:tests", tmp_path) is None

    def test_root_without_drive_stays_project_relative(self, tmp_path: Path) -> None:
        from mutmut_win.cli import _project_relative_parts

        assert _project_relative_parts("/tests/", tmp_path) == ("tests",)

    def test_backslash_separators_normalize(self, tmp_path: Path) -> None:
        from mutmut_win.cli import _project_relative_parts

        assert _project_relative_parts("src\\tests\\", tmp_path) == ("src", "tests")

    def test_node_id_suffix_is_split_off(self, tmp_path: Path) -> None:
        from mutmut_win.cli import _project_relative_parts

        entry = "tests/unit/test_x.py::TestA::test_b"
        assert _project_relative_parts(entry, tmp_path) == ("tests", "unit", "test_x.py")

    def test_case_differences_do_not_matter(self, tmp_path: Path) -> None:
        from mutmut_win.cli import _project_relative_parts

        assert _project_relative_parts("SRC/Mod.PY", tmp_path) == ("src", "mod.py")

    def test_project_root_entry_is_the_empty_tuple(self, tmp_path: Path) -> None:
        from mutmut_win.cli import _project_relative_parts

        assert _project_relative_parts(".", tmp_path) == ()

    def test_dotdot_escaping_the_project_is_none(self, tmp_path: Path) -> None:
        from mutmut_win.cli import _project_relative_parts

        project = tmp_path / "proj"
        project.mkdir()
        assert _project_relative_parts("../outside/mod.py", project) is None


@given(
    spelling=st.sampled_from(["absolute", "dot_segment", "upper", "trailing_sep"]),
    insertions=st.integers(min_value=0, max_value=2),
)
def test_alias_spellings_of_one_entry_share_the_canonical_parts(
    tmp_path_factory: pytest.TempPathFactory, spelling: str, insertions: int
) -> None:
    """Everyday alias spellings of ``src/tests`` canonicalize identically."""
    from mutmut_win.cli import _project_relative_parts

    root = tmp_path_factory.mktemp("m024_alias_root")
    canonical = "src/tests"
    if spelling == "absolute":
        entry = str(root / "src" / "tests")
    elif spelling == "dot_segment":
        entry = "src/" + "x/../" * insertions + "tests"
    elif spelling == "upper":
        entry = canonical.upper()
    else:
        entry = canonical + "/" * (insertions + 1)

    assert _project_relative_parts(entry, root) == _project_relative_parts(canonical, root)
    assert _project_relative_parts(canonical, root) == ("src", "tests")
