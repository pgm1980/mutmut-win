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
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

if TYPE_CHECKING:
    from collections.abc import Iterator


def frozen_worker_config(
    config_data: dict[str, object],
    *,
    project_root: Path | None = None,
    staging_root: Path = Path("mutants"),
) -> dict[str, object]:
    """Attach the production-equivalent serialized pytest boundary to a test payload."""

    from mutmut_win.pytest_boundary import prepare_pytest_boundary

    raw_targets = config_data.get("tests_dir", [])
    if not isinstance(raw_targets, list) or not all(
        isinstance(target, str) for target in raw_targets
    ):
        raise TypeError("test worker config tests_dir must be a string list")
    payload = dict(config_data)
    payload["_pytest_boundary"] = prepare_pytest_boundary(
        project_root=project_root or Path.cwd(),
        staging_root=staging_root,
        tests_dir=list(raw_targets),
    ).to_dict()
    return payload


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

    def fake_popen(*_args: object, **kwargs: object) -> MagicMock:
        # A successful real pytest process publishes this proof from the
        # generated phase-guard plugin. Keep the shared phase mock faithful to
        # that contract; dedicated negative tests patch Popen directly.
        if exit_code == 0 and wait_side_effect is None:
            env = kwargs.get("env")
            if isinstance(env, dict):
                marker = env.get("MUTMUT_PYTEST_PHASE_SENTINEL_PATH")
                token = env.get("MUTMUT_PYTEST_PHASE_SENTINEL_PROOF")
                if isinstance(marker, str) and isinstance(token, str):
                    Path(marker).write_text(token, encoding="utf-8")
        return proc

    with (
        patch("subprocess.Popen", side_effect=fake_popen) as popen,
        patch("mutmut_win.process.worker._create_task_job", return_value=None),
        patch("mutmut_win.process.worker._kill_proc_tree"),
    ):
        # Some contract tests inspect ``mock.return_value.wait`` directly.
        # Keep that legacy seam while the side effect publishes the proof.
        popen.return_value = proc
        yield popen
