"""Stats persistence for mutmut-win.

Handles loading and saving the per-test timing and trampoline-hit data
collected during a stats run (``MUTANT_UNDER_TEST=stats``).  Also provides
``collect_or_load_stats`` which either loads a cached result or triggers
a fresh collection via the pytest runner.

Ported from mutmut 3.5.0 ``__main__.py`` with the following adaptations:
- All global state replaced by an explicit ``MutmutStats`` dataclass.
- ``Path`` objects used throughout; ``encoding='utf-8'`` on every file I/O.
- ``collect_or_load_stats`` does not perform incremental stats (new-test
  detection) — that is a future extension.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from json import JSONDecodeError
from pathlib import Path
from time import process_time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mutmut_win.runner import PytestRunner

#: Default filename for the stats JSON cache.
_STATS_FILENAME = "mutmut-stats.json"

#: Environment variable used by the trampoline to select the active mutant.
_MUTANT_ENV_VAR = "MUTANT_UNDER_TEST"

#: Sentinel value that triggers stats recording in the trampoline.
_MUTANT_STATS_SENTINEL = "stats"


@dataclass
class MutmutStats:
    """Collected per-test timing and trampoline-hit data.

    Attributes:
        tests_by_mangled_function_name: Maps mangled function names to the set
            of test node IDs that exercise them (populated by the trampoline
            during a stats run).
        duration_by_test: Maps pytest node IDs to their measured duration
            in seconds.
        stats_time: Total CPU time (``process_time``) consumed by the stats
            collection run.
    """

    tests_by_mangled_function_name: dict[str, set[str]] = field(default_factory=dict)
    duration_by_test: dict[str, float] = field(default_factory=dict)
    stats_time: float = 0.0


def load_stats(mutants_dir: Path = Path("mutants")) -> MutmutStats | None:
    """Load stats from *mutants_dir*/mutmut-stats.json.

    Args:
        mutants_dir: Directory that contains the stats JSON file.
            Defaults to ``mutants/``.

    Returns:
        A populated ``MutmutStats`` instance, or ``None`` if the file does
        not exist or cannot be parsed.
    """
    stats_path = mutants_dir / _STATS_FILENAME
    try:
        with stats_path.open(encoding="utf-8") as f:
            data: dict[str, object] = json.load(f)
    except (FileNotFoundError, JSONDecodeError):
        return None

    raw_by_name = data.pop("tests_by_mangled_function_name", {})
    tests_by_mangled: dict[str, set[str]] = {}
    if isinstance(raw_by_name, dict):
        for k, v in raw_by_name.items():
            tests_by_mangled[str(k)] = set(v) if isinstance(v, list) else set()

    raw_durations = data.pop("duration_by_test", {})
    duration_by_test: dict[str, float] = {}
    if isinstance(raw_durations, dict):
        for k, v in raw_durations.items():
            if isinstance(v, (int, float)):
                duration_by_test[str(k)] = float(v)

    raw_time = data.pop("stats_time", 0.0)
    stats_time = float(raw_time) if isinstance(raw_time, (int, float)) else 0.0

    return MutmutStats(
        tests_by_mangled_function_name=tests_by_mangled,
        duration_by_test=duration_by_test,
        stats_time=stats_time,
    )


def save_stats(stats: MutmutStats, mutants_dir: Path = Path("mutants")) -> None:
    """Save *stats* to *mutants_dir*/mutmut-stats.json.

    The ``tests_by_mangled_function_name`` sets are serialised as sorted lists
    so the output is deterministic.

    Args:
        stats: The ``MutmutStats`` instance to persist.
        mutants_dir: Target directory.  Defaults to ``mutants/``.
    """
    mutants_dir.mkdir(parents=True, exist_ok=True)
    stats_path = mutants_dir / _STATS_FILENAME
    payload = {
        "tests_by_mangled_function_name": {
            k: sorted(v) for k, v in stats.tests_by_mangled_function_name.items()
        },
        "duration_by_test": stats.duration_by_test,
        "stats_time": stats.stats_time,
    }
    with stats_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=4)


def collect_or_load_stats(
    runner: PytestRunner,
    mutants_dir: Path = Path("mutants"),
) -> MutmutStats:
    """Load cached stats or collect fresh ones via *runner*.

    If a valid ``mutmut-stats.json`` exists in *mutants_dir*, it is returned
    directly.  Otherwise the runner is used to collect timing statistics and
    the result is persisted for future runs.

    Args:
        runner: ``PytestRunner`` instance used to collect fresh stats if no
            cached data is found.
        mutants_dir: Directory where the stats JSON file lives.
            Defaults to ``mutants/``.

    Returns:
        A ``MutmutStats`` instance populated with timing and test-mapping data.
    """
    cached = load_stats(mutants_dir)
    if cached is not None:
        return cached

    return _run_stats_collection(runner, mutants_dir)


def _run_stats_collection(
    runner: PytestRunner,
    mutants_dir: Path,
) -> MutmutStats:
    """Run a fresh stats collection and persist the result.

    Sets ``MUTANT_UNDER_TEST=stats`` in the environment before calling
    ``runner.run_stats()``, then saves the collected data to disk.

    Args:
        runner: ``PytestRunner`` used to execute the stats run.
        mutants_dir: Directory where the stats JSON file will be written.

    Returns:
        A freshly populated ``MutmutStats`` instance.
    """
    os.environ[_MUTANT_ENV_VAR] = _MUTANT_STATS_SENTINEL
    os.environ["PY_IGNORE_IMPORTMISMATCH"] = "1"

    start_cpu = process_time()
    duration_by_test = runner.run_stats()
    stats_time = process_time() - start_cpu

    stats = MutmutStats(
        duration_by_test=duration_by_test,
        stats_time=stats_time,
    )
    save_stats(stats, mutants_dir)
    return stats
