"""Unit tests for mutmut_win.stats."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

if TYPE_CHECKING:
    from pathlib import Path

import pytest

from mutmut_win.stats import (
    _STATS_FILENAME,
    MutmutStats,
    collect_or_load_stats,
    load_stats,
    save_stats,
)

# ---------------------------------------------------------------------------
# MutmutStats dataclass
# ---------------------------------------------------------------------------


class TestMutmutStats:
    def test_default_construction(self) -> None:
        stats = MutmutStats()
        assert stats.tests_by_mangled_function_name == {}
        assert stats.duration_by_test == {}
        assert stats.stats_time == 0.0

    def test_custom_construction(self) -> None:
        mapping = {"pkg.x_func": {"tests/t.py::test_a"}}
        durations = {"tests/t.py::test_a": 0.5}
        stats = MutmutStats(
            tests_by_mangled_function_name=mapping,
            duration_by_test=durations,
            stats_time=1.23,
        )
        assert stats.tests_by_mangled_function_name == mapping
        assert stats.duration_by_test == durations
        assert stats.stats_time == pytest.approx(1.23)


# ---------------------------------------------------------------------------
# save_stats
# ---------------------------------------------------------------------------


class TestSaveStats:
    def test_creates_json_file(self, tmp_path: Path) -> None:
        stats = MutmutStats(
            tests_by_mangled_function_name={"pkg.x_func": {"t::test_a"}},
            duration_by_test={"t::test_a": 0.3},
            stats_time=2.0,
        )
        save_stats(stats, mutants_dir=tmp_path)
        stats_file = tmp_path / _STATS_FILENAME
        assert stats_file.exists()

    def test_json_content_is_correct(self, tmp_path: Path) -> None:
        stats = MutmutStats(
            tests_by_mangled_function_name={"pkg.x_func": {"t::test_a", "t::test_b"}},
            duration_by_test={"t::test_a": 0.3, "t::test_b": 0.7},
            stats_time=5.5,
        )
        save_stats(stats, mutants_dir=tmp_path)
        with (tmp_path / _STATS_FILENAME).open(encoding="utf-8") as f:
            data = json.load(f)
        assert "tests_by_mangled_function_name" in data
        assert "duration_by_test" in data
        assert "stats_time" in data
        assert data["stats_time"] == pytest.approx(5.5)
        # Sets are serialised as sorted lists.
        assert sorted(data["tests_by_mangled_function_name"]["pkg.x_func"]) == [
            "t::test_a",
            "t::test_b",
        ]

    def test_creates_parent_dir_if_missing(self, tmp_path: Path) -> None:
        nested = tmp_path / "deep" / "mutants"
        stats = MutmutStats()
        save_stats(stats, mutants_dir=nested)
        assert (nested / _STATS_FILENAME).exists()

    def test_overwrites_existing_file(self, tmp_path: Path) -> None:
        stats_v1 = MutmutStats(stats_time=1.0)
        save_stats(stats_v1, mutants_dir=tmp_path)
        stats_v2 = MutmutStats(stats_time=9.9)
        save_stats(stats_v2, mutants_dir=tmp_path)
        loaded = load_stats(mutants_dir=tmp_path)
        assert loaded is not None
        assert loaded.stats_time == pytest.approx(9.9)


# ---------------------------------------------------------------------------
# load_stats
# ---------------------------------------------------------------------------


class TestLoadStats:
    def test_returns_none_when_file_missing(self, tmp_path: Path) -> None:
        result = load_stats(mutants_dir=tmp_path)
        assert result is None

    def test_returns_none_on_invalid_json(self, tmp_path: Path) -> None:
        (tmp_path / _STATS_FILENAME).write_text("not json", encoding="utf-8")
        result = load_stats(mutants_dir=tmp_path)
        assert result is None

    def test_roundtrip(self, tmp_path: Path) -> None:
        original = MutmutStats(
            tests_by_mangled_function_name={"pkg.x_func": {"t::test_a"}},
            duration_by_test={"t::test_a": 0.42},
            stats_time=3.14,
        )
        save_stats(original, mutants_dir=tmp_path)
        loaded = load_stats(mutants_dir=tmp_path)
        assert loaded is not None
        assert loaded.tests_by_mangled_function_name == {"pkg.x_func": {"t::test_a"}}
        assert loaded.duration_by_test == pytest.approx({"t::test_a": 0.42})
        assert loaded.stats_time == pytest.approx(3.14)

    def test_returns_mutmut_stats_instance(self, tmp_path: Path) -> None:
        save_stats(MutmutStats(), mutants_dir=tmp_path)
        result = load_stats(mutants_dir=tmp_path)
        assert isinstance(result, MutmutStats)

    def test_empty_mapping_loaded_correctly(self, tmp_path: Path) -> None:
        save_stats(MutmutStats(), mutants_dir=tmp_path)
        result = load_stats(mutants_dir=tmp_path)
        assert result is not None
        assert result.tests_by_mangled_function_name == {}

    def test_multiple_entries(self, tmp_path: Path) -> None:
        original = MutmutStats(
            tests_by_mangled_function_name={
                "pkg.x_a": {"t::test_1"},
                "pkg.x_b": {"t::test_2", "t::test_3"},
            },
            duration_by_test={"t::test_1": 0.1, "t::test_2": 0.2, "t::test_3": 0.3},
            stats_time=0.6,
        )
        save_stats(original, mutants_dir=tmp_path)
        loaded = load_stats(mutants_dir=tmp_path)
        assert loaded is not None
        assert "pkg.x_a" in loaded.tests_by_mangled_function_name
        assert "pkg.x_b" in loaded.tests_by_mangled_function_name
        assert loaded.tests_by_mangled_function_name["pkg.x_b"] == {"t::test_2", "t::test_3"}


# ---------------------------------------------------------------------------
# collect_or_load_stats
# ---------------------------------------------------------------------------


class TestCollectOrLoadStats:
    def test_returns_cached_stats_if_present(self, tmp_path: Path) -> None:
        cached = MutmutStats(stats_time=42.0)
        save_stats(cached, mutants_dir=tmp_path)

        runner = MagicMock()
        result = collect_or_load_stats(runner, mutants_dir=tmp_path)

        assert result.stats_time == pytest.approx(42.0)
        runner.run_stats.assert_not_called()

    def test_calls_runner_when_no_cache(self, tmp_path: Path) -> None:
        runner = MagicMock()
        runner.run_stats.return_value = {"t::test_a": 0.5}

        result = collect_or_load_stats(runner, mutants_dir=tmp_path)

        runner.run_stats.assert_called_once()
        assert "t::test_a" in result.duration_by_test

    def test_persists_collected_stats(self, tmp_path: Path) -> None:
        runner = MagicMock()
        runner.run_stats.return_value = {"t::test_a": 0.7}

        collect_or_load_stats(runner, mutants_dir=tmp_path)

        # A second call should use the cache and NOT call runner again.
        runner2 = MagicMock()
        result2 = collect_or_load_stats(runner2, mutants_dir=tmp_path)
        runner2.run_stats.assert_not_called()
        assert "t::test_a" in result2.duration_by_test

    def test_returns_mutmut_stats_instance(self, tmp_path: Path) -> None:
        runner = MagicMock()
        runner.run_stats.return_value = {}
        result = collect_or_load_stats(runner, mutants_dir=tmp_path)
        assert isinstance(result, MutmutStats)

    def test_stats_time_is_positive_after_collection(self, tmp_path: Path) -> None:
        runner = MagicMock()
        runner.run_stats.return_value = {}

        with patch("mutmut_win.stats.process_time", side_effect=[0.0, 1.5]):
            result = collect_or_load_stats(runner, mutants_dir=tmp_path)

        assert result.stats_time == pytest.approx(1.5)
