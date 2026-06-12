"""Worker entry point that runs in spawned child processes.

Each worker loops over a task_queue, runs pytest in a subprocess for each
MutationTask, and sends TaskStarted / TaskCompleted events back through
the event_queue.  A ``None`` sentinel value in the task_queue signals the
worker to exit cleanly.
"""

from __future__ import annotations

import contextlib
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from mutmut_win.constants import EXIT_CODE_INFINITE_LOOP, EXIT_CODE_TIMEOUT

# Explicit re-export for BWC — single source of truth: constants (#110).
from mutmut_win.constants import MUTANT_ENV_VAR as MUTANT_ENV_VAR
from mutmut_win.models import MutationTask, TaskCompleted, TaskStarted

if TYPE_CHECKING:
    import multiprocessing.queues

#: Maximum number of pytest output lines to capture on timeout/suspicious.
_MAX_DIAGNOSTIC_LINES: int = 50

#: Exit codes whose outcome needs no diagnostic log tail: clean survive (0),
#: regular kill (1), no tests (5/33), skipped (34). Everything else —
#: collection errors (2), pytest internal errors (3), suspicious (35),
#: crashes (NTSTATUS) — gets its last output captured (issue #91).
_QUIET_EXIT_CODES: frozenset[int] = frozenset({0, 1, 5, 33, 34})


def _suppress_windows_error_dialogs() -> None:
    """Keep WerFault from holding crashing pytest children (issue #123).

    External QA WIN-001 (code-evidenced): on interactive Windows hosts with
    WER UI enabled, a hard-crashing mutant (access violation, stack
    overflow) can stall on the Windows Error Reporting dialog past the
    task's wall-clock budget — the job object then reaps the tree and the
    mutant is misclassified ``timeout`` instead of ``segfault``.
    ``SetErrorMode`` is inherited by child processes, so crashes return
    immediately as NTSTATUS exit codes. POSIX: no-op.
    """
    if sys.platform != "win32":
        return
    import ctypes

    sem_failcriticalerrors = 0x0001
    sem_nogpfaulterrorbox = 0x0002
    with contextlib.suppress(Exception):  # never let dialog hygiene kill a worker
        kernel32 = ctypes.windll.kernel32
        current = kernel32.GetErrorMode()
        kernel32.SetErrorMode(current | sem_failcriticalerrors | sem_nogpfaulterrorbox)


def worker_main(
    task_queue: multiprocessing.queues.Queue[dict[str, object] | None],
    event_queue: multiprocessing.queues.Queue[dict[str, object]],
    config_data: dict[str, object],
) -> None:
    """Main loop executed in each spawned worker process.

    Pulls ``MutationTask`` objects from *task_queue*, runs pytest in a
    subprocess for the mutant under test, and sends domain events back via
    *event_queue*.  Exits when it receives the ``None`` sentinel.

    Args:
        task_queue: Queue from which ``MutationTask`` dicts (or ``None``) are
            consumed.  Items are serialised dicts to guarantee pickle safety.
        event_queue: Queue into which ``TaskStarted`` and ``TaskCompleted``
            events are placed.
        config_data: Serialised ``MutmutConfig`` as a plain ``dict``.  Using a
            dict instead of the Pydantic model avoids any potential pickle
            incompatibility across process boundaries.
    """
    pid = os.getpid()
    # Once per worker process — children inherit the error mode (issue #123
    # / external QA WIN-001).
    _suppress_windows_error_dialogs()
    pytest_extra_args: list[str] = []
    raw_extra = config_data.get("pytest_add_cli_args")
    if isinstance(raw_extra, list):
        pytest_extra_args = [str(a) for a in raw_extra]

    while True:
        raw_item = task_queue.get()
        if raw_item is None:
            # Sentinel: no more tasks — exit cleanly.
            break

        # Best-effort extract mutant_name from the raw dict so we can still
        # report something useful if validation itself blows up.
        fallback_name = "unknown"
        if isinstance(raw_item, dict):
            raw_name = raw_item.get("mutant_name")
            if isinstance(raw_name, str) and raw_name:
                fallback_name = raw_name

        try:
            _process_task(raw_item, event_queue, pid, pytest_extra_args, config_data)
        except Exception as exc:  # Bug #12 recovery: keep the worker alive
            # Any uncaught exception (Pydantic ValidationError, RuntimeError from
            # the subprocess layer, libcst hiccup, transient FS error, …) would
            # otherwise kill the worker mid-task. The orchestrator would then
            # hang in get_events() waiting for a TaskCompleted that will never
            # arrive. Emit a synthetic completion so progress can be made, and
            # continue the loop.
            print(
                f"WORKER RECOVERY (#12): uncaught {type(exc).__name__} on {fallback_name}: {exc}",
                flush=True,
            )
            event_queue.put(
                TaskCompleted(
                    mutant_name=fallback_name,
                    worker_pid=pid,
                    exit_code=35,  # suspicious
                    duration=0.0,
                    last_output=f"Worker recovery (Bug #12): {type(exc).__name__}: {exc}",
                ).model_dump()
            )


