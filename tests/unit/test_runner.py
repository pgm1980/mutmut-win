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
    MUTANT_STATS_SENTINEL,
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
        stdout = (
            "tests/unit/test_b.py::test_z\n"
            "tests/unit/test_a.py::test_a\n"
        )
        runner = PytestRunner(_config())
        with patch("subprocess.run", return_value=_make_completed_process(0, stdout=stdout)):
            tests = runner.collect_tests()
        assert tests == sorted(tests)

    def test_ignores_summary_lines(self) -> None:
        stdout = (
            "tests/unit/test_foo.py::test_alpha\n"
            "== 1 test collected ==\n"
            "WARNING: some warning\n"
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
        runner = PytestRunner(
            _config(pytest_add_cli_args_test_selection=["tests/unit/"])
        )
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
    def test_returns_dict_with_test_names(self) -> None:
        stdout = "tests/unit/test_foo.py::test_x\ntests/unit/test_foo.py::test_y\n"
        runner = PytestRunner(_config())
        with patch(
            "subprocess.run",
            side_effect=[
                _make_completed_process(0, stdout=stdout),  # collect_tests call
                _make_completed_process(0),  # test_x timing run
                _make_completed_process(0),  # test_y timing run
            ],
        ):
            stats = runner.run_stats()
        assert "tests/unit/test_foo.py::test_x" in stats
        assert "tests/unit/test_foo.py::test_y" in stats

    def test_durations_are_non_negative(self) -> None:
        stdout = "tests/unit/test_foo.py::test_a\n"
        runner = PytestRunner(_config())
        with patch(
            "subprocess.run",
            side_effect=[
                _make_completed_process(0, stdout=stdout),
                _make_completed_process(0),
            ],
        ):
            stats = runner.run_stats()
        assert all(v >= 0.0 for v in stats.values())

    def test_stats_sentinel_set_in_env(self) -> None:
        runner = PytestRunner(_config())

        captured_envs: list[dict[str, str]] = []

        def fake_run(cmd: list[str], **kwargs: Any) -> MagicMock:  # noqa: ARG001
            env = kwargs.get("env")
            if env is not None:
                captured_envs.append(env)
            return _make_completed_process(0, stdout="tests/unit/test_foo.py::test_a\n")

        with patch("subprocess.run", side_effect=fake_run):
            runner.run_stats()

        # The first call is collect_tests (no MUTANT_ENV_VAR set), subsequent
        # calls are timing runs that must have the stats sentinel.
        timing_envs = captured_envs[1:]  # skip collect call
        for env in timing_envs:
            assert env.get(MUTANT_ENV_VAR) == MUTANT_STATS_SENTINEL

    def test_returns_empty_dict_when_no_tests(self) -> None:
        runner = PytestRunner(_config())
        with patch("subprocess.run", return_value=_make_completed_process(0, stdout="")):
            stats = runner.run_stats()
        assert stats == {}


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
