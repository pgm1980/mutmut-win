"""Tests for the runtime hygiene batch (Issue #110).

Four small traps from the audit/dogfooding remainder:

* QX-018: ``max_stack_depth`` accepted 0 and values below -1.  0 silently
  discarded EVERY stats hit (``remaining=0`` never enters the frame walk),
  so every mutant ran the full suite — the third runtime trap next to
  #105/#106.  Values below -1 walked with a truthy-negative counter.
* QX-017: ``_reset_globals`` did not cover ``_cached_max_stack_depth`` —
  tests reset it by hand, and a stale cache survived collection cycles.
  The cache moved into ``_state`` (it IS trampoline state).
* QX-019: ``MUTANT_UNDER_TEST`` was defined as a module constant in both
  runner.py and worker.py — one drifting rename away from a silent
  mismatch. One source now: ``constants.MUTANT_ENV_VAR`` (the literal in
  the trampoline TEMPLATE stays: the generated artifact must be
  standalone; a consistency pin guards it instead).
* DOG-002: the window-vs-timeout hint (A2-JT-018) fired once per WORKER
  process — N-fold spam on N workers.  It is orchestrator-side now, once
  per run, compared against the SMALLEST task budget (the most at-risk
  task: if it doesn't fire for that one, it fires for none).
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from mutmut_win import _state
from mutmut_win._state import _reset_globals
from mutmut_win.config import MutmutConfig, load_config
from mutmut_win.constants import MUTANT_ENV_VAR
from mutmut_win.exceptions import InvalidConfigValueError
from mutmut_win.models import MutationTask, TaskCompleted, TaskStarted
from mutmut_win.orchestrator import MutationOrchestrator
from mutmut_win.stats import MutmutStats, save_stats

if TYPE_CHECKING:
    from pathlib import Path


class TestMaxStackDepthValidation:
    def test_zero_is_rejected_loudly(self) -> None:
        # QX-018: 0 means "discard every hit" — never what anyone wants.
        with pytest.raises(ValidationError, match="max_stack_depth"):
            MutmutConfig(max_stack_depth=0)

    def test_below_minus_one_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            MutmutConfig(max_stack_depth=-2)

    @pytest.mark.parametrize("value", [1, 2, 3])
    def test_instrumentation_depths_are_rejected(self, value: int) -> None:
        # M-072 / BC-083: the walk starts at the recorder itself — the
        # recorder, _mutmut_trampoline and the generated wrapper occupy
        # the first three frames and never match a pytest/unittest
        # filename, so 1..3 unconditionally discard EVERY stats hit
        # (behaviourally equal to the rejected 0). Before the fix these
        # were silently accepted.
        with pytest.raises(ValidationError, match="max_stack_depth"):
            MutmutConfig(max_stack_depth=value)

    def test_rejection_message_does_not_suggest_a_positive_depth(self) -> None:
        # 'a positive depth' was the misleading old recommendation — 1..3
        # ARE positive and dead. The message must name the frames instead.
        with pytest.raises(ValidationError, match="instrumentation frames"):
            MutmutConfig(max_stack_depth=2)

    @pytest.mark.parametrize("value", [-1, 4, 5, 8])
    def test_sentinel_and_live_depths_are_valid(self, value: int) -> None:
        assert MutmutConfig(max_stack_depth=value).max_stack_depth == value

    @given(value=st.integers(min_value=-1, max_value=64))
    def test_valid_exactly_when_unlimited_or_at_least_five(self, value: int) -> None:
        # Property: valid iff value == -1 or value >= 4. (4 stays valid in
        # the model: it is only dead for direct test-file call sites — the
        # run_stats hint covers that remainder.)
        try:
            config = MutmutConfig(max_stack_depth=value)
        except ValidationError:
            assert 0 <= value <= 3
        else:
            assert config.max_stack_depth == value
            assert value == -1 or value >= 4


class TestMaxStackDepthRejectionChannels:
    """M-072: 0..3 fail loudly on both configuration channels."""

    def test_pyproject_value_two_is_invalid_config_value(self, tmp_path: Path) -> None:
        (tmp_path / "src").mkdir()
        (tmp_path / "pyproject.toml").write_text(
            '[tool.mutmut]\npaths_to_mutate = ["src/"]\nmax_stack_depth = 2\n',
            encoding="utf-8",
        )

        with pytest.raises(InvalidConfigValueError, match="max_stack_depth"):
            load_config(tmp_path)

    def test_cli_run_exits_2_without_traceback(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from click.testing import CliRunner

        from mutmut_win.cli import cli

        monkeypatch.chdir(tmp_path)
        (tmp_path / "src").mkdir()
        (tmp_path / "mutants").mkdir()
        (tmp_path / "pyproject.toml").write_text(
            '[tool.mutmut]\npaths_to_mutate = ["src/"]\nmax_stack_depth = 1\n',
            encoding="utf-8",
        )

        result = CliRunner().invoke(cli, ["run", "--dry-run"])

        assert result.exit_code == 2
        combined = result.output + str(result.stderr)
        assert "Invalid [tool.mutmut] configuration" in combined
        assert "max_stack_depth" in combined
        assert "Traceback" not in combined


class TestRunStatsEmptyMappingHint:
    """M-072: run_stats names the cause when a LOADED but empty mapping
    meets a bounded max_stack_depth (value 4 is dead for direct test-file
    call sites — the validator cannot catch that remainder).
    """

    def _run_stats_output(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        max_stack_depth: int,
    ) -> str:
        from mutmut_win.runner import PytestRunner

        monkeypatch.chdir(tmp_path)
        (tmp_path / "mutants").mkdir()
        (tmp_path / "tests").mkdir()
        empty_mapping = MutmutStats(
            tests_by_mangled_function_name={},
            duration_by_test={"tests/test_x.py::test_one": 0.5},
            stats_time=1.0,
        )
        runner = PytestRunner(MutmutConfig(max_stack_depth=max_stack_depth))
        with (
            patch.object(runner, "_run_phase", return_value=0),
            patch.object(runner, "_write_stats_plugin"),
            patch("mutmut_win.stats.load_stats", return_value=empty_mapping),
        ):
            runner.run_stats()
        return capsys.readouterr().out

    def test_hint_names_the_cause_when_mapping_is_empty(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        out = self._run_stats_output(tmp_path, monkeypatch, capsys, max_stack_depth=4)

        assert "Collected 0 test-to-mutant mappings" in out
        assert "max_stack_depth=4" in out
        assert "instrumentation frames" in out

    def test_no_hint_when_depth_is_unlimited(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        out = self._run_stats_output(tmp_path, monkeypatch, capsys, max_stack_depth=-1)

        assert "Collected 0 test-to-mutant mappings" in out
        assert "instrumentation frames" not in out


class TestResetGlobalsCoversTheDepthCache:
    def test_reset_clears_the_cached_depth(self) -> None:
        # QX-017: the cache lives in _state now and resets with the rest.
        _state._cached_max_stack_depth = 7
        _reset_globals()
        assert _state._cached_max_stack_depth is None

    def test_get_max_stack_depth_uses_the_state_cache(self) -> None:
        import mutmut_win.__main__ as _main

        _reset_globals()
        _state._cached_max_stack_depth = 5
        assert _main._get_max_stack_depth() == 5
        _reset_globals()


class TestMutantEnvVarSingleSource:
    def test_runner_and_worker_share_the_constants_value(self) -> None:
        # QX-019: one source of truth; the re-exports stay for BWC.
        from mutmut_win import runner
        from mutmut_win.process import worker

        assert runner.MUTANT_ENV_VAR is MUTANT_ENV_VAR
        assert worker.MUTANT_ENV_VAR is MUTANT_ENV_VAR

    def test_trampoline_template_literal_matches_the_constant(self) -> None:
        # The generated artifact must stay standalone (no mutmut_win import
        # for the env read) — the literal is allowed, but it must never
        # drift from the constant.
        from mutmut_win.trampoline import trampoline_impl

        assert f"os.environ.get('{MUTANT_ENV_VAR}')" in trampoline_impl


class TestWindowHintOncePerRun:
    """DOG-002: the hint is emitted by the orchestrator, once per run."""

    def _run(
        self,
        tmp_path: Path,
        *,
        window_seconds: float,
        timeout_multiplier: float = 2.0,
    ) -> str:
        src = tmp_path / "src"
        src.mkdir()
        (src / "target.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")

        mutants_dir = tmp_path / "mutants"
        mutants_dir.mkdir(exist_ok=True)
        save_stats(
            MutmutStats(
                tests_by_mangled_function_name={},
                duration_by_test={"tests/test_x.py::test_one": 0.5},
                stats_time=1.0,
            ),
            mutants_dir,
        )

        captured_tasks: list[MutationTask] = []
        executor = MagicMock()
        executor.start.side_effect = captured_tasks.extend

        def fake_get_events() -> Any:
            pid = os.getpid()
            for task in captured_tasks:
                yield TaskStarted(mutant_name=task.mutant_name, worker_pid=pid)
                yield TaskCompleted(
                    mutant_name=task.mutant_name, worker_pid=pid, exit_code=1, duration=0.01
                )

        executor.get_events.side_effect = fake_get_events

        runner = MagicMock()
        runner.run_clean_test.return_value = 0
        runner.run_forced_fail.return_value = 1
        runner.collect_tests.return_value = ["tests/test_x.py::test_one"]

        orch = MutationOrchestrator(
            MutmutConfig(
                max_children=4,
                timeout_multiplier=timeout_multiplier,
                paths_to_mutate=["src"],
                infinite_loop_detection=True,
                infinite_loop_window_seconds=window_seconds,
            ),
            runner=runner,
            executor=executor,
            db_path=tmp_path / "db",
        )
        orch.run()
        return ""

    def test_hint_appears_exactly_once_for_a_large_window(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.chdir(tmp_path)
        # Mocked stats leave every task unassigned — since #130/B3 their budget
        # is the full-suite fallback (60s). IL-001: a 40s window down-scales to
        # 60/2 = 30s, and the notice fires exactly once (multiple mutants,
        # max_children=4 — per-worker would print 4x).
        self._run(tmp_path, window_seconds=40.0)
        out = capsys.readouterr().out
        assert out.count("auto-scaled the infinite-loop window") == 1
        assert "to 30.0s" in out

    def test_no_hint_when_window_fits_the_budget(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.chdir(tmp_path)
        # A 20s window already fits within 60/2 = 30s, so there is no
        # down-scaling and no notice (IL-001).
        self._run(tmp_path, window_seconds=20.0)
        out = capsys.readouterr().out
        assert "auto-scaled the infinite-loop window" not in out
