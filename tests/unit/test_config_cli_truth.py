"""Tests for config/CLI truth (Issue #102, audit A3-CM-004/005/006, A4-UI-005).

CLI overrides bypassed every pydantic constraint (``--max-children 0`` was
an accepted hang), config typos were silently swallowed (``paths_to_mutat``
mutated the wrong tree), an invalid ``--since-commit`` ref produced a FALSE
CI success (exit 0), and ``--debug`` was a dead flag while the run-level
``except Exception`` swallowed exactly the tracebacks it should reveal.
"""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from mutmut_win.cli import cli
from mutmut_win.config import load_config
from mutmut_win.models import MutationRunResult

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def _invoke_run(*args: str, orchestrator_error: Exception | None = None) -> tuple[int, str]:
    orchestrator = MagicMock()
    if orchestrator_error is not None:
        orchestrator.run.side_effect = orchestrator_error
    else:
        from mutmut_win.models import MutationRunResult

        orchestrator.run.return_value = MutationRunResult(total_mutants=1, killed=1)
    with (
        patch("mutmut_win.cli.MutationOrchestrator", return_value=orchestrator),
        patch("mutmut_win.cli.PytestRunner"),
        patch("mutmut_win.cli.SpawnPoolExecutor"),
    ):
        result = CliRunner().invoke(cli, ["run", *args])
    return result.exit_code, result.output


