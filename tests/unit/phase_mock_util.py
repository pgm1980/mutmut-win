"""Shared mock for the runner's phase subprocess (issue #132 / 360°-B5).

The pytest phases (clean run, stats, forced-fail, coverage) spawn via
``subprocess.Popen`` + a kill-on-close Job Object + ``proc.wait(timeout=)``
— plain ``subprocess.run`` mocks stopped matching when B5 landed. This
context manager patches all three seams:

- ``subprocess.Popen`` → a MagicMock process (``wait`` returns *exit_code*
  or raises *wait_side_effect*),
- ``_create_task_job`` → ``None`` (a REAL kill-on-close job assigned to a
  mock pid could reap an unrelated live process),
- ``_kill_proc_tree`` → no-op (the psutil sweep must not walk a mock pid).
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

if TYPE_CHECKING:
    from collections.abc import Iterator


@contextlib.contextmanager
def phase_popen(
    exit_code: int = 0, wait_side_effect: BaseException | None = None
) -> Iterator[MagicMock]:
    """Yield the patched ``subprocess.Popen`` mock for one phase run."""
    proc = MagicMock()
    proc.pid = 99999
    if wait_side_effect is not None:
        proc.wait.side_effect = wait_side_effect
    else:
        proc.wait.return_value = exit_code
    with (
        patch("subprocess.Popen", return_value=proc) as popen,
        patch("mutmut_win.process.worker._create_task_job", return_value=None),
        patch("mutmut_win.process.worker._kill_proc_tree"),
    ):
        yield popen
