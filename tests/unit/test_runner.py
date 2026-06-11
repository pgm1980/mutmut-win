"""Unit tests for mutmut_win.runner (PytestRunner)."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from mutmut_win.config import MutmutConfig
from mutmut_win.runner import (
    MUTANT_ENV_VAR,
    MUTANT_FAIL_SENTINEL,
    PytestRunner,
)


@pytest.fixture(autouse=True)
def _isolated_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Run in a temp cwd with a mutants/ dir.

    These tests exercise code that resolves 'mutants' RELATIVE TO THE CWD
    (sitecustomize writes, temp log files). They only passed from the repo
    root because a real mutants/ happened to exist there — and they wrote
    artifacts into it (A2-RN-010). Under dogfooding (#98) the suite itself
    runs INSIDE mutants/, where 'mutants/mutants' does not exist.
    """
    monkeypatch.chdir(tmp_path)
    (tmp_path / "mutants").mkdir(exist_ok=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _config(**overrides: Any) -> MutmutConfig:
    defaults: dict[str, Any] = {}
    defaults.update(overrides)
    return MutmutConfig(**defaults)


def _make_completed_process(returncode: int = 0, stdout: str = "", stderr: str = "") -> MagicMock:
    proc = MagicMock()
    proc.returncode = returncode
    proc.stdout = stdout
    proc.stderr = stderr
    return proc


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------


class TestPytestRunnerInit:
    def test_stores_config(self) -> None:
        cfg = _config(max_children=4)
        runner = PytestRunner(cfg)
        assert runner._config is cfg


# ---------------------------------------------------------------------------
# run_clean_test
# ---------------------------------------------------------------------------


class TestRunCleanTest:
    def test_returns_zero_on_success(self) -> None:
        runner = PytestRunner(_config())
        with patch("subprocess.run", return_value=_make_completed_process(0)) as mock_run:
            rc = runner.run_clean_test()
        assert rc == 0
        mock_run.assert_called_once()

    def test_returns_nonzero_on_failure(self) -> None:
        runner = PytestRunner(_config())
        with patch("subprocess.run", return_value=_make_completed_process(1)):
            rc = runner.run_clean_test()
        assert rc == 1

    def test_uses_sys_executable(self) -> None:
        runner = PytestRunner(_config())
        with patch("subprocess.run", return_value=_make_completed_process(0)) as mock_run:
            runner.run_clean_test()
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == sys.executable
        assert "-m" in cmd
        assert "pytest" in cmd

    def test_extra_args_forwarded(self) -> None:
        runner = PytestRunner(_config(pytest_add_cli_args=["--timeout=10", "-x"]))
        with patch("subprocess.run", return_value=_make_completed_process(0)) as mock_run:
            runner.run_clean_test()
        cmd = mock_run.call_args[0][0]
        assert "--timeout=10" in cmd
        assert "-x" in cmd

    def test_output_captured_to_file_not_pipe(self) -> None:
        """Issue #99 / A2-RN-001: stdout goes to a temp FILE (worker pattern —
        PIPE deadlocks on Windows when grandchildren inherit handles, DEVNULL
        left zero diagnostics on failure); stderr is folded into stdout."""
        import subprocess as _subprocess

        runner = PytestRunner(_config())
        with patch("subprocess.run", return_value=_make_completed_process(0)) as mock_run:
            runner.run_clean_test()
        kwargs = mock_run.call_args[1]
        assert isinstance(kwargs.get("stdout"), int)  # a real file descriptor
        assert kwargs.get("stdout") != _subprocess.DEVNULL
        assert kwargs.get("stderr") == _subprocess.STDOUT


# ---------------------------------------------------------------------------
# collect_tests
# ---------------------------------------------------------------------------


class TestCollectTests:
    def test_parses_test_node_ids(self) -> None:
        stdout = (
            "tests/unit/test_foo.py::test_alpha\n"
            "tests/unit/test_foo.py::test_beta\n"
            "2 tests collected\n"
        )
        runner = PytestRunner(_config())
        with patch("subprocess.run", return_value=_make_completed_process(0, stdout=stdout)):
            tests = runner.collect_tests()
        assert tests == [
            "tests/unit/test_foo.py::test_alpha",
            "tests/unit/test_foo.py::test_beta",
        ]

    def test_returns_sorted_list(self) -> None:
        stdout = "tests/unit/test_b.py::test_z\ntests/unit/test_a.py::test_a\n"
        runner = PytestRunner(_config())
        with patch("subprocess.run", return_value=_make_completed_process(0, stdout=stdout)):
            tests = runner.collect_tests()
        assert tests == sorted(tests)

    def test_ignores_summary_lines(self) -> None:
        stdout = (
            "tests/unit/test_foo.py::test_alpha\n== 1 test collected ==\nWARNING: some warning\n"
        )
        runner = PytestRunner(_config())
        with patch("subprocess.run", return_value=_make_completed_process(0, stdout=stdout)):
            tests = runner.collect_tests()
        assert len(tests) == 1
        assert tests[0] == "tests/unit/test_foo.py::test_alpha"

    def test_returns_empty_list_when_no_tests(self) -> None:
        runner = PytestRunner(_config())
        with patch("subprocess.run", return_value=_make_completed_process(0, stdout="")):
            tests = runner.collect_tests()
        assert tests == []

    def test_collect_only_flag_in_command(self) -> None:
        runner = PytestRunner(_config())
        with patch(
            "subprocess.run",
            return_value=_make_completed_process(0, stdout=""),
        ) as mock_run:
            runner.collect_tests()
        cmd = mock_run.call_args[0][0]
        assert "--collect-only" in cmd

    def test_selection_args_forwarded(self) -> None:
        runner = PytestRunner(_config(pytest_add_cli_args_test_selection=["tests/unit/"]))
        with patch(
            "subprocess.run",
            return_value=_make_completed_process(0, stdout=""),
        ) as mock_run:
            runner.collect_tests()
        cmd = mock_run.call_args[0][0]
        assert "tests/unit/" in cmd


# ---------------------------------------------------------------------------
# run_stats
# ---------------------------------------------------------------------------


class TestRunStats:
    """Tests for run_stats (subprocess-based stats collection with injected plugin)."""

    def test_returns_the_exit_code(self) -> None:
        """Issue #99 / A2-RN-003: callers must be able to detect a failed
        collection — run_stats returns the subprocess exit code now."""
        runner = PytestRunner(_config())
        run_result = MagicMock(stdout="", returncode=0)
        with patch("subprocess.run", return_value=run_result):
            result = runner.run_stats()
        assert result == 0

    def test_calls_subprocess_once(self) -> None:
        """run_stats calls subprocess.run once with the stats plugin."""
        runner = PytestRunner(_config())
        run_result = MagicMock(stdout="", returncode=0)
        with patch("subprocess.run", return_value=run_result) as mock_sub:
            runner.run_stats()
        assert mock_sub.call_count == 1

    def test_stats_plugin_flag_in_command(self) -> None:
        """The -p _mutmut_stats_plugin flag must be in the pytest command."""
        runner = PytestRunner(_config())
        run_result = MagicMock(stdout="", returncode=0)
        with patch("subprocess.run", return_value=run_result) as mock_sub:
            runner.run_stats()
        cmd = mock_sub.call_args[0][0]
        assert "-p" in cmd
        p_idx = cmd.index("-p")
        assert cmd[p_idx + 1] == "_mutmut_stats_plugin"

    def test_stats_plugin_file_written(self) -> None:
        """_write_stats_plugin must create the plugin file in mutants/."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mutants_dir = Path(tmpdir)
            PytestRunner._write_stats_plugin(mutants_dir)
            plugin_path = mutants_dir / "_mutmut_stats_plugin.py"
            assert plugin_path.exists()
            content = plugin_path.read_text(encoding="utf-8")
            assert "pytest_runtest_protocol" in content
            assert "pytest_sessionfinish" in content
            assert "mutmut-stats.json" in content

    def test_clears_mutant_env_after_run(self) -> None:
        """MUTANT_UNDER_TEST must be cleared after stats collection."""
        import os

        runner = PytestRunner(_config())
        run_result = MagicMock(stdout="", returncode=0)
        with patch("subprocess.run", return_value=run_result):
            runner.run_stats()
        assert os.environ.get(MUTANT_ENV_VAR, "") == ""

    def test_tests_dir_forwarded(self) -> None:
        """tests_dir config should be included in the pytest command."""
        runner = PytestRunner(_config(tests_dir=["tests/unit/"]))
        run_result = MagicMock(stdout="", returncode=0)
        with patch("subprocess.run", return_value=run_result) as mock_sub:
            runner.run_stats()
        cmd = mock_sub.call_args[0][0]
        assert "tests/unit/" in cmd


# ---------------------------------------------------------------------------
# run_forced_fail
# ---------------------------------------------------------------------------


class TestRunForcedFail:
    def test_returns_nonzero_when_tests_fail(self) -> None:
        runner = PytestRunner(_config())
        with patch("subprocess.run", return_value=_make_completed_process(1)):
            rc = runner.run_forced_fail("some_mutant")
        assert rc != 0

    def test_fail_sentinel_set_in_env(self) -> None:
        runner = PytestRunner(_config())
        captured_envs: list[dict[str, str]] = []

        def fake_run(cmd: list[str], **kwargs: Any) -> MagicMock:  # noqa: ARG001
            env = kwargs.get("env")
            if env is not None:
                captured_envs.append(dict(env))
            return _make_completed_process(1)

        with patch("subprocess.run", side_effect=fake_run):
            runner.run_forced_fail("mutant_x")

        assert len(captured_envs) == 1
        assert captured_envs[0][MUTANT_ENV_VAR] == MUTANT_FAIL_SENTINEL

    def test_output_captured_to_file_not_pipe(self) -> None:
        """Issue #99 / A2-RN-001: same capture pattern as the clean phase."""
        import subprocess as _subprocess

        runner = PytestRunner(_config())
        with patch("subprocess.run", return_value=_make_completed_process(1)) as mock_run:
            runner.run_forced_fail("m1")
        kwargs = mock_run.call_args[1]
        assert isinstance(kwargs.get("stdout"), int)
        assert kwargs.get("stderr") == _subprocess.STDOUT

    def test_returns_zero_when_all_tests_pass(self) -> None:
        """Edge case: if forced-fail somehow returns 0, runner faithfully reports it."""
        runner = PytestRunner(_config())
        with patch("subprocess.run", return_value=_make_completed_process(0)):
            rc = runner.run_forced_fail("m1")
        assert rc == 0

    def test_mutant_name_parameter_accepted(self) -> None:
        """run_forced_fail must accept arbitrary mutant_name without error."""
        runner = PytestRunner(_config())
        with patch("subprocess.run", return_value=_make_completed_process(1)):
            rc = runner.run_forced_fail("src/foo.py::bar__mutmut_1")
        assert isinstance(rc, int)


# ---------------------------------------------------------------------------
# Parametrize: extra args always appended to command
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("extra_args", [[], ["--tb=short"], ["-x", "--strict-markers"]])
def test_extra_args_always_appended_to_command(extra_args: list[str]) -> None:
    """pytest_add_cli_args must always appear in the subprocess command."""
    runner = PytestRunner(_config(pytest_add_cli_args=extra_args))
    with patch("subprocess.run", return_value=_make_completed_process(0)) as mock_run:
        runner.run_clean_test()
    cmd: list[str] = mock_run.call_args[0][0]
    for arg in extra_args:
        assert arg in cmd


# ---------------------------------------------------------------------------
# Coverage bridge (#95) — replaced the dead mutmut-3.5.0 compatibility API
# (prepare_main_test_run / run_tests), which only existed for the in-process
# coverage collection that the subprocess rewrite had already broken.
# ---------------------------------------------------------------------------


class TestRunCoverageCollection:
    def test_timeout_returns_36(self, tmp_path: Path) -> None:
        import subprocess

        runner = PytestRunner(_config(clean_run_timeout=7))
        with patch(
            "subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="coverage", timeout=7),
        ):
            rc = runner.run_coverage_collection(tmp_path / ".coverage.mutmut")
        assert rc == 36

    def test_returns_subprocess_exit_code(self, tmp_path: Path) -> None:
        runner = PytestRunner(_config())
        with patch("subprocess.run", return_value=_make_completed_process(1)):
            rc = runner.run_coverage_collection(tmp_path / ".coverage.mutmut")
        assert rc == 1
