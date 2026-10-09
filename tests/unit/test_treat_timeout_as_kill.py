"""Regression tests for Bug #71 — Hypothesis-driven infinite-loop mutants are
recorded as TIMEOUT instead of KILLED, deflating the reported score.

The Sprint 23 mitigation is a user-controlled switch: `--treat-timeout-as-kill`
on the `run` and `results` commands, plus a `MutationRunResult.compute_score`
method that takes the flag. Default behaviour is unchanged (timeouts stay in
their own bucket); the switch lets projects with known infinite-loop signals
report the adjusted score without changing the underlying result store.

M-025 (issue #160): the flag changes the `--min-score` gate but not the
reported score. The contract is now explicit — the JSON ``score`` field and
the text summary always stay RAW; with the flag set, one named stderr line
reports the effective (timeouts-as-kills) score next to the raw score, and
the gate judges exactly that effective value.

See critique-model-service ``_misc/mutmut-win-bugs.md`` Bug #5 (this repo's
issue #71) for the original observation — 76 timeout mutants in one sprint
where every single one corresponds to a Hypothesis test triggering an
infinite loop.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from mutmut_win.cli import _timeout_as_kill_score_line, cli
from mutmut_win.models import MutationRunResult

pytestmark = pytest.mark.usefixtures("isolated_cli_workspace")

_SCORE_LINE_MARKER = "timeouts counted as kills"


def _invoke_run_with(result: MutationRunResult, *args: str) -> tuple[int, str, str]:
    """Invoke ``run`` with runner/executor/orchestrator mocked out."""
    orchestrator = MagicMock()
    orchestrator.run.return_value = result
    with (
        patch("mutmut_win.cli.MutationOrchestrator", return_value=orchestrator),
        patch("mutmut_win.cli.PytestRunner"),
        patch("mutmut_win.cli.SpawnPoolExecutor"),
        patch("mutmut_win.cli.load_config", return_value=MagicMock(model_copy=MagicMock())),
    ):
        outcome = CliRunner().invoke(cli, ["run", *args])
    return outcome.exit_code, outcome.stderr, outcome.stdout


def test_compute_score_default_excludes_timeouts() -> None:
    """``compute_score()`` (no flag) must match the existing ``score`` property."""
    result = MutationRunResult(
        total_mutants=10,
        killed=5,
        survived=2,
        timeout=3,
    )

    # killed / (total - skipped - no_tests) = 5 / 10 = 50 %
    assert result.compute_score() == 50.0
    assert result.score == 50.0


def test_compute_score_with_treat_timeout_as_kill() -> None:
    """With the flag, timeouts count toward kills."""
    result = MutationRunResult(
        total_mutants=10,
        killed=5,
        survived=2,
        timeout=3,
    )

    # (killed + timeout) / (total - skipped - no_tests) = 8 / 10 = 80 %
    assert result.compute_score(treat_timeout_as_kill=True) == 80.0


def test_compute_score_ignores_skipped_and_no_tests_in_denominator() -> None:
    """Skipped + no_tests must drop out of the denominator (regression of
    existing ``score`` behaviour)."""
    result = MutationRunResult(
        total_mutants=20,
        killed=5,
        timeout=3,
        skipped=5,
        no_tests=2,
    )
    # denominator = 20 - 5 - 2 = 13
    # default: 5 / 13 ≈ 38.46 %
    # with flag: 8 / 13 ≈ 61.54 %
    assert result.compute_score() == 5 / 13 * 100.0
    assert result.compute_score(treat_timeout_as_kill=True) == 8 / 13 * 100.0


def test_compute_score_zero_denominator_returns_zero() -> None:
    """Edge: empty run / everything skipped → 0 %, not ZeroDivisionError."""
    result = MutationRunResult(
        total_mutants=5,
        skipped=3,
        no_tests=2,
    )
    assert result.compute_score() == 0.0
    assert result.compute_score(treat_timeout_as_kill=True) == 0.0


def test_compute_score_all_timeouts_with_flag_gives_full_score() -> None:
    """All-timeout run with the flag → 100 % (matches the downstream-documented
    'every timeout is a kill in disguise' scenario from Hypothesis-heavy suites)."""
    result = MutationRunResult(
        total_mutants=10,
        timeout=10,
    )
    assert result.compute_score() == 0.0
    assert result.compute_score(treat_timeout_as_kill=True) == 100.0


# ---------------------------------------------------------------------------
# M-025 — the flag gates on the effective score, the reported score stays raw
# ---------------------------------------------------------------------------


class TestTimeoutAsKillScoreReporting:
    @pytest.mark.parametrize("killed", [1, 2])
    def test_s3_minimum_score_uses_actual_cli_exit(self, killed: int) -> None:
        """A complete ordinary campaign must enforce the configured threshold."""
        result = MutationRunResult(
            total_mutants=2,
            killed=killed,
            survived=2 - killed,
            execution_basis_complete=True,
        )
        exit_code, stderr, stdout = _invoke_run_with(
            result, "--output", "json", "--min-score", "80"
        )

        assert json.loads(stdout)["score"] == killed * 50.0
        assert exit_code == (1 if killed == 1 else 0), stderr
        assert ("is below threshold 80.0%" in stderr) is (killed == 1)
        assert _SCORE_LINE_MARKER not in stderr

    @pytest.mark.parametrize("opt_in", [False, True])
    def test_s3_timeout_policy_changes_gate_but_never_raw_score(self, opt_in: bool) -> None:
        """The same unresolved timeout fails by default and passes only by opt-in."""
        result = MutationRunResult(
            total_mutants=2,
            killed=1,
            timeout=1,
            execution_basis_complete=True,
        )
        args = ["--output", "json", "--min-score", "80"]
        if opt_in:
            args.append("--treat-timeout-as-kill")

        exit_code, stderr, stdout = _invoke_run_with(result, *args)

        assert exit_code == (0 if opt_in else 1), stderr
        assert json.loads(stdout)["score"] == 50.0
        assert (_SCORE_LINE_MARKER in stderr) is opt_in

    def test_score_line_names_effective_and_raw_score(self) -> None:
        result = MutationRunResult(total_mutants=10, killed=5, timeout=5)

        line = _timeout_as_kill_score_line(result)

        assert _SCORE_LINE_MARKER in line
        assert "100.0%" in line
        assert "50.0%" in line
        assert line.startswith("Score with")

    def test_run_reports_gate_score_when_gate_passes(self) -> None:
        result = MutationRunResult(
            total_mutants=10,
            killed=5,
            timeout=5,
            execution_basis_complete=True,
        )

        exit_code, stderr, _stdout = _invoke_run_with(
            result, "--treat-timeout-as-kill", "--min-score", "100"
        )

        # The effective score (kills + timeouts) passes the gate ...
        assert exit_code == 0, stderr
        # ... and is reported even though the gate passed.
        assert _SCORE_LINE_MARKER in stderr
        assert "100.0%" in stderr
        assert "50.0%" in stderr

    def test_json_score_stays_raw_while_stderr_carries_the_line(self) -> None:
        result = MutationRunResult(total_mutants=10, killed=5, timeout=5)

        exit_code, stderr, stdout = _invoke_run_with(
            result, "--output", "json", "--treat-timeout-as-kill"
        )

        assert exit_code == 0, stderr
        payload = json.loads(stdout)
        assert payload["score"] == 50.0
        assert _SCORE_LINE_MARKER in stderr
        assert "100.0%" in stderr

    def test_dry_run_never_prints_the_score_line(self) -> None:
        orchestrator = MagicMock()
        orchestrator.dry_run.return_value = MutationRunResult(total_mutants=3)
        with (
            patch("mutmut_win.cli.MutationOrchestrator", return_value=orchestrator),
            patch("mutmut_win.cli.PytestRunner"),
            patch("mutmut_win.cli.SpawnPoolExecutor"),
            patch("mutmut_win.cli.load_config", return_value=MagicMock(model_copy=MagicMock())),
        ):
            outcome = CliRunner().invoke(cli, ["run", "--dry-run", "--treat-timeout-as-kill"])

        assert outcome.exit_code == 0, outcome.stderr
        assert _SCORE_LINE_MARKER not in outcome.stderr

    def test_aborted_run_never_prints_the_score_line(self) -> None:
        result = MutationRunResult(total_mutants=5, killed=2, run_aborted=True)

        exit_code, stderr, _stdout = _invoke_run_with(result, "--treat-timeout-as-kill")

        assert exit_code == 1
        assert _SCORE_LINE_MARKER not in stderr

    def test_no_testable_mutants_never_prints_the_score_line(self) -> None:
        result = MutationRunResult(total_mutants=4, skipped=4, execution_basis_complete=True)

        exit_code, stderr, _stdout = _invoke_run_with(result, "--treat-timeout-as-kill")

        assert exit_code == 0, stderr
        assert _SCORE_LINE_MARKER not in stderr

    def test_run_help_no_longer_promises_score_reporting(self) -> None:
        outcome = CliRunner().invoke(cli, ["run", "--help"])

        collapsed = " ".join(outcome.output.split())
        assert "and score reporting" not in collapsed
        assert "stay raw" in collapsed


@given(
    killed=st.integers(min_value=0, max_value=50),
    timeout=st.integers(min_value=0, max_value=50),
    survived=st.integers(min_value=0, max_value=50),
)
@settings(max_examples=40, deadline=None)
def test_score_line_always_matches_compute_score(killed: int, timeout: int, survived: int) -> None:
    """The stderr line and the JSON score never disagree about their basis."""
    assume(killed + timeout + survived > 0)
    result = MutationRunResult(
        total_mutants=killed + timeout + survived,
        killed=killed,
        timeout=timeout,
        survived=survived,
    )

    line = _timeout_as_kill_score_line(result)

    assert f"{result.compute_score(treat_timeout_as_kill=True):.1f}%" in line
    assert f"{result.compute_score(treat_timeout_as_kill=False):.1f}%" in line
