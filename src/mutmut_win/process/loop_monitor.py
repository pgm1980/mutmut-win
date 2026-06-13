"""Infinite-loop detection for mutation-test workers (Bug #5 / Issue #71).

The pre-Sprint-26 worker only knew "subprocess timed out — exit_code 36".
That bucketed two semantically different things into the same TIMEOUT bucket:

1. **Infinite loop** introduced by the mutation (CPU pegged, no output, the
   suite would never terminate). The mutation IS detected; classification as
   TIMEOUT understates the kill.
2. **Genuine slow test** that hit the wall-clock budget for non-mutation
   reasons (network wait, expensive setup, …). Real TIMEOUT.

This module distinguishes the two with a sampling classifier: a lightweight
``threading.Thread`` observes the subprocess tree during its lifetime; after
``TimeoutExpired`` the caller invokes :func:`classify_samples`, which returns
a :class:`LoopClassification` carrying the verdict, a confidence band, and a
structured :class:`IlForensics` snapshot that is persisted with the mutant so
every classification can be audited post hoc (``mutmut-win show <mutant>``).

Signals and their honest, platform-dependent reach (issues #88/#89):

- **CPU** (mean over the window, process tree): the primary signal, real on
  all platforms.
- **Progress** (negative signal — observable progress vetoes IL): captured-log
  growth (the worker sets ``PYTHONUNBUFFERED=1`` so ``st_size`` is honest)
  OR io_counters activity of the tree (a pure spin makes zero syscalls;
  unavailable on macOS). Note that pytest writes nothing *during* a single
  long test, so a silent log alone is weak evidence — hence the conjunction
  with CPU.
- **Process status** (``running_ratio``): POSIX only. Windows reports
  virtually every process as "running", so the worker declares the signal
  unavailable there (``status_signal_available=False``) and verdicts rest on
  the other signals — capped at ``medium`` confidence, never ``high``.

Reference scenarios (status column is POSIX semantics):

| Scenario                           | CPU      | Progress  | Status   | Verdict                  |
|------------------------------------|----------|-----------|----------|--------------------------|
| Hypothesis-IL (Bug #5 case)        | high     | none      | running  | killed_by_infinite_loop  |
| Slow DB / network test             | low      | none      | sleeping | timeout                  |
| Genuine many Hypothesis examples   | med-high | growing   | running  | timeout                  |
| Async event loop spinning          | high     | none      | running  | killed_by_infinite_loop  |
"""

from __future__ import annotations

import contextlib
import threading
import time
from collections import deque
from typing import TYPE_CHECKING, Any, Literal, NamedTuple

from pydantic import BaseModel, ConfigDict, Field

# Single-sourced from constants (issue #132 / 360°-B8) — these used to be
# duplicate literals here that could drift apart from the orchestrator's
# mapping. Re-exported (PEP 484 ``as`` idiom) because the worker and tests
# address them via this module.
from mutmut_win.constants import (
    EXIT_CODE_INFINITE_LOOP as EXIT_CODE_INFINITE_LOOP,
)
from mutmut_win.constants import (
    STATUS_KILLED_BY_INFINITE_LOOP as STATUS_KILLED_BY_INFINITE_LOOP,
)

if TYPE_CHECKING:
    from pathlib import Path

try:
    import psutil  # type: ignore[import-untyped,unused-ignore]

    _HAS_PSUTIL = True
except ImportError:  # pragma: no cover - graceful degradation path
    psutil = None  # type: ignore[assignment,unused-ignore]
    _HAS_PSUTIL = False


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------


Verdict = Literal["killed_by_infinite_loop", "timeout"]
Confidence = Literal["high", "medium", "low"]

#: Minimum number of samples before any IL verdict is possible (issue #88,
#: A2-JT-009: a single cpu=99 sample used to yield IL with HIGH confidence).
#: At the default 0.5 s poll interval this is 2.5 s of real observation.
#: Deliberately NOT configurable — it is a correctness floor of the
#: classifier, not a tuning knob.
MIN_SAMPLES_FOR_VERDICT: int = 5

