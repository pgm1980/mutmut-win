"""Issue #114 (audit A4-QX-005/006/023): exception hygiene.

Wire-before-delete: every exception class either has a real producer or
is gone. ``BadTestExecutionCommandsException`` finally gets the producer
its docstring promised (pytest exit 4 at the clean gate);
``InvalidConfigValueError`` wraps config validation failures;
``WorkerError`` covers unknown event shapes; ``MutationParseError``
covers the mutant-diff readers. ``WorkerCrashError``/``WorkerInitError``
are REMOVED — worker crashes are recovered into synthesized task events
by design (Bug #12 / issue #80), an exception class for a path that must
never raise is a lie. ``type_checking``/``code_coverage`` stop raising
bare ``Exception`` (QX-023), and the cli stops catching it — foreign
bugs propagate as tracebacks instead of masquerading as domain errors.
"""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from mutmut_win.cli import cli
from mutmut_win.code_coverage import gather_coverage
from mutmut_win.config import MutmutConfig, load_config
from mutmut_win.exceptions import (
    BadTestExecutionCommandsException,
    CleanTestFailedError,
    ConfigError,
    CoverageCollectionError,
    InvalidConfigValueError,
    MutationError,
    MutationParseError,
    MutmutWinError,
    TypeCheckCommandError,
    WorkerError,
)
from mutmut_win.mutant_diff import read_mutants_module, read_orig_module
from mutmut_win.orchestrator import MutationOrchestrator
from mutmut_win.type_checking import run_type_checker

if TYPE_CHECKING:
    from pathlib import Path


# ---------------------------------------------------------------------------
# Hierarchy: wired classes exist, unproducible classes are gone
# ---------------------------------------------------------------------------


class TestHierarchy:
    def test_new_domain_classes_are_mutmut_errors(self) -> None:
        assert issubclass(TypeCheckCommandError, MutmutWinError)
        assert issubclass(CoverageCollectionError, MutmutWinError)
        assert issubclass(InvalidConfigValueError, ConfigError)
        assert issubclass(WorkerError, MutmutWinError)
        assert issubclass(MutationParseError, MutationError)

    def test_unproducible_worker_classes_are_removed(self) -> None:
        """Crash recovery is event-based by design (Bug #12 / #80) — these
        classes could never be raised."""
        import mutmut_win.exceptions as exc_mod

        assert not hasattr(exc_mod, "WorkerCrashError")
        assert not hasattr(exc_mod, "WorkerInitError")


# ---------------------------------------------------------------------------
# QX-006 — InvalidConfigValueError producer: config validation
# ---------------------------------------------------------------------------


class TestInvalidConfigValueProducer:
    def test_bad_toml_value_raises_invalid_config_value(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / "pyproject.toml").write_text(
            "[tool.mutmut]\nmax_children = 0\n", encoding="utf-8"
        )
        with pytest.raises(InvalidConfigValueError):
            load_config()

    def test_it_still_is_a_config_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Existing ConfigError handling (exit-2 paths) keeps working."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "pyproject.toml").write_text(
            "[tool.mutmut]\ntimeout_multiplier = -1\n", encoding="utf-8"
        )
        with pytest.raises(ConfigError):
            load_config()


# ---------------------------------------------------------------------------
# QX-006 — WorkerError producer: unknown event shape
# ---------------------------------------------------------------------------


class TestWorkerErrorProducer:
    def test_unknown_event_shape_raises_worker_error(self) -> None:
        from mutmut_win.process.executor import SpawnPoolExecutor

        executor = SpawnPoolExecutor(max_workers=1, config=MutmutConfig())
        executor._num_tasks = 1
        executor._workers = []
        executor._event_queue.put({"neither_exit_code_nor_timestamp": True})
        with pytest.raises(WorkerError, match="unknown event shape"):
            list(executor.get_events())


# ---------------------------------------------------------------------------
# QX-005 — BadTestExecutionCommandsException producer: clean gate exit 4
# ---------------------------------------------------------------------------


def _gate_runner(clean_exit: int) -> MagicMock:
    runner = MagicMock()
    runner.run_clean_test.return_value = clean_exit
    runner.run_stats.return_value = None
    runner.collect_tests.return_value = []
    runner.run_forced_fail.return_value = 1
    runner.last_forced_fail_attributed = True
    runner.last_diagnostic_output = "usage: pytest [options]"
    return runner


