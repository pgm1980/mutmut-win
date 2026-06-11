"""Tests for configurable clean-run / forced-fail timeouts (Issue #74, W4.11 BUG-2).

The clean baseline run, the stats run and the forced-fail verification ran
with hard-coded module constants (300 s / 120 s) before v2.6.0.  Trampolined
suites run ~35 % slower than native, so legitimate green suites > 300 s could
never pass the clean gate, and the error text blamed the tests.
"""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

if TYPE_CHECKING:
    from pathlib import Path

from mutmut_win.config import MutmutConfig, load_config
from mutmut_win.exceptions import CleanTestFailedError
from mutmut_win.orchestrator import MutationOrchestrator
from mutmut_win.runner import PytestRunner

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _completed(returncode: int = 0) -> MagicMock:
    proc = MagicMock()
    proc.returncode = returncode
    proc.stdout = ""
    proc.stderr = ""
    return proc


# ---------------------------------------------------------------------------
# Config fields
# ---------------------------------------------------------------------------


class TestTimeoutConfigFields:
    def test_defaults_match_previous_constants(self) -> None:
        cfg = MutmutConfig()
        assert cfg.clean_run_timeout == 300
        assert cfg.forced_fail_timeout == 120

    def test_zero_and_negative_rejected(self) -> None:
        with pytest.raises(ValidationError):
            MutmutConfig(clean_run_timeout=0)
        with pytest.raises(ValidationError):
            MutmutConfig(forced_fail_timeout=-1)

    def test_pyproject_roundtrip(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            "[tool.mutmut]\nclean_run_timeout = 900\nforced_fail_timeout = 200\n",
            encoding="utf-8",
        )
        cfg = load_config(tmp_path)
        assert cfg.clean_run_timeout == 900
        assert cfg.forced_fail_timeout == 200

    def test_setup_cfg_roundtrip(self, tmp_path: Path) -> None:
        (tmp_path / "setup.cfg").write_text(
            "[mutmut]\nclean_run_timeout = 900\nforced_fail_timeout = 200\n",
            encoding="utf-8",
        )
        cfg = load_config(tmp_path)
        assert cfg.clean_run_timeout == 900
        assert cfg.forced_fail_timeout == 200


# ---------------------------------------------------------------------------
# Runner uses the configured values
# ---------------------------------------------------------------------------


class TestRunnerUsesConfiguredTimeouts:
    def test_clean_run_uses_configured_timeout(self) -> None:
        runner = PytestRunner(MutmutConfig(clean_run_timeout=900))
        with patch("subprocess.run", return_value=_completed(0)) as mock_run:
            runner.run_clean_test()
        assert mock_run.call_args[1]["timeout"] == 900

    def test_clean_run_default_timeout(self) -> None:
        runner = PytestRunner(MutmutConfig())
        with patch("subprocess.run", return_value=_completed(0)) as mock_run:
            runner.run_clean_test()
        assert mock_run.call_args[1]["timeout"] == 300

    def test_stats_run_uses_configured_timeout(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # chdir into tmp so the plugin/sitecustomize writes stay out of the repo.
        monkeypatch.chdir(tmp_path)
        (tmp_path / "mutants").mkdir()
        runner = PytestRunner(MutmutConfig(clean_run_timeout=900))
        with patch("subprocess.run", return_value=_completed(0)) as mock_run:
            runner.run_stats()
        assert mock_run.call_args[1]["timeout"] == 900

    def test_forced_fail_uses_configured_timeout(self) -> None:
        runner = PytestRunner(MutmutConfig(forced_fail_timeout=200))
        with patch("subprocess.run", return_value=_completed(1)) as mock_run:
            runner.run_forced_fail("token")
        assert mock_run.call_args[1]["timeout"] == 200

    def test_coverage_collection_builds_a_coverage_run_command(self, tmp_path: Path) -> None:
        """Issue #95: the coverage bridge runs pytest UNDER `coverage run`
        with an explicit data file inside mutants/ — the parent loads the
        data file afterwards."""
        runner = PytestRunner(MutmutConfig())
        captured: dict[str, Any] = {}

        def fake_run(cmd: list[str], **kwargs: Any) -> MagicMock:
            captured["cmd"] = cmd
            captured.update(kwargs)
            return _completed(0)

        data_file = tmp_path / ".coverage.mutmut"
        with patch("subprocess.run", side_effect=fake_run):
            exit_code = runner.run_coverage_collection(data_file)

        assert exit_code == 0
        cmd = captured["cmd"]
        assert cmd[1:4] == ["-m", "coverage", "run"]
        assert f"--data-file={data_file}" in cmd
        assert "--source=." in cmd
        assert "pytest" in cmd
        assert captured["cwd"] == "mutants"
        assert captured["timeout"] == MutmutConfig().clean_run_timeout

    def test_clean_timeout_warning_names_config_key(self, capsys: pytest.CaptureFixture) -> None:
        runner = PytestRunner(MutmutConfig(clean_run_timeout=7))
        with patch(
            "subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="pytest", timeout=7),
        ):
            rc = runner.run_clean_test()
        assert rc == 36
        out = capsys.readouterr().out
        assert "7" in out
        assert "clean_run_timeout" in out


# ---------------------------------------------------------------------------
# Orchestrator error message distinguishes timeout from genuine failure
# ---------------------------------------------------------------------------


class TestOrchestratorTimeoutMessage:
    def test_timeout_message_names_config_key(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # chdir into tmp so copy_src_dir/mutants-staging stays out of the repo.
        monkeypatch.chdir(tmp_path)
        src = tmp_path / "src"
        src.mkdir()
        (src / "target.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")

        runner = MagicMock()
        runner.run_clean_test.return_value = 36
        cfg = MutmutConfig(paths_to_mutate=["src"], clean_run_timeout=450)
        orch = MutationOrchestrator(
            cfg, runner=runner, executor=MagicMock(), db_path=tmp_path / "db"
        )
        with pytest.raises(CleanTestFailedError, match="clean_run_timeout"):
            orch.run()

    def test_genuine_failure_message_unchanged(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        src = tmp_path / "src"
        src.mkdir()
        (src / "target.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")

        runner = MagicMock()
        runner.run_clean_test.return_value = 1
        runner.last_diagnostic_output = "FAILED tests/test_x.py::test_y"
        cfg = MutmutConfig(paths_to_mutate=["src"])
        orch = MutationOrchestrator(
            cfg, runner=runner, executor=MagicMock(), db_path=tmp_path / "db"
        )
        # Issue #99 / A2-RN-001: the blanket "Fix tests" is gone — the message
        # decodes the exit class and carries the captured pytest tail.
        with pytest.raises(CleanTestFailedError, match="tests failed") as excinfo:
            orch.run()
        assert "FAILED tests/test_x.py::test_y" in str(excinfo.value)
