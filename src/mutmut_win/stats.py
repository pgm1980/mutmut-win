"""Stats persistence for mutmut-win.

Handles loading and saving the per-test timing and trampoline-hit data
collected during a stats run (``MUTANT_UNDER_TEST=stats``).  Also provides
``collect_or_load_stats`` which either loads a cached result or triggers
a fresh collection via the pytest runner.

Ported from mutmut 3.5.0 ``__main__.py`` with the following adaptations:
- All global state replaced by an explicit ``MutmutStats`` dataclass.
- ``Path`` objects used throughout; ``encoding='utf-8'`` on every file I/O.
- Collection runs pytest as a SUBPROCESS with an injected plugin; the
  plugin-written ``mutmut-stats.json`` is the single source of truth.
- ``collect_or_load_stats`` updates incrementally: new tests trigger a
  re-collection, removed tests trigger a cache cleanup (issue #99).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from json import JSONDecodeError
from pathlib import Path
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
        return _run_stats_collection(runner, mutants_dir, cached=None)

    # Incremental update: compare the live test list against the cache.
    current_tests = set(runner.collect_tests())
    all_known_tests = set(cached.duration_by_test.keys())
    new_tests = current_tests - all_known_tests
    removed_tests = all_known_tests - current_tests

    if removed_tests:
        # Issue #99 / A3-OS-007: pure deletion never triggered this cleanup —
        # dead node IDs stayed in the argfiles, pytest exited 4, and every
        # affected mutant flooded into "suspicious".
        print(f"Cleaning up {len(removed_tests)} removed tests from the stats cache")
        result = ListAllTestsResult(ids=current_tests, stats=cached)
        result.clear_out_obsolete_test_names(mutants_dir)
        save_stats(cached, mutants_dir)

    if new_tests:
        print(f"Found {len(new_tests)} new tests, re-running stats collection for them")
        # Re-run stats for new tests only.
        return _run_stats_collection(runner, mutants_dir, tests=list(new_tests), cached=cached)

    return cached


def _run_stats_collection(
    runner: PytestRunner,
    mutants_dir: Path,
    tests: list[str] | None = None,  # noqa: ARG001 — reserved for future per-test stats collection
    cached: MutmutStats | None = None,
) -> MutmutStats:
    """Run a fresh stats collection; never let a failure poison the cache.

    ``runner.run_stats()`` executes pytest as a subprocess with the stats
    plugin; the plugin writes ``mutmut-stats.json`` at session end — that
    file is the single source of truth (its ``stats_time`` is the accurate
    in-subprocess measurement, issue #99 / A2-RN-008: the parent used to
    re-save it with a near-zero ``process_time()``).

    On a FAILED run (issue #99 / A3-OS-006 + A2-RN-003): the freshly
    written JSON may be partial — it is neither loaded nor trusted; the
    pre-run *cached* copy is restored to disk (healing a partial write) and
    returned. Without any cache, the full-suite fallback is announced
    loudly instead of silently degrading every mutant run.

    Args:
        runner: ``PytestRunner`` used to execute the stats run.
        mutants_dir: Directory where the stats JSON file lives.
        tests: Reserved for future per-test collection.
        cached: The pre-run cache, used as fallback on failure.

    Returns:
        The freshly collected stats, or the fallback described above.
    """
    exit_code = runner.run_stats()
    if exit_code != 0:
        if cached is not None:
            print("Warning: stats collection failed — keeping the existing stats cache untouched.")
            save_stats(cached, mutants_dir)  # heal a possibly partial plugin write
            return cached
        print(
            "Warning: stats collection failed and no cache exists — every "
            "mutant will run the full test suite (slow)."
        )
        stats_path = mutants_dir / "mutmut-stats.json"
        if stats_path.exists():
            stats_path.unlink()  # a partial write must not become tomorrow's cache
        return MutmutStats()

    stats = load_stats(mutants_dir)
    if stats is None:
        print(
            "Warning: stats collection wrote no data — every mutant will "
            "run the full test suite (slow)."
        )
        return cached if cached is not None else MutmutStats()
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

        Cleans BOTH the per-mutant test mapping (whose dead node IDs end up
        in worker argfiles → pytest exit 4 → "suspicious" floods, issue #99 /
        A3-OS-007) and ``duration_by_test`` (whose dead keys would re-trigger
        the removed-tests cleanup on every run). Modifies *stats* in-place
        and persists the result if any entries were removed.

        Args:
            mutants_dir: Directory where the stats JSON file lives.
        """
        before = sum(len(v) for v in self._stats.tests_by_mangled_function_name.values())
        before_durations = len(self._stats.duration_by_test)

        for k in self._stats.tests_by_mangled_function_name:
            self._stats.tests_by_mangled_function_name[k] = {
                name for name in self._stats.tests_by_mangled_function_name[k] if name in self._ids
            }
        self._stats.duration_by_test = {
            name: duration
            for name, duration in self._stats.duration_by_test.items()
            if name in self._ids
        }

        after = sum(len(v) for v in self._stats.tests_by_mangled_function_name.values())
        removed = (before - after) + (before_durations - len(self._stats.duration_by_test))
        if removed:
            print(f"Removed {removed} obsolete test entries")
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
        killed: Number of mutants killed by tests, including infinite-loop
            kills (matching the run gate and the ``results`` command).
        survived: Number of surviving (un-killed) mutants.
        total: Total number of mutants generated.
        no_tests: Number of mutants with no covering tests.
        skipped: Number of explicitly skipped mutants.
        suspicious: Number of mutants with suspicious exit codes.
        timeout: Number of timed-out mutants.
        check_was_interrupted_by_user: Number of mutants interrupted by the user.
        segfault: Number of mutants that caused a segfault.
        caught_by_type_check: Number of mutants caught by the type checker.
        killed_by_infinite_loop: Subset of ``killed`` that was classified as
            an infinite loop by the IL detector.
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
    killed_by_infinite_loop: int = 0

    @property
    def effective_killed(self) -> int:
        """The kill class behind :attr:`score` (issue #91).

        ``killed`` already includes infinite-loop kills (#86); the type
        checker and a crash under a mutant are detections too.
        """
        return self.killed + self.caught_by_type_check + self.segfault

    @property
    def scoreable(self) -> int:
        """The score denominator: mutants a verdict was possible for.

        ``skipped`` and ``no tests`` leave the denominator — printing the
        raw total next to the score invited verifying it with the wrong
        division (issue #122 / external QA SCO-001).
        """
        return self.total - self.skipped - self.no_tests

    @property
    def score(self) -> float:
        """Mutation score as a percentage.

        The numerator is the kill class: ``killed`` (which already includes
        infinite-loop kills, #86) plus ``caught_by_type_check`` plus
        ``segfault`` — a crash under a mutant is a detection (issue #91).
        Buckets stay disjoint; aggregation happens only here.

        Returns:
            A float in [0.0, 100.0]; 0.0 if no testable mutants exist.
        """
        if self.scoreable <= 0:
            return 0.0
        return self.effective_killed / self.scoreable * 100.0


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
            case "killed_by_infinite_loop":
                # An IL kill IS a kill — the run gate and `results` already
                # count it that way; before #86 it silently deflated the score.
                stats.killed += 1
                stats.killed_by_infinite_loop += 1
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
        "killed_by_infinite_loop": stats.killed_by_infinite_loop,
        "score": stats.score,
    }
    with cicd_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=4)
    return stats