def _process_task(
    raw_item: dict[str, object],
    event_queue: multiprocessing.queues.Queue[dict[str, object]],
    pid: int,
    pytest_extra_args: list[str],
    config_data: dict[str, object],
) -> None:
    """Process a single mutation task.

    Extracted from the main loop so ``worker_main`` can catch any exception
    that bubbles up from here and synthesise a recovery event (Bug #12).
    """
    task = MutationTask.model_validate(raw_item)
    # Per-task budget computed by the orchestrator (estimated runtime of the
    # assigned tests times timeout_multiplier, floor 5 s).  Before issue #81 /
    # A2-JT-003 the worker ignored it and used max(60, timeout_multiplier) —
    # the MULTIPLIER acted as flat absolute seconds for every task.
    timeout_seconds = task.timeout_seconds

    # Notify main process that work has started.
    event_queue.put(TaskStarted(mutant_name=task.mutant_name, worker_pid=pid).model_dump())

    # Build the pytest command.
    cmd: list[str] = _pytest_base_cmd()
    cmd.extend(pytest_extra_args)

    # Always use pytest's @file syntax for test arguments.
    # This avoids the Windows CreateProcess 32767-char command line limit
    # (WinError 206) regardless of how many tests are assigned — no magic
    # thresholds, no dual code paths, predictable behavior at any scale.
    # pytest reads arguments from the file, one per line.
    tests_argfile: Path | None = None
    if task.tests:
        fd, argfile_path = tempfile.mkstemp(
            suffix=".txt",
            prefix="mutmut_tests_",
            dir="mutants",
            text=True,
        )
        tests_argfile = Path(argfile_path)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            for test in task.tests:
                f.write(test + "\n")
        cmd.append(f"@{tests_argfile.name}")
    else:
        # No specific tests assigned — use tests_dir from config if available.
        raw_tests_dir = config_data.get("tests_dir")
        if isinstance(raw_tests_dir, list):
            cmd.extend(str(d) for d in raw_tests_dir)

    # Activate the specific mutant via the trampoline env var.
    # Set PYTHONPATH so subprocess can import from mutants/src etc.
    env = os.environ.copy()
    pythonpath_dirs: list[str] = []
    for subdir in ["src", "source", "."]:
        candidate = Path("mutants") / subdir
        if candidate.exists():
            pythonpath_dirs.append(str(candidate.absolute()))
    # Bug #69: extra_paths from config map to mutants/<extra_path> and must be
    # on PYTHONPATH so sibling-package imports resolve inside the mutants venv.
    raw_extra_paths = config_data.get("extra_paths", [])
    if isinstance(raw_extra_paths, list):
        for extra in raw_extra_paths:
            extra_path = Path("mutants") / str(extra)
            if extra_path.exists():
                pythonpath_dirs.append(str(extra_path.absolute()))
    if pythonpath_dirs:
        existing = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = os.pathsep.join(pythonpath_dirs + ([existing] if existing else []))
    env[MUTANT_ENV_VAR] = task.mutant_name
    # Unbuffered stdout/stderr for the whole subprocess tree: with block
    # buffering the log's st_size froze at 0 while the suite made progress,
    # blinding the IL classifier's output signal (issue #88 / A2-JT-002).
    env["PYTHONUNBUFFERED"] = "1"
    # Same env truth as every runner phase (issue #111 / A2-RN-012): the
    # copied test modules in mutants/ keep their original basenames, and
    # pytest's import-mismatch check would reject them via stale __pycache__.
    env["PY_IGNORE_IMPORTMISMATCH"] = "1"

    # Redirect stdout+stderr to a temp file instead of PIPE or DEVNULL.
    # - PIPE deadlocks on Windows when grandchild processes inherit handles
    # - DEVNULL loses diagnostic output needed for timeout investigation
    # - Temp files: no deadlock (no pipe EOF semantics), output preserved
    log_fd, log_path_str = tempfile.mkstemp(
        suffix=".log",
        prefix="mutmut_out_",
        dir="mutants",
        text=True,
    )
    log_path = Path(log_path_str)
    last_output: str | None = None
    forensics_dict: dict[str, object] | None = None
    exit_code: int = 35  # default to suspicious so the finally clause is safe

    # ---- IL-detection setup (Issue #71, Sprint 26) ---------------------
    il_enabled = bool(config_data.get("infinite_loop_detection", True))
    il_thresholds = _build_il_thresholds(config_data)
    monitor: Any = None  # ProcessMonitor or None — Any avoids loop_monitor import
    # The window-vs-timeout configuration hint (A2-JT-018) is emitted by the
    # orchestrator, once per RUN — a per-worker guard meant N-fold spam on
    # N worker processes (issue #110 / DOG-002).

    start = time.monotonic()
    proc: subprocess.Popen[bytes] | None = None
    task_job_handle: int | None = None
    try:
        # Popen + wait(timeout) so we can attach the monitor against a live PID
        # and run our classifier on timeout. (subprocess.run cannot expose the
        # PID until after the call returns.)
        proc = subprocess.Popen(  # noqa: S603 - command is fully controlled
            cmd,
            env=env,
            stdout=log_fd,
            stderr=subprocess.STDOUT,
            cwd="mutants",
            # No console window for the pytest child (issue #123 / WIN-001);
            # 0 on POSIX where the attribute does not exist.
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        # Per-task kill-on-close job (issue #82 / A2-EW-008): descendants
        # inherit membership at creation, so closing the handle reaps the
        # whole pytest tree — even across already-dead intermediates, which
        # a live-pid sweep cannot bridge (uv launcher chains showed exactly
        # that).
        task_job_handle = _create_task_job(proc.pid)
        monitor = _maybe_start_loop_monitor(
            il_enabled, proc.pid, log_path, window_seconds=il_thresholds.window_seconds
        )
        try:
            exit_code = proc.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            # Kill the still-running subprocess tree before sampling so the
            # classifier sees the final state of the rolling window.
            _kill_proc_tree(proc, task_job_handle)
            task_job_handle = None  # consumed (closed) by the kill
            # Snapshot BEFORE the log read (A2-JT-014): the snapshot is a pure
            # deque copy, while the tail read can take long enough to matter.
            samples = monitor.take_samples_snapshot() if monitor is not None else []
            os.close(log_fd)
            log_fd = -1
            last_output = _read_last_lines(log_path, _MAX_DIAGNOSTIC_LINES)
            if monitor is not None:
                classification = _classify_with_monitor(
                    samples,
                    il_thresholds,
                    last_output,
                    status_signal_available=sys.platform != "win32",
                    sampler_errors=monitor.sampler_errors,
                )
                if classification.verdict == "killed_by_infinite_loop":
                    exit_code = EXIT_CODE_INFINITE_LOOP
                    forensics_dict = classification.forensics.model_dump()
                    forensics_dict["confidence"] = classification.confidence
                else:
                    exit_code = EXIT_CODE_TIMEOUT
                    # Persist forensics even on plain timeout so the user can see
                    # why the classifier said "not IL".
                    forensics_dict = classification.forensics.model_dump()
                    forensics_dict["confidence"] = classification.confidence
            else:
                exit_code = EXIT_CODE_TIMEOUT  # no detection available
    except OSError as exc:
        print(f"WORKER ERROR for {task.mutant_name}: {exc}", flush=True)
        exit_code = 35  # suspicious
    finally:
        if task_job_handle is not None:
            # Normal completion: closing the kill-on-close job reaps any
            # background processes the tests left behind (issue #82).
            with contextlib.suppress(Exception):
                from mutmut_win.process.job_object import close_job

                close_job(task_job_handle)
        if monitor is not None:
            with contextlib.suppress(Exception):
                monitor.shutdown()
        if log_fd >= 0:
            os.close(log_fd)
        # Read diagnostics for every anomalous exit (if not already read by
        # the timeout path). Issue #91: exit 2 is a collection-error kill and
        # NTSTATUS codes are crashes — their forensics ARE the pytest output;
        # only the quiet outcomes (survived/killed/no-tests/skipped) carry no
        # diagnostic value.
        if exit_code not in _QUIET_EXIT_CODES and last_output is None:
            last_output = _read_last_lines(log_path, _MAX_DIAGNOSTIC_LINES)
        with contextlib.suppress(OSError):
            log_path.unlink()
        if tests_argfile is not None and tests_argfile.exists():
            with contextlib.suppress(OSError):
                tests_argfile.unlink()

    duration = time.monotonic() - start

    event_queue.put(
        TaskCompleted(
            mutant_name=task.mutant_name,
            worker_pid=pid,
            exit_code=exit_code,
            duration=duration,
            last_output=last_output,
            forensics=forensics_dict,
        ).model_dump()
    )


#: Tail block size for diagnostic log reads — generously covers
#: ``_MAX_DIAGNOSTIC_LINES`` even with very long lines.
_TAIL_READ_BYTES: int = 64 * 1024


def _read_last_lines(path: Path, n: int) -> str | None:
    """Tail-read the last *n* lines from *path*, returning None on failure.

    Reads only the final block of the file (issue #81 / A2-EW-014):
    ``read_text`` loaded output-runaway mutant logs fully into memory,
    risking MemoryError right inside the diagnostic path.
    """
    try:
        with path.open("rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            block = min(size, _TAIL_READ_BYTES)
            f.seek(size - block)
            data = f.read(block)
    except OSError:
        return None
    lines = data.decode("utf-8", errors="replace").splitlines()
    return "\n".join(lines[-n:]) if lines else None


# ---------------------------------------------------------------------------
# IL-detection helpers (Issue #71, Sprint 26)
# ---------------------------------------------------------------------------


def _maybe_start_loop_monitor(
    enabled: bool, pid: int, log_path: Path, window_seconds: float = 10.0
) -> Any:
    """Try to spawn an IL-detection monitor; return ``None`` on opt-out / failure.

    Failures here MUST NEVER take down the worker — IL detection is best-effort
    enhancement. psutil missing, permission denied on the PID, or any other
    error degrades gracefully to "no detection, plain timeout".

    *window_seconds* carries the configured ``infinite_loop_window_seconds``
    through to the sampler — previously the monitor was hard-wired to its
    10 s default while the forensics claimed the configured value
    (issue #81 / A2-EW-009).
    """
    if not enabled:
        return None
    try:
        from mutmut_win.process.loop_monitor import ProcessMonitor, has_psutil

        if not has_psutil():
            return None
        monitor = ProcessMonitor(pid=pid, log_path=log_path, window_seconds=window_seconds)
        monitor.start()
    except Exception as exc:  # graceful degradation: never poison the run
        print(f"WORKER MONITOR start failed: {exc}", flush=True)
        return None
    return monitor


def _build_il_thresholds(config_data: dict[str, object]) -> Any:
    """Build an :class:`IlThresholds` from the worker's config dict.

    Lazy-imported so that workers can avoid the loop_monitor module entirely
    when IL detection is disabled (one less code path loaded under the GIL).
    """
    from mutmut_win.process.loop_monitor import IlThresholds

    def _coerce_float(key: str, default: float) -> float:
        v = config_data.get(key, default)
        try:
            return float(v) if isinstance(v, (int, float)) else default
        except (TypeError, ValueError):
            return default

    def _coerce_int(key: str, default: int) -> int:
        v = config_data.get(key, default)
        try:
            return int(v) if isinstance(v, (int, float)) else default
        except (TypeError, ValueError):
            return default

    return IlThresholds(
        cpu_threshold=_coerce_float("infinite_loop_cpu_threshold", 70.0),
        output_threshold=_coerce_int("infinite_loop_output_threshold", 1024),
        running_ratio=_coerce_float("infinite_loop_running_ratio", 0.8),
        window_seconds=_coerce_float("infinite_loop_window_seconds", 10.0),
    )


def _classify_with_monitor(
    samples: Any,
    thresholds: Any,
    last_output: str | None,
    *,
    status_signal_available: bool = True,
    sampler_errors: int = 0,
) -> Any:
    """Lazy-import classifier indirection — keeps loop_monitor optional in tests."""
    from mutmut_win.process.loop_monitor import classify_samples

    return classify_samples(  # type: ignore[arg-type,unused-ignore]
        samples,
        thresholds,
        last_output_tail=last_output,
        status_signal_available=status_signal_available,
        sampler_errors=sampler_errors,
    )


def _pytest_base_cmd() -> list[str]:
    """Pytest invocation pinned to the running interpreter (issue #82 / A4-QX-008).

    Bare ``"pytest"`` resolved via PATH could hit a different interpreter
    than the venv the clean gate validated (a non-activated venv produced
    exit-35 floods despite a green clean run); ``sys.executable -m pytest``
    matches what the runner phases use.
    """
    return [sys.executable, "-m", "pytest", "--tb=no", "-q"]


def _create_task_job(pid: int) -> int | None:
    """Best-effort per-task Windows Job Object (issue #82 / A2-EW-008).

    Returns the job handle with *pid* assigned, or ``None`` off-win32 or
    when creation/assignment fails (graceful degradation to the psutil
    sweep).  The micro window between ``Popen`` and assignment is the
    documented EW-018 race — pytest does not spawn children that fast.
    """
    if sys.platform != "win32":
        return None
    try:
        from mutmut_win.process.job_object import (
            assign_process_to_job,
            close_job,
            create_kill_on_close_job,
        )

        handle = create_kill_on_close_job()
    except (OSError, RuntimeError):
        return None
    try:
        assign_process_to_job(handle, pid)
    except (OSError, RuntimeError):
        with contextlib.suppress(Exception):
            close_job(handle)
        return None
    return handle


def _iter_descendants(root_pid: int) -> list[Any]:
    """Collect live descendant processes of *root_pid* by walking ppids.

    Unlike ``psutil.Process(root_pid).children(recursive=True)`` this also
    works when the root itself ALREADY EXITED (issue #82 / A2-EW-008):
    Windows does not re-parent orphans, so their recorded ppid keeps
    pointing at the dead pid.  Minor caveat: if the dead pid is recycled
    very quickly, an unrelated process tree could match — the window is
    milliseconds wide and the previous behaviour (orphans surviving until
    job-object close) was strictly worse.
    """
    import psutil  # type: ignore[import-untyped,unused-ignore]

    children_by_ppid: dict[int, list[Any]] = {}
    for proc in psutil.process_iter(["pid", "ppid"]):
        with contextlib.suppress(psutil.NoSuchProcess, psutil.AccessDenied):
            children_by_ppid.setdefault(proc.info["ppid"], []).append(proc)

    descendants: list[Any] = []
    pending = [root_pid]
    seen: set[int] = set()
    while pending:
        current = pending.pop()
        for child in children_by_ppid.get(current, []):
            if child.pid in seen:
                continue
            seen.add(child.pid)
            descendants.append(child)
            pending.append(child.pid)
    return descendants


def _kill_proc_tree(proc: subprocess.Popen[bytes], job_handle: int | None = None) -> None:
    """Terminate the subprocess AND its descendant tree.

    Primary mechanism (win32): closing the per-task kill-on-close
    *job_handle* makes the kernel reap the whole tree atomically — including
    across already-dead intermediate processes, which no live-pid scan can
    bridge (issue #82 / A2-EW-008).  The psutil ppid sweep below remains as
    belt-and-suspenders for non-win32 platforms and job failures; it runs
    even when the direct child already exited (the old code returned early
    and orphaned the grandchildren until the END of the whole run).  Two
    sweeps narrow the TOCTOU window for processes spawned mid-kill.
    """
    if job_handle is not None:
        with contextlib.suppress(Exception):
            from mutmut_win.process.job_object import close_job

            close_job(job_handle)

    use_psutil = False
    try:
        from mutmut_win.process.loop_monitor import has_psutil

        use_psutil = has_psutil()
    except ImportError:
        pass

    if use_psutil:
        import psutil  # type: ignore[import-untyped,unused-ignore]

        for _sweep in range(2):
            for child in _iter_descendants(proc.pid):
                with contextlib.suppress(psutil.NoSuchProcess, psutil.AccessDenied):
                    child.kill()
            if proc.poll() is None:
                with contextlib.suppress(Exception):
                    proc.kill()

    with contextlib.suppress(Exception):
        proc.kill()
    with contextlib.suppress(Exception):
        proc.wait(timeout=2.0)
