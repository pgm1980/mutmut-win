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
from tests.unit.phase_mock_util import phase_popen as _phase_popen


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
        with _phase_popen(0) as mock_run:
            rc = runner.run_clean_test()
        assert rc == 0
        mock_run.assert_called_once()

    def test_returns_nonzero_on_failure(self) -> None:
        runner = PytestRunner(_config())
        with _phase_popen(1):
            rc = runner.run_clean_test()
        assert rc == 1

    def test_uses_sys_executable(self) -> None:
        runner = PytestRunner(_config())
        with _phase_popen(0) as mock_run:
            runner.run_clean_test()
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == sys.executable
        assert "-m" in cmd
        assert "pytest" in cmd

    def test_extra_args_forwarded(self) -> None:
        runner = PytestRunner(_config(pytest_add_cli_args=["--timeout=10", "-x"]))
        with _phase_popen(0) as mock_run:
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
        with _phase_popen(0) as mock_run:
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

    def test_collection_scope_matches_the_stats_phase(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # 360°-B2 (#130): collection ran in the PROJECT root without
        # tests_dir or pytest_add_cli_args — marker filters or missing
        # testpaths made every run see "new" tests → permanent full
        # re-collection; strict utf-8 decoding crashed on cp1252 pipes.
        monkeypatch.chdir(tmp_path)
        (tmp_path / "mutants").mkdir(exist_ok=True)
        runner = PytestRunner(_config(pytest_add_cli_args=["-m", "not slow"], tests_dir=["tests/"]))
        with patch(
            "subprocess.run", return_value=_make_completed_process(0, stdout="")
        ) as mock_run:
            runner.collect_tests()

        cmd = mock_run.call_args[0][0]
        kwargs = mock_run.call_args[1]
        assert "-m" in cmd
        assert "not slow" in cmd
        assert "tests/" in cmd
        assert kwargs.get("cwd") == "mutants"
        assert kwargs.get("errors") == "replace"
        env = kwargs.get("env")
        assert env is not None
        assert env.get("MUTANT_UNDER_TEST") == ""

    def test_collection_falls_back_to_project_root_without_staging(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Defensive: callers outside the pipeline (unit tests, ad-hoc use)
        # may collect before any staging exists. A nested dir sidesteps the
        # module fixture that pre-creates mutants/ in tmp_path.
        isolated = tmp_path / "isolated"
        isolated.mkdir()
        monkeypatch.chdir(isolated)  # no mutants/ here
        runner = PytestRunner(_config())
        with patch(
            "subprocess.run", return_value=_make_completed_process(0, stdout="")
        ) as mock_run:
            runner.collect_tests()
        assert mock_run.call_args[1].get("cwd") is None

    def test_subprocess_contract_is_pinned(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Mutation hardening (#130 gate): the collection contract — exact
        # flags, decoding and staging env — is load-bearing for stats-phase
        # parity; pin every piece.
        monkeypatch.chdir(tmp_path)
        (tmp_path / "mutants").mkdir(exist_ok=True)
        runner = PytestRunner(_config())
        with patch(
            "subprocess.run", return_value=_make_completed_process(0, stdout="")
        ) as mock_run:
            runner.collect_tests()
        cmd = mock_run.call_args[0][0]
        index = cmd.index("--collect-only")
        assert cmd[index : index + 3] == ["--collect-only", "-q", "--no-header"]
        kwargs = mock_run.call_args[1]
        assert kwargs["capture_output"] is True
        assert kwargs["encoding"] == "utf-8"
        assert kwargs["errors"] == "replace"
        env = kwargs["env"]
        assert env["PYTHONIOENCODING"] == "utf-8"
        assert env["MUTANT_UNDER_TEST"] == ""

    def test_fallback_passes_inherited_env(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Without staging there is no env override — the subprocess must
        # inherit the parent environment (env=None), not an empty one.
        isolated = tmp_path / "isolated"
        isolated.mkdir()
        monkeypatch.chdir(isolated)
        runner = PytestRunner(_config())
        with patch(
            "subprocess.run", return_value=_make_completed_process(0, stdout="")
        ) as mock_run:
            runner.collect_tests()
        assert mock_run.call_args[1].get("env") is None

    def test_filter_pins_summary_and_warning_prefixes(self) -> None:
        # Only '='-summaries and UPPERCASE pytest WARNINGs are filtered; a
        # lowercase 'warning:'-style node id must survive untouched.
        stdout = (
            "tests/a.py::t1\n"
            "= 1 test collected =\n"
            "= slowest::durations =\n"  # '='-summary WITH '::' — prefix rule must drop it
            "WARNING: noise::ignored\n"
            "warning: keep::this\n"
        )
        runner = PytestRunner(_config())
        with patch("subprocess.run", return_value=_make_completed_process(0, stdout=stdout)):
            tests = runner.collect_tests()
        assert tests == ["tests/a.py::t1", "warning: keep::this"]


# ---------------------------------------------------------------------------
# run_stats
# ---------------------------------------------------------------------------


class TestRunStats:
    """Tests for run_stats (subprocess-based stats collection with injected plugin)."""

    def test_returns_the_exit_code(self) -> None:
        """Issue #99 / A2-RN-003: callers must be able to detect a failed
        collection — run_stats returns the subprocess exit code now."""
        runner = PytestRunner(_config())
        with _phase_popen(0):
            result = runner.run_stats()
        assert result == 0

    def test_calls_subprocess_once(self) -> None:
        """run_stats calls subprocess.run once with the stats plugin."""
        runner = PytestRunner(_config())
        with _phase_popen(0) as mock_sub:
            runner.run_stats()
        assert mock_sub.call_count == 1

    def test_stats_plugin_flag_in_command(self) -> None:
        """The -p _mutmut_stats_plugin flag must be in the pytest command."""
        runner = PytestRunner(_config())
        with _phase_popen(0) as mock_sub:
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

    def test_does_not_touch_the_process_env(self) -> None:
        """Issue #99 / A2-RN-007: the vestigial os.environ write is gone —
        the stats sentinel travels via the SUBPROCESS env parameter only.
        The parent process env must stay untouched, whatever it carries
        (under dogfooding it legitimately holds 'stats'; the old pin on
        '== ""' broke exactly there, found by the second self-run)."""
        import os

        before = os.environ.get(MUTANT_ENV_VAR)
        runner = PytestRunner(_config())
        with _phase_popen(0):
            runner.run_stats()
        assert os.environ.get(MUTANT_ENV_VAR) == before

    def test_tests_dir_forwarded(self) -> None:
        """tests_dir config should be included in the pytest command."""
        runner = PytestRunner(_config(tests_dir=["tests/unit/"]))
        with _phase_popen(0) as mock_sub:
            runner.run_stats()
        cmd = mock_sub.call_args[0][0]
        assert "tests/unit/" in cmd


# ---------------------------------------------------------------------------
# run_forced_fail
# ---------------------------------------------------------------------------


class TestRunForcedFail:
    def test_returns_nonzero_when_tests_fail(self) -> None:
        runner = PytestRunner(_config())
        with _phase_popen(1):
            rc = runner.run_forced_fail("some_mutant")
        assert rc != 0

    def test_fail_sentinel_set_in_env(self) -> None:
        runner = PytestRunner(_config())
        captured_envs: list[dict[str, str]] = []

        def fake_popen(cmd: list[str], **kwargs: Any) -> MagicMock:  # noqa: ARG001
            env = kwargs.get("env")
            if env is not None:
                captured_envs.append(dict(env))
            proc = MagicMock()
            proc.pid = 99999
            proc.wait.return_value = 1
            return proc

        with (
            patch("subprocess.Popen", side_effect=fake_popen),
            patch("mutmut_win.process.worker._create_task_job", return_value=None),
        ):
            runner.run_forced_fail("mutant_x")

        assert len(captured_envs) == 1
        assert captured_envs[0][MUTANT_ENV_VAR] == MUTANT_FAIL_SENTINEL

    def test_output_captured_to_file_not_pipe(self) -> None:
        """Issue #99 / A2-RN-001: same capture pattern as the clean phase."""
        import subprocess as _subprocess

        runner = PytestRunner(_config())
        with _phase_popen(1) as mock_run:
            runner.run_forced_fail("m1")
        kwargs = mock_run.call_args[1]
        assert isinstance(kwargs.get("stdout"), int)
        assert kwargs.get("stderr") == _subprocess.STDOUT

    def test_returns_zero_when_all_tests_pass(self) -> None:
        """Edge case: if forced-fail somehow returns 0, runner faithfully reports it."""
        runner = PytestRunner(_config())
        with _phase_popen(0):
            rc = runner.run_forced_fail("m1")
        assert rc == 0

    def test_mutant_name_parameter_accepted(self) -> None:
        """run_forced_fail must accept arbitrary mutant_name without error."""
        runner = PytestRunner(_config())
        with _phase_popen(1):
            rc = runner.run_forced_fail("src/foo.py::bar__mutmut_1")
        assert isinstance(rc, int)


# ---------------------------------------------------------------------------
# Parametrize: extra args always appended to command
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("extra_args", [[], ["--tb=short"], ["-x", "--strict-markers"]])
def test_extra_args_always_appended_to_command(extra_args: list[str]) -> None:
    """pytest_add_cli_args must always appear in the subprocess command."""
    runner = PytestRunner(_config(pytest_add_cli_args=extra_args))
    with _phase_popen(0) as mock_run:
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
    def test_timeout_returns_36_and_reaps_the_tree(self, tmp_path: Path) -> None:
        import subprocess

        runner = PytestRunner(_config(clean_run_timeout=7))
        proc = MagicMock()
        proc.pid = 99999
        proc.wait.side_effect = subprocess.TimeoutExpired(cmd="coverage", timeout=7)
        with (
            patch("subprocess.Popen", return_value=proc),
            patch("mutmut_win.process.worker._create_task_job", return_value=None),
            patch("mutmut_win.process.worker._kill_proc_tree") as kill_tree,
        ):
            rc = runner.run_coverage_collection(tmp_path / ".coverage.mutmut")
        assert rc == 36
        kill_tree.assert_called_once_with(proc, None)

    def test_returns_subprocess_exit_code(self, tmp_path: Path) -> None:
        runner = PytestRunner(_config())
        with _phase_popen(1):
            rc = runner.run_coverage_collection(tmp_path / ".coverage.mutmut")
        assert rc == 1
