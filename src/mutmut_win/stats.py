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
from dataclasses import dataclass, field
from json import JSONDecodeError
from pathlib import Path
from time import process_time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mutmut_win.runner import PytestRunner

#: Default filename for the CI/CD stats JSON export.
_CICD_STATS_FILENAME = "mutmut-cicd-stats.json"

#: Default filename for the stats JSON cache.
_STATS_FILENAME = "mutmut-stats.json"


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

    If cached stats exist, checks for new tests and re-collects only for those
    (incremental update). Otherwise, runs a full stats collection.

    This mirrors mutmut 3.5.0's ``collect_or_load_stats()`` behavior:
    1. Try to load cached stats from JSON.
    2. If loaded, list current tests and compare against cached test names.
    3. If new tests found, re-run stats collection for those tests only.
    4. If no cached stats, run full collection.

    Args:
        runner: ``PytestRunner`` instance.
        mutants_dir: Directory where the stats JSON file lives.

    Returns:
        A ``MutmutStats`` instance.
    """
    cached = load_stats(mutants_dir)
    if cached is None:
        return _run_stats_collection(runner, mutants_dir)

    # Incremental update: check if there are new tests.
    current_tests = set(runner.collect_tests())
    all_known_tests = set(cached.duration_by_test.keys())
    new_tests = current_tests - all_known_tests

    if new_tests:
        print(f"Found {len(new_tests)} new tests, re-running stats collection for them")
        # Use ListAllTestsResult to clean up obsolete tests.
        result = ListAllTestsResult(ids=current_tests)
        result.clear_out_obsolete_test_names(cached)
        save_stats(cached, mutants_dir)

        # Re-run stats for new tests only.
        return _run_stats_collection(runner, mutants_dir, tests=list(new_tests))

    return cached


def _run_stats_collection(
    runner: PytestRunner,
    mutants_dir: Path,
    tests: list[str] | None = None,  # noqa: ARG001 — reserved for future per-test stats collection
) -> MutmutStats:
    """Run a fresh stats collection and persist the result.

    Calls ``runner.run_stats()`` which runs pytest in-process with the
    ``StatsCollector`` plugin.  Reads the populated ``_state`` globals and
    saves the collected data to disk.

    Args:
        runner: ``PytestRunner`` used to execute the stats run.
        mutants_dir: Directory where the stats JSON file will be written.

    Returns:
        A freshly populated ``MutmutStats`` instance.
    """
    from mutmut_win import _state

    start_cpu = process_time()
    runner.run_stats()
    stats_time = process_time() - start_cpu

    stats = MutmutStats(
        tests_by_mangled_function_name=dict(_state.tests_by_mangled_function_name),
        duration_by_test=dict(_state.duration_by_test),
        stats_time=stats_time,
    )
    save_stats(stats, mutants_dir)
    return stats


# ---------------------------------------------------------------------------
# ListAllTestsResult — incremental stats update helper
# ---------------------------------------------------------------------------


class ListAllTestsResult:
    """Result of listing all currently collected test IDs.

    Used to perform incremental stats updates: obsolete test names that are
    no longer present are removed from the cached stats, and new tests are
    identified for a targeted re-run.

    Args:
        ids: Set of currently active pytest node IDs.
        stats: The loaded ``MutmutStats`` to compare against.
    """

    def __init__(self, *, ids: set[str], stats: MutmutStats) -> None:
        if not isinstance(ids, set):
            msg = "ids must be a set"
            raise TypeError(msg)
        self._ids = ids
        self._stats = stats

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def ids(self) -> set[str]:
        """Return the set of currently active test node IDs."""
        return self._ids

    def clear_out_obsolete_test_names(self, mutants_dir: Path = Path("mutants")) -> None:
        """Remove test names that no longer exist from the cached stats.

        Modifies *stats* in-place and persists the result if any entries were
        removed.

        Args:
            mutants_dir: Directory where the stats JSON file lives.
        """
        before = sum(len(v) for v in self._stats.tests_by_mangled_function_name.values())

        for k in self._stats.tests_by_mangled_function_name:
            self._stats.tests_by_mangled_function_name[k] = {
                name for name in self._stats.tests_by_mangled_function_name[k] if name in self._ids
            }

        after = sum(len(v) for v in self._stats.tests_by_mangled_function_name.values())
        if before != after:
            removed = before - after
            print(f"Removed {removed} obsolete test names")
            save_stats(self._stats, mutants_dir)

    def new_tests(self) -> set[str]:
        """Return test IDs that are not yet present in the cached stats.

        Returns:
            Set of test node IDs that appear in *ids* but not in the current
            ``duration_by_test`` mapping.
        """
        return self._ids - set(self._stats.duration_by_test.keys())


# ---------------------------------------------------------------------------
# CI/CD stats export
# ---------------------------------------------------------------------------


@dataclass
class CicdStats:
    """Aggregated mutation run statistics for CI/CD export.

    Attributes:
        killed: Number of mutants killed by tests.
        survived: Number of surviving (un-killed) mutants.
        total: Total number of mutants generated.
        no_tests: Number of mutants with no covering tests.
        skipped: Number of explicitly skipped mutants.
        suspicious: Number of mutants with suspicious exit codes.
        timeout: Number of timed-out mutants.
        check_was_interrupted_by_user: Number of mutants interrupted by the user.
        segfault: Number of mutants that caused a segfault.
        caught_by_type_check: Number of mutants caught by the type checker.
        score: Mutation score as a percentage (0.0-100.0).
    """

    killed: int = 0
    survived: int = 0
    total: int = 0
    no_tests: int = 0
    skipped: int = 0
    suspicious: int = 0
    timeout: int = 0
    check_was_interrupted_by_user: int = 0
    segfault: int = 0
    caught_by_type_check: int = 0

    @property
    def score(self) -> float:
        """Mutation score as a percentage.

        Returns:
            A float in [0.0, 100.0]; 0.0 if no testable mutants exist.
        """
        denominator = self.total - self.skipped - self.no_tests
        if denominator <= 0:
            return 0.0
        return (self.killed + self.caught_by_type_check) / denominator * 100.0


def compute_cicd_stats(results: list[tuple[str, str | None]]) -> CicdStats:
    """Compute CI/CD stats from a flat list of (mutant_name, status) pairs.

    Args:
        results: List of ``(mutant_name, status)`` tuples.  *status* is a
            string from ``constants.status_by_exit_code`` or ``None`` for
            unchecked mutants.

    Returns:
        A populated ``CicdStats`` instance.
    """
    stats = CicdStats(total=len(results))
    for _name, status in results:
        match status:
            case "killed":
                stats.killed += 1
            case "survived":
                stats.survived += 1
            case "no tests":
                stats.no_tests += 1
            case "skipped":
                stats.skipped += 1
            case "suspicious":
                stats.suspicious += 1
            case "timeout":
                stats.timeout += 1
            case "check was interrupted by user":
                stats.check_was_interrupted_by_user += 1
            case "segfault":
                stats.segfault += 1
            case "caught by type check":
                stats.caught_by_type_check += 1
    return stats


def save_cicd_stats(
    results: list[tuple[str, str | None]],
    mutants_dir: Path = Path("mutants"),
) -> CicdStats:
    """Compute and persist CI/CD stats to *mutants_dir*/mutmut-cicd-stats.json.

    Ported from ``save_cicd_stats`` in mutmut 3.5.0 ``__main__.py``.
    The output JSON is designed for consumption by CI/CD pipelines to gate
    pull requests based on mutation score.

    Args:
        results: List of ``(mutant_name, status)`` tuples.
        mutants_dir: Directory where the JSON file will be written.
            Defaults to ``mutants/``.

    Returns:
        The computed ``CicdStats`` instance.
    """
    stats = compute_cicd_stats(results)
    mutants_dir.mkdir(parents=True, exist_ok=True)
    cicd_path = mutants_dir / _CICD_STATS_FILENAME
    payload = {
        "killed": stats.killed,
        "survived": stats.survived,
        "total": stats.total,
        "no_tests": stats.no_tests,
        "skipped": stats.skipped,
        "suspicious": stats.suspicious,
        "timeout": stats.timeout,
        "check_was_interrupted_by_user": stats.check_was_interrupted_by_user,
        "segfault": stats.segfault,
        "caught_by_type_check": stats.caught_by_type_check,
        "score": stats.score,
    }
    with cicd_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=4)
    return stats
