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

        # Disk recovery remains intact, but the current run must not consume
        # mapping that it has just proven stale.
        assert result.duration_by_test == {}
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

        def dying_run_stats(output_file: Path) -> int:
            output_file.write_text("{ partial garbage", encoding="utf-8")
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

        def plugin_writes_refreshed_stats(output_file: Path) -> int:
            save_stats(
                MutmutStats(duration_by_test={"tests/test_a.py::test_one": 1.5}),
                output_file.parent,
            )
            return 0

        runner.run_stats.side_effect = plugin_writes_refreshed_stats

        result = collect_or_load_stats(runner, tmp_path)

        assert "tests/test_b.py::test_two" not in result.duration_by_test
        on_disk = load_stats(tmp_path)
        assert on_disk is not None
        assert "tests/test_b.py::test_two" not in on_disk.duration_by_test
        runner.run_stats.assert_called_once()


class TestPluginStatsTimeIsPreserved:
    def test_fresh_collection_keeps_the_plugin_stats_time(self, tmp_path: Path) -> None:
        # RN-008: the parent re-saved with process_time() ~ 0, overwriting the
        # accurate plugin measurement. The plugin JSON is the truth now.
        runner = MagicMock()
        runner.collect_tests.return_value = ["tests/test_a.py::test_one"]

        def plugin_writes_json(output_file: Path) -> int:
            save_stats(
                MutmutStats(
                    tests_by_mangled_function_name={},
                    duration_by_test={"tests/test_a.py::test_one": 1.0},
                    stats_time=42.5,
                ),
                output_file.parent,
            )
            return 0

        runner.run_stats.side_effect = plugin_writes_json

        result = collect_or_load_stats(runner, tmp_path)

        assert result.stats_time == 42.5
        on_disk = load_stats(tmp_path)
        assert on_disk is not None
        assert on_disk.stats_time == 42.5


