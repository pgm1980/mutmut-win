"""Foreground TUI child commands inside a kill-on-close Job Object.

The result browser suspends the Textual TUI and runs interactive
``python -m mutmut_win ...`` sub-commands (retest / apply /
tests-for-mutant) as foreground children on the shared console.  Before
M-057 (issue #158) that launch was the only uncontained start of a
long-lived mutmut-win process tree: a hard TUI death (terminal window
close, Task Manager) left the complete mutation-run child tree running.

``run_foreground_contained`` closes the gap the same way every other
production launcher does — fail closed: the child is created atomically
inside a ``JOB_OBJECT_LIMIT_KILL_ON_CLOSE`` job via
:class:`~mutmut_win.process.atomic_spawn.AtomicJobPopen`, so the kernel
terminates the entire tree once the last job handle closes.  The child
itself may create nested jobs for its own executor/worker pools
(supported on Windows 8+ / Server 2016+, the contract platforms).
"""

from __future__ import annotations

import contextlib
import subprocess
from typing import TYPE_CHECKING

from mutmut_win.exceptions import ProcessContainmentError
from mutmut_win.process.atomic_spawn import AtomicJobPopen
from mutmut_win.process.job_object import close_job, create_kill_on_close_job

if TYPE_CHECKING:
    from collections.abc import Sequence

#: Bounded grace period a console Ctrl-C gives the child for orderly
#: self-shutdown before the launcher hard-kills it.  Ctrl-C is delivered
#: to every process on the shared console, the child included, and a
#: mutmut-win ``run`` child needs a few seconds to tear down its own
#: nested worker jobs.  The bound itself is the contract: no unbounded
#: wait may keep the suspended TUI hostage after Ctrl-C.
_CTRL_C_GRACE_SECONDS: float = 5.0

__all__ = ["run_foreground_contained"]


def run_foreground_contained(cmd: Sequence[str]) -> int:
    """Run one foreground child inside a kill-on-close Windows Job Object.

    The child is started without pipes and without creationflags (no
    ``CREATE_NEW_CONSOLE`` / ``CREATE_NEW_PROCESS_GROUP``), so it inherits
    the caller's console: its output stays visible on the suspended TUI
    terminal and console Ctrl-C reaches it.  The job handle is closed in
    ``finally``; with ``JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`` the kernel
    then terminates the child and any descendant still alive.

    Fail-closed contract: if the Job Object cannot be created or the
    child cannot be created inside it, :class:`ProcessContainmentError`
    is raised and NOTHING is started — there is no uncontained fallback.

    Args:
        cmd: Command line to run, e.g.
            ``[sys.executable, "-m", "mutmut_win", "run", "m.x_f__mutmut_1"]``.

    Returns:
        The child's exit code, never converted to an exception — callers
        keep the ``check=False`` semantics of the former ``subprocess.run``.

    Raises:
        ProcessContainmentError: No Job Object could be established or the
            child could not be created inside it.
        KeyboardInterrupt: Propagated after a bounded grace period for the
            child's own shutdown; the kernel-side job cleanup has already
            run by then.
    """
    try:
        job_handle = create_kill_on_close_job()
    except (OSError, RuntimeError) as exc:  # fmt: skip
        raise ProcessContainmentError(
            "Could not create a kill-on-close Job Object for the foreground "
            "child; refusing to start an uncontained process."
        ) from exc

    try:
        try:
            proc = AtomicJobPopen(list(cmd), job_handle=job_handle)
        except ProcessContainmentError:
            # Already the fail-closed domain error (unsupported runtime,
            # unsupported startup attribute) — never double-wrap it.
            raise
        except OSError as exc:
            raise ProcessContainmentError(
                "Could not start the foreground child inside its Windows "
                "Job Object; refusing an uncontained launch."
            ) from exc
        try:
            return proc.wait()
        except KeyboardInterrupt:
            # The child shares this console and received the same Ctrl-C.
            # Give it a bounded grace period to tear down its own nested
            # worker jobs, then hard-kill whatever ignores it — mirroring
            # subprocess.run, which also never waits forever after Ctrl-C.
            with contextlib.suppress(subprocess.TimeoutExpired):
                proc.wait(timeout=_CTRL_C_GRACE_SECONDS)
            proc.kill()
            raise
    finally:
        # Last handle close: the kernel terminates any surviving descendant.
        close_job(job_handle)
