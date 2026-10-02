"""Real-git ``--since-commit`` coverage (AP-16 / M-021, M-022).

The unit tests in ``tests/unit/test_since_commit_targets.py`` emulate git's
``--relative`` and rev-parse semantics with a dispatcher.  These tests prove
the behaviour against a real repository: a project inside a git subfolder
(monorepo layout), a project at the git top level, the historical
``diff.relative=true`` escape hatch, and — M-022 — ref resolution for
branches, tags, commits and the rejection of option-like, pathspec-like,
range, tree and blob values.  Git for Windows is part of the environment
contract (same rationale as ``test_mutant_diff.py``); the skipif only
guards exotic CI images.
"""

from __future__ import annotations

import shutil
import subprocess
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from mutmut_win.cli import cli
from mutmut_win.models import MutationRunResult

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git is not on PATH")


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(  # noqa: S603 — git CLI, argv fully controlled by the test
        [  # noqa: S607 — git is a well-known executable
            "git",
            "-c",
            "user.email=mutmut-win@example.com",
            "-c",
            "user.name=mutmut-win test",
            *args,
        ],
        cwd=cwd,
        check=True,
        capture_output=True,
    )


def _make_project(project: Path) -> None:
    (project / "src").mkdir(parents=True)
    (project / "src" / "mod.py").write_text("x = 1\n", encoding="utf-8")
    (project / "pyproject.toml").write_text(
        '[tool.mutmut]\npaths_to_mutate = ["src/"]\ntests_dir = ["tests/"]\n',
        encoding="utf-8",
    )


def _invoke_and_capture(captured: dict[str, Any], ref: str = "HEAD") -> Any:
    def _fake(config: Any, **_kwargs: Any) -> MagicMock:
        captured["paths"] = list(config.paths_to_mutate)
        instance = MagicMock()
        instance.run.return_value = MutationRunResult(total_mutants=1, killed=1)
        return instance

    with (
        patch("mutmut_win.cli.MutationOrchestrator", side_effect=_fake),
        patch("mutmut_win.cli.PytestRunner"),
        patch("mutmut_win.cli.SpawnPoolExecutor"),
    ):
        # Diff against the resolved commit alone (no ..HEAD): the
        # uncommitted working-tree edit below is what the #128 contract
        # must keep visible.
        return CliRunner().invoke(cli, ["run", "--since-commit", ref])


def test_subproject_run_selects_targets_with_real_git(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    project = repo / "proj"
    _make_project(project)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "initial")
    # Uncommitted tracked change — the documented "check what you just
    # changed" workflow (issue #128).
    (project / "src" / "mod.py").write_text("x = 2\n", encoding="utf-8")

    monkeypatch.chdir(project)
    captured: dict[str, Any] = {}
    result = _invoke_and_capture(captured)

    assert result.exit_code == 0, result.output
    # Without --relative git reports "proj/src/mod.py" here; the old
    # CWD-based existence check dropped it and the run was a silent no-op.
    assert captured["paths"] == ["src/mod.py"]


def test_toplevel_project_run_selects_targets_with_real_git(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _make_project(repo)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "initial")
    (repo / "src" / "mod.py").write_text("x = 2\n", encoding="utf-8")

    monkeypatch.chdir(repo)
    captured: dict[str, Any] = {}
    result = _invoke_and_capture(captured)

    assert result.exit_code == 0, result.output
    assert captured["paths"] == ["src/mod.py"]


def test_diff_relative_config_composes_with_relative_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Historical escape hatch: with diff.relative=true git already reports
    # CWD-relative names.  The explicit --relative must stay a harmless
    # no-op on top of it.
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    project = repo / "proj"
    _make_project(project)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "initial")
    _git(repo, "config", "diff.relative", "true")
    (project / "src" / "mod.py").write_text("x = 2\n", encoding="utf-8")

    monkeypatch.chdir(project)
    captured: dict[str, Any] = {}
    result = _invoke_and_capture(captured)

    assert result.exit_code == 0, result.output
    assert captured["paths"] == ["src/mod.py"]


