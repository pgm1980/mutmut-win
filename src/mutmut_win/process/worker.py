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
from typing import TYPE_CHECKING

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
        extra_paths = []
        for subdir in ["src", "source", "."]:
            candidate = Path("mutants") / subdir
            if candidate.exists():
                extra_paths.append(str(candidate.absolute()))
        if extra_paths:
            existing = env.get("PYTHONPATH", "")
            env["PYTHONPATH"] = os.pathsep.join(extra_paths + ([existing] if existing else []))
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

        start = time.monotonic()
        try:
            result = subprocess.run(  # noqa: S603  # command is fully controlled — no user input
                cmd,
                env=env,
                stdout=log_fd,
                stderr=subprocess.STDOUT,
                cwd="mutants",
                timeout=worker_timeout,
            )
            exit_code = result.returncode
        except subprocess.TimeoutExpired:
            exit_code = 36  # timeout
            # Read last lines for diagnostics before cleanup.
            os.close(log_fd)
            log_fd = -1
            last_output = _read_last_lines(log_path, _MAX_DIAGNOSTIC_LINES)
        except OSError as exc:
            print(f"WORKER ERROR for {task.mutant_name}: {exc}", flush=True)
            exit_code = 35  # suspicious
        finally:
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
