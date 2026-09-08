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

pytestmark = pytest.mark.usefixtures("isolated_cli_workspace")


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


class TestExecutionBasisScoreAuthority:
    @pytest.mark.parametrize("minimum", ["0", "99"])
    def test_incomplete_basis_fails_every_score_gate_closed(self, minimum: str) -> None:
        result = MutationRunResult(total_mutants=5, killed=5)

        exit_code, output = _invoke_run_with(result, "--min-score", minimum)

        assert exit_code == 1
        assert "execution basis incomplete" in output.lower()
        assert "below threshold" not in output.lower()

    def test_incomplete_basis_is_serialized_before_json_gate_failure(self) -> None:
        import json

        result = MutationRunResult(total_mutants=5, killed=5)

        exit_code, output = _invoke_run_with(
            result,
            "--min-score",
            "99",
            "--output",
            "json",
        )

        payload = json.loads(output[output.index("{") : output.rindex("}") + 1])
        assert exit_code == 1
        assert payload["execution_basis_complete"] is False

    def test_complete_run_keeps_exit_0_and_gate_behaviour(self) -> None:
        result = MutationRunResult(
            total_mutants=5,
            killed=5,
            execution_basis_complete=True,
        )
        exit_code, output = _invoke_run_with(result, "--min-score", "99")
        assert exit_code == 0
        assert "below threshold" not in output


class TestCiJsonChannel:
    """Issue #97 / A3-OS-014: --output json dumped the model WITHOUT the
    score — the CI channel was blind on the one number it gates on."""

    def test_json_output_carries_the_score(self) -> None:
        import json

        result = MutationRunResult(total_mutants=4, killed=2, segfault=1)
        exit_code, output = _invoke_run_with(result, "--output", "json")
        assert exit_code == 0
        payload = json.loads(output[output.index("{") : output.rindex("}") + 1])
        assert payload["score"] == pytest.approx(75.0)
        # The v2.9.0 fields ride along additively.
        assert payload["segfault"] == 1
        assert payload["was_interrupted"] is False
        assert payload["unchecked"] == 0

    def test_model_dump_serializes_score_directly(self) -> None:
        result = MutationRunResult(total_mutants=2, killed=1, survived=1)
        assert result.model_dump()["score"] == pytest.approx(50.0)


class TestZeroMutantGate:
    """Issue #97 / A3-OS-026: --min-score with 0 testable mutants failed on
    'score 0.0 below threshold' — fail-closed is right, the message was not."""

    def test_zero_mutants_fails_closed_with_a_clear_message(self) -> None:
        result = MutationRunResult(total_mutants=0)
        exit_code, output = _invoke_run_with(result, "--min-score", "80")
        assert exit_code == 1
        assert "no testable mutants" in output.lower()
        assert "below threshold" not in output

    def test_all_skipped_counts_as_zero_testable(self) -> None:
        result = MutationRunResult(
            total_mutants=3,
            skipped=3,
            execution_basis_complete=True,
        )
        exit_code, output = _invoke_run_with(result, "--min-score", "80")
        assert exit_code == 1
        assert "no testable mutants" in output.lower()