def _make_orchestrator(tmp_path: Path, runner: MagicMock) -> MutationOrchestrator:
    src = tmp_path / "src"
    src.mkdir(exist_ok=True)
    (src / "target.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    executor = MagicMock()
    executor.get_events.return_value = iter([])
    cfg = MutmutConfig(paths_to_mutate=["src"], pytest_add_cli_args=["--bad-flag"])
    return MutationOrchestrator(cfg, runner=runner, executor=executor, db_path=tmp_path / "db")


class TestBadTestExecutionCommandsProducer:
    def test_clean_exit_4_raises_with_args_and_tail(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        orch = _make_orchestrator(tmp_path, _gate_runner(clean_exit=4))
        with pytest.raises(BadTestExecutionCommandsException, match="--bad-flag") as excinfo:
            orch.run()
        assert "usage: pytest" in str(excinfo.value)

    def test_other_clean_failures_keep_clean_test_failed_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        orch = _make_orchestrator(tmp_path, _gate_runner(clean_exit=1))
        with pytest.raises(CleanTestFailedError):
            orch.run()


# ---------------------------------------------------------------------------
# QX-023 — type_checking raises the domain class
# ---------------------------------------------------------------------------


def _completed(returncode: int, stdout: str = "", stderr: str = "") -> MagicMock:
    proc = MagicMock()
    proc.returncode = returncode
    proc.stdout = stdout
    proc.stderr = stderr
    return proc


class TestTypeCheckCommandError:
    def test_timeout_raises_domain_error(self) -> None:
        with (
            patch(
                "subprocess.run",
                side_effect=subprocess.TimeoutExpired(cmd="mypy", timeout=300),
            ),
            pytest.raises(TypeCheckCommandError, match="timed out"),
        ):
            run_type_checker(["mypy", "--output=json", "src/"])

    def test_checker_failure_exit_raises_domain_error(self) -> None:
        with (
            patch("subprocess.run", return_value=_completed(2, stderr="fatal")),
            pytest.raises(TypeCheckCommandError, match="exit code"),
        ):
            run_type_checker(["mypy", "--output=json", "src/"])

    def test_non_json_output_raises_domain_error(self) -> None:
        with (
            patch("subprocess.run", return_value=_completed(0, stdout="not json")),
            pytest.raises(TypeCheckCommandError, match="JSON"),
        ):
            run_type_checker(["mypy", "--output=json", "src/"])

    def test_invalid_pyright_report_raises_domain_error(self) -> None:
        with (
            patch("subprocess.run", return_value=_completed(0, stdout='{"wrong": 1}')),
            pytest.raises(TypeCheckCommandError, match="generalDiagnostics"),
        ):
            run_type_checker(["pyright", "--outputjson"])


# ---------------------------------------------------------------------------
# QX-023 (same hygiene class) — code_coverage raises the domain class
# ---------------------------------------------------------------------------


class TestCoverageCollectionError:
    @pytest.fixture(autouse=True)
    def _cwd(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / "mutants").mkdir()

    def test_failed_collection_run_raises_domain_error(self) -> None:
        runner = MagicMock()
        runner.run_coverage_collection.return_value = 1
        with pytest.raises(CoverageCollectionError, match="exit code 1"):
            gather_coverage(runner, ["src/foo.py"])

    def test_missing_data_file_raises_domain_error(self) -> None:
        runner = MagicMock()
        runner.run_coverage_collection.return_value = 0  # but writes nothing
        with pytest.raises(CoverageCollectionError, match="no data file"):
            gather_coverage(runner, ["src/foo.py"])


# ---------------------------------------------------------------------------
# QX-006 — MutationParseError producer: mutant-diff readers
# ---------------------------------------------------------------------------


class TestMutationParseErrorProducer:
    @pytest.fixture(autouse=True)
    def _cwd(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / "mutants" / "src").mkdir(parents=True)
        (tmp_path / "src").mkdir()

    def test_unparseable_original_raises_mutation_parse_error(self, tmp_path: Path) -> None:
        bad = tmp_path / "src" / "broken.py"
        bad.write_text("def broken(:\n", encoding="utf-8")
        with pytest.raises(MutationParseError, match=r"broken\.py"):
            read_orig_module("src/broken.py")

    def test_unparseable_staged_file_raises_mutation_parse_error(self, tmp_path: Path) -> None:
        bad = tmp_path / "mutants" / "src" / "broken.py"
        bad.write_text("class :\n", encoding="utf-8")
        with pytest.raises(MutationParseError, match=r"broken\.py"):
            read_mutants_module("src/broken.py")

    def test_missing_file_keeps_raising_file_not_found(self) -> None:
        with pytest.raises(FileNotFoundError):
            read_orig_module("src/nope.py")


# ---------------------------------------------------------------------------
# QX-006 — the cli catches MutmutWinError, not Exception
# ---------------------------------------------------------------------------


def _invoke_run_with_orchestrator_error(error: Exception) -> Any:
    runner = CliRunner()
    mock_orchestrator = MagicMock()
    mock_orchestrator.run.side_effect = error
    mock_config = MagicMock(max_children=2, debug=False)
    with (
        patch("mutmut_win.cli.load_config", return_value=mock_config),
        patch("mutmut_win.cli.MutationOrchestrator", return_value=mock_orchestrator),
        patch("mutmut_win.cli.PytestRunner"),
        patch("mutmut_win.cli.SpawnPoolExecutor"),
    ):
        return runner.invoke(cli, ["run"])


class TestCliCatchNarrowing:
    def test_domain_error_renders_one_liner_and_exit_1(self) -> None:
        result = _invoke_run_with_orchestrator_error(CleanTestFailedError("suite is red"))
        assert result.exit_code == 1
        assert "Error: suite is red" in result.output

    def test_foreign_exception_propagates_as_a_real_bug(self) -> None:
        """A RuntimeError is OUR bug — it must not be dressed up as a clean
        domain error one-liner."""
        result = _invoke_run_with_orchestrator_error(RuntimeError("internal bug"))
        assert result.exit_code != 0
        assert isinstance(result.exception, RuntimeError)
        assert "Error: internal bug" not in result.output

    def test_show_renders_mutation_parse_error_cleanly(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / "mutants").mkdir()
        runner = CliRunner()
        with (
            patch("mutmut_win.cli.load_config", return_value=MagicMock()),
            patch(
                "mutmut_win.cli.get_diff_for_mutant",
                side_effect=MutationParseError("cannot parse staged file x.py"),
            ),
        ):
            result = runner.invoke(cli, ["show", "src.x.x_f__mutmut_1"])
        assert result.exit_code == 1
        assert "cannot parse staged file" in result.output