class TestChangedTestFileInvalidation:
    """Issue #130 / 360°-B1: in-place test edits must refresh the mapping.

    Only new/removed node IDs used to trigger a re-collection — an edited
    test (same ID, different body) kept the STALE test↔function mapping:
    newly covered functions stayed 'no tests', strengthened tests reached
    their mutants with the old assignment.
    """

    def test_changed_test_file_triggers_full_recollection(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.chdir(tmp_path)
        test_file = tmp_path / "tests" / "test_a.py"
        test_file.parent.mkdir()
        test_file.write_text("def test_one(): pass\n", encoding="utf-8")
        mutants = tmp_path / "mutants"
        mutants.mkdir()
        save_stats(
            MutmutStats(
                tests_by_mangled_function_name={"x_f__mutmut_1": {"tests/test_a.py::test_one"}},
                duration_by_test={"tests/test_a.py::test_one": 1.5},
                stats_time=2.0,
            ),
            mutants,
        )
        runner = _runner(collected=["tests/test_a.py::test_one"])  # same node IDs
        collect_or_load_stats(runner, mutants)
        runner.run_stats.assert_not_called()  # unchanged file → cache served

        test_file.write_text("def test_one(): assert True\n", encoding="utf-8")  # in-place edit
        runner2 = _runner(collected=["tests/test_a.py::test_one"])
        collect_or_load_stats(runner2, mutants)

        runner2.run_stats.assert_called_once()  # mapping refresh forced
        assert "changed" in capsys.readouterr().out.lower()

    def test_fingerprints_are_persisted_with_the_cache(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_a.py").write_text("def test_one(): pass\n", encoding="utf-8")
        (tmp_path / "mutants").mkdir()

        save_stats(
            MutmutStats(duration_by_test={"tests/test_a.py::test_one": 1.0}),
            tmp_path / "mutants",
        )

        loaded = load_stats(tmp_path / "mutants")
        assert loaded is not None
        assert "tests/test_a.py" in loaded.test_file_fingerprints
        assert loaded.test_file_fingerprints["tests/test_a.py"] != "missing"

    def test_legacy_cache_without_fingerprints_recollects_once(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pre-#130 caches carry no fingerprint field: treat everything as
        # changed ONCE (self-healing), then settle.
        import json as json_module

        monkeypatch.chdir(tmp_path)
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_a.py").write_text("def test_one(): pass\n", encoding="utf-8")
        mutants = tmp_path / "mutants"
        mutants.mkdir()
        (mutants / "mutmut-stats.json").write_text(
            json_module.dumps(
                {
                    "tests_by_mangled_function_name": {},
                    "duration_by_test": {"tests/test_a.py::test_one": 1.0},
                    "stats_time": 1.0,
                }
            ),
            encoding="utf-8",
        )
        runner = _runner(collected=["tests/test_a.py::test_one"])

        def plugin_writes_fresh_stats(output_file: Path) -> int:
            save_stats(
                MutmutStats(
                    duration_by_test={"tests/test_a.py::test_one": 1.0},
                    stats_time=2.0,
                ),
                output_file.parent,
            )
            return 0

        runner.run_stats.side_effect = plugin_writes_fresh_stats

        collect_or_load_stats(runner, mutants)

        runner.run_stats.assert_called_once()  # legacy heal


class TestFingerprintHardening:
    """Mutation-hardening pins for the #130 fingerprint machinery."""

    def test_fingerprint_format_is_pinned(self, tmp_path: Path) -> None:
        # Content identity, not timestamp/size coincidence, is the contract.
        from mutmut_win.stats import _fingerprint_test_files

        test_file = tmp_path / "test_a.py"
        test_file.write_text("def test_one(): pass\n", encoding="utf-8")
        fps = _fingerprint_test_files([f"{test_file}::test_one"])
        import hashlib

        assert fps == {str(test_file): hashlib.sha256(test_file.read_bytes()).hexdigest()}

    def test_missing_file_fingerprints_as_the_pinned_sentinel(self) -> None:
        from mutmut_win.stats import _fingerprint_test_files

        fps = _fingerprint_test_files(["does/not/exist_test.py::test_x"])
        assert fps == {"does/not/exist_test.py": "missing"}

    def test_class_node_ids_and_multiple_files(self, tmp_path: Path) -> None:
        # 'file::Class::test' must key on the FILE (first '::' split, not
        # the last), and the dedupe skip must not abort later files.
        from mutmut_win.stats import _fingerprint_test_files

        for name in ("test_a.py", "test_b.py"):
            (tmp_path / name).write_text("def test_one(): pass\n", encoding="utf-8")
        fps = _fingerprint_test_files(
            [
                f"{tmp_path}/test_a.py::TestC::test_one",
                f"{tmp_path}/test_a.py::TestC::test_two",
                f"{tmp_path}/test_b.py::test_three",
            ]
        )
        assert set(fps) == {f"{tmp_path}/test_a.py", f"{tmp_path}/test_b.py"}

    def test_recollection_persists_fingerprints_into_the_given_dir(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The success path must re-save INTO mutants_dir — without it the
        # plugin JSON stays fingerprint-free and every later run re-collects.
        import json as json_module

        monkeypatch.chdir(tmp_path)
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_a.py").write_text("def test_one(): pass\n", encoding="utf-8")
        mutants = tmp_path / "custom_mutants"
        mutants.mkdir()
        (mutants / "mutmut-stats.json").write_text(
            json_module.dumps(
                {
                    "tests_by_mangled_function_name": {},
                    "duration_by_test": {"tests/test_a.py::test_one": 1.0},
                    "stats_time": 1.0,
                }
            ),
            encoding="utf-8",
        )
        runner = _runner(collected=["tests/test_a.py::test_one"])

        def plugin_writes_custom_stats(output_file: Path) -> int:
            save_stats(
                MutmutStats(
                    duration_by_test={"tests/test_a.py::test_one": 1.0},
                    stats_time=2.0,
                ),
                output_file.parent,
            )
            return 0

        runner.run_stats.side_effect = plugin_writes_custom_stats

        collect_or_load_stats(runner, mutants)

        runner.run_stats.assert_called_once()  # legacy cache → re-collection
        on_disk = json_module.loads((mutants / "mutmut-stats.json").read_text(encoding="utf-8"))
        assert on_disk.get("test_file_fingerprints", {}).get("tests/test_a.py") not in (
            None,
            "missing",
        )

    def test_corrupt_fingerprint_field_loads_as_empty_dict(self, tmp_path: Path) -> None:
        import json as json_module

        mutants = tmp_path / "mutants"
        mutants.mkdir()
        (mutants / "mutmut-stats.json").write_text(
            json_module.dumps(
                {
                    "tests_by_mangled_function_name": {},
                    "duration_by_test": {},
                    "stats_time": 0.0,
                    "test_file_fingerprints": ["not", "a", "dict"],
                }
            ),
            encoding="utf-8",
        )
        loaded = load_stats(mutants)
        assert loaded is not None
        assert loaded.test_file_fingerprints == {}

    def test_new_tests_message_is_word_exact(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_a.py").write_text("def test_one(): pass\n", encoding="utf-8")
        mutants = tmp_path / "mutants"
        mutants.mkdir()
        save_stats(
            MutmutStats(duration_by_test={"tests/test_a.py::test_one": 1.0}),
            mutants,
        )
        runner = _runner(collected=["tests/test_a.py::test_one", "tests/test_a.py::test_two_new"])
        collect_or_load_stats(runner, mutants)
        assert (
            "Found 1 new tests — re-collecting the full stats run "
            "(per-test collection is not implemented; the run is always complete).\n"
        ) in capsys.readouterr().out

    def test_changed_files_message_is_word_exact(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.chdir(tmp_path)
        test_file = tmp_path / "tests" / "test_a.py"
        test_file.parent.mkdir()
        test_file.write_text("def test_one(): pass\n", encoding="utf-8")
        mutants = tmp_path / "mutants"
        mutants.mkdir()
        save_stats(
            MutmutStats(duration_by_test={"tests/test_a.py::test_one": 1.0}),
            mutants,
        )
        test_file.write_text("def test_one(): assert True\n", encoding="utf-8")
        runner = _runner(collected=["tests/test_a.py::test_one"])
        collect_or_load_stats(runner, mutants)
        assert ("1 test file(s) changed in place — re-collecting ") in capsys.readouterr().out
