"""Unit tests for mutmut_win.stats."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

if TYPE_CHECKING:
    from pathlib import Path

import pytest

import mutmut_win.atomic_file as atomic_file_module
from mutmut_win.atomic_file import UnsafeAtomicWriteError
from mutmut_win.stats import (
    _CICD_STATS_FILENAME,
    _STATS_FILENAME,
    CicdStats,
    ListAllTestsResult,
    MutmutStats,
    collect_or_load_stats,
    compute_cicd_stats,
    load_stats,
    save_cicd_stats,
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

    def test_refuses_missing_parent_without_creating_it(self, tmp_path: Path) -> None:
        nested = tmp_path / "deep" / "mutants"
        stats = MutmutStats()
        with pytest.raises(UnsafeAtomicWriteError, match="cannot inspect atomic-write parent"):
            save_stats(stats, mutants_dir=nested)
        assert not (tmp_path / "deep").exists()

    def test_refuses_redirected_parent_without_writing_outside(self, tmp_path: Path) -> None:
        outside = tmp_path / "outside"
        outside.mkdir()
        staging = tmp_path / "mutants"
        try:
            staging.symlink_to(outside, target_is_directory=True)
        except OSError as exc:
            pytest.skip(f"directory symlinks are unavailable: {exc}")

        with pytest.raises(UnsafeAtomicWriteError, match="parent must be a real directory"):
            save_stats(MutmutStats(), mutants_dir=staging)

        assert list(outside.iterdir()) == []

    def test_detects_parent_swap_and_cleans_external_sibling(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        staging = tmp_path / "mutants"
        staging.mkdir()
        original = tmp_path / "original-mutants"
        outside = tmp_path / "outside"
        outside.mkdir()
        probe = tmp_path / "symlink-probe"
        try:
            probe.symlink_to(outside, target_is_directory=True)
            probe.unlink()
        except OSError as exc:
            pytest.skip(f"directory symlinks are unavailable: {exc}")

        real_open = atomic_file_module._open_random_sibling
        swapped = False

        def swap_parent_then_open(path: Path) -> tuple[int, Path, tuple[int, int]]:
            nonlocal swapped
            if not swapped:
                staging.rename(original)
                staging.symlink_to(outside, target_is_directory=True)
                swapped = True
            return real_open(path)

        monkeypatch.setattr(atomic_file_module, "_open_random_sibling", swap_parent_then_open)

        with pytest.raises(UnsafeAtomicWriteError, match="parent changed"):
            save_stats(MutmutStats(), mutants_dir=staging)

        assert swapped
        assert list(outside.iterdir()) == []

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

    @pytest.mark.parametrize(
        "payload",
        [
            [],
            {"tests_by_mangled_function_name": []},
            {"tests_by_mangled_function_name": {"m": [[]]}},
            {"duration_by_test": {"t": float("nan")}},
            {"stats_time": float("inf")},
        ],
    )
    def test_returns_none_on_structurally_invalid_cache(
        self, payload: object, tmp_path: Path
    ) -> None:
        (tmp_path / _STATS_FILENAME).write_text(json.dumps(payload), encoding="utf-8")
        assert load_stats(mutants_dir=tmp_path) is None

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

    def _plugin_writing_runner(self, tmp_path: Path, stats: MutmutStats) -> MagicMock:
        """Mock runner that does what the real one does (issue #99): the
        stats SUBPROCESS plugin writes mutmut-stats.json; run_stats returns
        the exit code. The plugin JSON is the single source of truth."""
        runner = MagicMock()
        runner.collect_tests.return_value = list(stats.duration_by_test)

        def write_and_succeed() -> int:
            save_stats(stats, mutants_dir=tmp_path)
            return 0

        runner.run_stats.side_effect = write_and_succeed
        return runner

    def test_calls_runner_when_no_cache(self, tmp_path: Path) -> None:
        runner = self._plugin_writing_runner(
            tmp_path, MutmutStats(duration_by_test={"t::test_a": 0.5})
        )

        result = collect_or_load_stats(runner, mutants_dir=tmp_path)

        runner.run_stats.assert_called_once()
        assert "t::test_a" in result.duration_by_test

    def test_persists_collected_stats(self, tmp_path: Path) -> None:
        runner = self._plugin_writing_runner(
            tmp_path, MutmutStats(duration_by_test={"t::test_a": 0.7})
        )

        collect_or_load_stats(runner, mutants_dir=tmp_path)

        # A second call should use the cache and NOT call runner again.
        runner2 = MagicMock()
        runner2.collect_tests.return_value = ["t::test_a"]
        result2 = collect_or_load_stats(runner2, mutants_dir=tmp_path)
        runner2.run_stats.assert_not_called()
        assert "t::test_a" in result2.duration_by_test

    def test_returns_mutmut_stats_instance(self, tmp_path: Path) -> None:
        runner = MagicMock()
        runner.run_stats.return_value = 0
        result = collect_or_load_stats(runner, mutants_dir=tmp_path)
        assert isinstance(result, MutmutStats)

    def test_plugin_stats_time_is_the_truth(self, tmp_path: Path) -> None:
        # Issue #99 / A2-RN-008: the parent used to re-save with a near-zero
        # process_time(); the plugin measurement must survive.
        runner = self._plugin_writing_runner(
            tmp_path, MutmutStats(duration_by_test={"t::test_a": 0.5}, stats_time=1.5)
        )

        result = collect_or_load_stats(runner, mutants_dir=tmp_path)

        assert result.stats_time == pytest.approx(1.5)

    def test_tests_by_mangled_populated_from_plugin_json(self, tmp_path: Path) -> None:
        runner = self._plugin_writing_runner(
            tmp_path,
            MutmutStats(
                tests_by_mangled_function_name={"pkg.func__mutmut_1": {"tests/t.py::test_x"}},
                duration_by_test={"tests/t.py::test_x": 0.1},
            ),
        )

        result = collect_or_load_stats(runner, mutants_dir=tmp_path)

        assert "pkg.func__mutmut_1" in result.tests_by_mangled_function_name
        assert "tests/t.py::test_x" in result.tests_by_mangled_function_name["pkg.func__mutmut_1"]


# ---------------------------------------------------------------------------
# ListAllTestsResult
# ---------------------------------------------------------------------------


class TestListAllTestsResult:
    def _make_stats(
        self,
        mapping: dict[str, set[str]] | None = None,
        durations: dict[str, float] | None = None,
    ) -> MutmutStats:
        return MutmutStats(
            tests_by_mangled_function_name=mapping or {},
            duration_by_test=durations or {},
        )

    def test_requires_set_for_ids(self) -> None:
        stats = self._make_stats()
        with pytest.raises(TypeError):
            ListAllTestsResult(ids=["a", "b"], stats=stats)  # type: ignore[arg-type]

    def test_ids_property(self) -> None:
        stats = self._make_stats()
        ids = {"tests/t.py::test_a", "tests/t.py::test_b"}
        result = ListAllTestsResult(ids=ids, stats=stats)
        assert result.ids == ids

    def test_new_tests_returns_unknown_ids(self) -> None:
        stats = self._make_stats(durations={"tests/t.py::test_a": 0.1})
        ids = {"tests/t.py::test_a", "tests/t.py::test_NEW"}
        result = ListAllTestsResult(ids=ids, stats=stats)
        new = result.new_tests()
        assert "tests/t.py::test_NEW" in new
        assert "tests/t.py::test_a" not in new

    def test_new_tests_empty_when_all_known(self) -> None:
        stats = self._make_stats(durations={"tests/t.py::test_a": 0.1})
        result = ListAllTestsResult(ids={"tests/t.py::test_a"}, stats=stats)
        assert result.new_tests() == set()

    def test_clear_out_obsolete_removes_stale_tests(self, tmp_path: Path) -> None:
        stats = self._make_stats(
            mapping={"pkg.x_foo": {"tests/t.py::test_a", "tests/t.py::test_GONE"}},
            durations={"tests/t.py::test_a": 0.1, "tests/t.py::test_GONE": 0.2},
        )
        save_stats(stats, mutants_dir=tmp_path)
        # Only test_a is still present
        ids = {"tests/t.py::test_a"}
        result = ListAllTestsResult(ids=ids, stats=stats)
        result.clear_out_obsolete_test_names(mutants_dir=tmp_path)

        # Stats should be updated in place
        assert "tests/t.py::test_GONE" not in stats.tests_by_mangled_function_name["pkg.x_foo"]
        assert "tests/t.py::test_a" in stats.tests_by_mangled_function_name["pkg.x_foo"]

    def test_clear_out_no_change_when_all_present(self, tmp_path: Path, capsys) -> None:
        stats = self._make_stats(
            mapping={"pkg.x_foo": {"tests/t.py::test_a"}},
        )
        save_stats(stats, mutants_dir=tmp_path)
        ids = {"tests/t.py::test_a"}
        result = ListAllTestsResult(ids=ids, stats=stats)
        result.clear_out_obsolete_test_names(mutants_dir=tmp_path)
        # Nothing should have been printed
        captured = capsys.readouterr()
        assert "Removed" not in captured.out


# ---------------------------------------------------------------------------
# CicdStats
# ---------------------------------------------------------------------------


class TestCicdStats:
    def test_default_construction(self) -> None:
        stats = CicdStats()
        assert stats.killed == 0
        assert stats.total == 0
        assert stats.score == 0.0

    def test_score_calculation(self) -> None:
        stats = CicdStats(killed=2, survived=1, total=3)
        assert stats.score == pytest.approx(2 / 3 * 100)

    def test_score_zero_when_no_testable_mutants(self) -> None:
        stats = CicdStats(skipped=5, no_tests=3, total=8)
        assert stats.score == 0.0

    def test_score_includes_type_check_caught(self) -> None:
        stats = CicdStats(killed=1, caught_by_type_check=1, survived=0, total=2)
        assert stats.score == pytest.approx(100.0)


# ---------------------------------------------------------------------------
# compute_cicd_stats
# ---------------------------------------------------------------------------


class TestComputeCicdStats:
    def test_empty_results(self) -> None:
        stats = compute_cicd_stats([])
        assert stats.total == 0

    def test_counts_killed(self) -> None:
        results = [("a__mutmut_1", "killed"), ("a__mutmut_2", "survived")]
        stats = compute_cicd_stats(results)
        assert stats.killed == 1
        assert stats.survived == 1
        assert stats.total == 2

    def test_counts_all_statuses(self) -> None:
        results = [
            ("m1", "killed"),
            ("m2", "survived"),
            ("m3", "timeout"),
            ("m4", "skipped"),
            ("m5", "no tests"),
            ("m6", "suspicious"),
            ("m7", "caught by type check"),
        ]
        stats = compute_cicd_stats(results)
        assert stats.killed == 1
        assert stats.survived == 1
        assert stats.timeout == 1
        assert stats.skipped == 1
        assert stats.no_tests == 1
        assert stats.suspicious == 1
        assert stats.caught_by_type_check == 1
        assert stats.total == 7


# ---------------------------------------------------------------------------
# save_cicd_stats
# ---------------------------------------------------------------------------


class TestSaveCicdStats:
    def test_creates_file(self, tmp_path: Path) -> None:
        save_cicd_stats([], mutants_dir=tmp_path)
        assert (tmp_path / _CICD_STATS_FILENAME).exists()

    def test_json_content(self, tmp_path: Path) -> None:
        import json

        results = [("a__mutmut_1", "killed"), ("a__mutmut_2", "survived")]
        save_cicd_stats(results, mutants_dir=tmp_path)
        with (tmp_path / _CICD_STATS_FILENAME).open(encoding="utf-8") as f:
            data = json.load(f)
        assert data["killed"] == 1
        assert data["survived"] == 1
        assert data["total"] == 2

    def test_returns_cicd_stats(self, tmp_path: Path) -> None:
        cicd = save_cicd_stats([("m1", "killed")], mutants_dir=tmp_path)
        assert isinstance(cicd, CicdStats)
        assert cicd.killed == 1

    def test_refuses_missing_parent_without_creating_it(self, tmp_path: Path) -> None:
        nested = tmp_path / "deep" / "mutants"
        with pytest.raises(UnsafeAtomicWriteError, match="cannot inspect atomic-write parent"):
            save_cicd_stats([], mutants_dir=nested)
        assert not (tmp_path / "deep").exists()

    def test_refuses_redirected_parent_without_writing_outside(self, tmp_path: Path) -> None:
        outside = tmp_path / "outside"
        outside.mkdir()
        staging = tmp_path / "mutants"
        try:
            staging.symlink_to(outside, target_is_directory=True)
        except OSError as exc:
            pytest.skip(f"directory symlinks are unavailable: {exc}")

        with pytest.raises(UnsafeAtomicWriteError, match="parent must be a real directory"):
            save_cicd_stats([], mutants_dir=staging)

        assert list(outside.iterdir()) == []

    def test_failed_publish_preserves_previous_artifact_and_cleans_temp(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        artifact = tmp_path / _CICD_STATS_FILENAME
        artifact.write_text('{"known": "good"}\n', encoding="utf-8")

        def fail_dump(_payload: object, **_kwargs: object) -> str:
            raise OSError("simulated ENOSPC")

        monkeypatch.setattr("mutmut_win.stats.json.dumps", fail_dump)

        with pytest.raises(OSError, match="ENOSPC"):
            save_cicd_stats([("m1", "killed")], mutants_dir=tmp_path)

        assert artifact.read_text(encoding="utf-8") == '{"known": "good"}\n'
        assert not list(tmp_path.glob(f".{_CICD_STATS_FILENAME}.*.tmp"))
