"""End-to-end deterministic test for Issue #71 — true IL detection.

Spawns a real Python subprocess running ``while True: pass`` (CPU-pegged, no
output), attaches a ``ProcessMonitor``, samples for a few seconds, then asks
:func:`classify_samples` for a verdict. The classifier must return
``killed_by_infinite_loop`` with ``high`` confidence — anything else means the
detector regressed.

This is the integration counterpart to the unit-level classifier tests in
``tests/unit/test_loop_monitor.py``. It exercises the full chain
(psutil → ProcessMonitor → classify_samples) against a real process tree.

Skipped when psutil is unavailable in the test environment, since IL detection
is structurally impossible without it.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.slow]

psutil = pytest.importorskip("psutil", reason="psutil not installed in test env")

# Import after importorskip so collection on psutil-less environments still
# yields a clean skip (rather than crashing here on the loop_monitor import).
from mutmut_win.process.loop_monitor import (  # noqa: E402, I001
    IlThresholds,
    ProcessMonitor,
    classify_samples,
)


_BUSY_LOOP_SOURCE = "while True: pass"


def _run_classifier_against_subprocess(
    cmd: list[str], window_seconds: float = 3.0
) -> tuple[str, str, int]:
    """Spawn ``cmd``, monitor it for ``window_seconds``, kill, classify.

    Returns ``(verdict, confidence, samples_collected)``.
    """
    tmp_log = Path("test_il_smoke.log")
    tmp_log.write_text("", encoding="utf-8")
    child = subprocess.Popen(cmd)  # noqa: S603 - cmd is fully controlled in this test
    try:
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
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=2.0)
        if tmp_log.exists():
            tmp_log.unlink()

    classification = classify_samples(snapshot, IlThresholds(window_seconds=window_seconds))
    return classification.verdict, classification.confidence, len(snapshot)


def test_busy_loop_subprocess_classified_as_infinite_loop() -> None:
    """``while True: pass`` must classify as killed_by_infinite_loop with high confidence."""
    verdict, confidence, samples = _run_classifier_against_subprocess(
        [sys.executable, "-c", _BUSY_LOOP_SOURCE]
    )

    assert samples >= 5, (
        f"Expected at least 5 samples in the 3s window at 0.2s polling, got {samples}"
    )
    assert verdict == "killed_by_infinite_loop", (
        f"Real busy-loop subprocess wrongly classified as {verdict!r}. "
        f"This is the canonical Bug #5 / Issue #71 case — if it fails the IL "
        f"detector is broken."
    )
    assert confidence in {"high", "medium"}, (
        f"Confidence should be at least medium for a clear busy loop, got {confidence!r}"
    )


def test_sleeping_subprocess_classified_as_timeout() -> None:
    """``time.sleep(20)`` (no CPU, status=sleeping) must classify as timeout, not IL."""
    verdict, _confidence, samples = _run_classifier_against_subprocess(
        [sys.executable, "-c", "import time; time.sleep(20)"]
    )

    assert samples >= 5, f"Expected at least 5 samples, got {samples}"
    assert verdict == "timeout", (
        f"Idle/sleeping subprocess wrongly classified as IL — false positive. "
        f"Got verdict={verdict!r}. This is the slow-network-test case that "
        f"must NOT register as a kill."
    )
