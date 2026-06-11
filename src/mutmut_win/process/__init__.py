"""Process management for Windows-native mutation testing.

Public API for the ``process`` sub-package:

- ``SpawnPoolExecutor`` — spawn-based worker pool.
- ``worker_main`` — worker entry point (called in child processes).
- ``MUTANT_ENV_VAR`` — name of the env var used by the trampoline.

The former ``WallClockTimeout`` monitor was removed in v2.7.0 (issue #81):
it was never wired into production — per-task timeouts are enforced by the
worker itself via ``proc.wait(timeout=task.timeout_seconds)``.
"""

from mutmut_win.process.executor import SpawnPoolExecutor
from mutmut_win.process.worker import MUTANT_ENV_VAR, worker_main

__all__ = [
    "MUTANT_ENV_VAR",
    "SpawnPoolExecutor",
    "worker_main",
]
