"""Process management for Windows-native mutation testing.

Public API for the ``process`` sub-package:

- ``SpawnPoolExecutor`` — spawn-based worker pool.
- ``WallClockTimeout`` — background deadline monitor.
- ``worker_main`` — worker entry point (called in child processes).
- ``MUTANT_ENV_VAR`` — name of the env var used by the trampoline.
"""

from mutmut_win.process.executor import SpawnPoolExecutor
from mutmut_win.process.timeout import WallClockTimeout
from mutmut_win.process.worker import MUTANT_ENV_VAR, worker_main

__all__ = [
    "MUTANT_ENV_VAR",
    "SpawnPoolExecutor",
    "WallClockTimeout",
    "worker_main",
]
