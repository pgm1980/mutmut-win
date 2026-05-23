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
import tempfile
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from mutmut_win.models import MutationTask, TaskCompleted, TaskStarted

if TYPE_CHECKING:
    import multiprocessing.queues

#: Environment variable checked by mutmut's trampoline to activate a mutant.
MUTANT_ENV_VAR = "MUTANT_UNDER_TEST"

#: Maximum number of pytest output lines to capture on timeout/suspicious.
_MAX_DIAGNOSTIC_LINES: int = 50


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
    pytest_extra_args: list[str] = []
    raw_extra = config_data.get("pytest_add_cli_args")
    if isinstance(raw_extra, list):
        pytest_extra_args = [str(a) for a in raw_extra]

    # Per-mutant timeout: generous default (60s), prevents hung pytest processes
    # (e.g. pytest-asyncio event loop corruption) from blocking the pool forever.
    raw_timeout = config_data.get("timeout_multiplier", 30.0)
    timeout_val = float(raw_timeout) if isinstance(raw_timeout, (int, float)) else 60.0
    worker_timeout = max(60.0, timeout_val)

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
            _process_task(
                raw_item, event_queue, pid, pytest_extra_args, config_data, worker_timeout
            )
        except Exception as exc:  # Bug #12 recovery: keep the worker alive
            # Any uncaught exception (Pydantic ValidationError, RuntimeError from
            # the subprocess layer, libcst hiccup, transient FS error, …) would
            # otherwise kill the worker mid-task. The orchestrator would then
            # hang in get_events() waiting for a TaskCompleted that will never
            # arrive. Emit a synthetic completion so progress can be made, and
            # continue the loop.
            print(
                f"WORKER RECOVERY (#12): uncaught {type(exc).__name__} on "
                f"{fallback_name}: {exc}",
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
    worker_timeout: float,
) -> None:
    """Process a single mutation task.

    Extracted from the main loop so ``worker_main`` can catch any exception
    that bubbles up from here and synthesise a recovery event (Bug #12).
    """
    task = MutationTask.model_validate(raw_item)

    # Notify main process that work has started.
    event_queue.put(TaskStarted(mutant_name=task.mutant_name, worker_pid=pid).model_dump())

    # Build the pytest command.
    cmd: list[str] = ["pytest", "--tb=no", "-q"]
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
        env["PYTHONPATH"] = os.pathsep.join(
            pythonpath_dirs + ([existing] if existing else [])
        )
    env[MUTANT_ENV_VAR] = task.mutant_name

    # Redirect stdout+stderr to a temp file instead of PIPE or DEVNULL.
    # - PIPE deadlocks on Windows when grandchild processes inherit handles
    # - DEVNULL loses diagnostic output needed for timeout investigation
    # - Temp files: no deadlock (no pipe EOF semantics), output preserved
    log_fd, log_path_str = tempfile.mkstemp(
        suffix=".log", prefix="mutmut_out_", dir="mutants", text=True,
    )
    log_path = Path(log_path_str)
    last_output: str | None = None
    forensics_dict: dict[str, object] | None = None
    exit_code: int = 35  # default to suspicious so the finally clause is safe

    # ---- IL-detection setup (Issue #71, Sprint 26) ---------------------
    il_enabled = bool(config_data.get("infinite_loop_detection", True))
    il_thresholds = _build_il_thresholds(config_data)
    monitor: Any = None  # ProcessMonitor or None — Any avoids loop_monitor import

    start = time.monotonic()
    proc: subprocess.Popen[bytes] | None = None
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
        )
        monitor = _maybe_start_loop_monitor(il_enabled, proc.pid, log_path)
        try:
            exit_code = proc.wait(timeout=worker_timeout)
        except subprocess.TimeoutExpired:
            # Kill the still-running subprocess (and its children via Job Object
            # if available) before sampling so the classifier sees the final
            # state of the rolling window.
            _kill_proc_tree(proc)
            os.close(log_fd)
            log_fd = -1
            last_output = _read_last_lines(log_path, _MAX_DIAGNOSTIC_LINES)
            if monitor is not None:
                samples = monitor.take_samples_snapshot()
                classification = _classify_with_monitor(samples, il_thresholds, last_output)
                if classification.verdict == "killed_by_infinite_loop":
                    exit_code = 38  # EXIT_CODE_INFINITE_LOOP — kill-bucket
                    forensics_dict = classification.forensics.model_dump()
                    forensics_dict["confidence"] = classification.confidence
                else:
                    exit_code = 36  # timeout
                    # Persist forensics even on plain timeout so the user can see
                    # why the classifier said "not IL".
                    forensics_dict = classification.forensics.model_dump()
                    forensics_dict["confidence"] = classification.confidence
            else:
                exit_code = 36  # timeout (no detection available)
    except OSError as exc:
        print(f"WORKER ERROR for {task.mutant_name}: {exc}", flush=True)
        exit_code = 35  # suspicious
    finally:
        if monitor is not None:
            with contextlib.suppress(Exception):
                monitor.shutdown()
        if log_fd >= 0:
            os.close(log_fd)
        # Read diagnostics for suspicious exits (if not already read).
        if exit_code == 35 and last_output is None:
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


def _read_last_lines(path: Path, n: int) -> str | None:
    """Read the last *n* lines from *path*, returning None on failure."""
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    lines = content.splitlines()
    return "\n".join(lines[-n:]) if lines else None


# ---------------------------------------------------------------------------
# IL-detection helpers (Issue #71, Sprint 26)
# ---------------------------------------------------------------------------


def _maybe_start_loop_monitor(
    enabled: bool, pid: int, log_path: Path
) -> Any:
    """Try to spawn an IL-detection monitor; return ``None`` on opt-out / failure.

    Failures here MUST NEVER take down the worker — IL detection is best-effort
    enhancement. psutil missing, permission denied on the PID, or any other
    error degrades gracefully to "no detection, plain timeout".
    """
    if not enabled:
        return None
    try:
        from mutmut_win.process.loop_monitor import ProcessMonitor, has_psutil

        if not has_psutil():
            return None
        monitor = ProcessMonitor(pid=pid, log_path=log_path)
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
) -> Any:
    """Lazy-import classifier indirection — keeps loop_monitor optional in tests."""
    from mutmut_win.process.loop_monitor import classify_samples

    return classify_samples(samples, thresholds, last_output_tail=last_output)  # type: ignore[arg-type,unused-ignore]


def _kill_proc_tree(proc: subprocess.Popen[bytes]) -> None:
    """Terminate the subprocess (and its child tree if psutil is around)."""
    if proc.poll() is not None:
        return
    try:
        from mutmut_win.process.loop_monitor import has_psutil

        if has_psutil():
            import psutil  # type: ignore[import-untyped,unused-ignore]

            try:
                parent = psutil.Process(proc.pid)
                for child in parent.children(recursive=True):
                    with contextlib.suppress(psutil.NoSuchProcess, psutil.AccessDenied):
                        child.kill()
            except psutil.NoSuchProcess:
                pass
    except ImportError:
        pass
    with contextlib.suppress(Exception):
        proc.kill()
    with contextlib.suppress(Exception):
        proc.wait(timeout=2.0)