#: Default sampling cadence of :class:`ProcessMonitor` (seconds between polls).
#: Single-sourced here so the classifier's lower window bound
#: (``MIN_SAMPLES_FOR_VERDICT * DEFAULT_POLL_INTERVAL``) and the sampler stay in
#: lockstep — the IL-001 window auto-scaling (:func:`effective_window_seconds`)
#: relies on both agreeing.
DEFAULT_POLL_INTERVAL: float = 0.5

#: io_counters delta above which the process tree is demonstrably making
#: syscalls — vetoing an IL verdict (spike #89). A pure spin measures EXACTLY
#: 0 ops over a 5 s window while real I/O work measures thousands (14k for a
#: writing loop), so 100 is an order-of-magnitude margin against stray ticks.
#: Veto-only: io activity can prevent an IL verdict, never create one.
#: Like MIN_SAMPLES_FOR_VERDICT, a correctness floor — not a tuning knob.
IO_OPS_PROGRESS_THRESHOLD: int = 100


class IlSample(NamedTuple):
    """A single point-in-time observation of the monitored subprocess."""

    timestamp: float  # time.monotonic() at sample
    cpu_pct: float  # 0.0 to 100.0 * N_cores (process-tree sum)
    output_bytes: int | None  # cumulative log size; None if stat() failed
    status: str  # psutil status string ("running", "sleeping", …)
    io_ops: int | None = None  # cumulative tree io_counters ops; None if unavailable


class IlThresholds(BaseModel):
    """Tunable classifier thresholds (configurable via ``[tool.mutmut]``)."""

    cpu_threshold: float = Field(default=70.0, ge=0.0, le=10_000.0)
    # gt=0: a threshold of 0 would make `growth < threshold` unsatisfiable and
    # silently disable IL detection (A2-JT-010). Opting out has its own
    # switch: [tool.mutmut].infinite_loop_detection = false.
    output_threshold: int = Field(default=1024, gt=0)
    running_ratio: float = Field(default=0.8, ge=0.0, le=1.0)
    window_seconds: float = Field(default=10.0, gt=0.0)


class IlForensics(BaseModel):
    """Per-mutation evidence panel persisted alongside the result.

    The user can render this in ``mutmut-win show <mutant>`` to see *why*
    a mutant was classified as ``killed_by_infinite_loop`` (or why not).
    """

    model_config = ConfigDict(frozen=True)

    cpu_pct_mean: float
    cpu_pct_max: float
    output_growth_bytes: int
    running_ratio: float
    samples_collected: int
    window_seconds: float
    last_output_tail: str | None = None  # last few lines of pytest output
    # New in v2.8.0 (#88) — defaults keep rows persisted by v2.6-v2.7 parseable.
    status_signal_used: bool = True  # False when the platform can't report it
    sampler_errors: int = 0  # exceptions survived by the sampler thread
    # New in v2.8.0 (#89): io_counters ops delta over the window; None when
    # the signal was unavailable (macOS, AccessDenied).
    io_ops_delta: int | None = None


class LoopClassification(BaseModel):
    """The classifier's verdict packaged with forensics + confidence."""

    model_config = ConfigDict(frozen=True)

    verdict: Verdict
    confidence: Confidence
    forensics: IlForensics


# ---------------------------------------------------------------------------
# Pure classifier — testable without psutil / threads
# ---------------------------------------------------------------------------


