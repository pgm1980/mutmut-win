"""Target selection for ``--since-commit`` (AP-16 / M-021, M-022, M-024).

M-021 (BC-015 / CLI-02): ``git diff`` ran without ``--relative``, so git
emitted repo-root-relative names while the target filter checked
``Path(name).exists()`` against the process CWD.  A run started inside a
repository subproject (monorepo) therefore selected NOTHING and still
exited 0 — a silent no-op instead of the requested incremental run.

M-022 (CLI-01): the raw ``--since-commit`` value traveled into the
``git diff`` argv, where git interpreted option-like values
(``--output=…``) as diff options, existing directories as pathspecs, tree
objects as tree-vs-worktree diffs and range expressions as ranges — each
with exit 0, a false incremental success.  The value is now resolved to
ONE canonical commit oid via ``git rev-parse --verify --end-of-options
<ref>^{commit}`` and only that oid travels to ``git diff`` followed by a
terminating ``--``; everything unresolvable is a usage error (exit 2).

M-024 (CLI-03): the tests_dir exclusion compared raw ``Path.parts``, so
absolute entries and ``..``-aliases never matched and changed test files
became mutation targets.  Both sides now canonicalize through
``_project_relative_parts``.

The unit tests use a recording ``subprocess.run`` dispatcher that encodes
git's path semantics: with ``--relative`` in argv the diff reports
CWD-relative names, without it repo-root-relative names; a
``git rev-parse`` call answers with the configured oid.  Real-git
coverage lives in ``tests/integration/test_since_commit_git_subproject.py``.
"""

from __future__ import annotations

import contextlib
import io
import json
import subprocess
from typing import TYPE_CHECKING, Any, ClassVar
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner
from hypothesis import given, settings
from hypothesis import strategies as st

from mutmut_win.cli import cli
from mutmut_win.models import MutationRunResult

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


class GitRecorder:
    """``subprocess.run`` double encoding git's rev-parse/diff semantics.

    Git without ``--relative`` (and without ``diff.relative``) reports
    repo-root-relative paths; with ``--relative`` it reports paths relative
    to the process working directory and limits the diff to that subtree.
    The dispatcher returns different payloads for the two forms so a
    missing ``--relative`` cannot accidentally pass.

    A ``git rev-parse`` call (M-022) answers with the configured ``oid``
    (plus newline, like real rev-parse) unless ``rev_parse_stdout``
    overrides it; ``rev_parse_returncode`` drives the rejection path.
    ``text_stdout`` switches the double to the text-mode seam (third-party
    subprocess doubles may return ``str``); ``stderr`` can be ``bytes`` or
    ``str``.  Every call's argv AND kwargs are recorded so the exact
    ``subprocess.run`` contract stays assertable.
    """

    def __init__(self) -> None:
        self.calls: list[list[str]] = []
        self.kwargs: list[dict[str, Any]] = []
        self.oid = "5" * 40
        self.rev_parse_stdout: str | None = None
        self.rev_parse_returncode = 0
        self.rev_parse_stderr: bytes | str = b""
        self.relative_stdout = b""
        self.root_relative_stdout = b""
        self.text_stdout: str | None = None
        self.stderr: bytes | str = b""
        self.returncode = 0

    def __call__(
        self, argv: list[str], **kwargs: Any
    ) -> subprocess.CompletedProcess[bytes] | subprocess.CompletedProcess[str]:
        self.calls.append(list(argv))
        self.kwargs.append(dict(kwargs))
        if argv[:2] == ["git", "rev-parse"]:
            stdout: bytes | str
            stdout = self.rev_parse_stdout if self.rev_parse_stdout is not None else f"{self.oid}\n"
            return subprocess.CompletedProcess(
                args=argv,
                returncode=self.rev_parse_returncode,
                stdout=stdout,
                stderr=self.rev_parse_stderr,
            )
        if argv[:2] != ["git", "diff"]:
            raise AssertionError(f"unexpected subprocess argv while expecting a git call: {argv!r}")
        if self.text_stdout is not None:
            diff_stdout: bytes | str = self.text_stdout
        else:
            diff_stdout = (
                self.relative_stdout if "--relative" in argv else self.root_relative_stdout
            )
        return subprocess.CompletedProcess(
            args=argv, returncode=self.returncode, stdout=diff_stdout, stderr=self.stderr
        )

    @property
    def diff_calls(self) -> list[list[str]]:
        """The recorded argv lists of ``git diff`` invocations only."""
        return [argv for argv in self.calls if argv[:2] == ["git", "diff"]]


