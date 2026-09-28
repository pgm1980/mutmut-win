"""Monotonic I/O counter and classifier increment sum (M-004, issue #150)."""

from __future__ import annotations

from typing import Any

from mutmut_win.process.loop_monitor import (
    IlSample,
    IlThresholds,
    ProcessMonitor,
    classify_samples,
)

_THRESHOLD = IlThresholds(cpu_threshold=70.0, output_threshold=1024, running_ratio=0.8)


def _sample(
    cpu: float = 99.0,
    output: int | None = 0,
    io: int | None = 0,
) -> IlSample:
    return IlSample(
        timestamp=0.0,
        cpu_pct=cpu,
        output_bytes=output,
        status="running",
        io_ops=io,
    )


class _FakeIO:
    read_count: int
    write_count: int
    other_count: int

    def __init__(self, total: int) -> None:
        self.read_count = total
        self.write_count = 0
        self.other_count = 0


class _FakeProc:
    """Minimal psutil-compatible fake with (pid, create_time) identity."""

    def __init__(
        self,
        pid: int,
        create_time: float,
        io: int = 0,
        children: list[Any] | None = None,
    ) -> None:
        self.pid = pid
        self.create_time = create_time
        self._io = io
        self._children = children or []

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, _FakeProc):
            return NotImplemented
        return self.pid == other.pid and self.create_time == other.create_time

    def __hash__(self) -> int:
        return hash((self.pid, self.create_time))

    def io_counters(self) -> _FakeIO:
        if self._io < 0:
            raise PermissionError("simulated AccessDenied")
        return _FakeIO(self._io)

    def cpu_percent(self, interval: Any = None) -> float:  # noqa: ARG002  # psutil API signature
        return 99.0

    def status(self) -> str:
        return "running"

    def children(self, recursive: bool = True) -> list[Any]:  # noqa: ARG002  # psutil API signature
        return list(self._children)


def _make_monitor(root: _FakeProc) -> ProcessMonitor:
    monitor = ProcessMonitor.__new__(ProcessMonitor)
    monitor._pid = root.pid
    monitor._proc = root
    monitor._proc_cache = {}
    monitor._io_high_water = {}
    monitor._output_counter = None
    monitor._log_path = None
    return monitor


class TestMonotonicTreeCounter:
    """M-004: the monitor's io_ops never decreases when children exit."""

    def test_exited_child_retains_io(self) -> None:
        child = _FakeProc(pid=2, create_time=100.0, io=5000)
        root = _FakeProc(pid=1, create_time=99.0, io=10, children=[child])
        monitor = _make_monitor(root)

        sample1 = monitor._take_sample()
        assert sample1 is not None
        assert sample1.io_ops == 5010

        root._children.clear()
        sample2 = monitor._take_sample()
        assert sample2 is not None
        assert sample2.io_ops >= sample1.io_ops

    def test_none_measurement_retains_io(self) -> None:
        child = _FakeProc(pid=2, create_time=100.0, io=5000)
        root = _FakeProc(pid=1, create_time=99.0, io=10, children=[child])
        monitor = _make_monitor(root)

        sample1 = monitor._take_sample()
        assert sample1 is not None
        assert sample1.io_ops == 5010

        child._io = -1  # Simulate AccessDenied
        sample2 = monitor._take_sample()
        assert sample2 is not None
        assert sample2.io_ops >= sample1.io_ops

    def test_pid_reuse_keeps_separate_entries(self) -> None:
        old_child = _FakeProc(pid=2, create_time=100.0, io=5000)
        root = _FakeProc(pid=1, create_time=99.0, io=10, children=[old_child])
        monitor = _make_monitor(root)

        sample1 = monitor._take_sample()
        assert sample1 is not None

        new_child = _FakeProc(pid=2, create_time=200.0, io=100)
        root._children.clear()
        root._children.append(new_child)
        sample2 = monitor._take_sample()
        assert sample2 is not None
        assert sample2.io_ops == 5110  # old(5000) + new(100) + root(10)

    def test_never_measured_returns_none(self) -> None:
        root = _FakeProc(pid=1, create_time=99.0, io=-1)
        monitor = _make_monitor(root)

        sample = monitor._take_sample()
        assert sample is not None
        assert sample.io_ops is None


class TestClassifierIncrementSum:
    """M-004: io_ops_delta uses sum of positive increments, not last-first."""

    def test_dropped_io_still_vetoes(self) -> None:
        samples = [_sample(io=v) for v in [10] * 5 + [5010] * 5 + [10] * 10]
        result = classify_samples(samples, _THRESHOLD, status_signal_available=False)
        assert result.verdict == "timeout"
        assert result.forensics.io_ops_delta is not None
        assert result.forensics.io_ops_delta >= 5000

    def test_monotone_series_identical_to_old_formula(self) -> None:
        values = list(range(0, 1500, 100))
        samples = [_sample(io=v) for v in values]
        result = classify_samples(samples, _THRESHOLD, status_signal_available=False)
        assert result.forensics.io_ops_delta == values[-1] - values[0]

    def test_zero_increments_stay_zero(self) -> None:
        samples = [_sample(io=100)] * 15
        result = classify_samples(samples, _THRESHOLD, status_signal_available=False)
        assert result.forensics.io_ops_delta == 0

    def test_none_series_stays_none(self) -> None:
        samples = [_sample(io=None)] * 15
        result = classify_samples(samples, _THRESHOLD, status_signal_available=False)
        assert result.forensics.io_ops_delta is None