def effective_window_seconds(
    configured: float,
    timeout: float,
    *,
    poll_interval: float = DEFAULT_POLL_INTERVAL,
    min_samples: int = MIN_SAMPLES_FOR_VERDICT,
) -> float:
    """Auto-scale the IL sampling window into the band where a verdict is possible.

    A verdict is only reachable when the window fits ``[min_samples *
    poll_interval, timeout / 2]`` (IL-001):

    - **Upper bound ``timeout / 2``** — :meth:`ProcessMonitor.take_samples_snapshot`
      returns the *last* ``window`` seconds of samples. A window at or above the
      task's wall-clock ``timeout`` keeps the CPU-priming samples (every freshly
      observed process reports ``0.0`` on its first ``cpu_percent`` call) inside
      the snapshot, diluting ``cpu_pct_mean`` below ``cpu_threshold`` so a genuine
      infinite loop is scored ``timeout`` instead of ``killed_by_infinite_loop``.
      Half the budget covers the settled second half of the run and drops the
      priming head.
    - **Lower bound ``min_samples * poll_interval``** — below it the snapshot holds
      fewer than ``min_samples`` observations and :func:`classify_samples` returns
      ``timeout`` for lack of data.

    The shipped 10 s default is left untouched on slow suites (large ``timeout``)
    and only scaled down on fast suites whose per-task budget is small — exactly
    where the window/timeout mismatch silently degraded IL kills to ``timeout``.

    Args:
        configured: The user's ``infinite_loop_window_seconds`` (or its default).
        timeout: Per-task wall-clock budget (``MutationTask.timeout_seconds``).
        poll_interval: Sampler cadence; with *min_samples* it sets the floor.
        min_samples: Classifier sample floor (:data:`MIN_SAMPLES_FOR_VERDICT`).

    Returns:
        The effective window (seconds), clamped into the valid band. When the band
        collapses (``timeout / 2 < floor`` — only for sub-5 s timeouts, below the
        orchestrator's ``_MIN_TIMEOUT``) the floor wins: *some* chance of enough
        samples beats a guaranteed data deficit.
    """
    floor = min_samples * poll_interval
    return max(min(configured, timeout / 2.0), floor)


