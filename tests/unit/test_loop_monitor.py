"""Unit tests for the IL-detection classifier and ProcessMonitor.

The classifier (``classify_samples``) is a pure function and is tested
exhaustively without psutil. The thread (``ProcessMonitor``) lifecycle is
smoke-tested with a real subprocess only when psutil is installed.

See Issue #71 (re-opened in Sprint 26) and ``loop_monitor.py`` module docstring
for the architecture rationale.
"""

from __future__ import annotations

import sys
import time
from typing import TYPE_CHECKING

import pytest

from mutmut_win.process.loop_monitor import (
    EXIT_CODE_INFINITE_LOOP,
    STATUS_KILLED_BY_INFINITE_LOOP,
    IlSample,
    IlThresholds,
    classify_samples,
    has_psutil,
)

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# classify_samples — pure function tests (no psutil dep)
# ---------------------------------------------------------------------------


def _make_samples(
    n: int,
    cpu: float,
    output_bytes_start: int = 0,
    output_growth_per_sample: int = 0,
    status: str = "running",
) -> list[IlSample]:
    """Build a synthetic sample list for classifier tests."""
    base_ts = time.monotonic()
    return [
        IlSample(
            timestamp=base_ts + i * 0.5,
            cpu_pct=cpu,
            output_bytes=output_bytes_start + i * output_growth_per_sample,
            status=status,
        )
        for i in range(n)
    ]


def test_classify_hypothesis_infinite_loop_is_killed_with_high_confidence() -> None:
    """CPU pegged + no output + running for full window → killed_by_infinite_loop, high conf."""
    samples = _make_samples(n=20, cpu=99.0, output_growth_per_sample=0, status="running")
    result = classify_samples(samples, IlThresholds())

    assert result.verdict == "killed_by_infinite_loop"
    assert result.confidence == "high", (
        f"Expected high confidence with CPU=99 (margin 41% over threshold 70%), "
        f"got {result.confidence}. Forensics: {result.forensics}"
    )
    assert result.forensics.cpu_pct_mean == 99.0
    assert result.forensics.output_growth_bytes == 0
    assert result.forensics.running_ratio == 1.0
    assert result.forensics.samples_collected == 20


def test_classify_slow_io_test_is_timeout_not_loop() -> None:
    """CPU low + no output → timeout (not IL — process waiting on I/O).

    The "sleeping" status here is POSIX semantics: Windows reports virtually
    every process as "running" (A2-JT-001), so on win32 the worker declares
    the status signal unavailable and CPU alone carries this discrimination —
    see tests/unit/test_classifier_honesty.py for the win32 path.
    """
    samples = _make_samples(n=20, cpu=5.0, output_growth_per_sample=0, status="sleeping")
    result = classify_samples(samples, IlThresholds())

    assert result.verdict == "timeout", (
        f"Slow I/O test wrongly classified as IL — false positive. "
        f"Forensics: {result.forensics}"
    )
    assert result.confidence == "low"


def test_classify_genuine_many_hypothesis_examples_is_timeout() -> None:
    """CPU high + output growing + running → timeout (output growth = progress)."""
    samples = _make_samples(
        n=20,
        cpu=85.0,
        output_growth_per_sample=500,  # 9.5 KB total growth over window
        status="running",
    )
    result = classify_samples(samples, IlThresholds())

    assert result.verdict == "timeout", (
        f"Genuine slow test (with output progress) wrongly classified as IL. "
        f"Forensics: {result.forensics}"
    )


def test_classify_async_event_loop_spinning_is_killed() -> None:
    """High CPU + no output + running (async busy-loop) → killed_by_infinite_loop."""
    samples = _make_samples(n=20, cpu=92.0, output_growth_per_sample=0, status="running")
    result = classify_samples(samples, IlThresholds())

    assert result.verdict == "killed_by_infinite_loop"


def test_classify_empty_samples_returns_timeout_low_confidence() -> None:
    """No samples → safe default: timeout, low confidence."""
    result = classify_samples([], IlThresholds())

    assert result.verdict == "timeout"
    assert result.confidence == "low"
    assert result.forensics.samples_collected == 0


def test_classify_just_below_cpu_threshold_is_timeout() -> None:
    """CPU mean just below threshold → timeout (boundary check)."""
    samples = _make_samples(n=20, cpu=69.0, output_growth_per_sample=0, status="running")
    result = classify_samples(samples, IlThresholds(cpu_threshold=70.0))

    assert result.verdict == "timeout"


