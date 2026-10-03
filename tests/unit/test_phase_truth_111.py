"""Issue #111 (audit A2-RN-006 + A2-RN-012): runner phase truth.

RN-006 — the forced-fail verification must
  (a) stop at the first failure (``-x``) instead of burning the full
      suite for a check that needs exactly one failure,
  (b) never convert a timeout into success (a hung suite proves nothing
      about the trampoline), and
  (c) attribute the failure to the trampoline's forced fail
      (``MutmutProgrammaticFailException`` in the captured output)
      instead of accepting any arbitrary broken test as proof.

RN-012 — ``PY_IGNORE_IMPORTMISMATCH=1`` was set only for the stats run;
clean / forced-fail / coverage / worker phases ran without it
(inconsistent phases). One env truth for all of them.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from queue import Queue
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

import mutmut_win.process.worker as worker_module
from mutmut_win.config import MutmutConfig
from mutmut_win.exceptions import ForcedFailError
from mutmut_win.orchestrator import MutationOrchestrator
from mutmut_win.process.worker import worker_main
from mutmut_win.runner import FORCED_FAIL_MARKER, PytestRunner
from tests.unit.phase_mock_util import frozen_worker_config, phase_popen


@pytest.fixture(autouse=True)
def _isolated_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Temp cwd with mutants/ — runner code resolves 'mutants' via cwd."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "mutants").mkdir(exist_ok=True)


def _make_completed_process(returncode: int = 0) -> MagicMock:
    proc = MagicMock()
    proc.returncode = returncode
    return proc


def _fake_popen_writing(text: str, returncode: int) -> Any:
    """Fake subprocess.Popen that writes *text* to the phase log fd."""

    def fake_popen(cmd: list[str], **kwargs: Any) -> MagicMock:  # noqa: ARG001
        fd = kwargs.get("stdout")
        if isinstance(fd, int) and fd != subprocess.DEVNULL:
            os.write(fd, text.encode("utf-8"))
        proc = MagicMock()
        proc.pid = 99999
        proc.wait.return_value = returncode
        return proc

    return fake_popen


# ---------------------------------------------------------------------------
# RN-006 — forced-fail command shape
# ---------------------------------------------------------------------------


class TestForcedFailCommand:
    def test_stops_at_first_failure(self) -> None:
        """One failure is all the proof there is — no full-suite runtime."""
        runner = PytestRunner(MutmutConfig())
        with phase_popen(1) as mock_run:
            runner.run_forced_fail("m1")
        cmd = mock_run.call_args[0][0]
        assert "-x" in cmd

    def test_requests_failure_summary_for_attribution(self) -> None:
        """-rfE + --tb=line put the exception name into the output; the
        one-line traceback is never width-truncated (the -rfE summary is)."""
        runner = PytestRunner(MutmutConfig())
        with phase_popen(1) as mock_run:
            runner.run_forced_fail("m1")
        cmd = mock_run.call_args[0][0]
        assert "-rfE" in cmd
        assert "--tb=line" in cmd
        assert "--tb=no" not in cmd

    def test_widens_the_summary_against_truncation(self) -> None:
        """pytest cuts the -rfE summary to terminal width — a long node id
        must not push the marker off the line."""
        runner = PytestRunner(MutmutConfig())
        with phase_popen(1) as mock_run:
            runner.run_forced_fail("m1")
        env = mock_run.call_args[1]["env"]
        assert int(env.get("COLUMNS", "0")) >= 200


# ---------------------------------------------------------------------------
# RN-006 — timeout is never success
# ---------------------------------------------------------------------------


class TestForcedFailTimeout:
    def test_timeout_returns_36_not_one(self) -> None:
        """The old code returned 1 ('trampoline works') on timeout — a hung
        suite proves nothing about the trampoline."""
        runner = PytestRunner(MutmutConfig(forced_fail_timeout=1))
        with phase_popen(wait_side_effect=subprocess.TimeoutExpired(cmd="pytest", timeout=1)):
            rc = runner.run_forced_fail("m1")
        assert rc == 36

    def test_timeout_yields_no_attribution_verdict(self) -> None:
        runner = PytestRunner(MutmutConfig(forced_fail_timeout=1))
        with phase_popen(wait_side_effect=subprocess.TimeoutExpired(cmd="pytest", timeout=1)):
            runner.run_forced_fail("m1")
        assert runner.last_forced_fail_attributed is None


# ---------------------------------------------------------------------------
# RN-006 — failure attribution
# ---------------------------------------------------------------------------


class TestForcedFailAttribution:
    def test_trampoline_proof_attributes_the_failure(self) -> None:
        """M-130: attribution comes from the structured trampoline proof.

        The fake Popen writes the proof token to the proof path from the
        child environment, exactly like the phase-guard plugin hook does
        for a real failed MutmutProgrammaticFailException report.
        """
        out = (
            "FAILED tests/test_a.py::test_x - "
            "mutmut_win.exceptions.MutmutProgrammaticFailException: Forced fail\n"
        )

        def fake_popen(*_args: object, **kwargs: object) -> object:
            from mutmut_win.process.worker import (
                _FORCED_FAIL_PROOF_PATH_ENV,
                _FORCED_FAIL_PROOF_TOKEN_ENV,
            )

            env = kwargs.get("env") or {}
            proof_path = env.get(_FORCED_FAIL_PROOF_PATH_ENV)
            proof_token = env.get(_FORCED_FAIL_PROOF_TOKEN_ENV)
            if proof_path and proof_token:
                Path(proof_path).write_text(proof_token, encoding="utf-8")
            return _fake_popen_writing(out, 1)(*_args, **kwargs)

        runner = PytestRunner(MutmutConfig())
        with (
            patch("subprocess.Popen", side_effect=fake_popen),
            patch("mutmut_win.process.worker._create_task_job", return_value=None),
        ):
            rc = runner.run_forced_fail("m1")
        assert rc == 1
        assert runner.last_forced_fail_attributed is True

    def test_marker_text_without_trampoline_proof_is_not_attributed(self) -> None:
        """M-130 RED case: the exception name in the output alone never
        attributes — a test merely NAMED after the exception used to pass
        the gate on a substring match."""
        out = (
            "FAILED tests/test_a.py::test_MutmutProgrammaticFailException - AssertionError: boom\n"
        )
        runner = PytestRunner(MutmutConfig())
        with (
            patch("subprocess.Popen", side_effect=_fake_popen_writing(out, 1)),
            patch("mutmut_win.process.worker._create_task_job", return_value=None),
        ):
            rc = runner.run_forced_fail("m1")
        assert rc == 1
        assert runner.last_forced_fail_attributed is False

    def test_foreign_failure_is_not_attributed(self) -> None:
        out = "FAILED tests/test_a.py::test_x - AssertionError: boom\n"
        runner = PytestRunner(MutmutConfig())
        with (
            patch("subprocess.Popen", side_effect=_fake_popen_writing(out, 1)),
            patch("mutmut_win.process.worker._create_task_job", return_value=None),
        ):
            rc = runner.run_forced_fail("m1")
        assert rc == 1
        assert runner.last_forced_fail_attributed is False

    def test_exit_zero_is_never_attributed(self) -> None:
        runner = PytestRunner(MutmutConfig())
        with phase_popen(0):
            rc = runner.run_forced_fail("m1")
        assert rc == 0
        assert runner.last_forced_fail_attributed is False

    def test_marker_constant_matches_the_trampoline_exception(self) -> None:
        """The marker must be the exception's class name — the one string the
        trampoline guarantees in any failure rendering (-rfE summary,
        conftest tracebacks, collection errors)."""
        assert FORCED_FAIL_MARKER == "MutmutProgrammaticFailException"


# ---------------------------------------------------------------------------
# RN-006 — orchestrator gate uses the verdict
# ---------------------------------------------------------------------------


def _orchestrator_with(tmp_path: Path, runner: MagicMock) -> MutationOrchestrator:
    src = tmp_path / "src"
    src.mkdir(exist_ok=True)
    (src / "target.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    executor = MagicMock()
    executor.get_events.return_value = iter([])
    cfg = MutmutConfig(paths_to_mutate=["src"], max_children=1)
    return MutationOrchestrator(cfg, runner=runner, executor=executor, db_path=tmp_path / "db")


def _gate_runner(ff_exit: int, attributed: bool | None) -> MagicMock:
    runner = MagicMock()
    runner.run_clean_test.return_value = 0
    runner.run_stats.return_value = None
    runner.collect_tests.return_value = []
    runner.run_forced_fail.return_value = ff_exit
    runner.last_forced_fail_attributed = attributed
    runner.last_diagnostic_output = "tail of pytest output"
    return runner


class TestOrchestratorForcedFailGate:
    def test_timeout_fails_the_gate(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        orch = _orchestrator_with(tmp_path, _gate_runner(ff_exit=36, attributed=None))
        with pytest.raises(ForcedFailError, match="timed out"):
            orch.run()

    def test_unattributed_failure_fails_the_gate(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        orch = _orchestrator_with(tmp_path, _gate_runner(ff_exit=1, attributed=False))
        with pytest.raises(ForcedFailError, match="MutmutProgrammaticFailException"):
            orch.run()

    def test_attributed_failure_passes_the_gate(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        orch = _orchestrator_with(tmp_path, _gate_runner(ff_exit=1, attributed=True))
        result = orch.run()
        assert result.total_mutants >= 0  # run completed, no gate error


# ---------------------------------------------------------------------------
# RN-012 — PY_IGNORE_IMPORTMISMATCH in every phase
# ---------------------------------------------------------------------------


class TestImportMismatchEnvConsistency:
    def _captured_env(self, invoke: Any) -> dict[str, str]:
        runner = PytestRunner(MutmutConfig())
        with phase_popen(0) as mock_popen:
            invoke(runner)
        env = mock_popen.call_args[1].get("env")
        return dict(env) if env is not None else {}

    def test_clean_phase_sets_it(self) -> None:
        env = self._captured_env(lambda r: r.run_clean_test())
        assert env.get("PY_IGNORE_IMPORTMISMATCH") == "1"

    def test_forced_fail_phase_sets_it(self) -> None:
        env = self._captured_env(lambda r: r.run_forced_fail("m1"))
        assert env.get("PY_IGNORE_IMPORTMISMATCH") == "1"

    def test_stats_phase_sets_it(self) -> None:
        env = self._captured_env(lambda r: r.run_stats())
        assert env.get("PY_IGNORE_IMPORTMISMATCH") == "1"

    def test_coverage_phase_sets_it(self, tmp_path: Path) -> None:
        env = self._captured_env(lambda r: r.run_coverage_collection(tmp_path / "cov.db"))
        assert env.get("PY_IGNORE_IMPORTMISMATCH") == "1"


class _SimpleQueue:
    """Thread-safe queue that quacks like multiprocessing.Queue for tests."""

    def __init__(self) -> None:
        self._q: Queue[Any] = Queue()

    def put(self, item: Any) -> None:
        self._q.put(item)

    def get(self) -> Any:
        return self._q.get()

    def empty(self) -> bool:
        return self._q.empty()


class TestWorkerImportMismatchEnv:
    def test_worker_subprocess_env_sets_it(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The worker builds its env independently of the runner — the
        phase-consistency contract covers it too."""
        monkeypatch.setattr(worker_module, "_create_task_job", lambda _pid: None)
        from mutmut_win.models import MutationTask

        captured_env: dict[str, str] = {}

        def fake_popen(cmd: list[str], **kwargs: Any) -> MagicMock:  # noqa: ARG001
            captured_env.update(kwargs.get("env") or {})
            proc = MagicMock()
            proc.pid = 12345
            proc.wait.return_value = 0
            proc.poll.return_value = 0
            return proc

        task_q = _SimpleQueue()
        event_q = _SimpleQueue()
        task_q.put(
            MutationTask(
                mutant_name="src/foo.py::bar__mutmut_1", tests=["tests/test_foo.py"]
            ).model_dump()
        )
        task_q.put(None)

        config_data: dict[str, Any] = frozen_worker_config(
            {
                "paths_to_mutate": ["src/"],
                "tests_dir": ["tests/"],
                "do_not_mutate": [],
                "also_copy": [],
                "max_children": 1,
                "timeout_multiplier": 10.0,
                "max_stack_depth": -1,
                "debug": False,
                "pytest_add_cli_args": [],
                "pytest_add_cli_args_test_selection": [],
                "mutate_only_covered_lines": False,
                "type_check_command": [],
                "infinite_loop_detection": False,
            }
        )
        with patch("mutmut_win.process.worker.subprocess.Popen", side_effect=fake_popen):
            worker_main(task_q, event_q, config_data)  # type: ignore[arg-type]

        assert captured_env.get("PY_IGNORE_IMPORTMISMATCH") == "1"


