"""Shared mutable state for trampoline hit tracking during stats collection.

These module-level globals are written by:
- record_trampoline_hit() — called from trampoline_impl during 'stats' mode
- StatsCollector plugin — pytest plugin that reads/clears _stats per test

They are read by:
- stats.py collect_or_load_stats() — after stats phase completes
"""

from __future__ import annotations

from collections import defaultdict

_stats: set[str] = set()
tests_by_mangled_function_name: defaultdict[str, set[str]] = defaultdict(set)
duration_by_test: dict[str, float] = {}
stats_time: float | None = None

#: Cached ``max_stack_depth`` config value used by ``record_trampoline_hit``;
#: ``None`` means not yet loaded. Lives here (issue #110 / A4-QX-017) so
#: ``_reset_globals`` covers it like every other piece of trampoline state.
_cached_max_stack_depth: int | None = None


def _reset_globals() -> None:
    """Reset all state. Called before each stats collection."""
    global stats_time, _cached_max_stack_depth
    _stats.clear()
    tests_by_mangled_function_name.clear()
    duration_by_test.clear()
    stats_time = None
    _cached_max_stack_depth = None
