"""Deterministic tests for the IL precondition decision logic (M-139, issue #151)."""

from __future__ import annotations

from typing import Any

from hypothesis import given
from hypothesis import strategies as st

from mutmut_win.process.loop_monitor import IlThresholds
from tests.unit.il_precondition_util import (
    PRECONDITION_MARGIN,
    assess_busy_loop_run,
)

_THRESHOLD = IlThresholds(cpu_threshold=70.0, output_threshold=1024, running_ratio=0.8)


def _make_classification(cpu_mean: float, verdict: str = "timeout") -> Any:
    """Build a minimal LoopClassification-compatible object."""
    from mutmut_win.process.loop_monitor import IlForensics, LoopClassification

    forensics = IlForensics(
        cpu_pct_mean=cpu_mean,
        cpu_pct_max=cpu_mean,
        output_growth_bytes=0,
        running_ratio=1.0,
        samples_collected=15,
        window_seconds=3.0,
        loop_suspected=verdict == "killed_by_infinite_loop",
    )
    return LoopClassification(verdict=verdict, confidence="low", forensics=forensics)


class TestAssessBusyLoopRun:
    def test_il_verdict_accepted_without_oracle(self) -> None:
        """A correct IL verdict is accepted even with low granted CPU."""
        cls = _make_classification(40.0, verdict="killed_by_infinite_loop")
        result = assess_busy_loop_run(cls, granted_cpu_pct=40.0, thresholds=_THRESHOLD)
        assert result.decision == "assert_il"

    def test_contended_run_is_precondition_unmet(self) -> None:
        """Low granted CPU with non-IL verdict → precondition_unmet."""
        cls = _make_classification(50.0, verdict="timeout")
        result = assess_busy_loop_run(cls, granted_cpu_pct=50.0, thresholds=_THRESHOLD)
        assert result.decision == "precondition_unmet"
        assert "host contention" in result.reason

    def test_precondition_boundary(self) -> None:
        """Granted exactly at the margin boundary."""
        boundary = 70.0 * PRECONDITION_MARGIN  # 80.5
        cls = _make_classification(70.0, verdict="timeout")
        result = assess_busy_loop_run(cls, granted_cpu_pct=boundary, thresholds=_THRESHOLD)
        assert result.decision == "assert_il"  # precondition met

    def test_satisfied_precondition_with_divergence_is_defect(self) -> None:
        """Precondition met but huge oracle/monitor gap → measurement_defect."""
        cls = _make_classification(10.0, verdict="timeout")
        result = assess_busy_loop_run(cls, granted_cpu_pct=98.0, thresholds=_THRESHOLD)
        assert result.decision == "measurement_defect"
        assert "divergence" in result.reason.lower()

    def test_satisfied_precondition_without_divergence_is_defect(self) -> None:
        """Precondition met, no divergence, but non-IL → assert_il (detector defect)."""
        cls = _make_classification(90.0, verdict="timeout")
        result = assess_busy_loop_run(cls, granted_cpu_pct=95.0, thresholds=_THRESHOLD)
        assert result.decision == "assert_il"
        assert "precondition met" in result.reason


class TestHypothesisProperties:
    @given(
        granted=st.floats(0, 400, allow_nan=False, allow_infinity=False),
        monitor_mean=st.floats(0, 400, allow_nan=False, allow_infinity=False),
    )
    def test_decision_boundaries(self, granted: float, monitor_mean: float) -> None:
        """The decision follows the documented boundary rules."""
        threshold = _THRESHOLD.cpu_threshold
        precondition = threshold * PRECONDITION_MARGIN

        # Build a classification with the given monitor_mean.
        # Verdict: IL if monitor_mean >= threshold (simplified).
        verdict = "killed_by_infinite_loop" if monitor_mean >= threshold else "timeout"
        cls = _make_classification(monitor_mean, verdict=verdict)

        result = assess_busy_loop_run(cls, granted, _THRESHOLD)

        if verdict == "killed_by_infinite_loop":
            # Correct IL is always accepted.
            assert result.decision == "assert_il"
        elif granted < precondition:
            # Non-IL with unmet precondition.
            assert result.decision == "precondition_unmet"
        else:
            # Non-IL with met precondition: defect or assert_il.
            assert result.decision in ("assert_il", "measurement_defect")
