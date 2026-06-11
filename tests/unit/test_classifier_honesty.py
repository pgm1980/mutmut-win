"""Tests for IL classifier honesty (Issue #88, audit A2-JT-001/002/009/010/011/012/014/015).

On Windows two of the three classifier signals were compromised: psutil
reports every process as "running" (running_ratio vacuously true) and block
buffering froze the log's st_size (output stagnation vacuously true).  The
triple check silently collapsed to "CPU >= threshold" — sold as high
confidence.  #88 makes the caller declare which signals are real
(``status_signal_available``), caps confidence at "medium" for two-signal
verdicts, adds a minimum-sample floor, treats unmeasurable output as
missing data instead of pro-IL zeros, and makes the sampler thread survive
and count unexpected errors instead of dying silently.
"""

from __future__ import annotations

import os
import time
from typing import TYPE_CHECKING

import pytest
from pydantic import ValidationError

from mutmut_win.process.loop_monitor import (
    IO_OPS_PROGRESS_THRESHOLD,
    MIN_SAMPLES_FOR_VERDICT,
    IlForensics,
    IlSample,
    IlThresholds,
    ProcessMonitor,
    classify_samples,
    has_psutil,
)

if TYPE_CHECKING:
    from pathlib import Path


def _samples(
    n: int,
    cpu: float = 99.0,
    output_bytes: int | None = 0,
    status: str = "running",
) -> list[IlSample]:
    base = time.monotonic()
    return [
        IlSample(timestamp=base + i * 0.5, cpu_pct=cpu, output_bytes=output_bytes, status=status)
        for i in range(n)
    ]


class TestTwoSignalConfidenceCap:
    def test_win32_two_signal_verdict_is_capped_at_medium(self) -> None:
        # Perfect margins on CPU and output — but with the status signal
        # declared unavailable only two of three checks are real.
        result = classify_samples(_samples(20), IlThresholds(), status_signal_available=False)
        assert result.verdict == "killed_by_infinite_loop"
        assert result.confidence == "medium"
        assert result.forensics.status_signal_used is False

    def test_three_signal_verdict_still_reaches_high(self) -> None:
        result = classify_samples(_samples(20), IlThresholds(), status_signal_available=True)
        assert result.verdict == "killed_by_infinite_loop"
        assert result.confidence == "high"
        assert result.forensics.status_signal_used is True

    def test_unavailable_status_signal_does_not_block_the_verdict(self) -> None:
        # On win32 every sample says "running" — but even an all-"sleeping"
        # fixture must not block the verdict when the signal is declared dead.
        result = classify_samples(
            _samples(20, status="sleeping"), IlThresholds(), status_signal_available=False
        )
        assert result.verdict == "killed_by_infinite_loop"


class TestMinimumSampleFloor:
    def test_below_floor_never_yields_a_verdict(self) -> None:
        # JT-009: a single cpu=99 sample used to produce IL with HIGH confidence.
        result = classify_samples(_samples(MIN_SAMPLES_FOR_VERDICT - 1), IlThresholds())
        assert result.verdict == "timeout"
        assert result.confidence == "low"
        assert result.forensics.samples_collected == MIN_SAMPLES_FOR_VERDICT - 1

    def test_at_floor_a_verdict_is_possible(self) -> None:
        result = classify_samples(_samples(MIN_SAMPLES_FOR_VERDICT), IlThresholds())
        assert result.verdict == "killed_by_infinite_loop"


class TestOutputSignalMissingData:
    def test_all_unmeasurable_output_blocks_il(self) -> None:
        # JT-015: stat() failures used to clamp output to 0 = "stagnating",
        # a pro-IL bias.  Missing data must never argue FOR a kill.
        result = classify_samples(_samples(20, output_bytes=None), IlThresholds())
        assert result.verdict == "timeout"

    def test_growth_is_computed_over_measurable_samples_only(self) -> None:
        base = time.monotonic()
        measurable = [
            IlSample(timestamp=base + i, cpu_pct=99.0, output_bytes=5000 * i, status="running")
            for i in range(10)
        ]
        with_holes = [
            IlSample(timestamp=base + 10 + i, cpu_pct=99.0, output_bytes=None, status="running")
            for i in range(3)
        ]
        result = classify_samples(measurable + with_holes, IlThresholds())
        # 45 KB growth across the measurable subset — clearly above threshold.
        assert result.verdict == "timeout"
        assert result.forensics.output_growth_bytes == 45_000


class TestForensicsExtensions:
    def test_sampler_errors_are_surfaced(self) -> None:
        result = classify_samples(_samples(20), IlThresholds(), sampler_errors=3)
        assert result.forensics.sampler_errors == 3

    def test_new_fields_have_backward_compatible_defaults(self) -> None:
        # Rows persisted between #85 and #88 lack the new keys — the model
        # must still parse them.
        legacy = IlForensics(
            cpu_pct_mean=99.0,
            cpu_pct_max=99.0,
            output_growth_bytes=0,
            running_ratio=1.0,
            samples_collected=20,
            window_seconds=10.0,
        )
        assert legacy.status_signal_used is True
        assert legacy.sampler_errors == 0