def test_classify_just_above_threshold_is_killed_medium_confidence() -> None:
    """All three thresholds barely met → killed_by_infinite_loop, medium confidence."""
    samples = _make_samples(n=20, cpu=72.0, output_growth_per_sample=0, status="running")
    # cpu=72 vs threshold 70 → margin ~3% < 20% → medium
    result = classify_samples(samples, IlThresholds(cpu_threshold=70.0))

    assert result.verdict == "killed_by_infinite_loop"
    assert result.confidence == "medium", (
        f"Expected medium confidence for narrow threshold margin, got {result.confidence}"
    )


def test_classify_running_ratio_below_threshold_blocks_il_verdict() -> None:
    """running_ratio in ISOLATION blocks IL (POSIX semantics, A2-JT-016).

    The pre-#90 version of this test mixed low CPU into the sleeping samples,
    so the ratio was never the deciding signal and the suite could not have
    caught A2-JT-001 (the ratio check being vacuous on Windows). Here CPU is
    pegged on EVERY sample and output is silent — the ratio alone must veto.
    """
    # 12 running + 8 sleeping = ratio 0.6, below the default 0.8 threshold;
    # cpu=95 throughout → cpu_ok and output_ok both hold.
    samples = (
        _make_samples(n=12, cpu=95.0, status="running")
        + _make_samples(n=8, cpu=95.0, status="sleeping")
    )
    result = classify_samples(samples, IlThresholds())

    assert result.verdict == "timeout"
    assert result.forensics.running_ratio == 0.6


def test_classify_tunable_thresholds_lower_cpu_floor() -> None:
    """A user with low-CPU IL patterns can lower the threshold."""
    samples = _make_samples(n=20, cpu=55.0, output_growth_per_sample=0, status="running")
    permissive = IlThresholds(cpu_threshold=50.0)

    result = classify_samples(samples, permissive)
    assert result.verdict == "killed_by_infinite_loop"


def test_classify_forensics_capture_last_output_tail() -> None:
    """The forensics panel must include the supplied last_output_tail verbatim."""
    samples = _make_samples(n=20, cpu=99.0, status="running")
    last_tail = "stuck on test_parse[a=0]\nrunning sample 1042"
    result = classify_samples(samples, IlThresholds(), last_output_tail=last_tail)

    assert result.forensics.last_output_tail == last_tail


def test_exit_code_and_status_constants_are_stable() -> None:
    """These constants are part of the on-disk contract — guard against drift."""
    assert EXIT_CODE_INFINITE_LOOP == 38
    assert STATUS_KILLED_BY_INFINITE_LOOP == "killed_by_infinite_loop"


# ---------------------------------------------------------------------------
# ProcessMonitor — smoke test with real psutil + real subprocess
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not has_psutil(), reason="psutil not installed")
def test_process_monitor_collects_samples_for_running_subprocess(tmp_path: Path) -> None:
    """ProcessMonitor must accumulate samples while a subprocess runs."""
    import subprocess

    from mutmut_win.process.loop_monitor import ProcessMonitor

    log_path = tmp_path / "monitor_smoke.log"
    log_path.write_text("", encoding="utf-8")

    # A 3-second sleep gives the monitor several poll intervals to sample.
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(3)"])
    try:
        monitor = ProcessMonitor(
            pid=child.pid,
            log_path=log_path,
            poll_interval=0.2,
            window_seconds=2.0,
        )
        monitor.start()
        time.sleep(1.5)  # let the monitor collect several samples
        snapshot = monitor.take_samples_snapshot()
        monitor.shutdown()
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=2.0)

    assert len(snapshot) >= 3, (
        f"Expected the monitor to collect at least 3 samples in 1.5s at "
        f"0.2s polling, got {len(snapshot)}"
    )
    for sample in snapshot:
        assert isinstance(sample.cpu_pct, float)
        assert sample.output_bytes >= 0
        assert sample.status  # non-empty status string


@pytest.mark.skipif(
    has_psutil(),
    reason="psutil IS installed - graceful-fail path only triggers without it",
)
def test_process_monitor_raises_when_psutil_unavailable(tmp_path: Path) -> None:
    """Without psutil, instantiating ProcessMonitor must raise a clear error."""
    from mutmut_win.process.loop_monitor import ProcessMonitor

    with pytest.raises(RuntimeError, match="psutil"):
        ProcessMonitor(pid=1, log_path=tmp_path / "x.log")