class TestOverrideRevalidation:
    def test_max_children_zero_is_a_validation_error_not_a_hang(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # A3-CM-004: model_copy(update=...) bypassed the ge=1 constraint —
        # 0 workers consumed no tasks and the run hung forever.
        monkeypatch.chdir(tmp_path)
        exit_code, output = _invoke_run("--max-children", "0")
        assert exit_code != 0
        assert "max_children" in output

    def test_negative_timeout_multiplier_is_rejected(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        exit_code, output = _invoke_run("--timeout-multiplier", "-1")
        assert exit_code != 0
        assert "timeout_multiplier" in output

    def test_valid_overrides_still_pass(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / "src").mkdir()  # #120 / CLI-002 validates path existence
        exit_code, _ = _invoke_run("--max-children", "2")
        assert exit_code == 0


class TestConfigTypoWarning:
    def test_unknown_key_warns_with_a_suggestion(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # A3-CM-005: extra='ignore' swallowed typos — 'paths_to_mutat'
        # silently fell back to the default guess and mutated the wrong tree.
        (tmp_path / "pyproject.toml").write_text(
            '[tool.mutmut]\npaths_to_mutat = ["src"]\n', encoding="utf-8"
        )
        load_config(tmp_path)
        out = capsys.readouterr().err  # warnings live on stderr (#127/A6)
        assert "paths_to_mutat" in out
        assert "paths_to_mutate" in out  # difflib suggestion

    def test_known_keys_do_not_warn(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        (tmp_path / "pyproject.toml").write_text(
            '[tool.mutmut]\npaths_to_mutate = ["src"]\n', encoding="utf-8"
        )
        load_config(tmp_path)
        assert "unknown" not in capsys.readouterr().out.lower()


class TestSinceCommitTruth:
    def _git(self, stdout: str = "", returncode: int = 0) -> MagicMock:
        completed = MagicMock()
        completed.stdout = stdout
        completed.stderr = "fatal: bad revision" if returncode else ""
        completed.returncode = returncode
        return completed

    def test_invalid_ref_fails_instead_of_false_success(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # A3-CM-006: the git returncode was never checked — an invalid ref
        # meant 'nothing changed' + exit 0: a FALSE CI success.
        monkeypatch.chdir(tmp_path)
        with patch("subprocess.run", return_value=self._git(returncode=128)):
            result = CliRunner().invoke(cli, ["run", "--since-commit", "not-a-ref"])
        assert result.exit_code != 0
        assert "git" in result.output.lower()

    def test_deleted_and_test_files_are_not_mutation_targets(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        src = tmp_path / "src"
        src.mkdir()
        (src / "mod.py").write_text("x = 1\n", encoding="utf-8")
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_mod.py").write_text("def test_x(): pass\n", encoding="utf-8")

        captured: dict[str, Any] = {}

        def fake_orchestrator(config: Any, **_kwargs: Any) -> MagicMock:
            captured["paths"] = list(config.paths_to_mutate)
            instance = MagicMock()
            from mutmut_win.models import MutationRunResult

            instance.run.return_value = MutationRunResult(total_mutants=1, killed=1)
            return instance

        git_output = "src/mod.py\nsrc/deleted.py\ntests/test_mod.py\n"
        with (
            patch("subprocess.run", return_value=self._git(stdout=git_output)),
            patch("mutmut_win.cli.MutationOrchestrator", side_effect=fake_orchestrator),
            patch("mutmut_win.cli.PytestRunner"),
            patch("mutmut_win.cli.SpawnPoolExecutor"),
        ):
            result = CliRunner().invoke(cli, ["run", "--since-commit", "HEAD~1"])

        assert result.exit_code == 0, result.output
        assert captured["paths"] == ["src/mod.py"]  # deleted + test files filtered

    def test_nested_tests_dir_excludes_changed_test_files(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # 360°-A4 (#128): parts[0] was compared against the FULL tests_dir
        # string — with tests_dir='tests/unit/' (this project's own
        # config!) changed TEST files became mutation targets.
        monkeypatch.chdir(tmp_path)
        src = tmp_path / "src"
        src.mkdir()
        (src / "mod.py").write_text("x = 1\n", encoding="utf-8")
        nested = tmp_path / "tests" / "unit"
        nested.mkdir(parents=True)
        (nested / "test_mod.py").write_text("def test_x(): pass\n", encoding="utf-8")
        (tmp_path / "pyproject.toml").write_text(
            '[tool.mutmut]\npaths_to_mutate = ["src/"]\ntests_dir = ["tests/unit/"]\n',
            encoding="utf-8",
        )

        captured: dict[str, Any] = {}

        def fake_orchestrator(config: Any, **_kwargs: Any) -> MagicMock:
            captured["paths"] = list(config.paths_to_mutate)
            instance = MagicMock()
            from mutmut_win.models import MutationRunResult

            instance.run.return_value = MutationRunResult(total_mutants=1, killed=1)
            return instance

        git_output = "src/mod.py\ntests/unit/test_mod.py\n"
        with (
            patch("subprocess.run", return_value=self._git(stdout=git_output)),
            patch("mutmut_win.cli.MutationOrchestrator", side_effect=fake_orchestrator),
            patch("mutmut_win.cli.PytestRunner"),
            patch("mutmut_win.cli.SpawnPoolExecutor"),
        ):
            result = CliRunner().invoke(cli, ["run", "--since-commit", "HEAD~1"])

        assert result.exit_code == 0, result.output
        assert captured["paths"] == ["src/mod.py"]  # nested test dir excluded

    def test_non_ascii_changed_path_is_read_from_nul_terminated_git_output(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        source = tmp_path / "src" / "grüße.py"
        source.parent.mkdir()
        source.write_text("x = 1\n", encoding="utf-8")
        captured: dict[str, Any] = {}

        def fake_orchestrator(config: Any, **_kwargs: Any) -> MagicMock:
            captured["paths"] = list(config.paths_to_mutate)
            instance = MagicMock()
            instance.run.return_value = MutationRunResult(total_mutants=1, killed=1)
            return instance

        completed = subprocess.CompletedProcess(
            args=["git", "diff"],
            returncode=0,
            stdout="src/grüße.py\0".encode(),
            stderr=b"",
        )
        with (
            patch("subprocess.run", return_value=completed) as git_diff,
            patch("mutmut_win.cli.MutationOrchestrator", side_effect=fake_orchestrator),
            patch("mutmut_win.cli.PytestRunner"),
            patch("mutmut_win.cli.SpawnPoolExecutor"),
        ):
            result = CliRunner().invoke(cli, ["run", "--since-commit", "HEAD~1"])

        assert result.exit_code == 0, result.output
        assert captured["paths"] == ["src/grüße.py"]
        assert git_diff.call_args.args[0] == ["git", "diff", "--name-only", "-z", "HEAD~1"]

    def test_uppercase_python_suffix_is_a_windows_mutation_target(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        source = tmp_path / "src" / "MODULE.PY"
        source.parent.mkdir()
        source.write_text("x = 1\n", encoding="utf-8")
        captured: dict[str, Any] = {}

        def fake_orchestrator(config: Any, **_kwargs: Any) -> MagicMock:
            captured["paths"] = list(config.paths_to_mutate)
            instance = MagicMock()
            instance.run.return_value = MutationRunResult(total_mutants=1, killed=1)
            return instance

        completed = subprocess.CompletedProcess(
            args=["git", "diff"],
            returncode=0,
            stdout=b"src/MODULE.PY\0",
            stderr=b"",
        )
        with (
            patch("subprocess.run", return_value=completed),
            patch("mutmut_win.cli.MutationOrchestrator", side_effect=fake_orchestrator),
            patch("mutmut_win.cli.PytestRunner"),
            patch("mutmut_win.cli.SpawnPoolExecutor"),
        ):
            result = CliRunner().invoke(cli, ["run", "--since-commit", "HEAD~1"])

        assert result.exit_code == 0, result.output
        assert captured["paths"] == ["src/MODULE.PY"]

    def test_tests_dir_node_id_excludes_its_file_from_since_commit_targets(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        source = tmp_path / "src" / "mod.py"
        source.parent.mkdir()
        source.write_text("x = 1\n", encoding="utf-8")
        test_file = tmp_path / "tests" / "test_mod.py"
        test_file.parent.mkdir()
        test_file.write_text("def test_x(): pass\n", encoding="utf-8")
        (tmp_path / "pyproject.toml").write_text(
            '[tool.mutmut]\npaths_to_mutate = ["src/"]\n'
            'tests_dir = ["tests/test_mod.py::test_x"]\n',
            encoding="utf-8",
        )
        captured: dict[str, Any] = {}

        def fake_orchestrator(config: Any, **_kwargs: Any) -> MagicMock:
            captured["paths"] = list(config.paths_to_mutate)
            instance = MagicMock()
            instance.run.return_value = MutationRunResult(total_mutants=1, killed=1)
            return instance

        completed = subprocess.CompletedProcess(
            args=["git", "diff"],
            returncode=0,
            stdout=b"src/mod.py\0tests/test_mod.py\0",
            stderr=b"",
        )
        with (
            patch("subprocess.run", return_value=completed),
            patch("mutmut_win.cli.MutationOrchestrator", side_effect=fake_orchestrator),
            patch("mutmut_win.cli.PytestRunner"),
            patch("mutmut_win.cli.SpawnPoolExecutor"),
        ):
            result = CliRunner().invoke(cli, ["run", "--since-commit", "HEAD~1"])

        assert result.exit_code == 0, result.output
        assert captured["paths"] == ["src/mod.py"]

    def test_tests_dir_comparison_uses_windows_case_insensitive_semantics(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        source = tmp_path / "src" / "mod.py"
        source.parent.mkdir()
        source.write_text("x = 1\n", encoding="utf-8")
        test_file = tmp_path / "Tests" / "test_mod.py"
        test_file.parent.mkdir()
        test_file.write_text("def test_x(): pass\n", encoding="utf-8")
        (tmp_path / "pyproject.toml").write_text(
            '[tool.mutmut]\npaths_to_mutate = ["src/"]\ntests_dir = ["tests/"]\n',
            encoding="utf-8",
        )
        captured: dict[str, Any] = {}

        def fake_orchestrator(config: Any, **_kwargs: Any) -> MagicMock:
            captured["paths"] = list(config.paths_to_mutate)
            instance = MagicMock()
            instance.run.return_value = MutationRunResult(total_mutants=1, killed=1)
            return instance

        completed = subprocess.CompletedProcess(
            args=["git", "diff"],
            returncode=0,
            stdout=b"src/mod.py\0Tests/test_mod.py\0",
            stderr=b"",
        )
        with (
            patch("subprocess.run", return_value=completed),
            patch("mutmut_win.cli.MutationOrchestrator", side_effect=fake_orchestrator),
            patch("mutmut_win.cli.PytestRunner"),
            patch("mutmut_win.cli.SpawnPoolExecutor"),
        ):
            result = CliRunner().invoke(cli, ["run", "--since-commit", "HEAD~1"])

        assert result.exit_code == 0, result.output
        assert captured["paths"] == ["src/mod.py"]

    def test_diff_includes_the_working_tree(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # 360°-A4 (#128): 'ref..HEAD' compared two COMMITS — uncommitted
        # edits were invisible and the documented 'check what you just
        # changed' workflow reported 'No .py files changed'. Diffing
        # against the ref alone includes the working tree.
        monkeypatch.chdir(tmp_path)
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "mod.py").write_text("x = 1\n", encoding="utf-8")

        seen: dict[str, Any] = {}

        def spy_run(cmd: Any, **_kwargs: Any) -> MagicMock:
            seen["cmd"] = list(cmd)
            return self._git(stdout="src/mod.py\n")

        with (
            patch("subprocess.run", side_effect=spy_run),
            patch("mutmut_win.cli.MutationOrchestrator") as orch,
            patch("mutmut_win.cli.PytestRunner"),
            patch("mutmut_win.cli.SpawnPoolExecutor"),
        ):
            from mutmut_win.models import MutationRunResult

            orch.return_value.run.return_value = MutationRunResult(total_mutants=1, killed=1)
            result = CliRunner().invoke(cli, ["run", "--since-commit", "HEAD~1"])

        assert result.exit_code == 0, result.output
        assert seen["cmd"][:5] == ["git", "diff", "--name-only", "-z", "HEAD~1"]
        assert "HEAD~1..HEAD" not in seen["cmd"]


class TestDebugIsReal:
    # Since issue #114 / A4-QX-006 the run-level except only handles DOMAIN
    # errors (MutmutWinError) — a foreign RuntimeError propagates with its
    # full traceback regardless of --debug (covered in
    # test_exception_hygiene_114.py). The --debug contract from A4-UI-005
    # therefore pins a domain error here.
    def test_debug_shows_the_traceback(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # A4-UI-005: --debug was a dead flag (zero reads) and the run-level
        # except swallowed tracebacks exactly where debug should help.
        from mutmut_win.exceptions import CleanTestFailedError

        monkeypatch.chdir(tmp_path)
        (tmp_path / "src").mkdir()  # #120 / CLI-002 validates path existence
        exit_code, output = _invoke_run(
            "--debug", orchestrator_error=CleanTestFailedError("kaboom in step 3")
        )
        assert exit_code != 0
        assert "Traceback" in output
        assert "kaboom in step 3" in output

    def test_without_debug_the_one_liner_stays(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from mutmut_win.exceptions import CleanTestFailedError

        monkeypatch.chdir(tmp_path)
        (tmp_path / "src").mkdir()  # #120 / CLI-002 validates path existence
        exit_code, output = _invoke_run(orchestrator_error=CleanTestFailedError("kaboom"))
        assert exit_code != 0
        assert "kaboom" in output
        assert "Traceback" not in output
