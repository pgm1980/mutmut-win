"""Real-git ``--since-commit`` coverage (AP-16 / M-021).

The unit tests in ``tests/unit/test_since_commit_targets.py`` emulate git's
``--relative`` semantics with a dispatcher.  These tests prove the
behaviour against a real repository: a project inside a git subfolder
(monorepo layout), a project at the git top level, and the historical
``diff.relative=true`` escape hatch.  Git for Windows is part of the
environment contract (same rationale as ``test_mutant_diff.py``); the
skipif only guards exotic CI images.
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


def _invoke_and_capture(captured: dict[str, Any]) -> Any:
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
        # Diff against HEAD alone (no ..HEAD): the uncommitted working-tree
        # edit below is what the #128 contract must keep visible.
        return CliRunner().invoke(cli, ["run", "--since-commit", "HEAD"])


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