class TestRealGitRefResolution:
    """M-022 against the real git oracle: resolution and rejections.

    Every fixture is a fresh, isolated repository with a branch ``feature``,
    a tag ``v1``, two commits and an uncommitted working-tree edit, so the
    #128 "diff against the ref alone" semantics stay observable for every
    accepted ref form.
    """

    @staticmethod
    def _make_repo(tmp_path: Path) -> Path:
        repo = tmp_path / "repo"
        repo.mkdir()
        _git(repo, "init", "-q", "-b", "main")
        project = repo / "proj"
        _make_project(project)
        (project / "scripts").mkdir()
        (project / "scripts" / "tool.py").write_text("y = 2\n", encoding="utf-8")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-qm", "initial")
        _git(repo, "branch", "feature")
        _git(repo, "tag", "v1")
        (project / "src" / "mod.py").write_text("x = 2\n", encoding="utf-8")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-qm", "change mod")
        # Uncommitted working-tree change (issue #128 workflow).
        (project / "src" / "mod.py").write_text("x = 3\n", encoding="utf-8")
        return project

    def _head_oid(self, project: Path) -> str:
        return (
            subprocess.run(
                [  # noqa: S607 — git is a well-known executable
                    "git",
                    "rev-parse",
                    "HEAD",
                ],
                cwd=project,
                check=True,
                capture_output=True,
            )
            .stdout.decode("ascii")
            .strip()
        )

    @pytest.mark.parametrize("ref_kind", ["branch", "tag", "tilde", "full-oid"])
    def test_single_commit_refs_resolve_and_select_targets(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, ref_kind: str
    ) -> None:
        project = self._make_repo(tmp_path)
        monkeypatch.chdir(project)
        refs = {
            "branch": "feature",
            "tag": "v1",
            "tilde": "HEAD~1",
            "full-oid": self._head_oid(project),
        }

        captured: dict[str, Any] = {}
        result = _invoke_and_capture(captured, ref=refs[ref_kind])

        assert result.exit_code == 0, result.output
        assert captured["paths"] == ["src/mod.py"]

    def test_option_like_ref_is_rejected_and_writes_no_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pre-fix evidence (p08-022-repro.md case 1): git read the value as
        # its own --output option, wrote the diff into evil.txt and the run
        # ended as a FALSE exit-0 success.
        project = self._make_repo(tmp_path)
        monkeypatch.chdir(project)

        captured: dict[str, Any] = {}
        result = _invoke_and_capture(captured, ref="--output=evil.txt")

        assert result.exit_code == 2
        assert "--output=evil.txt" in result.output
        assert not (project / "evil.txt").exists()
        assert "paths" not in captured

    def test_empty_ref_is_rejected(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        project = self._make_repo(tmp_path)
        monkeypatch.chdir(project)

        captured: dict[str, Any] = {}
        result = _invoke_and_capture(captured, ref="")

        assert result.exit_code == 2
        assert "empty" in result.output
        assert "paths" not in captured

    def test_pathspec_like_directory_ref_is_rejected(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # 'src' exists as a directory but not as a revision: git diff used
        # to read it as a pathspec and exit 0 (false no-op success).  The
        # rev-parse oracle proves the value is not a commit.
        project = self._make_repo(tmp_path)
        monkeypatch.chdir(project)
        raw = subprocess.run(
            [  # noqa: S607 — git is a well-known executable
                "git",
                "rev-parse",
                "--verify",
                "--quiet",
                "--end-of-options",
                "src^{commit}",
            ],
            cwd=project,
            capture_output=True,
        )
        assert raw.returncode != 0, "oracle: an existing directory is not a revision"

        captured: dict[str, Any] = {}
        result = _invoke_and_capture(captured, ref="src")

        assert result.exit_code == 2
        assert "src" in result.output
        assert "is not a commit" in result.output
        assert "paths" not in captured

    @pytest.mark.parametrize("ref", ["HEAD~1..HEAD", "main...HEAD"])
    def test_range_refs_are_rejected_with_merge_base_hint(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, ref: str
    ) -> None:
        # Undocumented range syntax used to pass straight through to git
        # diff (p08-022-repro.md case 4).  Decision M-022 = A ends it and
        # names the documented merge-base migration.
        project = self._make_repo(tmp_path)
        monkeypatch.chdir(project)

        captured: dict[str, Any] = {}
        result = _invoke_and_capture(captured, ref=ref)

        assert result.exit_code == 2
        assert ref in result.output
        assert "merge-base" in result.output
        assert "paths" not in captured

    @pytest.mark.parametrize("object_kind", ["tree", "blob"])
    def test_tree_and_blob_refs_are_rejected(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, object_kind: str
    ) -> None:
        # A tree used to make git diff compare TREE vs WORKING TREE — a
        # silent success with different semantics than "since a commit".
        project = self._make_repo(tmp_path)
        monkeypatch.chdir(project)
        spec = "HEAD^{tree}" if object_kind == "tree" else "HEAD:proj/src/mod.py"
        oid = (
            subprocess.run(  # noqa: S603 — git CLI, argv fully controlled by the test
                [  # noqa: S607 — git is a well-known executable
                    "git",
                    "rev-parse",
                    spec,
                ],
                cwd=project,
                check=True,
                capture_output=True,
            )
            .stdout.decode("ascii")
            .strip()
        )

        captured: dict[str, Any] = {}
        result = _invoke_and_capture(captured, ref=oid)

        assert result.exit_code == 2
        assert "is not a commit" in result.output
        assert "paths" not in captured