@pytest.fixture
def git_cmds(monkeypatch: pytest.MonkeyPatch) -> GitRecorder:
    """Replace ``subprocess.run`` with the recording git dispatcher."""
    recorder = GitRecorder()
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


def _invoke_since_commit_run(
    captured: dict[str, Any], *extra_args: str, ref: str = "HEAD~1"
) -> Any:
    """Invoke ``run --since-commit REF`` with the heavy collaborators mocked."""
    with (
        patch("mutmut_win.cli.MutationOrchestrator", side_effect=_capturing_orchestrator(captured)),
        patch("mutmut_win.cli.PytestRunner"),
        patch("mutmut_win.cli.SpawnPoolExecutor"),
    ):
        return CliRunner().invoke(cli, ["run", "--since-commit", ref, *extra_args])


class TestSubprojectRuns:
    def test_subproject_run_selects_project_relative_targets(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, git_cmds: GitRecorder
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
        git_cmds.relative_stdout = b"src/mod.py\0"
        git_cmds.root_relative_stdout = b"proj/src/mod.py\0"

        captured: dict[str, Any] = {}
        result = _invoke_since_commit_run(captured)

        assert result.exit_code == 0, result.output
        assert captured["paths"] == ["src/mod.py"]
        # M-022: exactly one revision element — the CANONICAL OID from
        # rev-parse, never the raw user value — and a terminating "--" so
        # nothing after it can be read as an option or pathspec.  #128
        # guard: no '..' range element anywhere.
        assert git_cmds.calls[0] == [
            "git",
            "rev-parse",
            "--verify",
            "--quiet",
            "--end-of-options",
            "HEAD~1^{commit}",
        ]
        assert git_cmds.calls[1] == [
            "git",
            "diff",
            "--name-only",
            "-z",
            "--relative",
            git_cmds.oid,
            "--",
        ]
        assert not any(".." in arg for arg in git_cmds.calls[1][1:])

    def test_toplevel_project_run_still_selects_targets(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, git_cmds: GitRecorder
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
        git_cmds.relative_stdout = b"src/mod.py\0"
        git_cmds.root_relative_stdout = b"src/mod.py\0"

        captured: dict[str, Any] = {}
        result = _invoke_since_commit_run(captured)

        assert result.exit_code == 0, result.output
        assert captured["paths"] == ["src/mod.py"]

    def test_invalid_ref_still_fails_with_exit_2(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, git_cmds: GitRecorder
    ) -> None:
        # The #102 returncode contract must survive the --relative rebuild.
        # M-022: an unresolvable ref fails at the rev-parse stage — the
        # message names the ref instead of git's (silenced) stderr.
        monkeypatch.chdir(tmp_path)
        git_cmds.rev_parse_returncode = 128
        git_cmds.rev_parse_stderr = b""
        git_cmds.relative_stdout = b""
        git_cmds.root_relative_stdout = b""

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
        assert "not-a-ref" in result.output
        assert "is not a commit" in result.output
        assert git_cmds.diff_calls == []
        assert "paths" not in captured


class TestGitInvocationContract:
    """The exact ``subprocess.run`` call is part of the #102/#128 contract."""

    def test_captures_output_and_pins_the_relative_base_to_the_cwd(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, git_cmds: GitRecorder
    ) -> None:
        project = tmp_path / "repo" / "proj"
        (project / "src").mkdir(parents=True)
        (project / "src" / "mod.py").write_text("x = 1\n", encoding="utf-8")
        (project / "pyproject.toml").write_text(
            '[tool.mutmut]\npaths_to_mutate = ["src/"]\ntests_dir = ["tests/"]\n',
            encoding="utf-8",
        )
        monkeypatch.chdir(project)
        git_cmds.relative_stdout = b"src/mod.py\0"
        git_cmds.root_relative_stdout = b"proj/src/mod.py\0"

        captured: dict[str, Any] = {}
        result = _invoke_since_commit_run(captured)

        assert result.exit_code == 0, result.output
        # capture_output feeds the #102 returncode check and the name
        # decoding; cwd is the base git resolves --relative against.  M-022:
        # BOTH git invocations (rev-parse and diff) share the contract.
        assert git_cmds.kwargs == [
            {"capture_output": True, "cwd": project},
            {"capture_output": True, "cwd": project},
        ]


class TestTargetFilterContract:
    """Only existing production ``.py`` files inside the project are targets."""

    @staticmethod
    def _make_project(tmp_path: Path) -> Path:
        project = tmp_path / "proj"
        (project / "src").mkdir(parents=True)
        (project / "src" / "mod.py").write_text("x = 1\n", encoding="utf-8")
        (project / "README.md").write_text("docs\n", encoding="utf-8")
        (project / "tests").mkdir()
        (project / "tests" / "test_mod.py").write_text("def test_x(): pass\n", encoding="utf-8")
        # src/deleted.py intentionally NOT created: a deleted file in the
        # diff must not become a mutation target.
        (project / "pyproject.toml").write_text(
            '[tool.mutmut]\npaths_to_mutate = ["src/"]\ntests_dir = ["tests/"]\n',
            encoding="utf-8",
        )
        return project

    def test_deleted_non_py_and_test_files_are_not_targets(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, git_cmds: GitRecorder
    ) -> None:
        project = self._make_project(tmp_path)
        monkeypatch.chdir(project)
        git_cmds.relative_stdout = b"src/mod.py\0src/deleted.py\0README.md\0tests/test_mod.py\0"
        git_cmds.root_relative_stdout = git_cmds.relative_stdout

        captured: dict[str, Any] = {}
        result = _invoke_since_commit_run(captured)

        assert result.exit_code == 0, result.output
        assert captured["paths"] == ["src/mod.py"]

    def test_existing_name_outside_the_project_is_never_a_target(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, git_cmds: GitRecorder
    ) -> None:
        # Fail-closed: a changed name that canonicalizes outside the
        # project root is excluded, never mutated.
        project = tmp_path / "repo" / "proj"
        (project / "src").mkdir(parents=True)
        (project / "src" / "mod.py").write_text("x = 1\n", encoding="utf-8")
        (project / "pyproject.toml").write_text(
            '[tool.mutmut]\npaths_to_mutate = ["src/"]\ntests_dir = ["tests/"]\n',
            encoding="utf-8",
        )
        outside = tmp_path / "repo" / "esc"
        outside.mkdir()
        (outside / "mod.py").write_text("x = 1\n", encoding="utf-8")
        monkeypatch.chdir(project)
        git_cmds.relative_stdout = b"../esc/mod.py\0"
        git_cmds.root_relative_stdout = git_cmds.relative_stdout

        captured: dict[str, Any] = {}
        result = _invoke_since_commit_run(captured)

        assert result.exit_code == 0, result.output
        assert "No mutation-target .py files changed" in result.output
        assert "paths" not in captured


class TestInvalidRefContract:
    """The #102 failure path at the diff stage: exit 2, decoded stderr, clean JSON channel.

    M-022 moved unresolvable refs to the rev-parse stage (see
    ``TestSubprojectRuns``); these pins keep the returncode contract for a
    ``git diff`` that itself fails after a successfully resolved oid.
    """

    @staticmethod
    def _make_project(tmp_path: Path) -> Path:
        project = tmp_path / "proj"
        (project / "src").mkdir(parents=True)
        (project / "src" / "mod.py").write_text("x = 1\n", encoding="utf-8")
        (project / "pyproject.toml").write_text(
            '[tool.mutmut]\npaths_to_mutate = ["src/"]\ntests_dir = ["tests/"]\n',
            encoding="utf-8",
        )
        return project

    def test_message_embeds_the_replacement_decoded_stderr(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, git_cmds: GitRecorder
    ) -> None:
        # Non-empty stderr with an invalid UTF-8 byte: the decode must use
        # errors="replace" (U+FFFD) and the exact message format is contract.
        project = self._make_project(tmp_path)
        monkeypatch.chdir(project)
        git_cmds.returncode = 128
        git_cmds.stderr = b"fatal: bad revision \xff\n"
        git_cmds.relative_stdout = b""
        git_cmds.root_relative_stdout = b""

        captured: dict[str, Any] = {}
        result = _invoke_since_commit_run(captured)

        assert result.exit_code == 2
        assert "git diff failed (exit 128): fatal: bad revision \ufffd" in result.output
        # Prose lives on stderr (the #127/A6 convention; in --output json
        # mode a redirect_stdout(sys.stderr) wrapper would mask a wrong
        # err flag, so pin the routing here in text mode).
        assert "git diff failed (exit 128): fatal: bad revision \ufffd" in result.stderr
        assert result.stdout == ""
        assert "paths" not in captured

    def test_text_stderr_seam_is_passed_through_undecoded(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, git_cmds: GitRecorder
    ) -> None:
        project = self._make_project(tmp_path)
        monkeypatch.chdir(project)
        git_cmds.returncode = 128
        git_cmds.stderr = "fatal: bad revision\n"
        git_cmds.relative_stdout = b""
        git_cmds.root_relative_stdout = b""

        captured: dict[str, Any] = {}
        result = _invoke_since_commit_run(captured)

        assert result.exit_code == 2
        assert "git diff failed (exit 128): fatal: bad revision" in result.output

    def test_json_channel_stays_pure_and_reports_exit_code_2(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, git_cmds: GitRecorder
    ) -> None:
        project = self._make_project(tmp_path)
        monkeypatch.chdir(project)
        git_cmds.returncode = 128
        git_cmds.stderr = b"fatal: bad revision\n"
        git_cmds.relative_stdout = b""
        git_cmds.root_relative_stdout = b""

        captured: dict[str, Any] = {}
        result = _invoke_since_commit_run(captured, "--output", "json")

        assert result.exit_code == 2
        # stdout carries ONLY the machine-readable error object; the prose
        # goes to stderr even in JSON mode.
        payload = json.loads(result.stdout)
        assert payload["exit_code"] == 2
        assert "git diff failed (exit 128)" in payload["error"]
        assert "git diff failed" in result.stderr


class TestResolveSinceCommitRejections:
    """M-022 (CLI-01): option-like, empty and range values never reach git diff.

    The raw value used to travel into the ``git diff`` argv where git
    interpreted it as an option (``--output=…``), a pathspec (existing
    directory) or a range — each with exit 0, a false success.  Rejections
    are usage errors: exit 2 with a clear diagnosis, no diff invocation.
    """

    @staticmethod
    def _make_project(tmp_path: Path) -> Path:
        project = tmp_path / "proj"
        (project / "src").mkdir(parents=True)
        (project / "src" / "mod.py").write_text("x = 1\n", encoding="utf-8")
        (project / "pyproject.toml").write_text(
            '[tool.mutmut]\npaths_to_mutate = ["src/"]\ntests_dir = ["tests/"]\n',
            encoding="utf-8",
        )
        return project

    def test_option_like_ref_is_rejected_before_any_git_call(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, git_cmds: GitRecorder
    ) -> None:
        # '--output=evil.txt' as the option VALUE: click hands it to the
        # callback, and git used to read it as its own --output option.
        project = self._make_project(tmp_path)
        monkeypatch.chdir(project)

        captured: dict[str, Any] = {}
        result = _invoke_since_commit_run(captured, ref="--output=evil.txt")

        assert result.exit_code == 2
        assert "--output=evil.txt" in result.output
        assert "option-like" in result.output
        # Fail fast: not even rev-parse runs, no file can be written.
        assert git_cmds.calls == []
        assert not (project / "evil.txt").exists()
        assert "paths" not in captured

    def test_empty_ref_is_rejected_before_any_git_call(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, git_cmds: GitRecorder
    ) -> None:
        project = self._make_project(tmp_path)
        monkeypatch.chdir(project)

        captured: dict[str, Any] = {}
        result = _invoke_since_commit_run(captured, ref="")

        assert result.exit_code == 2
        assert "empty" in result.output
        assert git_cmds.calls == []
        assert "paths" not in captured

    @pytest.mark.parametrize("ref", ["HEAD~1..HEAD", "main...feature", "v1..v2", "A...B"])
    def test_range_refs_are_rejected_with_merge_base_hint(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        git_cmds: GitRecorder,
        ref: str,
    ) -> None:
        # Undocumented range syntax used to work because the raw value
        # reached git diff.  M-022 = A ends that explicitly and points
        # former range users at the documented merge-base workflow.
        project = self._make_project(tmp_path)
        monkeypatch.chdir(project)

        captured: dict[str, Any] = {}
        result = _invoke_since_commit_run(captured, ref=ref)

        assert result.exit_code == 2
        assert ref in result.output
        assert "merge-base" in result.output
        assert git_cmds.calls == []
        assert "paths" not in captured

    def test_unresolvable_ref_exits_2_with_the_ref_in_the_message(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, git_cmds: GitRecorder
    ) -> None:
        # rev-parse runs with --quiet: stderr is EMPTY on failure, so the
        # diagnosis must name the ref and the exit code itself (no git
        # stderr passthrough available on this path).
        project = self._make_project(tmp_path)
        monkeypatch.chdir(project)
        git_cmds.rev_parse_returncode = 128
        git_cmds.rev_parse_stderr = b""

        captured: dict[str, Any] = {}
        result = _invoke_since_commit_run(captured, ref="no-such-branch")

        assert result.exit_code == 2
        assert "no-such-branch" in result.output
        assert "is not a commit" in result.output
        assert "128" in result.output
        # rev-parse ran (one call), the diff never did.
        assert len(git_cmds.calls) == 1
        assert git_cmds.diff_calls == []
        assert "paths" not in captured

    @pytest.mark.parametrize("stdout", ["main", "abc123", "", "HEAD~1"])
    def test_non_canonical_rev_parse_stdout_is_rejected(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        git_cmds: GitRecorder,
        stdout: str,
    ) -> None:
        # Defensive: rev-parse answered rc 0 but NOT with a canonical oid
        # (40/64 hex).  Anything else would re-open the injection surface
        # in the diff argv — reject instead of forwarding.
        project = self._make_project(tmp_path)
        monkeypatch.chdir(project)
        git_cmds.rev_parse_stdout = stdout

        captured: dict[str, Any] = {}
        result = _invoke_since_commit_run(captured)

        assert result.exit_code == 2
        assert "did not resolve to a canonical" in result.output
        assert git_cmds.diff_calls == []
        assert "paths" not in captured


class TestResolveSinceCommitAcceptance:
    """M-022: branch/tag/commit values resolve to one canonical oid."""

    @staticmethod
    def _make_project(tmp_path: Path) -> Path:
        project = tmp_path / "proj"
        (project / "src").mkdir(parents=True)
        (project / "src" / "mod.py").write_text("x = 1\n", encoding="utf-8")
        (project / "pyproject.toml").write_text(
            '[tool.mutmut]\npaths_to_mutate = ["src/"]\ntests_dir = ["tests/"]\n',
            encoding="utf-8",
        )
        return project

    @pytest.mark.parametrize("ref", ["feature", "v1.2.3", "HEAD~1", "1234567890"])
    def test_valid_refs_resolve_and_diff_against_the_canonical_oid_only(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        git_cmds: GitRecorder,
        ref: str,
    ) -> None:
        project = self._make_project(tmp_path)
        monkeypatch.chdir(project)
        git_cmds.relative_stdout = b"src/mod.py\0"
        git_cmds.root_relative_stdout = b"proj/src/mod.py\0"

        captured: dict[str, Any] = {}
        result = _invoke_since_commit_run(captured, ref=ref)

        assert result.exit_code == 0, result.output
        assert captured["paths"] == ["src/mod.py"]
        assert git_cmds.calls[0] == [
            "git",
            "rev-parse",
            "--verify",
            "--quiet",
            "--end-of-options",
            f"{ref}^{{commit}}",
        ]
        # The raw ref NEVER reaches git diff — only the canonical oid,
        # terminated by "--" (option and pathspec interpretation closed).
        assert git_cmds.diff_calls == [
            ["git", "diff", "--name-only", "-z", "--relative", git_cmds.oid, "--"]
        ]

    def test_sha256_length_object_id_is_accepted(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, git_cmds: GitRecorder
    ) -> None:
        # SHA-256 repositories report 64 hex digits — still a canonical oid.
        project = self._make_project(tmp_path)
        monkeypatch.chdir(project)
        git_cmds.oid = "f" * 64
        git_cmds.relative_stdout = b"src/mod.py\0"
        git_cmds.root_relative_stdout = git_cmds.relative_stdout

        captured: dict[str, Any] = {}
        result = _invoke_since_commit_run(captured)

        assert result.exit_code == 0, result.output
        assert captured["paths"] == ["src/mod.py"]
        assert git_cmds.diff_calls[0][5] == "f" * 64


class TestStdoutSeams:
    """Bytes and text ``stdout`` doubles both parse to the same names."""

    @staticmethod
    def _make_project(tmp_path: Path) -> Path:
        project = tmp_path / "proj"
        (project / "src").mkdir(parents=True)
        (project / "src" / "mod.py").write_text("x = 1\n", encoding="utf-8")
        # A space in the name is why git uses -z: text seams must not
        # collapse it (whitespace-splitting loses the name).
        (project / "src" / "my mod.py").write_text("x = 2\n", encoding="utf-8")
        (project / "pyproject.toml").write_text(
            '[tool.mutmut]\npaths_to_mutate = ["src/"]\ntests_dir = ["tests/"]\n',
            encoding="utf-8",
        )
        return project

    def test_text_stdout_with_nul_separator_keeps_spaced_names(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, git_cmds: GitRecorder
    ) -> None:
        project = self._make_project(tmp_path)
        monkeypatch.chdir(project)
        git_cmds.text_stdout = "src/mod.py\0src/my mod.py\0"

        captured: dict[str, Any] = {}
        result = _invoke_since_commit_run(captured)

        assert result.exit_code == 0, result.output
        assert captured["paths"] == ["src/mod.py", "src/my mod.py"]

    def test_text_stdout_with_newline_separator_splits_and_filters(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, git_cmds: GitRecorder
    ) -> None:
        project = tmp_path / "proj"
        (project / "src").mkdir(parents=True)
        (project / "src" / "mod.py").write_text("x = 1\n", encoding="utf-8")
        (project / "pyproject.toml").write_text(
            '[tool.mutmut]\npaths_to_mutate = ["src/"]\ntests_dir = ["tests/"]\n',
            encoding="utf-8",
        )
        monkeypatch.chdir(project)
        git_cmds.text_stdout = "src/mod.py\nsrc/deleted.py\n"

        captured: dict[str, Any] = {}
        result = _invoke_since_commit_run(captured)

        assert result.exit_code == 0, result.output
        assert captured["paths"] == ["src/mod.py"]

    def test_undecodable_name_is_surrogate_escaped_not_fatal(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, git_cmds: GitRecorder
    ) -> None:
        # git -z preserves arbitrary path bytes; an invalid UTF-8 name must
        # decode via surrogateescape and then simply fail the existence
        # check instead of aborting the run.
        project = tmp_path / "proj"
        (project / "src").mkdir(parents=True)
        (project / "src" / "mod.py").write_text("x = 1\n", encoding="utf-8")
        (project / "pyproject.toml").write_text(
            '[tool.mutmut]\npaths_to_mutate = ["src/"]\ntests_dir = ["tests/"]\n',
            encoding="utf-8",
        )
        monkeypatch.chdir(project)
        git_cmds.relative_stdout = b"src/mod.py\0src/bad\xff.py\0"
        git_cmds.root_relative_stdout = git_cmds.relative_stdout

        captured: dict[str, Any] = {}
        result = _invoke_since_commit_run(captured)

        assert result.exit_code == 0, result.output
        assert captured["paths"] == ["src/mod.py"]


class TestGitChangedNamesUnit:
    """Direct unit pins for the NUL/newline name decoding (M-021 helper)."""

    def test_nul_terminated_bytes_decode_without_empty_tail(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from mutmut_win.cli import _git_changed_names

        monkeypatch.chdir(tmp_path)
        completed = subprocess.CompletedProcess(
            args=["git", "diff"], returncode=0, stdout=b"src/mod.py\0", stderr=b""
        )
        with patch("subprocess.run", return_value=completed):
            assert _git_changed_names("HEAD~1", json_stdout=None) == ["src/mod.py"]

    def test_text_newline_output_splits_without_empty_tail(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from mutmut_win.cli import _git_changed_names

        monkeypatch.chdir(tmp_path)
        completed = subprocess.CompletedProcess(
            args=["git", "diff"], returncode=0, stdout="src/mod.py\n", stderr=b""
        )
        with patch("subprocess.run", return_value=completed):
            assert _git_changed_names("HEAD~1", json_stdout=None) == ["src/mod.py"]


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
        git_cmds: GitRecorder,
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
        git_cmds.relative_stdout = b"src/mod.py\0src/tests/test_mod.py\0"
        git_cmds.root_relative_stdout = git_cmds.relative_stdout

        captured: dict[str, Any] = {}
        result = _invoke_since_commit_run(captured, "--tests-dir", entries[entry_kind])

        assert result.exit_code == 0, result.output
        assert captured["paths"] == ["src/mod.py"]

    def test_leading_separator_entry_still_excludes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, git_cmds: GitRecorder
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
        git_cmds.relative_stdout = b"src/mod.py\0tests/test_mod.py\0"
        git_cmds.root_relative_stdout = git_cmds.relative_stdout

        captured: dict[str, Any] = {}
        result = _invoke_since_commit_run(captured, "--tests-dir", "\\tests\\")

        assert result.exit_code == 0, result.output
        assert captured["paths"] == ["src/mod.py"]

    def test_drive_anchored_entry_stays_ineffective(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, git_cmds: GitRecorder
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
        git_cmds.relative_stdout = b"src/mod.py\0tests/test_mod.py\0"
        git_cmds.root_relative_stdout = git_cmds.relative_stdout
        drive = project.drive
        assert drive, "tmp_path lives on a Windows drive"

        captured: dict[str, Any] = {}
        result = _invoke_since_commit_run(captured, "--tests-dir", f"{drive}tests")

        assert result.exit_code == 0, result.output
        # M-023: tests/test_mod.py is no longer an incremental target —
        # the positive filter intersects with paths_to_mutate=["src/"].
        assert captured["paths"] == ["src/mod.py"]

    def test_project_root_entry_excludes_everything(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, git_cmds: GitRecorder
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
        git_cmds.relative_stdout = b"src/mod.py\0"
        git_cmds.root_relative_stdout = git_cmds.relative_stdout

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

    def test_leading_separator_strip_removes_only_separators(self, tmp_path: Path) -> None:
        from mutmut_win.cli import _project_relative_parts

        # '/Xsrc' is the directory 'Xsrc' at the project root — the legacy
        # leading-separator strip must not eat the 'X'.
        assert _project_relative_parts("/Xsrc", tmp_path) == ("xsrc",)

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


@given(
    value=st.text(
        alphabet=st.characters(exclude_categories=("Cs",), exclude_characters="\x00"),
        max_size=16,
    ).map(lambda s: "-" + s)
)
@settings(max_examples=50)
def test_every_dash_prefixed_value_is_a_usage_error_without_a_git_call(value: str) -> None:
    """M-022 property: no option-like --since-commit value reaches git.

    Whatever follows the leading dash (including digits, spaces, unicode,
    or more dashes), the value is rejected as a usage error BEFORE any
    subprocess runs — git never gets to interpret it as an option.
    """
    from mutmut_win.cli import _resolve_since_commit

    recorder = GitRecorder()
    with (
        patch("subprocess.run", recorder),
        contextlib.redirect_stderr(io.StringIO()),
        pytest.raises(SystemExit) as excinfo,
    ):
        _resolve_since_commit(value, json_stdout=None)

    assert excinfo.value.code == 2
    assert recorder.calls == []


class TestIncrementalTargetIntersection:
    """M-023: incremental targets are the intersection with paths_to_mutate."""

    def _make_intersection_project(self, tmp_path: Path) -> Path:
        project = tmp_path / "proj"
        (project / "src").mkdir(parents=True)
        (project / "src" / "mod.py").write_text("x = 1\n", encoding="utf-8")
        (project / "scripts").mkdir(parents=True)
        (project / "scripts" / "tool.py").write_text("x = 1\n", encoding="utf-8")
        (project / "setup.py").write_text("x = 1\n", encoding="utf-8")
        (project / "tests").mkdir(parents=True)
        (project / "tests" / "test_mod.py").write_text("def test_x(): pass\n", encoding="utf-8")
        (project / "pyproject.toml").write_text(
            '[tool.mutmut]\npaths_to_mutate = ["src/"]\ntests_dir = ["tests/"]\n',
            encoding="utf-8",
        )
        return project

    def test_files_outside_paths_to_mutate_are_not_targets(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        git_cmds: GitRecorder,
    ) -> None:
        """scripts/ and setup.py are never incremental targets (M-023)."""
        project = self._make_intersection_project(tmp_path)
        monkeypatch.chdir(project)
        git_cmds.relative_stdout = b"src/mod.py\0scripts/tool.py\0setup.py\0"
        git_cmds.root_relative_stdout = git_cmds.relative_stdout

        captured: dict[str, Any] = {}
        result = _invoke_since_commit_run(captured)

        assert result.exit_code == 0, result.output
        assert captured["paths"] == ["src/mod.py"]

    def test_paths_to_mutate_cli_intersects_instead_of_replacing(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        git_cmds: GitRecorder,
    ) -> None:
        """--paths-to-mutate + --since-commit is an intersection, not a replacement."""
        from unittest.mock import patch

        project = self._make_intersection_project(tmp_path)
        (project / "src" / "other.py").write_text("y = 2\n", encoding="utf-8")
        monkeypatch.chdir(project)
        git_cmds.relative_stdout = b"src/mod.py\0src/other.py\0scripts/tool.py\0"
        git_cmds.root_relative_stdout = git_cmds.relative_stdout

        captured: dict[str, Any] = {}

        def _capture_orchestrator(config: Any, *_a: object, **_k: object) -> Any:
            captured["paths"] = list(config.paths_to_mutate)

            class _R:
                total_mutants = 0
                killed = 0
                survived = 0
                timeout = 0
                suspicious = 0
                skipped = 0
                no_tests = 0
                caught_by_type_check = 0
                unchecked = 0
                killed_by_infinite_loop = 0
                duration_seconds = 0.0
                was_interrupted = False
                run_aborted = False
                degraded_files: ClassVar[list[str]] = []

                def compute_score(self, *_args: object, **_kwargs: object) -> float:
                    return 0.0

            class _Orch:
                def __init__(self) -> None:
                    pass

                def run(self) -> _R:
                    return _R()

                def dry_run(self) -> _R:
                    return _R()

            return _Orch()

        with (
            patch("mutmut_win.cli.MutationOrchestrator", side_effect=_capture_orchestrator),
            patch("mutmut_win.cli.PytestRunner"),
            patch("mutmut_win.cli.SpawnPoolExecutor"),
        ):
            from mutmut_win.cli import cli as cli_entry

            result = CliRunner().invoke(
                cli_entry,
                [
                    "run",
                    "--since-commit",
                    "HEAD~1",
                    "--paths-to-mutate",
                    "src/mod.py",
                    "--dry-run",
                ],
            )
        # --dry-run avoids the explicit-selection exit-2 guard; the
        # captured config proves that the override narrowed to the
        # intersection rather than replacing it.
        assert result.exit_code == 0, result.output
        # Only src/mod.py is both changed AND under the --paths-to-mutate
        # intersection; src/other.py is changed but outside the CLI root,
        # scripts/tool.py is outside both.
        assert captured.get("paths") == ["src/mod.py"]

    def test_multiple_source_roots_all_intersect(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        git_cmds: GitRecorder,
    ) -> None:
        """Multiple configured source roots each contribute their changed files."""
        project = self._make_intersection_project(tmp_path)
        (project / "lib").mkdir(parents=True)
        (project / "lib" / "helper.py").write_text("z = 3\n", encoding="utf-8")
        # Reconfigure with two roots
        (project / "pyproject.toml").write_text(
            '[tool.mutmut]\npaths_to_mutate = ["src/", "lib/"]\ntests_dir = ["tests/"]\n',
            encoding="utf-8",
        )
        monkeypatch.chdir(project)
        git_cmds.relative_stdout = b"src/mod.py\0lib/helper.py\0scripts/tool.py\0"
        git_cmds.root_relative_stdout = git_cmds.relative_stdout

        captured: dict[str, Any] = {}
        result = _invoke_since_commit_run(captured)

        assert result.exit_code == 0, result.output
        assert sorted(captured["paths"]) == ["lib/helper.py", "src/mod.py"]

    def test_dot_root_entry_permits_everything(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        git_cmds: GitRecorder,
    ) -> None:
        """paths_to_mutate = ['.'] makes the positive filter a no-op (the
        empty tuple from _project_relative_parts matches every prefix)."""
        project = self._make_intersection_project(tmp_path)
        (project / "pyproject.toml").write_text(
            '[tool.mutmut]\npaths_to_mutate = ["."]\ntests_dir = ["tests/"]\n',
            encoding="utf-8",
        )
        monkeypatch.chdir(project)
        git_cmds.relative_stdout = b"src/mod.py\0scripts/tool.py\0"
        git_cmds.root_relative_stdout = git_cmds.relative_stdout

        captured: dict[str, Any] = {}
        result = _invoke_since_commit_run(captured)

        assert result.exit_code == 0, result.output
        assert sorted(captured["paths"]) == ["scripts/tool.py", "src/mod.py"]

    def test_incremental_set_is_subset_of_full_run_walk(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        git_cmds: GitRecorder,
    ) -> None:
        """Abnahme: the incremental target set is a subset of the actual
        full-run walk selection (not just manual path expectations)."""
        from mutmut_win.config import MutmutConfig
        from mutmut_win.file_setup import walk_source_files

        project = self._make_intersection_project(tmp_path)
        monkeypatch.chdir(project)
        git_cmds.relative_stdout = b"src/mod.py\0scripts/tool.py\0"
        git_cmds.root_relative_stdout = git_cmds.relative_stdout

        captured: dict[str, Any] = {}
        result = _invoke_since_commit_run(captured)

        assert result.exit_code == 0, result.output
        config = MutmutConfig(paths_to_mutate=["src/"])
        full_run_files = {str(p).replace("\\", "/") for p in walk_source_files(config)}
        for target in captured["paths"]:
            assert target in full_run_files, (
                f"incremental target {target} is not in the full-run walk set"
            )