def classify_samples(
    samples: list[IlSample],
    thresholds: IlThresholds,
    last_output_tail: str | None = None,
    *,
    status_signal_available: bool = True,
    sampler_errors: int = 0,
) -> LoopClassification:
    """Apply the triple-check rule and return a :class:`LoopClassification`.

    The rule:
    ``killed_by_infinite_loop`` iff all *available* checks hold simultaneously
    over the rolling window of ``samples``:

    - mean(cpu_pct) >= ``thresholds.cpu_threshold``
    - no observable progress: output_growth_in_window <
      ``thresholds.output_threshold`` (computed over samples with a
      *measurable* ``output_bytes`` — samples where ``stat()`` failed carry
      ``None`` and never argue for a kill, A2-JT-015) AND the tree's
      io_counters delta stays at :data:`IO_OPS_PROGRESS_THRESHOLD` or below
      (spike #89: a pure spin makes zero syscalls; io activity is progress
      the captured log cannot see — veto-only, unmeasurable io is neutral)
    - running_ratio >= ``thresholds.running_ratio`` — only if
      ``status_signal_available``

    Otherwise: ``timeout`` (the pre-Sprint-26 default).

    Args:
        samples: Rolling-window observations from :class:`ProcessMonitor`.
        thresholds: Tunable classifier thresholds.
        last_output_tail: Last pytest output lines for the forensics panel.
        status_signal_available: Whether ``IlSample.status`` carries signal on
            this platform. The caller declares the platform reality: psutil
            reports virtually every Windows process as "running"
            (A2-JT-001), so the worker passes ``sys.platform != "win32"``.
        sampler_errors: Number of exceptions the sampler thread survived;
            recorded in the forensics for post-hoc auditing (A2-JT-011).

    Confidence semantics — reflects evidence quality, not just margins:
    - ``high``: ALL THREE signals were available and passed with ≥20 % margin
    - ``medium``: IL verdict, but either a margin <20 % or only two signals
      were available (two-of-three is never sold as ``high``)
    - ``low``: ``timeout`` verdict, zero samples, or fewer than
      :data:`MIN_SAMPLES_FOR_VERDICT` samples (A2-JT-009)
    """
    if len(samples) < MIN_SAMPLES_FOR_VERDICT:
        # No/insufficient data — fall back to the safe default. The forensics
        # carry samples_collected so `show` reveals the evidence deficit.
        forensics = IlForensics(
            cpu_pct_mean=0.0,
            cpu_pct_max=0.0,
            output_growth_bytes=0,
            running_ratio=0.0,
            samples_collected=len(samples),
            window_seconds=thresholds.window_seconds,
            last_output_tail=last_output_tail,
            status_signal_used=status_signal_available,
            sampler_errors=sampler_errors,
        )
        return LoopClassification(
            verdict="timeout",
            confidence="low",
            forensics=forensics,
        )

    cpu_values = [s.cpu_pct for s in samples]
    cpu_mean = sum(cpu_values) / len(cpu_values)
    cpu_max = max(cpu_values)
    # Output growth only over measurable samples — a failed stat() is missing
    # data, not "the log stagnated" (the old clamp-to-0 was a pro-IL bias).
    measurable = [s.output_bytes for s in samples if s.output_bytes is not None]
    output_growth = max(0, measurable[-1] - measurable[0]) if measurable else 0
    measurable_io = [s.io_ops for s in samples if s.io_ops is not None]
    io_ops_delta = max(0, measurable_io[-1] - measurable_io[0]) if measurable_io else None
    running_ratio = sum(1 for s in samples if s.status == "running") / len(samples)

    forensics = IlForensics(
        cpu_pct_mean=cpu_mean,
        cpu_pct_max=cpu_max,
        output_growth_bytes=output_growth,
        running_ratio=running_ratio,
        samples_collected=len(samples),
        window_seconds=thresholds.window_seconds,
        last_output_tail=last_output_tail,
        status_signal_used=status_signal_available,
        sampler_errors=sampler_errors,
        io_ops_delta=io_ops_delta,
    )

    cpu_ok = cpu_mean >= thresholds.cpu_threshold
    # Demonstrated syscall activity is progress the captured log cannot see
    # (spike #89) — it vetoes IL. Unmeasurable io (None) is neutral.
    io_active = io_ops_delta is not None and io_ops_delta > IO_OPS_PROGRESS_THRESHOLD
    output_ok = bool(measurable) and output_growth < thresholds.output_threshold and not io_active
    # A dead status signal is excluded from the verdict, not vacuously passed
    # off as evidence — the confidence cap below accounts for the gap.
    running_ok = running_ratio >= thresholds.running_ratio if status_signal_available else True

    if cpu_ok and output_ok and running_ok:
        # Margin-based confidence: how far past each threshold are we?
        cpu_margin = (cpu_mean - thresholds.cpu_threshold) / max(thresholds.cpu_threshold, 1.0)
        # output_growth being well below the threshold = strong signal.
        # thresholds.output_threshold is validated gt=0.
        output_margin = (thresholds.output_threshold - output_growth) / thresholds.output_threshold
        margins = [cpu_margin, output_margin]
        if status_signal_available:
            margins.append(
                (running_ratio - thresholds.running_ratio) / max(thresholds.running_ratio, 0.01)
            )
        weakest = min(margins)
        confidence: Confidence = "high" if weakest >= 0.2 else "medium"
        if not status_signal_available:
            # Two-of-three checks is honest evidence for a kill, but never
            # "high" — the cap is monotone (only ever lowers confidence).
            confidence = "medium"
        return LoopClassification(
            verdict="killed_by_infinite_loop",
            confidence=confidence,
            forensics=forensics,
        )

    return LoopClassification(
        verdict="timeout",
        confidence="low",
        forensics=forensics,
    )


# ---------------------------------------------------------------------------
# Sampling thread — requires psutil
# ---------------------------------------------------------------------------


def has_psutil() -> bool:
    """Return ``True`` if :mod:`psutil` was importable at module load time.

    Callers should consult this before instantiating :class:`ProcessMonitor`.
    When ``False``, true IL detection is unavailable and the worker should
    fall back to the legacy "everything that times out is TIMEOUT" path.
    """
    return _HAS_PSUTIL


