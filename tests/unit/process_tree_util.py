"""Process-tree test helpers (remediation AP-00 / Q-04).

Deterministic observation primitives for Windows process trees used by the
containment and infinite-loop regression tests:

- :func:`wait_for_pid_file` — deadline-bounded wait for an atomically
  published PID file (no fixed sleeps, no unbounded reads),
- :func:`write_pid_file_snippet` — the matching child-side snippet that
  publishes ``os.getpid()`` atomically,
- :func:`tree_handles` — ``psutil`` handles for a root process and all of
  its descendants,
- :func:`tree_cpu_seconds` — summed CPU seconds over such handles,
- :func:`assert_tree_terminated` — deadline-bounded assertion that every
  handle is gone, failing with the list of survivors.

Background: ``sys.executable`` is the venv launcher; the working interpreter
is its child, so observing the *leaf* via ``os.getpid()`` inside a child
script is mandatory. All waits use ``time.monotonic()`` deadlines; every
failure surfaces as ``AssertionError``/``pytest.fail`` instead of hanging.

Consumers are the regression tests for M-139, M-140, M-004, M-009 and M-144.
``loop_monitor.py`` and ``job_object.py`` are deliberately not imported here:
this module observes, it never changes production behaviour.
"""

from __future__ import annotations

import contextlib
import time
from typing import TYPE_CHECKING

import psutil

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

__all__ = [
    "assert_tree_terminated",
    "tree_cpu_seconds",
    "tree_handles",
    "wait_for_pid_file",
    "write_pid_file_snippet",
]


def write_pid_file_snippet() -> str:
    """Return Python source that publishes ``os.getpid()`` atomically.

    The snippet expects the target PID-file path as ``sys.argv[1]``: it
    writes the PID to ``<path>.tmp`` and then renames it into place, so a
    reader never observes partial content.
    """

    return (
        "import os, sys\n"
        "target = sys.argv[1]\n"
        "with open(target + '.tmp', 'w', encoding='ascii') as handle:\n"
        "    handle.write(str(os.getpid()))\n"
        "os.replace(target + '.tmp', target)\n"
    )


def wait_for_pid_file(path: Path, *, timeout: float = 10.0, poll_seconds: float = 0.05) -> int:
    """Wait until the atomic PID file exists and return its PID.

    Args:
        path: PID file written via :func:`write_pid_file_snippet`.
        timeout: Maximum seconds to wait (``time.monotonic`` deadline).
        poll_seconds: Poll interval.

    Returns:
        The process ID parsed from the file.

    Raises:
        AssertionError: If the file does not appear within the deadline.
    """

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.is_file():
            content = path.read_text(encoding="ascii")
            try:
                return int(content.strip())
            except ValueError as exc:
                msg = f"PID file {path} contains non-integer content {content!r}"
                raise AssertionError(msg) from exc
        time.sleep(poll_seconds)
    msg = f"PID file {path} did not appear within {timeout} s"
    raise AssertionError(msg)


def tree_handles(root_pid: int) -> list[psutil.Process]:
    """Return handles for ``root_pid`` and all living descendants.

    Args:
        root_pid: PID of the tree root.

    Returns:
        Handles with root first; empty if the root is already gone.

    Raises:
        psutil.NoSuchProcess: If the root disappears before capture.
    """

    root = psutil.Process(root_pid)
    return [root, *root.children(recursive=True)]


def tree_cpu_seconds(handles: Sequence[psutil.Process]) -> float:
    """Return the summed CPU seconds (user + system) over ``handles``."""

    total = 0.0
    for handle in handles:
        with contextlib.suppress(psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            cpu = handle.cpu_times()
            total += cpu.user + cpu.system
    return total


def assert_tree_terminated(
    handles: Sequence[psutil.Process],
    *,
    timeout: float = 10.0,
) -> None:
    """Assert that every process in ``handles`` terminates within ``timeout``.

    Args:
        handles: Handles captured before termination started.
        timeout: Maximum seconds to wait via ``psutil.wait_procs``.

    Raises:
        AssertionError: Listing the PIDs that were still alive.
    """

    _gone, alive = psutil.wait_procs(list(handles), timeout=timeout)
    if alive:
        msg = f"process tree survived: {[p.pid for p in alive]}"
        raise AssertionError(msg)
