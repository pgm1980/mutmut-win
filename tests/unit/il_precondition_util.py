"""IL precondition assessment for the busy-loop integration test (M-139, issue #151).

Pure, psutil-free decision logic and retry loop so the integration test can
distinguish "host contention" (retry/skip with measurements) from a genuine
detector defect (hard fail).  The authority is the independent CPU oracle,
not the classifier under test.

The verdict is checked FIRST (counter-review correction 2): a correct
``killed_by_infinite_loop`` is accepted regardless of the oracle — the
oracle can only explain a non-IL verdict, never override a correct one.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

#: Safety margin: the oracle must see at least cpu_threshold x this factor
#: to consider the precondition met (accounting for measurement noise).
PRECONDITION_MARGIN: float = 1.15

#: Maximum tolerated divergence (percentage points) between the oracle's
#: granted CPU and the classifier's measured cpu_pct_mean.
ORACLE_TOLERANCE_PCT: float = 25.0

#: Maximum busy-loop attempts before skipping with measurements.
MAX_ATTEMPTS: int = 3


class IlRunAssessment(BaseModel):
    """One assessment of a busy-loop run against its precondition."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    decision: Literal["assert_il", "precondition_unmet", "measurement_defect"]
    reason: str = Field(min_length=1)


def assess_busy_loop_run(
    classification: Any,
    granted_cpu_pct: float,
    thresholds: Any,
) -> IlRunAssessment:
    """Assess one busy-loop run: IL verdict, unmet precondition, or defect.

    Decision order (counter-review correction 2):
    1. ``killed_by_infinite_loop`` → ``assert_il`` (oracle not consulted).
    2. Non-IL + granted < cpu_threshold x margin → ``precondition_unmet``.
    3. Non-IL + granted >= threshold but classifier CPU diverges > 25 pp
       → ``measurement_defect``.
    4. Non-IL + granted >= threshold + no divergence → ``assert_il``
       (a genuine detector defect — the busy loop should have been caught).

    Args:
        classification: The ``LoopClassification`` from ``classify_samples``.
        granted_cpu_pct: CPU % measured by the independent oracle.
        thresholds: The ``IlThresholds`` used for classification.

    Returns:
        The assessment with a machine-readable decision.
    """
    threshold = float(thresholds.cpu_threshold)

    # Correct IL verdict: accept without oracle dependency.
    if classification.verdict == "killed_by_infinite_loop":
        return IlRunAssessment(
            decision="assert_il",
            reason="classifier returned killed_by_infinite_loop",
        )

    # Non-IL: check the precondition first.
    precondition = threshold * PRECONDITION_MARGIN
    if granted_cpu_pct < precondition:
        return IlRunAssessment(
            decision="precondition_unmet",
            reason=(
                f"granted CPU {granted_cpu_pct:.1f}% < {precondition:.1f}% "
                f"(threshold {threshold:.0f}% x {PRECONDITION_MARGIN}); "
                "host contention"
            ),
        )

    # Precondition met but verdict is not IL: detector defect or divergence.
    monitor_cpu = float(classification.forensics.cpu_pct_mean)
    divergence = granted_cpu_pct - monitor_cpu
    if divergence > ORACLE_TOLERANCE_PCT:
        return IlRunAssessment(
            decision="measurement_defect",
            reason=(
                f"oracle {granted_cpu_pct:.1f}% vs monitor {monitor_cpu:.1f}% "
                f"(divergence {divergence:.1f} pp > {ORACLE_TOLERANCE_PCT} pp)"
            ),
        )

    return IlRunAssessment(
        decision="assert_il",
        reason=(
            f"precondition met (granted {granted_cpu_pct:.1f}%) but "
            f"verdict is {classification.verdict!r}"
        ),
    )