class TestForcedFailOptionOrder:
    """M-129: the proof presentation options must win over user arguments.

    ``-r``/``--tb`` are action='store' — the last one wins. A user
    ``--tb=no`` plus ``-rN`` used to override ``--tb=line``/``-rfE`` and
    fail the forced-fail gate with a wrong diagnosis (the marker was
    simply not printed).
    """

    def test_mandatory_report_options_follow_user_args(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from mutmut_win.runner import PytestRunner

        monkeypatch.chdir(tmp_path)
        (tmp_path / "mutants").mkdir(exist_ok=True)
        runner = PytestRunner(MutmutConfig(pytest_add_cli_args=["--tb=no", "-rN"]))
        captured: dict[str, list[str]] = {}

        def fake_run_phase(_name: str, cmd: list[str], *_args: object, **_kwargs: object) -> int:
            captured["cmd"] = list(cmd)
            return 1

        monkeypatch.setattr(runner, "_run_phase", fake_run_phase)
        runner.run_forced_fail("some::mutant")
        cmd = captured["cmd"]
        head = cmd[: cmd.index("--")]
        tb_options = [arg for arg in head if arg.startswith("--tb")]
        r_options = [arg for arg in head if arg.startswith("-r") and not arg.startswith("--")]
        assert tb_options[-1] == "--tb=line"
        assert r_options[-1] == "-rfE"

    def test_mandatory_report_options_follow_addopts(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from mutmut_win.runner import PytestRunner

        monkeypatch.chdir(tmp_path)
        (tmp_path / "mutants").mkdir(exist_ok=True)
        monkeypatch.setenv("PYTEST_ADDOPTS", "--tb no -r N")
        runner = PytestRunner(MutmutConfig())
        captured: dict[str, list[str]] = {}

        def fake_run_phase(_name: str, cmd: list[str], *_args: object, **_kwargs: object) -> int:
            captured["cmd"] = list(cmd)
            return 1

        monkeypatch.setattr(runner, "_run_phase", fake_run_phase)
        runner.run_forced_fail("some::mutant")
        cmd = captured["cmd"]
        head = cmd[: cmd.index("--")]
        # The pin must appear AFTER the split PYTEST_ADDOPTS form '--tb no'
        # (last-one-wins): the LAST --tb-prefixed option is the engine's.
        tb_options = [arg for arg in head if arg.startswith("--tb")]
        assert tb_options[-1] == "--tb=line"
        assert "-rfE" in head[-3:]
