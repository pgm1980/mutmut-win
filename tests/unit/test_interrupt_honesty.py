"""Tests for Ctrl-C honesty in the model and the CLI (Issue #94, audit A3-OS-005).

An interrupted run used to end exactly like a complete one: full denominator
(deflated score), no marker anywhere, process exit 0 — CI could not tell an
aborted run from a finished one, and a --min-score gate judged a partial,
misleading score.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from mutmut_win.cli import cli
from mutmut_win.models import MutationRunResult


class TestUncheckedDenominator:
    def test_score_is_computed_over_checked_mutants_only(self) -> None:
        summary = MutationRunResult(
            total_mutants=10, killed=3, survived=1, unchecked=6, was_interrupted=True
        )
        assert summary.score == pytest.approx(75.0)  # 3 of 4 checked

    def test_sum_invariant_includes_unchecked(self) -> None:
        summary = MutationRunResult(
            total_mutants=10, killed=3, survived=1, unchecked=6, was_interrupted=True
        )
        buckets = (
            summary.killed
            + summary.survived
            + summary.timeout
            + summary.suspicious
            + summary.skipped
            + summary.no_tests
            + summary.segfault
            + summary.type_check_caught
        )
        assert buckets + summary.unchecked == summary.total_mutants


def _invoke_run_with(result: MutationRunResult, *args: str) -> tuple[int, str]:
    orchestrator = MagicMock()
    orchestrator.run.return_value = result
    with (
        patch("mutmut_win.cli.MutationOrchestrator", return_value=orchestrator),
        patch("mutmut_win.cli.PytestRunner"),
        patch("mutmut_win.cli.SpawnPoolExecutor"),
        patch("mutmut_win.cli.load_config", return_value=MagicMock(model_copy=MagicMock())),
    ):
        outcome = CliRunner().invoke(cli, ["run", *args])
    return outcome.exit_code, outcome.output


class TestCliInterruptHonesty:
    def test_interrupted_run_exits_130(self) -> None:
        result = MutationRunResult(total_mutants=5, killed=2, unchecked=3, was_interrupted=True)
        exit_code, output = _invoke_run_with(result)
        assert exit_code == 130
        assert "interrupted" in output.lower()

    def test_interrupted_run_skips_the_score_gate(self) -> None:
        # A partial score is misleading in BOTH directions — the gate must
        # report "skipped", not judge it.
        result = MutationRunResult(total_mutants=5, killed=2, unchecked=3, was_interrupted=True)
        exit_code, output = _invoke_run_with(result, "--min-score", "99")
        assert exit_code == 130
        assert "gate" in output.lower()
        assert "below threshold" not in output

    def test_complete_run_keeps_exit_0_and_gate_behaviour(self) -> None:
        result = MutationRunResult(total_mutants=5, killed=5)
        exit_code, output = _invoke_run_with(result, "--min-score", "99")
        assert exit_code == 0
        assert "below threshold" not in output
