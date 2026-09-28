"""Integration tests for the IL classifier against real subprocesses (Bug #5/71, M-139).

The busy-loop test uses an independent CPU oracle (psutil cpu_times summed
over the whole process tree) to distinguish host contention from a genuine
detector defect.  The verdict is checked FIRST; the oracle only explains a
non-IL verdict (counter-review correction 2).  The log file lives under
``tmp_path`` so parallel runs from the same checkout cannot delete each
other's output (counter-review correction 3).

The old CPU-affinity pin (last core) was removed: it made concurrent runs
contend for the SAME core, which is the primary cause of false-timeout
flakes (counter-review correction 1).
"""

from __future__ import annotations

import contextlib
import subprocess
import sys
import time
from typing import TYPE_CHECKING, Any

import psutil
import pytest

from mutmut_win.process.loop_monitor import (
    IlThresholds,
    ProcessMonitor,
    classify_samples,
)
from tests.unit.il_precondition_util import (
    MAX_ATTEMPTS,
    assess_busy_loop_run,
)

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.integration, pytest.mark.slow]

_WARMUP_SECONDS = 1.0
_BUSY_LOOP_SOURCE = "while True: pass"
_SLEEPING_SOURCE = "import time; time.sleep(20)"

# The old _pin_for_stable_cpu was removed (M-139 counter-review correction 1):
# pinning all tree members to the LAST core made concurrent runs contend for
# the same core and was the primary cause of false-timeout flakes.


def _tree_cpu_seconds(root_pid: int) -> dict[int, float]:
    """Sum user+system CPU seconds per PID over the whole tree (oracle)."""
    result: dict[int, float] = {}
    try:
        root = psutil.Process(root_pid)
        members = [root, *root.children(recursive=True)]
    except psutil.NoSuchProcess, psutil.AccessDenied:
        return result
    for member in members:
        with contextlib.suppress(psutil.NoSuchProcess, psutil.AccessDenied):
            times = member.cpu_times()
            result[member.pid] = times.user + times.system
    return result


def _run_classifier_against_subprocess(
    cmd: list[str],
    log_dir: Path,
    window_seconds: float = 3.0,
) -> tuple[Any, float]:
    """Spawn ``cmd``, monitor it, classify, and measure granted CPU%.

    Returns ``(LoopClassification, granted_cpu_pct)`` where the granted CPU
    is measured by an independent psutil oracle over the same window.
    """
    tmp_log = log_dir / "test_il_smoke.log"
    tmp_log.write_text("", encoding="utf-8")
    child = subprocess.Popen(cmd)  # noqa: S603 - cmd is fully controlled in this test
    try:
        time.sleep(_WARMUP_SECONDS)
        # Oracle t0: measure tree CPU just before the monitor starts.
        t0 = time.monotonic()
        cpu0 = _tree_cpu_seconds(child.pid)

        monitor = ProcessMonitor(
            pid=child.pid,
            log_path=tmp_log,
            poll_interval=0.2,
            window_seconds=window_seconds,
        )
        monitor.start()
        time.sleep(window_seconds + 0.3)
        snapshot = monitor.take_samples_snapshot()
        monitor.shutdown()

        # Oracle t1: measure tree CPU just after the window.
        t1 = time.monotonic()
        cpu1 = _tree_cpu_seconds(child.pid)
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=2.0)

    # Compute granted CPU % from the oracle measurements.
    elapsed = t1 - t0
    total_cpu = sum(cpu1.get(pid, 0.0) - cpu0.get(pid, 0.0) for pid in cpu1)
    granted_cpu_pct = (total_cpu / elapsed * 100.0) if elapsed > 0 else 0.0

    classification = classify_samples(
        snapshot,
        IlThresholds(window_seconds=window_seconds),
        status_signal_available=sys.platform != "win32",
    )
    return classification, granted_cpu_pct


def test_busy_loop_subprocess_classified_as_infinite_loop(
    tmp_path: Path,
) -> None:
    """``while True: pass`` must classify as killed_by_infinite_loop.

    Uses an independent CPU oracle to distinguish host contention (skip
    with measurements after retries) from a genuine detector defect
    (hard fail).  See M-139 / issue #151.
    """
    thresholds = IlThresholds(window_seconds=3.0)
    attempts: list[float] = []

    for _attempt in range(MAX_ATTEMPTS):
        classification, granted = _run_classifier_against_subprocess(
            [sys.executable, "-c", _BUSY_LOOP_SOURCE],
            log_dir=tmp_path,
        )
        attempts.append(granted)
        assessment = assess_busy_loop_run(classification, granted, thresholds)

        if assessment.decision == "assert_il":
            # Run the original assertions.
            samples = classification.forensics.samples_collected
            assert samples >= 5, f"Expected at least 5 samples, got {samples}"
            assert classification.verdict == "killed_by_infinite_loop", (
                f"Real busy-loop wrongly classified as "
                f"{classification.verdict!r} (granted {granted:.1f}%). "
                f"Bug #5 / Issue #71 — IL detector defect."
            )
            allowed = {"medium"} if sys.platform == "win32" else {"medium", "high"}
            assert classification.confidence in allowed
            return  # Success

        if assessment.decision == "measurement_defect":
            pytest.fail(
                f"IL measurement defect: {assessment.reason} "
                f"(attempts: {[f'{a:.0f}%' for a in attempts]})"
            )

    # All attempts had unmet preconditions: skip with measurements.
    pytest.skip(
        f"IL precondition unmet after {MAX_ATTEMPTS} attempts: "
        f"granted CPU {[f'{a:.0f}%' for a in attempts]} "
        f"< threshold {thresholds.cpu_threshold * 1.15:.0f}% "
        "(host contention)"
    )


def test_sleeping_subprocess_classified_as_timeout(tmp_path: Path) -> None:
    """``time.sleep(20)`` must classify as timeout, not IL."""
    classification, _granted = _run_classifier_against_subprocess(
        [sys.executable, "-c", _SLEEPING_SOURCE],
        log_dir=tmp_path,
    )
    assert classification.verdict == "timeout"
