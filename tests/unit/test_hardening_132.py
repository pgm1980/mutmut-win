"""Tests for the #132 hardening bundle (360° wave 5).

B5: pytest *phases* (clean run, stats, forced-fail) used plain
``subprocess.run(timeout=)`` — a phase timeout killed only the direct
child; pytest's grandchildren survived. The phases now mirror the
worker's Popen + job-object + kill-tree pattern.

B7: ``..``-sibling ``extra_paths`` are STAGED under their basename, but
both PYTHONPATH builders mapped ``mutants / "../x"`` — pointing the
test run at the UNSTAGED original. The mappings are now in sync.

B8: the IL exit code / status string lived as duplicate literals in
``loop_monitor`` — single-sourced from ``constants`` now.

B9: setup.cfg knew only a subset of the config fields; unknown keys
were silently ignored. Full parity + a warning.

C1: mass persists go through one connection (``save_results``).
C5: regex mutation results are deduplicated.
C6: status maps are plain dicts — lookups cannot grow them.
"""

from __future__ import annotations

import os
import subprocess
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

from mutmut_win.config import MutmutConfig, load_config
from mutmut_win.runner import PytestRunner

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


class TestPhaseGrandchildReaping:
    """360°-B5: a timed-out phase must reap the whole process tree."""

    def test_timeout_kills_the_whole_process_tree(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / "mutants").mkdir(exist_ok=True)
        runner = PytestRunner(MutmutConfig(paths_to_mutate=["src"]))
        fake_proc = MagicMock()
        fake_proc.pid = 4242
        fake_proc.wait.side_effect = subprocess.TimeoutExpired(cmd="pytest", timeout=1)
        with (
            patch("subprocess.Popen", return_value=fake_proc),
            patch("mutmut_win.process.worker._create_task_job", return_value=None) as job,
            patch("mutmut_win.process.worker._kill_proc_tree") as kill_tree,
        ):
            exit_code = runner._run_phase("clean run", ["pytest"], env={}, timeout=1)
        assert exit_code == 36
        job.assert_called_once_with(4242)
        kill_tree.assert_called_once_with(fake_proc, None)
        assert "clean run timed out" in capsys.readouterr().out

    def test_successful_phase_returns_the_exit_code_and_does_not_kill(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / "mutants").mkdir(exist_ok=True)
        runner = PytestRunner(MutmutConfig(paths_to_mutate=["src"]))
        fake_proc = MagicMock()
        fake_proc.pid = 4242
        fake_proc.wait.return_value = 5
        with (
            patch("subprocess.Popen", return_value=fake_proc),
            patch("mutmut_win.process.worker._create_task_job", return_value=None),
            patch("mutmut_win.process.worker._kill_proc_tree") as kill_tree,
        ):
            exit_code = runner._run_phase("stats", ["pytest"], env={})
        assert exit_code == 5
        kill_tree.assert_not_called()

    def test_phase_job_handle_lifecycle_with_a_real_handle(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Mutation hardening: with the handle mocked to None every handle
        # branch is inert — a sentinel handle pins the lifecycle. Success:
        # the kill-on-close job MUST be closed (it reaps leftovers).
        monkeypatch.chdir(tmp_path)
        (tmp_path / "mutants").mkdir(exist_ok=True)
        runner = PytestRunner(MutmutConfig(paths_to_mutate=["src"]))
        fake_proc = MagicMock()
        fake_proc.pid = 4242
        fake_proc.wait.return_value = 0
        with (
            patch("subprocess.Popen", return_value=fake_proc),
            patch("mutmut_win.process.worker._create_task_job", return_value=42),
            patch("mutmut_win.process.worker._kill_proc_tree") as kill_tree,
            patch("mutmut_win.process.job_object.close_job") as close_job,
        ):
            runner._run_phase("clean run", ["pytest"], env={})
        kill_tree.assert_not_called()
        close_job.assert_called_once_with(42)

    def test_phase_timeout_passes_the_handle_to_the_sweep_and_closes_once(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Timeout: the sweep gets the REAL handle (job kill beats psutil
        # walk) and owns its closing — no double close in finally.
        monkeypatch.chdir(tmp_path)
        (tmp_path / "mutants").mkdir(exist_ok=True)
        runner = PytestRunner(MutmutConfig(paths_to_mutate=["src"]))
        fake_proc = MagicMock()
        fake_proc.pid = 4242
        fake_proc.wait.side_effect = subprocess.TimeoutExpired(cmd="pytest", timeout=1)
        with (
            patch("subprocess.Popen", return_value=fake_proc),
            patch("mutmut_win.process.worker._create_task_job", return_value=42),
            patch("mutmut_win.process.worker._kill_proc_tree") as kill_tree,
            patch("mutmut_win.process.job_object.close_job") as close_job,
        ):
            exit_code = runner._run_phase("clean run", ["pytest"], env={}, timeout=1)
        assert exit_code == 36
        kill_tree.assert_called_once_with(fake_proc, 42)
        close_job.assert_not_called()

    def test_coverage_job_handle_lifecycle_with_a_real_handle(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / "mutants").mkdir(exist_ok=True)
        runner = PytestRunner(MutmutConfig(paths_to_mutate=["src"]))
        fake_proc = MagicMock()
        fake_proc.pid = 4242
        fake_proc.wait.return_value = 0
        with (
            patch("subprocess.Popen", return_value=fake_proc),
            patch("mutmut_win.process.worker._create_task_job", return_value=42) as job,
            patch("mutmut_win.process.worker._kill_proc_tree") as kill_tree,
            patch("mutmut_win.process.job_object.close_job") as close_job,
        ):
            exit_code = runner.run_coverage_collection(tmp_path / ".coverage.mutmut")
        assert exit_code == 0
        job.assert_called_once_with(4242)
        kill_tree.assert_not_called()
        close_job.assert_called_once_with(42)

    def test_coverage_timeout_passes_the_handle_to_the_sweep_and_closes_once(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / "mutants").mkdir(exist_ok=True)
        runner = PytestRunner(MutmutConfig(paths_to_mutate=["src"], clean_run_timeout=1))
        fake_proc = MagicMock()
        fake_proc.pid = 4242
        fake_proc.wait.side_effect = subprocess.TimeoutExpired(cmd="coverage", timeout=1)
        with (
            patch("subprocess.Popen", return_value=fake_proc),
            patch("mutmut_win.process.worker._create_task_job", return_value=42),
            patch("mutmut_win.process.worker._kill_proc_tree") as kill_tree,
            patch("mutmut_win.process.job_object.close_job") as close_job,
        ):
            exit_code = runner.run_coverage_collection(tmp_path / ".coverage.mutmut")
        assert exit_code == 36
        kill_tree.assert_called_once_with(fake_proc, 42)
        close_job.assert_not_called()


class TestExtraPathsStagingParity:
    """360°-B7: PYTHONPATH must use the SAME mapping as the staging copy.

    ``copy_also_copy_files`` stages a ``..``-sibling under its basename
    (``mutants/<name>``, issue #101 / A3-FD-002) — but the PYTHONPATH
    builders mapped ``mutants / "../x"``, which resolves to the UNSTAGED
    original: mutants imported unmutated code and the measurement was
    silently wrong.
    """

    def test_runner_env_points_dotdot_siblings_at_the_staged_copy(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        project = tmp_path / "project"
        sibling = tmp_path / "benchmarks"
        (project / "mutants" / "benchmarks").mkdir(parents=True)
        sibling.mkdir()
        monkeypatch.chdir(project)
        runner = PytestRunner(MutmutConfig(paths_to_mutate=["src"], extra_paths=["../benchmarks"]))
        python_path = runner._mutants_env()["PYTHONPATH"]
        staged = str((project / "mutants" / "benchmarks").absolute())
        assert staged in python_path.split(os.pathsep)
        assert str(sibling.absolute()) not in python_path.split(os.pathsep)

    def test_runner_env_keeps_plain_relative_entries(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_path / "mutants" / "libs" / "shared").mkdir(parents=True)
        monkeypatch.chdir(tmp_path)
        runner = PytestRunner(MutmutConfig(paths_to_mutate=["src"], extra_paths=["libs/shared"]))
        python_path = runner._mutants_env()["PYTHONPATH"]
        staged = str((tmp_path / "mutants" / "libs" / "shared").absolute())
        assert staged in python_path.split(os.pathsep)

    def test_worker_env_points_dotdot_siblings_at_the_staged_copy(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from queue import Queue

        from mutmut_win.models import MutationTask
        from mutmut_win.process.worker import worker_main

        project = tmp_path / "project"
        sibling = tmp_path / "benchmarks"
        (project / "mutants" / "benchmarks").mkdir(parents=True)
        sibling.mkdir()
        monkeypatch.chdir(project)

        captured_env: dict[str, str] = {}

        def fake_popen(_cmd: list[str], **kwargs: object) -> MagicMock:
            env = kwargs.get("env", {})
            captured_env.update(env)  # type: ignore[arg-type]
            proc = MagicMock()
            proc.pid = 12345
            proc.wait.return_value = 0
            proc.poll.return_value = 0
            return proc

        task_q: Queue[object] = Queue()
        event_q: Queue[object] = Queue()
        task_q.put(MutationTask(mutant_name="src/foo.py::bar__mutmut_1").model_dump())
        task_q.put(None)
        config_data = {
            "paths_to_mutate": ["src/"],
            "tests_dir": ["tests/"],
            "extra_paths": ["../benchmarks"],
            "pytest_add_cli_args": [],
            "pytest_add_cli_args_test_selection": [],
            "timeout_multiplier": 10.0,
            "infinite_loop_detection": False,
        }
        with patch("mutmut_win.process.worker.subprocess.Popen", side_effect=fake_popen):
            worker_main(task_q, event_q, config_data)  # type: ignore[arg-type]

        paths = captured_env.get("PYTHONPATH", "").split(os.pathsep)
        staged = str((project / "mutants" / "benchmarks").absolute())
        assert staged in paths
        assert str(sibling.absolute()) not in paths


class TestIlConstantSingleSource:
    """360°-B8: IL exit code / status string have ONE defining module."""

    def test_constants_owns_the_il_exit_code_and_status(self) -> None:
        from mutmut_win import constants
        from mutmut_win.process import loop_monitor

        assert loop_monitor.EXIT_CODE_INFINITE_LOOP == constants.EXIT_CODE_INFINITE_LOOP
        assert (
            loop_monitor.STATUS_KILLED_BY_INFINITE_LOOP == constants.STATUS_KILLED_BY_INFINITE_LOOP
        )
        assert (
            constants.status_by_exit_code[constants.EXIT_CODE_INFINITE_LOOP]
            == constants.STATUS_KILLED_BY_INFINITE_LOOP
        )


class TestSetupCfgParity:
    """360°-B9: setup.cfg supports the full field set and warns on typos."""

    def test_extra_paths_and_il_fields_load_from_setup_cfg(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / "setup.cfg").write_text(
            "[mutmut]\n"
            "paths_to_mutate = src/\n"
            "extra_paths = benchmarks/\n"
            "infinite_loop_detection = false\n"
            "infinite_loop_window_seconds = 7.5\n"
            "infinite_loop_cpu_threshold = 42.5\n"
            "infinite_loop_output_threshold = 11\n"
            "infinite_loop_running_ratio = 0.75\n",
            encoding="utf-8",
        )
        config = load_config(tmp_path)
        assert config.extra_paths == ["benchmarks/"]
        assert config.infinite_loop_detection is False
        assert config.infinite_loop_window_seconds == 7.5
        assert config.infinite_loop_cpu_threshold == 42.5
        assert config.infinite_loop_output_threshold == 11
        assert config.infinite_loop_running_ratio == 0.75

    def test_unknown_setup_cfg_keys_warn_but_do_not_fail(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / "setup.cfg").write_text(
            "[mutmut]\npaths_to_mutate = src/\ninfinite_loop_windw = 5\n",
            encoding="utf-8",
        )
        config = load_config(tmp_path)
        assert config.paths_to_mutate == ["src/"]
        err = capsys.readouterr().err
        assert "infinite_loop_windw" in err
        assert "unknown" in err.lower()

    def test_unknown_key_warning_is_word_exact_and_sorted(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # Four typo keys written in reverse order: the warning lists them
        # SORTED in one stable, word-exact line.
        monkeypatch.chdir(tmp_path)
        (tmp_path / "setup.cfg").write_text(
            "[mutmut]\n"
            "paths_to_mutate = src/\n"
            "zz_typo = 1\n"
            "mm_typo = 2\n"
            "dd_typo = 3\n"
            "aa_typo = 4\n",
            encoding="utf-8",
        )
        load_config(tmp_path)
        assert capsys.readouterr().err == (
            "Warning: setup.cfg [mutmut] contains unknown option(s): "
            "aa_typo, dd_typo, mm_typo, zz_typo — ignored.\n"
        )

    def test_known_keys_do_not_warn(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / "setup.cfg").write_text("[mutmut]\npaths_to_mutate = src/\n", encoding="utf-8")
        load_config(tmp_path)
        assert capsys.readouterr().err == ""


class TestBatchPersistence:
    """360°-C1: mass persists share one connection."""

    def test_save_results_batch_roundtrip(self, tmp_path: Path) -> None:
        from mutmut_win.db import load_results, save_results

        db_path = tmp_path / "results.db"
        save_results(
            db_path,
            [
                ("pkg.x_f__mutmut_1", "skipped", 34, None, None, None, None),
                ("pkg.x_f__mutmut_2", "killed", 1, 0.5, "boom", None, "fp"),
                ("pkg.x_f__mutmut_3", "no tests", 33, None, None, None, None),
            ],
        )
        rows = {r.mutant_name: r for r in load_results(db_path)}
        assert set(rows) == {
            "pkg.x_f__mutmut_1",
            "pkg.x_f__mutmut_2",
            "pkg.x_f__mutmut_3",
        }
        assert rows["pkg.x_f__mutmut_1"].status == "skipped"
        assert rows["pkg.x_f__mutmut_2"].duration == 0.5
        assert rows["pkg.x_f__mutmut_2"].tests_fingerprint == "fp"

    def test_batch_uses_a_single_connection(self, tmp_path: Path) -> None:
        import sqlite3 as sqlite3_module

        from mutmut_win.db import save_results

        db_path = tmp_path / "results.db"
        real_connect = sqlite3_module.connect
        calls: list[str] = []

        def counting_connect(*args: object, **kwargs: object) -> object:
            calls.append("connect")
            return real_connect(*args, **kwargs)  # type: ignore[arg-type]

        rows = [(f"pkg.x_f__mutmut_{i}", "skipped", 34, None, None, None, None) for i in range(50)]
        with patch("sqlite3.connect", side_effect=counting_connect):
            save_results(db_path, rows)
        # create_db + the batch write — NOT one connection per row.
        assert len(calls) <= 2

    def test_surrogates_are_scrubbed_in_batch_rows(self, tmp_path: Path) -> None:
        from mutmut_win.db import load_results, save_results

        db_path = tmp_path / "results.db"
        save_results(
            db_path,
            [("pkg.x_f__mutmut_1", "timeout", 36, None, "lone \udcff surrogate", None, None)],
        )
        [row] = load_results(db_path)
        assert "surrogate" in (row.last_output or "")


class TestRegexMutationDedup:
    """360°-C5: duplicate regex mutations are filtered out."""

    def test_duplicate_candidates_collapse(self) -> None:
        import mutmut_win.regex_mutation as rm

        with (
            patch.object(rm, "_mutate_quantifiers", return_value=["ab", "ab"]),
            patch.object(rm, "_mutate_char_classes", return_value=["ab"]),
            patch.object(rm, "_mutate_anchors", return_value=[]),
        ):
            assert rm.mutate_regex_pattern("a+b") == ["ab"]

    def test_results_are_unique_for_real_patterns(self) -> None:
        from mutmut_win.regex_mutation import mutate_regex_pattern

        for pattern in ("a+b+", r"\d\D", "^xy$", "[ab]+c*", "a{2,5}"):
            results = mutate_regex_pattern(pattern)
            assert len(results) == len(set(results)), pattern


class TestPlainDictStatusMaps:
    """360°-C6: lookups must not mutate the status maps."""

    def test_status_map_is_a_plain_dict_and_lookups_do_not_grow_it(self) -> None:
        from mutmut_win import constants

        assert type(constants.status_by_exit_code) is dict
        size_before = len(constants.status_by_exit_code)
        assert constants.status_by_exit_code.get(99999, "suspicious") == "suspicious"
        assert len(constants.status_by_exit_code) == size_before

    def test_emoji_map_is_a_plain_dict(self) -> None:
        from mutmut_win import constants

        assert type(constants.exit_code_to_emoji) is dict
        size_before = len(constants.exit_code_to_emoji)
        assert constants.exit_code_to_emoji.get(99999, "?") == "?"
        assert len(constants.exit_code_to_emoji) == size_before

    def test_unknown_exit_code_still_counts_as_suspicious(self) -> None:
        from mutmut_win import constants

        assert constants.status_by_exit_code.get(87, "suspicious") == "suspicious"