class ProcessMonitor(threading.Thread):
    """Background sampler for a subprocess + its child tree.

    Spawned by the worker right after ``subprocess.Popen()``. Polls every
    ``poll_interval`` seconds and appends an :class:`IlSample` to an internal
    bounded ``deque``. The worker calls :meth:`take_samples_snapshot` when it
    needs to classify, and :meth:`shutdown` to terminate the thread.

    Memory bound: ``maxlen = ceil(window_seconds / poll_interval) * 2`` so we
    always have at least one full window's worth of samples even mid-poll.
    """

    def __init__(
        self,
        pid: int,
        log_path: Path,
        *,
        poll_interval: float = DEFAULT_POLL_INTERVAL,
        window_seconds: float = 10.0,
    ) -> None:
        # daemon=True belongs here, not as a class attribute shadowing the
        # Thread property (A2-JT-012: it worked, but left _daemonic stale).
        super().__init__(name=f"il-monitor-{pid}", daemon=True)
        if not _HAS_PSUTIL:
            msg = (
                "ProcessMonitor requires psutil. Install with `uv add psutil` "
                "or set [tool.mutmut].infinite_loop_detection = false."
            )
            raise RuntimeError(msg)
        self._pid = pid
        self._log_path = log_path
        self._poll_interval = poll_interval
        self._window_seconds = window_seconds
        maxlen = max(4, int(window_seconds / poll_interval) * 2)
        self._samples: deque[IlSample] = deque(maxlen=maxlen)
        self._stop_event = threading.Event()
        # Bind the psutil.Process lazily — the pid may not be observable yet
        # at __init__ time on some platforms. Typed as Any because psutil's
        # type stubs are optional / not installed in our CI matrix.
        self._proc: Any = None
        # Cache of psutil.Process instances keyed by pid.
        #
        # CRITICAL psutil contract: cpu_percent(interval=None) returns a
        # meaningful value only on the SECOND-and-later call against a given
        # ``Process`` *instance*. The state lives on the instance, not on the
        # pid. ``Process.children()`` returns *new* ``Process`` objects on
        # every call, so re-creating them would reset the cpu_times baseline
        # on every sample and always return 0.0 — a critical bug that breaks
        # IL detection for the canonical Windows case where
        # ``subprocess.Popen([python, "-c", "while True: pass"])`` wraps the
        # real interpreter as a child (the busy loop lives in the child).
        #
        # We therefore cache the ``Process`` instance per pid for the
        # lifetime of the monitor, re-use it for every sample, and only
        # discard it when the process disappears.
        self._proc_cache: dict[int, Any] = {}
        # Exceptions survived by the sampling loop (A2-JT-011) — surfaced via
        # the forensics so a degraded observation is never silent.
        self._sampler_errors = 0

    # ---------------------------------------------------------------- public

    @property
    def sampler_errors(self) -> int:
        """Number of unexpected exceptions the sampling loop survived."""
        return self._sampler_errors

    def take_samples_snapshot(self) -> list[IlSample]:
        """Return a snapshot of the samples deque (last full window).

        The cutoff is anchored to the LAST sample, not to ``now``: the worker
        kills the subprocess and reads the log before classifying, and that
        latency used to silently shrink the effective window (A2-JT-014).
        """
        all_samples = list(self._samples)
        if not all_samples:
            return []
        cutoff = all_samples[-1].timestamp - self._window_seconds
        return [s for s in all_samples if s.timestamp >= cutoff]

    def shutdown(self, timeout: float = 1.0) -> None:
        """Signal the thread to stop and join (bounded by *timeout*)."""
        self._stop_event.set()
        self.join(timeout=timeout)

    # ----------------------------------------------------- threading.Thread

    def run(self) -> None:
        if psutil is None:  # pragma: no cover - guarded at __init__
            return
        try:
            self._proc = psutil.Process(self._pid)
            # Prime the parent — first cpu_percent returns 0.0, see _proc_cache.
            self._proc.cpu_percent(interval=None)
            self._proc_cache[self._pid] = self._proc
        except psutil.NoSuchProcess:
            return  # subprocess gone already — nothing to sample

        while not self._stop_event.is_set():
            try:
                sample = self._take_sample()
                if sample is not None:
                    self._samples.append(sample)
            except Exception:  # the sampler must survive any glitch
                # A2-JT-011: one bad tick must not end the whole observation.
                # The count reaches the forensics via the worker, so degraded
                # sampling is auditable instead of silently becoming
                # "timeout/low for every mutant from here on".
                self._sampler_errors += 1
            # event.wait returns True if set, False on timeout
            if self._stop_event.wait(self._poll_interval):
                break

    # ---------------------------------------------------------------- inner

    def _take_sample(self) -> IlSample | None:
        if self._proc is None or psutil is None:
            return None
        try:
            # cpu_percent over the interval since the previous call. We must
            # accumulate the parent + its full descendant tree because:
            # 1) Windows wraps subprocess.Popen([python, ...]) in a launcher
            #    that itself uses 0% CPU; the real Python interpreter (and
            #    therefore the busy loop we are trying to detect) lives in a
            #    child process.
            # 2) pytest's --forked / xdist plugins spawn their own children.
            cpu = self._cached_cpu_percent(self._proc)
            io_ops = self._io_ops(self._proc)
            try:
                live_pids: set[int] = {self._pid}
                for child in self._proc.children(recursive=True):
                    cpu += self._cached_cpu_percent(child)
                    child_io = self._io_ops(child)
                    if child_io is not None:
                        io_ops = child_io if io_ops is None else io_ops + child_io
                    live_pids.add(child.pid)
                # Drop cached processes that have exited so the dict doesn't
                # grow without bound during long runs.
                self._proc_cache = {
                    pid: p for pid, p in self._proc_cache.items() if pid in live_pids
                }
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
            status_value = self._proc.status()
            status = str(status_value)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return None
        try:
            output_bytes: int | None = self._log_path.stat().st_size
        except OSError:
            # Missing data, not "output stagnated" — clamping to 0 was a
            # pro-IL bias (A2-JT-015). The classifier skips None samples.
            output_bytes = None
        return IlSample(
            timestamp=time.monotonic(),
            cpu_pct=cpu,
            output_bytes=output_bytes,
            status=status,
            io_ops=io_ops,
        )

    @staticmethod
    def _io_ops(proc: Any) -> int | None:
        """Total io_counters operations for *proc*, or ``None`` if unavailable.

        io_counters is stateless (unlike cpu_percent — no instance caching
        needed) but platform-limited: absent on macOS, and individual reads
        can fail with AccessDenied. Missing data stays ``None`` so the
        classifier treats it as neutral (spike #89).
        """
        if psutil is None:  # pragma: no cover - guarded at run()
            return None
        try:
            io = proc.io_counters()
        except (psutil.Error, AttributeError, NotImplementedError, OSError):
            return None
        return int(io.read_count + io.write_count + getattr(io, "other_count", 0))

    def _cached_cpu_percent(self, proc: Any) -> float:
        """Re-use a cached ``Process`` instance for ``proc.pid`` and read its CPU%.

        psutil's ``Process.children()`` returns *new* ``Process`` objects on
        every call. cpu_percent's comparison baseline lives on the instance,
        so a fresh instance always returns 0.0 (the documented first-call
        rule). We therefore look up the pid in ``self._proc_cache`` and:

        - **hit**: reuse the cached instance → ``cpu_percent(interval=None)``
          returns a real percentage since the previous sample
        - **miss**: store the new instance, prime it once (cpu_percent returns
          0.0), and return 0.0 — the next sample for this pid will be real
        """
        if psutil is None:  # pragma: no cover - guarded at run()
            return 0.0
        try:
            pid = proc.pid
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return 0.0
        cached = self._proc_cache.get(pid)
        if cached is None:
            # First time we see this pid — prime the instance and return 0.0.
            self._proc_cache[pid] = proc
            with contextlib.suppress(psutil.NoSuchProcess, psutil.AccessDenied):
                proc.cpu_percent(interval=None)
            return 0.0
        try:
            return float(cached.cpu_percent(interval=None))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            self._proc_cache.pop(pid, None)
            return 0.0