class TestThresholdValidation:
    def test_output_threshold_zero_is_rejected(self) -> None:
        # JT-010: output_threshold=0 silently disabled IL detection
        # (growth < 0 can never hold).  Fail fast instead.
        with pytest.raises(ValidationError):
            IlThresholds(output_threshold=0)


def _io_samples(n: int, io_ops_per_sample: int) -> list[IlSample]:
    """CPU pegged, stdout silent — io activity is the only varying signal."""
    base = time.monotonic()
    return [
        IlSample(
            timestamp=base + i * 0.5,
            cpu_pct=99.0,
            output_bytes=0,
            status="running",
            io_ops=1000 + i * io_ops_per_sample,
        )
        for i in range(n)
    ]


class TestIoProgressVeto:
    """Spike #89: a pure spin makes ZERO syscalls (measured: 0 deltas over 5 s
    for busy loops, 14k ops for a writing loop).  io activity therefore vetoes
    an IL verdict — it widens "observable progress" beyond the captured log to
    every handle the test touches.  Veto-only: it can never CREATE a verdict.
    """

    def test_io_activity_vetoes_il_despite_cpu_and_silent_stdout(self) -> None:
        samples = _io_samples(20, io_ops_per_sample=500)
        result = classify_samples(samples, IlThresholds())
        assert result.verdict == "timeout"
        assert result.forensics.io_ops_delta == 19 * 500

    def test_frozen_io_does_not_veto(self) -> None:
        result = classify_samples(_io_samples(20, io_ops_per_sample=0), IlThresholds())
        assert result.verdict == "killed_by_infinite_loop"
        assert result.forensics.io_ops_delta == 0

    def test_unmeasurable_io_is_neutral(self) -> None:
        # macOS has no io_counters; AccessDenied can hit individual reads.
        # Missing data neither vetoes nor argues for a kill.
        result = classify_samples(_samples(20), IlThresholds())  # io_ops=None default
        assert result.verdict == "killed_by_infinite_loop"
        assert result.forensics.io_ops_delta is None

    def test_delta_at_threshold_does_not_veto(self) -> None:
        # The veto needs delta STRICTLY above the threshold — an order-of-
        # magnitude margin against stray ticks, not a hair trigger.
        per_sample = IO_OPS_PROGRESS_THRESHOLD // 19  # total stays <= threshold
        result = classify_samples(_io_samples(20, per_sample), IlThresholds())
        assert result.verdict == "killed_by_infinite_loop"


@pytest.mark.skipif(not has_psutil(), reason="psutil not installed")
class TestProcessMonitorMechanics:
    def test_daemon_flag_is_set_via_init(self, tmp_path: Path) -> None:
        # JT-012: `daemon = True` as a class attribute shadowed the Thread
        # property; the flag belongs in super().__init__.
        monitor = ProcessMonitor(pid=os.getpid(), log_path=tmp_path / "x.log")
        assert monitor.daemon is True
        assert "daemon" not in ProcessMonitor.__dict__

    def test_snapshot_window_is_relative_to_last_sample(self, tmp_path: Path) -> None:
        # JT-014: the cutoff used `now`, so kill + log-read latency between
        # process death and classification silently shrank the window.
        monitor = ProcessMonitor(pid=os.getpid(), log_path=tmp_path / "x.log", window_seconds=10.0)
        stale_base = time.monotonic() - 120.0  # samples "collected" 2 min ago
        for i in range(20):
            monitor._samples.append(
                IlSample(
                    timestamp=stale_base + i * 0.5,
                    cpu_pct=99.0,
                    output_bytes=0,
                    status="running",
                )
            )
        snapshot = monitor.take_samples_snapshot()
        assert len(snapshot) == 20  # a now-relative cutoff would return []

    def test_run_survives_sampler_exceptions_and_counts_them(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # JT-011: an unexpected exception used to kill the sampler thread
        # silently → systematic timeout/low without any warning.
        monitor = ProcessMonitor(pid=os.getpid(), log_path=tmp_path / "x.log", poll_interval=0.05)

        def _boom() -> None:
            raise RuntimeError("sampler glitch")

        monkeypatch.setattr(monitor, "_take_sample", _boom)
        monitor.start()
        try:
            deadline = time.monotonic() + 5.0
            while monitor.sampler_errors < 2 and time.monotonic() < deadline:
                time.sleep(0.05)
            assert monitor.is_alive(), "sampler thread died on first exception"
            assert monitor.sampler_errors >= 2  # survived AND kept sampling
        finally:
            monitor.shutdown()
