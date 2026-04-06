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
import time
from pathlib import Path
from typing import TYPE_CHECKING

from mutmut_win.models import MutationTask, TaskCompleted, TaskStarted

if TYPE_CHECKING:
    import multiprocessing.queues

#: Environment variable checked by mutmut's trampoline to activate a mutant.
MUTANT_ENV_VAR = "MUTANT_UNDER_TEST"


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

        # Windows CreateProcess has a 32767-char command line limit.
        # When a mutant has many assigned tests, passing them all as args
        # exceeds this limit → WinError 206. Use pytest's @file syntax:
        # pytest @testlist.txt reads arguments from a file, one per line.
        # Threshold: if the joined test list would exceed 8000 chars (leaves
        # plenty of headroom for PYTHONPATH + other args), write to a file.
        tests_argfile: Path | None = None
        if task.tests:
            total_len = sum(len(t) + 1 for t in task.tests)
            if total_len > 8000:
                # Too many tests for the command line — use @file syntax.
                import tempfile

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
                # pytest accepts @file for argument-file loading
                cmd.append(f"@{tests_argfile.name}")
            else:
                cmd.extend(task.tests)
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

        start = time.monotonic()
        try:
            # Run pytest inside mutants/ so it imports the trampolined code.
            result = subprocess.run(  # noqa: S603  # command is fully controlled — no user input
                cmd,
                env=env,
                capture_output=True,
                encoding="utf-8",
                cwd="mutants",
            )
            exit_code = result.returncode
        except OSError as exc:
            # WinError 206 / ENAMETOOLONG: command line too long even with @file.
            # Report as suspicious (exit code 35) so the orchestrator doesn't crash.
            print(f"WORKER ERROR for {task.mutant_name}: {exc}", flush=True)
            exit_code = 35  # suspicious
        finally:
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
            ).model_dump()
        )
