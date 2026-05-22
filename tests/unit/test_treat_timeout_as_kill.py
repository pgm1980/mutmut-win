"""Regression tests for Bug #71 — Hypothesis-driven infinite-loop mutants are
recorded as TIMEOUT instead of KILLED, deflating the reported score.

The Sprint 23 mitigation is a user-controlled switch: `--treat-timeout-as-kill`
on the `run` and `results` commands, plus a `MutationRunResult.compute_score`
method that takes the flag. Default behaviour is unchanged (timeouts stay in
their own bucket); the switch lets projects with known infinite-loop signals
report the adjusted score without changing the underlying result store.

See critique-model-service ``_misc/mutmut-win-bugs.md`` Bug #5 (this repo's
issue #71) for the original observation — 76 timeout mutants in one sprint
where every single one corresponds to a Hypothesis test triggering an
infinite loop.
"""

from __future__ import annotations

from mutmut_win.models import MutationRunResult


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
