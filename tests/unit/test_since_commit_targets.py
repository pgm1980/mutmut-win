"""Target selection for ``--since-commit`` (AP-16 / M-021, M-024).

M-021 (BC-015 / CLI-02): ``git diff`` ran without ``--relative``, so git
emitted repo-root-relative names while the target filter checked
``Path(name).exists()`` against the process CWD.  A run started inside a
repository subproject (monorepo) therefore selected NOTHING and still
exited 0 — a silent no-op instead of the requested incremental run.

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
