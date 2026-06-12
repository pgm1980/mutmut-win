"""Issue #123 (external QA CLI-003, CFG-002, WIN-001): robustness & Windows.

CLI-003 — the apply staleness refusal (correct behavior) surfaced as a
raw 25-line RuntimeError traceback; the #114 contract routes only
``MutmutWinError`` through the clean error path. ``StaleStagingError``
joins the hierarchy with its producer.

CFG-002 — a ``do_not_mutate`` pattern matching no file was silently
ignored: a typo re-enables mutation of "excluded" files, discoverable
only by noticing unexpected mutants. Run and dry-run now warn.

WIN-001 (code-evidenced) — the worker spawned pytest without WER
suppression: a hard-crashing mutant can stall on WerFault and be
misclassified ``timeout`` instead of ``segfault`` on interactive hosts.
The worker sets SEM_NOGPFAULTERRORBOX|SEM_FAILCRITICALERRORS (children
inherit) and spawns with CREATE_NO_WINDOW, win32-gated.
"""

from __future__ import annotations

import subprocess
import sys
from queue import Queue
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest

import mutmut_win.process.worker as worker_module
from mutmut_win.config import MutmutConfig
from mutmut_win.exceptions import MutmutWinError, StaleStagingError
from mutmut_win.models import MutationTask
from mutmut_win.process.worker import worker_main

if TYPE_CHECKING:
    from pathlib import Path


# ---------------------------------------------------------------------------
# CLI-003 — StaleStagingError instead of a raw traceback
# ---------------------------------------------------------------------------


class TestStaleStagingError:
    def test_is_a_domain_error(self) -> None:
        assert issubclass(StaleStagingError, MutmutWinError)

    def test_apply_refusal_is_a_one_liner(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """End to end through the CLI: stale staging refuses cleanly —
        exit 1, the message, no Click/runpy traceback."""
        from click.testing import CliRunner

        from mutmut_win.cli import cli

        monkeypatch.chdir(tmp_path)
        (tmp_path / "mutants").mkdir(exist_ok=True)
        with (
            patch("mutmut_win.cli.load_config", return_value=MagicMock()),
            patch(
                "mutmut_win.cli.apply_mutant",
                side_effect=StaleStagingError(
                    "src/mod.py changed after its mutants were generated — "
                    "re-run 'mutmut-win run' before applying mutants."
                ),
            ),
        ):
            result = CliRunner().invoke(cli, ["apply", "src.mod.x_f__mutmut_1"])
        assert result.exit_code == 1
        assert "re-run 'mutmut-win run'" in result.output
        assert "Traceback" not in result.output


# ---------------------------------------------------------------------------
# CFG-002 — no-match exclusion patterns warn
# ---------------------------------------------------------------------------


class TestUnmatchedExclusionWarning:
    def _project(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "calc.py").write_text(
            "def add(a, b):\n    return a + b\n", encoding="utf-8"
        )

    def test_config_reports_unmatched_patterns(self) -> None:
        cfg = MutmutConfig(
            paths_to_mutate=["src"], do_not_mutate=["**/nothing_matches.py", "src/calc.py"]
        )
        unmatched = cfg.unmatched_exclusion_patterns(["src/calc.py"])
        assert unmatched == ["**/nothing_matches.py"]

    def test_dry_run_warns_on_typo_pattern(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from mutmut_win.orchestrator import MutationOrchestrator

        self._project(tmp_path, monkeypatch)
        cfg = MutmutConfig(paths_to_mutate=["src"], do_not_mutate=["**/nothing_matches.py"])
        MutationOrchestrator(cfg, runner=MagicMock(), executor=MagicMock()).dry_run()
        out = capsys.readouterr().out
        assert "do_not_mutate pattern '**/nothing_matches.py' matched no files" in out

    def test_dry_run_stays_silent_for_matching_pattern(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from mutmut_win.orchestrator import MutationOrchestrator

        self._project(tmp_path, monkeypatch)
        cfg = MutmutConfig(paths_to_mutate=["src"], do_not_mutate=["src/calc.py"])
        result = MutationOrchestrator(cfg, runner=MagicMock(), executor=MagicMock()).dry_run()
        out = capsys.readouterr().out
        assert "matched no files" not in out
        assert result.total_mutants == 0  # control: the pattern really excluded


# ---------------------------------------------------------------------------
# WIN-001 — WER suppression in the worker
# ---------------------------------------------------------------------------


class _SimpleQueue:
    def __init__(self) -> None:
        self._q: Queue[Any] = Queue()

    def put(self, item: Any) -> None:
        self._q.put(item)

    def get(self) -> Any:
        return self._q.get()

    def empty(self) -> bool:
        return self._q.empty()


def _worker_config() -> dict[str, Any]:
    return {
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


@pytest.fixture(autouse=True)
def _no_real_task_jobs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(worker_module, "_create_task_job", lambda _pid: None)


@pytest.fixture(autouse=True)
def _isolated_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "mutants").mkdir(exist_ok=True)


class TestWerSuppression:
    def _run_one_task(self) -> tuple[MagicMock, dict[str, Any]]:
        captured_kwargs: dict[str, Any] = {}

        def fake_popen(cmd: list[str], **kwargs: Any) -> MagicMock:  # noqa: ARG001
            captured_kwargs.update(kwargs)
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
        with (
            patch("mutmut_win.process.worker.subprocess.Popen", side_effect=fake_popen),
            patch.object(worker_module, "_suppress_windows_error_dialogs") as suppress,
        ):
            worker_main(task_q, event_q, _worker_config())  # type: ignore[arg-type]
        return suppress, captured_kwargs

    def test_worker_suppresses_wer_once_per_process(self) -> None:
        suppress, _kwargs = self._run_one_task()
        suppress.assert_called_once()

    def test_spawn_uses_no_window_creationflags(self) -> None:
        _suppress, kwargs = self._run_one_task()
        expected = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        assert kwargs.get("creationflags", 0) == expected

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX no-op path")
    def test_suppressor_is_a_posix_noop(self) -> None:
        worker_module._suppress_windows_error_dialogs()  # must not raise

    @pytest.mark.skipif(sys.platform != "win32", reason="win32 error-mode bits")
    def test_suppressor_sets_the_error_mode_bits(self) -> None:
        import ctypes

        worker_module._suppress_windows_error_dialogs()
        mode = ctypes.windll.kernel32.GetErrorMode()
        assert mode & 0x0001  # SEM_FAILCRITICALERRORS
        assert mode & 0x0002  # SEM_NOGPFAULTERRORBOX
