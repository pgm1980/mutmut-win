"""Contracts for the MBR-2026-09-14-01 side fixes A and C.

Fix A: ``--force`` cleanup retries transient antivirus/indexer locks before
refusing, and still refuses after exhausting the retries.

Fix C: run-startup observability — the prelude announces its phases and a
stall watchdog dumps the Python stack when no progress is observable.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from mutmut_win import cli
from mutmut_win.cli import cli as cli_entry
from mutmut_win.config import MutmutConfig
from mutmut_win.models import MutationRunResult
from mutmut_win.orchestrator import MutationOrchestrator
from mutmut_win.stall_watchdog import StallWatchdog
from mutmut_win.stats import RunBasisEvidence


def _write_source(tmp_path: Path) -> None:
    source = tmp_path / "src" / "mod.py"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("def value():\n    return 1\n", encoding="utf-8")


def _invoke_force_run() -> object:
    orchestrator = MagicMock()
    orchestrator.run.return_value = MutationRunResult(total_mutants=1, killed=1)
    with (
        patch("mutmut_win.cli.load_config", return_value=MutmutConfig(paths_to_mutate=[])),
        patch("mutmut_win.cli.MutationOrchestrator", return_value=orchestrator),
        patch("mutmut_win.cli.PytestRunner"),
        patch("mutmut_win.cli.SpawnPoolExecutor"),
    ):
        return CliRunner().invoke(cli_entry, ["run", "--force"])


class TestForceCleanupRetry:
    def test_transient_lock_is_absorbed_by_retry(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        _write_source(tmp_path)
        (tmp_path / "mutants").mkdir()
        monkeypatch.setattr(cli, "_FORCE_CLEANUP_RETRY_DELAYS", (0.0, 0.0))

        real_rmtree = shutil.rmtree
        calls: list[Path] = []

        def transient_rmtree(path: Path, **_kwargs: object) -> None:
            calls.append(Path(path))
            # The first two attempts lose the race against the filter driver;
            # the third one observes the released directory.
            if len([c for c in calls if c == Path(path)]) > 2:
                real_rmtree(path)

        with patch("shutil.rmtree", side_effect=transient_rmtree):
            result = _invoke_force_run()

        assert result.exit_code == 0, result.output
        assert "Removed mutants/" in result.output
        assert len(calls) == 3
        assert not (tmp_path / "mutants").exists()

    def test_persistent_lock_still_refuses(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        _write_source(tmp_path)
        (tmp_path / "mutants").mkdir()
        monkeypatch.setattr(cli, "_FORCE_CLEANUP_RETRY_DELAYS", (0.0, 0.0))

        with patch("shutil.rmtree", return_value=None):
            result = _invoke_force_run()

        expected_message = (
            "Could not fully remove mutants/ (files in use?); refusing to run with stale state."
        )
        assert result.exit_code == 1
        assert expected_message in result.output
        assert (tmp_path / "mutants").exists()


class TestStallWatchdog:
    def _mocked_faulthandler(self, monkeypatch: pytest.MonkeyPatch) -> MagicMock:
        fake = MagicMock()
        monkeypatch.setattr("mutmut_win.stall_watchdog.faulthandler", fake)
        return fake

    def test_arm_starts_repeating_timer(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake = self._mocked_faulthandler(monkeypatch)
        watchdog = StallWatchdog(timeout=12.5)
        assert watchdog.armed is False
        watchdog.arm()
        assert watchdog.armed is True
        fake.dump_traceback_later.assert_called_once()
        args, kwargs = fake.dump_traceback_later.call_args
        assert args[0] == 12.5
        assert kwargs["repeat"] is True

    def test_progress_rearms_only_while_armed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake = self._mocked_faulthandler(monkeypatch)
        watchdog = StallWatchdog()
        watchdog.progress()  # disarmed: no timer interaction
        fake.dump_traceback_later.assert_not_called()
        fake.cancel_dump_traceback_later.assert_not_called()

        watchdog.arm()
        fake.reset_mock()
        watchdog.progress()
        fake.cancel_dump_traceback_later.assert_called_once()
        assert fake.dump_traceback_later.call_count == 1

    def test_close_disarms_and_is_repeatable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake = self._mocked_faulthandler(monkeypatch)
        watchdog = StallWatchdog()
        watchdog.arm()
        watchdog.close()
        watchdog.close()
        assert watchdog.armed is False
        fake.cancel_dump_traceback_later.assert_called_once()

    def test_context_manager_closes_on_exception(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake = self._mocked_faulthandler(monkeypatch)
        with pytest.raises(RuntimeError), StallWatchdog():
            raise RuntimeError("boom")
        fake.cancel_dump_traceback_later.assert_called_once()


class TestPreludeObservability:
    def _patched_orchestrator(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> MutationOrchestrator:
        monkeypatch.chdir(tmp_path)
        (tmp_path / "mutants").mkdir()
        config = MutmutConfig(paths_to_mutate=["src/mod.py"])
        _write_source(tmp_path)
        orchestrator = MutationOrchestrator(config)

        evidence = RunBasisEvidence(
            digest="a" * 64,
            complete=True,
            core_digest="b" * 64,
            core_complete=True,
        )
        monkeypatch.setattr(orchestrator, "_stable_run_basis_evidence", lambda: evidence)
        monkeypatch.setattr(orchestrator, "_recover_abandoned_run", lambda: None)

        def fake_pipeline() -> MutationRunResult:
            # Persist the run plan exactly like the real pipeline does, so
            # the post-run finalization in _run_with_identity accepts the
            # terminal status.
            orchestrator._start_current_run([])
            return MutationRunResult(total_mutants=1, killed=1)

        monkeypatch.setattr(orchestrator, "_run_pipeline", fake_pipeline)
        return orchestrator

    def test_prelude_announces_basis_fingerprint(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.Capsys,
    ) -> None:
        orchestrator = self._patched_orchestrator(tmp_path, monkeypatch)
        result = orchestrator._run_with_identity()

        assert result.total_mutants == 1
        captured = capsys.readouterr()
        assert "Fingerprinting execution basis (sources, tests, dependencies)…" in captured.out
        assert "Execution basis fingerprinted in" in captured.out

    def test_debug_adds_step_traces_to_stderr(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.Capsys,
    ) -> None:
        orchestrator = self._patched_orchestrator(tmp_path, monkeypatch)
        monkeypatch.setattr(
            orchestrator._config,
            "debug",
            True,
            raising=False,
        )
        orchestrator._run_with_identity()

        captured = capsys.readouterr()
        assert "[debug] validating staging root…" in captured.err
        assert "[debug] persisting run attempt…" in captured.err

    def test_watchdog_is_disarmed_after_prelude(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        orchestrator = self._patched_orchestrator(tmp_path, monkeypatch)
        fake = MagicMock()
        monkeypatch.setattr("mutmut_win.stall_watchdog.StallWatchdog", fake)
        watchdog_instance = fake.return_value
        watchdog_instance.armed = True

        orchestrator._run_with_identity()

        watchdog_instance.arm.assert_called_once()
        watchdog_instance.close.assert_called_once()
