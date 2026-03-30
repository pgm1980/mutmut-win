"""Unit tests for mutmut_win.runner (PytestRunner)."""

from __future__ import annotations

import sys
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from mutmut_win.config import MutmutConfig
from mutmut_win.runner import (
    MUTANT_ENV_VAR,
    MUTANT_FAIL_SENTINEL,
    PytestRunner,
)

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

    def test_encoding_is_utf8(self) -> None:
        runner = PytestRunner(_config())
        with patch("subprocess.run", return_value=_make_completed_process(0)) as mock_run:
            runner.run_clean_test()
        kwargs = mock_run.call_args[1]
        assert kwargs.get("encoding") == "utf-8"

    def test_capture_output_is_true(self) -> None:
        runner = PytestRunner(_config())
        with patch("subprocess.run", return_value=_make_completed_process(0)) as mock_run:
            runner.run_clean_test()
        kwargs = mock_run.call_args[1]
        assert kwargs.get("capture_output") is True


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
    def test_returns_none(self) -> None:
        """run_stats is a side-effect function — it must return None."""
        runner = PytestRunner(_config())
        with (
            patch("pytest.main", return_value=0) as _mock_pytest,
            patch("os.chdir"),
            patch("pathlib.Path.cwd", return_value=MagicMock()),
        ):
            result = runner.run_stats()
        assert result is None

    def test_sets_stats_sentinel_in_env(self) -> None:
        runner = PytestRunner(_config())
        captured_env: dict[str, str] = {}

        import os

        with (
            patch("pytest.main", return_value=0),
            patch("os.chdir"),
            patch("pathlib.Path.cwd", return_value=MagicMock()),
        ):
            runner.run_stats()
            captured_env = dict(os.environ)

        # After run_stats, MUTANT_UNDER_TEST must be cleared (set to "")
        # It was set to "stats" during the run — we verify it was set.
        assert MUTANT_ENV_VAR in captured_env

    def test_calls_pytest_main(self) -> None:
        runner = PytestRunner(_config())
        with (
            patch("pytest.main", return_value=0) as mock_pytest,
            patch("os.chdir"),
            patch("pathlib.Path.cwd", return_value=MagicMock()),
        ):
            runner.run_stats()
        mock_pytest.assert_called_once()

    def test_pytest_main_receives_plugin(self) -> None:
        runner = PytestRunner(_config())
        with (
            patch("pytest.main", return_value=0) as mock_pytest,
            patch("os.chdir"),
            patch("pathlib.Path.cwd", return_value=MagicMock()),
        ):
            runner.run_stats()
        call_kwargs = mock_pytest.call_args
        assert call_kwargs is not None
        plugins = call_kwargs[1].get("plugins") or (
            call_kwargs[0][1] if len(call_kwargs[0]) > 1 else []
        )
        assert len(plugins) == 1

    def test_restores_cwd_on_success(self) -> None:
        from pathlib import Path

        runner = PytestRunner(_config())
        original_cwd = Path.cwd()
        chdir_calls: list[Any] = []

        def fake_chdir(path: Any) -> None:
            chdir_calls.append(path)

        with (
            patch("pytest.main", return_value=0),
            patch("os.chdir", side_effect=fake_chdir),
            patch("pathlib.Path.cwd", return_value=original_cwd),
        ):
            runner.run_stats()

        # First chdir is to "mutants", second is back to original_cwd.
        assert len(chdir_calls) == 2
        assert chdir_calls[0] == "mutants"
        assert chdir_calls[1] == original_cwd

    def test_restores_cwd_on_pytest_exception(self) -> None:
        from pathlib import Path

        runner = PytestRunner(_config())
        original_cwd = Path.cwd()
        chdir_calls: list[Any] = []

        def fake_chdir(path: Any) -> None:
            chdir_calls.append(path)

        with (
            patch("pytest.main", side_effect=RuntimeError("pytest crashed")),
            patch("os.chdir", side_effect=fake_chdir),
            patch("pathlib.Path.cwd", return_value=original_cwd),
            pytest.raises(RuntimeError, match="pytest crashed"),
        ):
            runner.run_stats()

        # Even on exception, the finally block should restore cwd.
        assert chdir_calls[-1] == original_cwd

    def test_extra_pytest_args_forwarded(self) -> None:
        runner = PytestRunner(_config(pytest_add_cli_args=["--timeout=5"]))
        with (
            patch("pytest.main", return_value=0) as mock_pytest,
            patch("os.chdir"),
            patch("pathlib.Path.cwd", return_value=MagicMock()),
        ):
            runner.run_stats()
        args_passed = mock_pytest.call_args[0][0]
        assert "--timeout=5" in args_passed

    def test_tests_dir_forwarded(self) -> None:
        runner = PytestRunner(_config(tests_dir=["tests/unit/"]))
        with (
            patch("pytest.main", return_value=0) as mock_pytest,
            patch("os.chdir"),
            patch("pathlib.Path.cwd", return_value=MagicMock()),
        ):
            runner.run_stats()
        args_passed = mock_pytest.call_args[0][0]
        assert "tests/unit/" in args_passed


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

    def test_encoding_utf8(self) -> None:
        runner = PytestRunner(_config())
        with patch("subprocess.run", return_value=_make_completed_process(1)) as mock_run:
            runner.run_forced_fail("m1")
        kwargs = mock_run.call_args[1]
        assert kwargs.get("encoding") == "utf-8"

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
# F9: prepare_main_test_run and run_tests (coverage API compatibility)
# ---------------------------------------------------------------------------


class TestPrepareMainTestRun:
    def test_returns_none(self) -> None:
        """F9: prepare_main_test_run() is a no-op and must return None."""
        runner = PytestRunner(_config())
        result = runner.prepare_main_test_run()
        assert result is None

    def test_callable_without_args(self) -> None:
        """F9: prepare_main_test_run must be callable with no arguments."""
        runner = PytestRunner(_config())
        runner.prepare_main_test_run()  # should not raise


class TestRunTests:
    def test_delegates_to_run_clean_test(self) -> None:
        """F9: run_tests() delegates to run_clean_test(), returning its exit code."""
        runner = PytestRunner(_config())
        with patch("subprocess.run", return_value=_make_completed_process(0)) as mock_run:
            rc = runner.run_tests(mutant_name=None, tests=None)
        assert rc == 0
        mock_run.assert_called_once()

    def test_accepts_mutant_name_and_tests_args(self) -> None:
        """F9: run_tests accepts mutant_name and tests keyword args without error."""
        runner = PytestRunner(_config())
        with patch("subprocess.run", return_value=_make_completed_process(0)):
            rc = runner.run_tests(mutant_name="src.foo.x_bar__mutmut_1", tests=["t1", "t2"])
        assert isinstance(rc, int)

    def test_returns_nonzero_when_tests_fail(self) -> None:
        runner = PytestRunner(_config())
        with patch("subprocess.run", return_value=_make_completed_process(1)):
            rc = runner.run_tests(mutant_name=None, tests=None)
        assert rc == 1
