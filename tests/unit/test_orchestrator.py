"""Unit tests for mutmut_win.orchestrator (MutationOrchestrator)."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import pytest

from mutmut_win.config import MutmutConfig
from mutmut_win.exceptions import CleanTestFailedError, ForcedFailError
from mutmut_win.models import (
    MutationRunResult,
    MutationTask,
    TaskCompleted,
    TaskStarted,
)
from mutmut_win.orchestrator import (
    MutationOrchestrator,
    _apply_timeouts,
    _filter_tasks_by_names,
    _increment_summary,
    _update_source_data,
    _update_summary_and_persist,
)

if TYPE_CHECKING:
    from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _config(**overrides: Any) -> MutmutConfig:
    defaults: dict[str, Any] = {"max_children": 1, "timeout_multiplier": 2.0}
    defaults.update(overrides)
    return MutmutConfig(**defaults)


def _task(name: str = "src/foo.py::bar__mutmut_1", **kwargs: Any) -> MutationTask:
    return MutationTask(mutant_name=name, **kwargs)


def _make_runner(
    clean_exit: int = 0,
    forced_fail_exit: int = 1,
    tests: list[str] | None = None,
) -> MagicMock:
    runner = MagicMock()
    runner.run_clean_test.return_value = clean_exit
    runner.run_forced_fail.return_value = forced_fail_exit
    # run_stats returns None (side-effect: populates _state globals)
    runner.run_stats.return_value = None
    runner.collect_tests.return_value = tests or []
    return runner


def _make_executor(events: list[Any] | None = None) -> MagicMock:
    executor = MagicMock()
    executor.get_events.return_value = iter(events or [])
    return executor


# ---------------------------------------------------------------------------
# _apply_timeouts (pure helper)
# ---------------------------------------------------------------------------


# Issue #105 / DOG-001: the budget formula gained an additive startup floor
# and a clean-wall-scaled fallback — these tests pin the NEW semantics
# (the dedicated model tests live in test_timeout_model.py).
class TestApplyTimeouts:
    def test_uses_fallback_when_no_stats(self) -> None:
        tasks = [_task()]
        result = _apply_timeouts(tasks, {}, 10.0, startup_floor=5.0, clean_wall_seconds=1.0)
        assert result[0].timeout_seconds == 60.0  # _FALLBACK_TIMEOUT lower bound

    def test_uses_floor_plus_scaled_estimate_with_known_stats(self) -> None:
        tasks = [_task(tests=["tests/test_foo.py::test_x"])]
        stats = {"tests/test_foo.py::test_x": 2.0}
        result = _apply_timeouts(tasks, stats, 5.0, startup_floor=7.0, clean_wall_seconds=9.0)
        # floor 7.0 + 2.0 * 5.0 = 17.0
        assert result[0].timeout_seconds == pytest.approx(17.0)

    def test_min_timeout_enforced(self) -> None:
        tasks = [_task(tests=["tests/test_foo.py::test_x"])]
        stats = {"tests/test_foo.py::test_x": 0.001}
        result = _apply_timeouts(tasks, stats, 1.0, startup_floor=5.0, clean_wall_seconds=5.0)
        assert result[0].timeout_seconds >= 5.0  # _MIN_TIMEOUT

    def test_unassigned_task_gets_full_suite_budget_even_with_stats(self) -> None:
        # 360°-B3 (#130): tests=[] + non-empty durations used to budget a
        # FULL-SUITE run with a single-test MEAN — a guaranteed timeout
        # flood (e.g. empty mapping from broken hit recording). The mean
        # still feeds the fast-first SORT; the budget is the full-suite
        # fallback.
        tasks = [_task()]  # no tests assigned
        stats = {"tests/test_a.py::test_x": 2.0, "tests/test_b.py::test_y": 4.0}
        result = _apply_timeouts(tasks, stats, 2.0, startup_floor=5.0, clean_wall_seconds=100.0)
        assert result[0].estimated_time == pytest.approx(3.0)  # mean keeps sorting
        assert result[0].timeout_seconds == pytest.approx(200.0)  # clean_wall x mult

    def test_does_not_mutate_original_tasks(self) -> None:
        original = _task()
        original_timeout = original.timeout_seconds
        _apply_timeouts([original], {}, 10.0, startup_floor=5.0, clean_wall_seconds=1.0)
        assert original.timeout_seconds == original_timeout  # unchanged

    def test_preserves_task_count(self) -> None:
        tasks = [_task(f"m{i}") for i in range(5)]
        result = _apply_timeouts(tasks, {}, 2.0, startup_floor=5.0, clean_wall_seconds=1.0)
        assert len(result) == 5


# ---------------------------------------------------------------------------
# _increment_summary (pure helper)
# ---------------------------------------------------------------------------


class TestIncrementSummary:
    def test_killed_increments_killed(self) -> None:
        s = MutationRunResult()
        _increment_summary(s, "killed")
        assert s.killed == 1

    def test_caught_by_type_check_increments_killed(self) -> None:
        s = MutationRunResult()
        _increment_summary(s, "caught by type check")
        assert s.killed == 1

    def test_survived(self) -> None:
        s = MutationRunResult()
        _increment_summary(s, "survived")
        assert s.survived == 1

    def test_timeout(self) -> None:
        s = MutationRunResult()
        _increment_summary(s, "timeout")
        assert s.timeout == 1

    def test_suspicious(self) -> None:
        s = MutationRunResult()
        _increment_summary(s, "suspicious")
        assert s.suspicious == 1

    def test_skipped(self) -> None:
        s = MutationRunResult()
        _increment_summary(s, "skipped")
        assert s.skipped == 1

    def test_no_tests(self) -> None:
        s = MutationRunResult()
        _increment_summary(s, "no tests")
        assert s.no_tests == 1

    def test_unknown_status_does_not_raise(self) -> None:
        s = MutationRunResult()
        # Should not raise; unknown statuses are silently ignored.
        _increment_summary(s, "totally_unknown_status")
        assert s.killed == 0


# ---------------------------------------------------------------------------
# _update_source_data (pure helper)
# ---------------------------------------------------------------------------


class TestUpdateSourceData:
    """Issue #124 / A1: exact key membership instead of the prefix heuristic.

    Real mutant names are src-stripped by ``get_mutant_name`` while the old
    ``startswith(norm_path)`` heuristic kept the ``src.`` prefix — on
    src-layouts NOTHING ever matched (real .meta files stayed all-``None``),
    and the unanchored prefix let ``pkg.util`` swallow ``pkg.utils`` mutants.
    """

    def test_updates_file_with_src_stripped_name(self) -> None:
        # A1 regression: src/pkg/mod.py owns 'pkg.mod.…' (stripped) names.
        from mutmut_win.models import SourceFileMutationData

        sfd = SourceFileMutationData(path="src/pkg/mod.py")
        sfd.exit_code_by_key = {"pkg.mod.x_f__mutmut_1": None}
        source_data = {"src/pkg/mod.py": sfd}

        _update_source_data("pkg.mod.x_f__mutmut_1", 1, 0.5, source_data)

        assert sfd.exit_code_by_key["pkg.mod.x_f__mutmut_1"] == 1
        assert sfd.durations_by_key["pkg.mod.x_f__mutmut_1"] == 0.5

    def test_no_cross_match_between_similar_module_names(self) -> None:
        # A1 regression: 'pkg.util' must not swallow 'pkg.utils' results.
        from mutmut_win.models import SourceFileMutationData

        util = SourceFileMutationData(path="src/pkg/util.py")
        util.exit_code_by_key = {"pkg.util.x_g__mutmut_1": None}
        utils = SourceFileMutationData(path="src/pkg/utils.py")
        utils.exit_code_by_key = {"pkg.utils.x_f__mutmut_1": None}
        source_data = {"src/pkg/util.py": util, "src/pkg/utils.py": utils}

        _update_source_data("pkg.utils.x_f__mutmut_1", 1, 0.5, source_data)

        assert utils.exit_code_by_key["pkg.utils.x_f__mutmut_1"] == 1
        assert util.exit_code_by_key == {"pkg.util.x_g__mutmut_1": None}

    def test_skips_unknown_name_without_guessing(self) -> None:
        # Membership-only semantics: an unknown name must not be attributed
        # to any file (no fallback guessing).
        from mutmut_win.models import SourceFileMutationData

        sfd = SourceFileMutationData(path="src/baz.py")
        sfd.exit_code_by_key = {"baz.x_known__mutmut_1": None}
        source_data = {"src/baz.py": sfd}

        _update_source_data("foo.x_other__mutmut_1", 1, 0.5, source_data)

        assert sfd.exit_code_by_key == {"baz.x_known__mutmut_1": None}
        assert sfd.durations_by_key == {}

    def test_duration_none_not_stored(self) -> None:
        from mutmut_win.models import SourceFileMutationData

        sfd = SourceFileMutationData(path="src/foo.py")
        sfd.exit_code_by_key = {"foo.bar__mutmut_1": None}
        source_data = {"src/foo.py": sfd}

        _update_source_data("foo.bar__mutmut_1", 1, None, source_data)

        assert sfd.exit_code_by_key["foo.bar__mutmut_1"] == 1
        assert "foo.bar__mutmut_1" not in sfd.durations_by_key


# ---------------------------------------------------------------------------
# _ensure_supported_pytest (issue #125 / A2)
# ---------------------------------------------------------------------------


class TestPytestVersionGuard:
    """Issue #125 / A2: @argfile needs pytest >= 8.2 — fail fast, not per task.

    The worker hands tests to pytest via ``@argfile`` (the only path — no
    dual code paths by design); that syntax exists since pytest 8.2. The
    resolver floor is the primary defence, the guard catches bypassed
    resolvers (``pip --no-deps``, hand-patched envs) BEFORE the first mutant.
    """

    @staticmethod
    def _guard() -> Any:
        # Late import: in the red phase only these tests fail, not collection.
        from mutmut_win.orchestrator import _ensure_supported_pytest

        return _ensure_supported_pytest

    def test_accepts_minimum_version(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(pytest, "__version__", "8.2.0")
        self._guard()()  # must not raise

    def test_rejects_last_pre_argfile_version(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from mutmut_win.exceptions import UnsupportedPytestVersionError

        monkeypatch.setattr(pytest, "__version__", "8.1.2")
        with pytest.raises(UnsupportedPytestVersionError) as excinfo:
            self._guard()()
        # The message is actionable contract: found version, required
        # version, the @argfile reason, and the concrete fix command.
        message = str(excinfo.value)
        assert message.startswith("pytest 8.1.2 is too old for mutation runs")
        assert "@argfile syntax, which exists since pytest 8.2" in message
        assert 'uv add "pytest>=8.2" --dev' in message  # names the @argfile mechanism as the reason

    def test_rejects_old_major(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from mutmut_win.exceptions import UnsupportedPytestVersionError

        monkeypatch.setattr(pytest, "__version__", "7.4.4")
        with pytest.raises(UnsupportedPytestVersionError):
            self._guard()()

    def test_accepts_dev_and_rc_suffixes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(pytest, "__version__", "9.0.0.dev0")
        self._guard()()
        monkeypatch.setattr(pytest, "__version__", "8.2.0rc1")
        self._guard()()

    def test_two_digit_components_parse_cleanly(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # Kills regex mutants of the (\d+)\.(\d+) pattern: '10.11' must parse
        # as (10, 11) — single-digit or character-class mutants either fail
        # to match (spurious warning) or truncate the comparison.
        monkeypatch.setattr(pytest, "__version__", "10.11.2")
        self._guard()()  # must not raise
        assert capsys.readouterr().out == ""  # parsed cleanly — no warning

    def test_double_digit_minor_above_floor_is_accepted(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # Kills the (\d+)\.(\d) minor-truncation mutant: a future pytest
        # 8.10 truncated to (8, 1) would falsely abort below the (8, 2)
        # floor. Must parse as (8, 10) and pass silently.
        monkeypatch.setattr(pytest, "__version__", "8.10.0")
        self._guard()()  # must not raise
        assert capsys.readouterr().out == ""

    def test_unparseable_version_warns_and_proceeds(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # Fail-open by design: the resolver floor is the primary defence; an
        # exotic dev build must not block the run (documented trade-off).
        # The warning line is pinned verbatim — diagnostics are contract.
        monkeypatch.setattr(pytest, "__version__", "exotic-build")
        self._guard()()  # must not raise
        expected = (
            "Warning: could not parse pytest version 'exotic-build' — proceeding "
            "(the pytest>=8.2 dependency floor is the primary guard)."
        )
        assert expected in capsys.readouterr().out.splitlines()

    def test_floor_pin_matches_guard_constant(self) -> None:
        # Drift protection (the #110 pin-test pattern): the pyproject runtime
        # floor must encode exactly MINIMUM_PYTEST_VERSION.
        import tomllib
        from pathlib import Path as _Path

        from mutmut_win.constants import MINIMUM_PYTEST_VERSION

        pyproject = _Path(__file__).parents[2] / "pyproject.toml"
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        pytest_dep = next(
            dep for dep in data["project"]["dependencies"] if dep.startswith("pytest")
        )
        major, minor = MINIMUM_PYTEST_VERSION
        assert pytest_dep == f"pytest>={major}.{minor}"

    def test_run_aborts_before_any_staging(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        # Integration: the guard fires BEFORE copy_src_dir — an unsupported
        # environment must not touch the filesystem.
        from mutmut_win.exceptions import UnsupportedPytestVersionError

        monkeypatch.setattr(pytest, "__version__", "8.1.0")
        monkeypatch.chdir(tmp_path)
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "mod.py").write_text("def f():\n    return 1\n", encoding="utf-8")

        orch = MutationOrchestrator(_config())
        with pytest.raises(UnsupportedPytestVersionError):
            orch.run()
        assert not (tmp_path / "mutants").exists()


# ---------------------------------------------------------------------------
# MutationOrchestrator — init
# ---------------------------------------------------------------------------


class TestMutationOrchestratorInit:
    def test_accepts_config(self) -> None:
        cfg = _config()
        orch = MutationOrchestrator(cfg)
        assert orch._config is cfg

    def test_accepts_injected_runner(self) -> None:
        runner = _make_runner()
        orch = MutationOrchestrator(_config(), runner=runner)
        assert orch._runner is runner

    def test_accepts_injected_executor(self) -> None:
        executor = _make_executor()
        orch = MutationOrchestrator(_config(), executor=executor)
        assert orch._executor_override is executor

    def test_custom_db_path(self, tmp_path: Path) -> None:
        db = tmp_path / "custom.db"
        orch = MutationOrchestrator(_config(), db_path=db)
        assert orch._db_path == db


# ---------------------------------------------------------------------------
# MutationOrchestrator.run — early-exit cases
# ---------------------------------------------------------------------------


class TestMutationOrchestratorRunNoMutants:
    def test_returns_empty_result_when_no_mutants(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        runner = _make_runner()
        executor = _make_executor()
        cfg = _config(paths_to_mutate=["src"])
        orch = MutationOrchestrator(cfg, runner=runner, executor=executor, db_path=tmp_path / "db")
        result = orch.run()
        assert result.total_mutants == 0
        # Clean test and forced-fail should NOT be called when there are no mutants.
        runner.run_clean_test.assert_not_called()


# ---------------------------------------------------------------------------
# MutationOrchestrator.run — clean-test failure
# ---------------------------------------------------------------------------


class TestMutationOrchestratorRunCleanTestFail:
    def test_raises_clean_test_failed_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        # Create a real Python file that produces at least one mutant.
        src = tmp_path / "src"
        src.mkdir()
        (src / "target.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")

        runner = _make_runner(clean_exit=1)
        executor = _make_executor()
        cfg = _config(paths_to_mutate=["src"])
        orch = MutationOrchestrator(cfg, runner=runner, executor=executor, db_path=tmp_path / "db")
        with pytest.raises(CleanTestFailedError):
            orch.run()


# ---------------------------------------------------------------------------
# MutationOrchestrator.run — forced-fail check failure
# ---------------------------------------------------------------------------


class TestMutationOrchestratorRunForcedFailCheck:
    def test_raises_forced_fail_error_when_exit_0(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        src = tmp_path / "src"
        src.mkdir()
        (src / "target.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")

        runner = _make_runner(clean_exit=0, forced_fail_exit=0)
        executor = _make_executor()
        cfg = _config(paths_to_mutate=["src"])
        orch = MutationOrchestrator(cfg, runner=runner, executor=executor, db_path=tmp_path / "db")
        with pytest.raises(ForcedFailError):
            orch.run()


# ---------------------------------------------------------------------------
# MutationOrchestrator.run — full happy-path with mock executor
# ---------------------------------------------------------------------------


class TestMutationOrchestratorRunHappyPath:
    def test_returns_correct_total_mutants(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        src = tmp_path / "src"
        src.mkdir()
        (src / "target.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")

        runner = _make_runner(clean_exit=0, forced_fail_exit=1)
        cfg = _config(paths_to_mutate=["src"])

        # Capture tasks passed to executor.start so we can build matching events.
        captured_tasks: list[MutationTask] = []

        def fake_start(tasks: list[MutationTask]) -> None:
            captured_tasks.extend(tasks)

        executor = MagicMock()
        executor.start.side_effect = fake_start

        def fake_get_events() -> Any:
            pid = os.getpid()
            for task in captured_tasks:
                yield TaskStarted(mutant_name=task.mutant_name, worker_pid=pid)
                yield TaskCompleted(
                    mutant_name=task.mutant_name, worker_pid=pid, exit_code=1, duration=0.05
                )

        executor.get_events.side_effect = fake_get_events

        orch = MutationOrchestrator(cfg, runner=runner, executor=executor, db_path=tmp_path / "db")
        result = orch.run()
        assert result.total_mutants > 0
        assert result.killed == result.total_mutants

    def test_timeout_events_counted(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        src = tmp_path / "src"
        src.mkdir()
        (src / "target.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")

        runner = _make_runner(clean_exit=0, forced_fail_exit=1)
        cfg = _config(paths_to_mutate=["src"])

        captured_tasks: list[MutationTask] = []

        def fake_start(tasks: list[MutationTask]) -> None:
            captured_tasks.extend(tasks)

        executor = MagicMock()
        executor.start.side_effect = fake_start

        def fake_get_events() -> Any:
            pid = os.getpid()
            for task in captured_tasks:
                yield TaskStarted(mutant_name=task.mutant_name, worker_pid=pid)
                # Worker-side timeout: TaskCompleted with exit code 36 (#81).
                yield TaskCompleted(
                    mutant_name=task.mutant_name, worker_pid=pid, exit_code=36, duration=60.0
                )

        executor.get_events.side_effect = fake_get_events

        orch = MutationOrchestrator(cfg, runner=runner, executor=executor, db_path=tmp_path / "db")
        result = orch.run()
        assert result.timeout == result.total_mutants

    def test_results_persisted_to_db(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from mutmut_win.db import load_results

        monkeypatch.chdir(tmp_path)
        src = tmp_path / "src"
        src.mkdir()
        (src / "target.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")

        runner = _make_runner(clean_exit=0, forced_fail_exit=1)
        cfg = _config(paths_to_mutate=["src"])
        db_path = tmp_path / "cache.db"

        captured_tasks: list[MutationTask] = []

        def fake_start(tasks: list[MutationTask]) -> None:
            captured_tasks.extend(tasks)

        executor = MagicMock()
        executor.start.side_effect = fake_start

        def fake_get_events() -> Any:
            pid = os.getpid()
            for task in captured_tasks:
                yield TaskStarted(mutant_name=task.mutant_name, worker_pid=pid)
                yield TaskCompleted(
                    mutant_name=task.mutant_name, worker_pid=pid, exit_code=1, duration=0.01
                )

        executor.get_events.side_effect = fake_get_events

        orch = MutationOrchestrator(cfg, runner=runner, executor=executor, db_path=db_path)
        result = orch.run()
        db_results = load_results(db_path)
        assert len(db_results) == result.total_mutants


# ---------------------------------------------------------------------------
# MutationOrchestrator.run — type-check filter integration (#93)
# ---------------------------------------------------------------------------


def _setup_mini_project(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "target.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")


def _executor_yielding_kills() -> tuple[MagicMock, list[MutationTask]]:
    captured_tasks: list[MutationTask] = []
    executor = MagicMock()
    executor.start.side_effect = captured_tasks.extend

    def fake_get_events() -> Any:
        pid = os.getpid()
        for task in captured_tasks:
            yield TaskStarted(mutant_name=task.mutant_name, worker_pid=pid)
            yield TaskCompleted(
                mutant_name=task.mutant_name, worker_pid=pid, exit_code=1, duration=0.01
            )

    executor.get_events.side_effect = fake_get_events
    return executor, captured_tasks


class TestTypeCheckFilterIntegration:
    def test_all_caught_is_a_successful_run_not_an_indexerror(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # A3-OS-010: all_tasks[0] after the filter crashed when the checker
        # caught everything. 100% caught is a legitimate, successful run.
        import mutmut_win.orchestrator as orch_module

        monkeypatch.chdir(tmp_path)
        _setup_mini_project(tmp_path)

        def catch_everything(
            tasks: list[MutationTask], _source_data: Any, _command: Any
        ) -> tuple[list[MutationTask], set[str]]:
            return [], {t.mutant_name for t in tasks}

        monkeypatch.setattr(orch_module, "_filter_with_type_checker", catch_everything)
        executor, _ = _executor_yielding_kills()
        orch = MutationOrchestrator(
            _config(paths_to_mutate=["src"], type_check_command=["mypy", "--output=json", "."]),
            runner=_make_runner(),
            executor=executor,
            db_path=tmp_path / "db",
        )
        result = orch.run()
        assert result.total_mutants > 0
        assert result.type_check_caught == result.total_mutants
        assert result.score == pytest.approx(100.0)
        executor.start.assert_not_called()  # nothing left to execute

    def test_caught_mutants_are_persisted_and_counted_in_their_own_bucket(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # A3-OS-003: type-check kills never reached the DB — results/CICD
        # diverged from the run gate forever. They also flowed into `killed`
        # while the dedicated type_check_caught field stayed orphaned at 0.
        import mutmut_win.orchestrator as orch_module
        from mutmut_win.db import load_results

        monkeypatch.chdir(tmp_path)
        _setup_mini_project(tmp_path)

        def catch_first(
            tasks: list[MutationTask], _source_data: Any, _command: Any
        ) -> tuple[list[MutationTask], set[str]]:
            return tasks[1:], {tasks[0].mutant_name}

        monkeypatch.setattr(orch_module, "_filter_with_type_checker", catch_first)
        executor, _ = _executor_yielding_kills()
        db_path = tmp_path / "cache.db"
        orch = MutationOrchestrator(
            _config(paths_to_mutate=["src"], type_check_command=["mypy", "--output=json", "."]),
            runner=_make_runner(),
            executor=executor,
            db_path=db_path,
        )
        result = orch.run()

        assert result.type_check_caught == 1
        assert result.killed == result.total_mutants - 1  # buckets disjoint
        assert result.score == pytest.approx(100.0)

        rows = {r.mutant_name: r for r in load_results(db_path)}
        assert len(rows) == result.total_mutants  # caught row included
        caught_rows = [r for r in rows.values() if r.status == "caught by type check"]
        assert len(caught_rows) == 1
        assert caught_rows[0].exit_code == 37


# ---------------------------------------------------------------------------
# MutationOrchestrator.run — keyboard interrupt
# ---------------------------------------------------------------------------


class TestMutationOrchestratorKeyboardInterrupt:
    def test_shutdown_called_on_keyboard_interrupt(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        src = tmp_path / "src"
        src.mkdir()
        (src / "target.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")

        runner = _make_runner(clean_exit=0, forced_fail_exit=1)
        executor = MagicMock()
        executor.start.return_value = None
        executor.get_events.side_effect = KeyboardInterrupt

        cfg = _config(paths_to_mutate=["src"])
        orch = MutationOrchestrator(cfg, runner=runner, executor=executor, db_path=tmp_path / "db")
        # KeyboardInterrupt is caught internally; run() should return a result.
        result = orch.run()
        executor.shutdown.assert_called_once()
        assert isinstance(result, MutationRunResult)

    def test_interrupted_run_reports_honestly(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Issue #94 / A3-OS-005: Ctrl-C used to end as a regular completion —
        # full denominator (deflated score), no marker, exit 0.
        monkeypatch.chdir(tmp_path)
        _setup_mini_project(tmp_path)

        captured_tasks: list[MutationTask] = []
        executor = MagicMock()
        executor.start.side_effect = captured_tasks.extend

        def one_kill_then_interrupt() -> Any:
            pid = os.getpid()
            task = captured_tasks[0]
            yield TaskStarted(mutant_name=task.mutant_name, worker_pid=pid)
            yield TaskCompleted(
                mutant_name=task.mutant_name, worker_pid=pid, exit_code=1, duration=0.01
            )
            raise KeyboardInterrupt

        executor.get_events.side_effect = one_kill_then_interrupt

        orch = MutationOrchestrator(
            _config(paths_to_mutate=["src"]),
            runner=_make_runner(),
            executor=executor,
            db_path=tmp_path / "db",
        )
        result = orch.run()

        assert result.was_interrupted is True
        assert result.killed == 1
        assert result.unchecked == result.total_mutants - 1
        # The score must be computed over the CHECKED mutants only:
        # 1 kill of 1 checked = 100%, not 1/total.
        assert result.score == pytest.approx(100.0)

    def test_complete_run_has_no_unchecked_and_no_interrupt_flag(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        _setup_mini_project(tmp_path)
        executor, _ = _executor_yielding_kills()
        orch = MutationOrchestrator(
            _config(paths_to_mutate=["src"]),
            runner=_make_runner(),
            executor=executor,
            db_path=tmp_path / "db",
        )
        result = orch.run()
        assert result.was_interrupted is False
        assert result.unchecked == 0


# ---------------------------------------------------------------------------
# _update_summary_and_persist — event routing
# ---------------------------------------------------------------------------


class TestUpdateSummaryAndPersist:
    def test_task_started_is_ignored(self, tmp_path: Path) -> None:
        db = tmp_path / "db.sqlite"
        summary = MutationRunResult(total_mutants=1)
        event = TaskStarted(mutant_name="m1", worker_pid=1)
        _update_summary_and_persist(event, summary, db, {})
        # No DB file created, no counters changed.
        assert not db.exists()
        assert summary.killed == 0

    def test_task_completed_killed(self, tmp_path: Path) -> None:
        from mutmut_win.db import load_results

        db = tmp_path / "db.sqlite"
        summary = MutationRunResult(total_mutants=1)
        event = TaskCompleted(mutant_name="m1", worker_pid=1, exit_code=1, duration=0.5)
        _update_summary_and_persist(event, summary, db, {})
        assert summary.killed == 1
        results = load_results(db)
        assert results[0].status == "killed"

    def test_worker_reported_timeout(self, tmp_path: Path) -> None:
        """Timeouts arrive as TaskCompleted with exit code 36 since the dead
        WallClockTimeout monitor was removed (issue #81)."""
        from mutmut_win.db import load_results

        db = tmp_path / "db.sqlite"
        summary = MutationRunResult(total_mutants=1)
        event = TaskCompleted(mutant_name="m1", worker_pid=1, exit_code=36, duration=60.0)
        _update_summary_and_persist(event, summary, db, {})
        assert summary.timeout == 1
        results = load_results(db)
        assert results[0].status == "timeout"


# ---------------------------------------------------------------------------
# _filter_tasks_by_names — F2 mutant_names filtering
# ---------------------------------------------------------------------------


class TestFilterTasksByNames:
    def test_exact_match_keeps_task(self) -> None:
        tasks = [_task("src.foo.x_bar__mutmut_1"), _task("src.foo.x_baz__mutmut_2")]
        result = _filter_tasks_by_names(tasks, ("src.foo.x_bar__mutmut_1",))
        assert len(result) == 1
        assert result[0].mutant_name == "src.foo.x_bar__mutmut_1"

    def test_fnmatch_glob_pattern(self) -> None:
        tasks = [
            _task("src.foo.x_bar__mutmut_1"),
            _task("src.foo.x_bar__mutmut_2"),
            _task("src.baz.x_qux__mutmut_1"),
        ]
        result = _filter_tasks_by_names(tasks, ("src.foo.*",))
        assert len(result) == 2
        assert all(t.mutant_name.startswith("src.foo.") for t in result)

    def test_multiple_patterns(self) -> None:
        tasks = [
            _task("src.a.x_fn__mutmut_1"),
            _task("src.b.x_fn__mutmut_1"),
            _task("src.c.x_fn__mutmut_1"),
        ]
        result = _filter_tasks_by_names(tasks, ("src.a.*", "src.c.*"))
        names = {t.mutant_name for t in result}
        assert "src.a.x_fn__mutmut_1" in names
        assert "src.c.x_fn__mutmut_1" in names
        assert "src.b.x_fn__mutmut_1" not in names

    def test_no_match_returns_empty(self) -> None:
        tasks = [_task("src.foo.x_bar__mutmut_1")]
        result = _filter_tasks_by_names(tasks, ("src.totally_different.*",))
        assert result == []

    def test_empty_names_returns_empty(self) -> None:
        tasks = [_task("src.foo.x_bar__mutmut_1")]
        result = _filter_tasks_by_names(tasks, ())
        assert result == []

    def test_preserves_order(self) -> None:
        tasks = [_task(f"src.mod.x_fn__mutmut_{i}") for i in range(5)]
        result = _filter_tasks_by_names(tasks, ("src.mod.*",))
        assert [t.mutant_name for t in result] == [t.mutant_name for t in tasks]


# ---------------------------------------------------------------------------
# MutationOrchestrator — F7 sort by estimated_time
# ---------------------------------------------------------------------------


class TestSortByEstimatedTime:
    def test_apply_timeouts_result_is_sortable(self) -> None:
        """F7: tasks after _apply_timeouts can be sorted by estimated_time."""
        tasks = [
            _task("m3", tests=["t3"]),
            _task("m1", tests=["t1"]),
            _task("m2", tests=["t2"]),
        ]
        stats = {"t1": 0.1, "t2": 1.0, "t3": 0.5}
        result = _apply_timeouts(tasks, stats, 1.0, startup_floor=5.0, clean_wall_seconds=2.0)
        sorted_result = sorted(result, key=lambda t: t.estimated_time)
        times = [t.estimated_time for t in sorted_result]
        assert times == sorted(times)

    def test_tasks_sorted_ascending_by_estimated_time(self) -> None:
        """F7: after sorting, fast mutants come first."""
        tasks = [
            _task("fast", tests=["t_fast"]),
            _task("slow", tests=["t_slow"]),
        ]
        stats = {"t_fast": 0.1, "t_slow": 5.0}
        result = _apply_timeouts(tasks, stats, 1.0, startup_floor=5.0, clean_wall_seconds=6.0)
        result.sort(key=lambda t: t.estimated_time)
        assert result[0].mutant_name == "fast"
        assert result[1].mutant_name == "slow"


# ---------------------------------------------------------------------------
# MutationOrchestrator — F2 mutant_names parameter in __init__
# ---------------------------------------------------------------------------


class TestMutationOrchestratorMutantNamesParam:
    def test_accepts_mutant_names_in_init(self) -> None:
        cfg = _config()
        orch = MutationOrchestrator(cfg, mutant_names=("src.foo.*",))
        assert orch._mutant_names == ("src.foo.*",)

    def test_mutant_names_none_by_default(self) -> None:
        cfg = _config()
        orch = MutationOrchestrator(cfg)
        assert orch._mutant_names is None
