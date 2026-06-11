"""Tests for stats-cache truth (Issue #99, audit A3-OS-006/007, A2-RN-003/008).

A failed stats subprocess used to be followed by an unchecked load of the
(possibly partial) JSON, and the empty ``_state`` globals were SAVED over a
good cache — from then on every mutant silently ran the full suite.
Deleting tests without adding new ones never triggered the obsolete-test
cleanup, and the accurate plugin ``stats_time`` was overwritten with a
near-zero parent ``process_time()`` on every re-save.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

from mutmut_win.stats import MutmutStats, collect_or_load_stats, load_stats, save_stats

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def _good_cache(mutants_dir: Path) -> MutmutStats:
    stats = MutmutStats(
        tests_by_mangled_function_name={"x_f__mutmut_1": {"tests/test_a.py::test_one"}},
        duration_by_test={
            "tests/test_a.py::test_one": 1.5,
            "tests/test_b.py::test_two": 2.5,
        },
        stats_time=4.0,
    )
    save_stats(stats, mutants_dir)
    return stats


def _runner(collected: list[str], stats_exit: int = 0) -> MagicMock:
    runner = MagicMock()
    runner.collect_tests.return_value = collected
    runner.run_stats.return_value = stats_exit
    return runner


class TestStatsFailureNeverPoisonsTheCache:
    def test_failed_rerun_keeps_the_good_cache(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # New test appears -> re-run is attempted -> subprocess FAILS.
        # OS-006: the empty result used to be saved over the good cache.
        cached = _good_cache(tmp_path)
        runner = _runner(
            collected=[*cached.duration_by_test.keys(), "tests/test_c.py::test_new"],
            stats_exit=1,
        )

        result = collect_or_load_stats(runner, tmp_path)

        assert result.duration_by_test.keys() >= cached.duration_by_test.keys()
        on_disk = load_stats(tmp_path)
        assert on_disk is not None
        assert "tests/test_a.py::test_one" in on_disk.duration_by_test  # cache intact
        assert "failed" in capsys.readouterr().out.lower()

    def test_failed_first_run_announces_the_fallback_loudly(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # No cache at all + failing collection -> empty stats, but SAY so
        # (the silent full-suite fallback was the OS-006 damage).
        runner = _runner(collected=["tests/test_a.py::test_one"], stats_exit=2)

        result = collect_or_load_stats(runner, tmp_path)

        assert result.duration_by_test == {}
        out = capsys.readouterr().out.lower()
        assert "failed" in out
        assert "full" in out  # announces full-suite fallback

    def test_partial_plugin_json_is_healed_from_the_cached_copy(self, tmp_path: Path) -> None:
        # RN-003: the plugin may have written a partial/garbage JSON before
        # the subprocess died — the next run must not inherit it as "cache".
        cached = _good_cache(tmp_path)
        runner = _runner(
            collected=[*cached.duration_by_test.keys(), "tests/test_c.py::test_new"],
            stats_exit=1,
        )

        def dying_run_stats() -> int:
            (tmp_path / "mutmut-stats.json").write_text("{ partial garbage", encoding="utf-8")
            return 1

        runner.run_stats.side_effect = dying_run_stats

        collect_or_load_stats(runner, tmp_path)

        healed = load_stats(tmp_path)
        assert healed is not None
        assert "tests/test_a.py::test_one" in healed.duration_by_test


class TestObsoleteCleanupOnDeletion:
    def test_deleted_tests_are_cleaned_without_new_ones(self, tmp_path: Path) -> None:
        # OS-007: pure deletion never triggered the cleanup -> dead node IDs
        # stayed in the argfiles -> pytest exit 4 -> 'suspicious' flood.
        _good_cache(tmp_path)
        runner = _runner(collected=["tests/test_a.py::test_one"])  # test_two deleted

        result = collect_or_load_stats(runner, tmp_path)

        assert "tests/test_b.py::test_two" not in result.duration_by_test
        on_disk = load_stats(tmp_path)
        assert on_disk is not None
        assert "tests/test_b.py::test_two" not in on_disk.duration_by_test
        runner.run_stats.assert_not_called()  # no new tests -> no re-run needed


class TestPluginStatsTimeIsPreserved:
    def test_fresh_collection_keeps_the_plugin_stats_time(self, tmp_path: Path) -> None:
        # RN-008: the parent re-saved with process_time() ~ 0, overwriting the
        # accurate plugin measurement. The plugin JSON is the truth now.
        runner = MagicMock()
        runner.collect_tests.return_value = ["tests/test_a.py::test_one"]

        def plugin_writes_json() -> int:
            save_stats(
                MutmutStats(
                    tests_by_mangled_function_name={},
                    duration_by_test={"tests/test_a.py::test_one": 1.0},
                    stats_time=42.5,
                ),
                tmp_path,
            )
            return 0

        runner.run_stats.side_effect = plugin_writes_json

        result = collect_or_load_stats(runner, tmp_path)

        assert result.stats_time == 42.5
        on_disk = load_stats(tmp_path)
        assert on_disk is not None
        assert on_disk.stats_time == 42.5
