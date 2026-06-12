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
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from mutmut_win import _state
from mutmut_win._state import _reset_globals
from mutmut_win.config import MutmutConfig
from mutmut_win.constants import MUTANT_ENV_VAR
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

    @pytest.mark.parametrize("value", [-1, 1, 8])
    def test_sentinel_and_positive_depths_are_valid(self, value: int) -> None:
        assert MutmutConfig(max_stack_depth=value).max_stack_depth == value


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
        # Mocked stats leave every task unassigned — since #130/B3 their
        # budget is the full-suite fallback (60s). A 40s window covers
        # >= 50% of that smallest budget -> hint, exactly once
        # (multiple mutants, max_children=4 — per-worker would print 4x).
        self._run(tmp_path, window_seconds=40.0)
        out = capsys.readouterr().out
        assert out.count("IL window covers") == 1

    def test_no_hint_for_a_small_window(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.chdir(tmp_path)
        self._run(tmp_path, window_seconds=0.5)
        out = capsys.readouterr().out
        assert "IL window covers" not in out
