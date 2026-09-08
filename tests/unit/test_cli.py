"""Unit tests for mutmut_win.cli (Click CLI commands).

Uses click.testing.CliRunner with mocked dependencies so no filesystem
mutations or subprocesses are triggered during the test run.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from mutmut_win.cli import cli
from mutmut_win.constants import Profile
from mutmut_win.db import MutationRunState
from mutmut_win.exceptions import StaleStagingError
from mutmut_win.models import (
    MutationResult,
    MutationRunResult,
)
from mutmut_win.stats import MutmutStats

pytestmark = pytest.mark.usefixtures("isolated_cli_workspace")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_result(
    mutant_name: str = "src.foo__mutmut_1",
    status: str = "survived",
    exit_code: int | None = 0,
    duration: float | None = 0.5,
) -> MutationResult:
    return MutationResult(
        mutant_name=mutant_name,
        status=status,
        exit_code=exit_code,
        duration=duration,
    )


_VERIFIED_BASIS = "a" * 64


def _verified_snapshot(
    rows: list[MutationResult],
) -> tuple[MutationRunState, list[MutationResult]]:
    """Return a complete modern run snapshot accepted by the CI gate."""
    names = tuple(row.mutant_name for row in rows)
    return (
        MutationRunState(
            run_id="verified-run",
            status="completed",
            started_at="2026-01-01T00:00:00+00:00",
            finished_at="2026-01-01T00:01:00+00:00",
            planned_names=names,
            completed_results=(),
            completed_names=names,
            pending_names=(),
            universe_fingerprint="b" * 64,
            plan_digest="c" * 64,
            basis_fingerprint=_VERIFIED_BASIS,
            basis_config_json="{}",
            is_full_run=True,
        ),
        rows,
    )


# ---------------------------------------------------------------------------
# run command
# ---------------------------------------------------------------------------


class TestRunCommand:
    def test_run_calls_orchestrator(self) -> None:
        runner = CliRunner()
        mock_run_result = MutationRunResult(total_mutants=2, killed=1, survived=1)
        mock_orchestrator = MagicMock()
        mock_orchestrator.run.return_value = mock_run_result

        with (
            patch("mutmut_win.cli.load_config") as mock_load_config,
            patch("mutmut_win.cli.MutationOrchestrator", return_value=mock_orchestrator),
            patch("mutmut_win.cli.PytestRunner"),
            patch("mutmut_win.cli.SpawnPoolExecutor"),
        ):
            mock_load_config.return_value = MagicMock(max_children=2)
            result = runner.invoke(cli, ["run"])

        assert result.exit_code == 0
        mock_orchestrator.run.assert_called_once()

    def test_run_with_max_children_option(self) -> None:
        # Changed in v2.10.0 (#102 / A3-CM-004): overrides go through a full
        # MutmutConfig re-validation instead of constraint-bypassing
        # model_copy — the orchestrator must receive the validated value.
        from mutmut_win.config import MutmutConfig

        runner = CliRunner()
        mock_orchestrator = MagicMock()
        mock_orchestrator.run.return_value = MutationRunResult(total_mutants=1, killed=1)
        captured: dict[str, int] = {}

        def capture_config(config: MutmutConfig, **_kwargs: object) -> MagicMock:
            captured["max_children"] = config.max_children
            return mock_orchestrator

        with (
            patch("mutmut_win.cli.load_config", return_value=MutmutConfig()),
            patch("mutmut_win.cli.MutationOrchestrator", side_effect=capture_config),
            patch("mutmut_win.cli.PytestRunner"),
            patch("mutmut_win.cli.SpawnPoolExecutor"),
        ):
            result = runner.invoke(cli, ["run", "--max-children", "4"])

        assert result.exit_code == 0
        assert captured["max_children"] == 4

    def test_run_profile_option_overrides_config(self) -> None:
        # C4: --profile basic re-validates the merged config to Profile.BASIC.
        from mutmut_win.config import MutmutConfig

        runner = CliRunner()
        mock_orchestrator = MagicMock()
        mock_orchestrator.run.return_value = MutationRunResult(total_mutants=1, killed=1)
        captured: dict[str, Profile] = {}

        def capture_config(config: MutmutConfig, **_kwargs: object) -> MagicMock:
            captured["profile"] = config.mutation_profile
            return mock_orchestrator

        with (
            patch("mutmut_win.cli.load_config", return_value=MutmutConfig()),
            patch("mutmut_win.cli.MutationOrchestrator", side_effect=capture_config),
            patch("mutmut_win.cli.PytestRunner"),
            patch("mutmut_win.cli.SpawnPoolExecutor"),
        ):
            result = runner.invoke(cli, ["run", "--profile", "basic"])

        assert result.exit_code == 0
        assert captured["profile"] is Profile.BASIC

    def test_run_without_profile_keeps_config_default(self) -> None:
        from mutmut_win.config import MutmutConfig

        runner = CliRunner()
        mock_orchestrator = MagicMock()
        mock_orchestrator.run.return_value = MutationRunResult(total_mutants=1, killed=1)
        captured: dict[str, Profile] = {}

        def capture_config(config: MutmutConfig, **_kwargs: object) -> MagicMock:
            captured["profile"] = config.mutation_profile
            return mock_orchestrator

        with (
            patch("mutmut_win.cli.load_config", return_value=MutmutConfig()),
            patch("mutmut_win.cli.MutationOrchestrator", side_effect=capture_config),
            patch("mutmut_win.cli.PytestRunner"),
            patch("mutmut_win.cli.SpawnPoolExecutor"),
        ):
            result = runner.invoke(cli, ["run"])

        assert result.exit_code == 0
        assert captured["profile"] is Profile.ADVANCED  # config default stands

    def test_run_rejects_invalid_profile(self) -> None:
        # click.Choice rejects an unknown profile before the command body runs.
        runner = CliRunner()
        with (
            patch("mutmut_win.cli.load_config"),
            patch("mutmut_win.cli.MutationOrchestrator"),
            patch("mutmut_win.cli.PytestRunner"),
            patch("mutmut_win.cli.SpawnPoolExecutor"),
        ):
            result = runner.invoke(cli, ["run", "--profile", "aggressive"])

        assert result.exit_code == 2

    @pytest.mark.parametrize("json_output", [False, True])
    def test_force_rejects_staging_collision_before_deleting_state(self, json_output: bool) -> None:
        from mutmut_win.config import MutmutConfig

        runner = CliRunner()
        with runner.isolated_filesystem():
            source = Path("src/mod.py")
            source.parent.mkdir()
            source.write_text("def value():\n    return 1\n", encoding="utf-8")
            Path("src/mod.py.meta").write_bytes(b"PROJECT-FIXTURE-METADATA")
            Path("mutants").mkdir()
            Path("mutants/keep.txt").write_text("old evidence", encoding="utf-8")
            Path(".mutmut-cache").mkdir()
            Path(".mutmut-cache/keep.txt").write_text("old evidence", encoding="utf-8")
            config = MutmutConfig(paths_to_mutate=["src/mod.py"])
            lock = MagicMock()
            lock.__enter__.return_value = lock

            args = ["run", "--force"]
            if json_output:
                args.extend(["--output", "json"])
            with (
                patch("mutmut_win.cli.load_config", return_value=config),
                patch("mutmut_win.cli._require_safe_workspace_roots"),
                patch("mutmut_win.cli.validate_cache_path"),
                patch("mutmut_win.cli.WorkspaceRunLock", return_value=lock),
                patch("mutmut_win.cli.SpawnPoolExecutor") as executor,
            ):
                result = runner.invoke(cli, args)

            assert result.exit_code == 2
            assert "reserved staging namespace" in result.output
            if json_output:
                payload = json.loads(result.stdout)
                assert payload["exit_code"] == 2
                assert "reserved staging namespace" in payload["error"]
            assert Path("mutants/keep.txt").read_text(encoding="utf-8") == "old evidence"
            assert Path(".mutmut-cache/keep.txt").read_text(encoding="utf-8") == "old evidence"
            executor.assert_not_called()

    def test_run_exits_nonzero_on_domain_error(self) -> None:
        """Domain errors render as a one-liner; foreign exceptions propagate
        as real bugs instead (issue #114 / A4-QX-006 — the dedicated
        contract tests live in test_exception_hygiene_114.py)."""
        from mutmut_win.exceptions import CleanTestFailedError

        runner = CliRunner()
        mock_orchestrator = MagicMock()
        mock_orchestrator.run.side_effect = CleanTestFailedError("clean test failed")

        with (
            patch("mutmut_win.cli.load_config") as mock_load_config,
            patch("mutmut_win.cli.MutationOrchestrator", return_value=mock_orchestrator),
            patch("mutmut_win.cli.PytestRunner"),
            patch("mutmut_win.cli.SpawnPoolExecutor"),
        ):
            mock_load_config.return_value = MagicMock(max_children=2)
            result = runner.invoke(cli, ["run"])

        assert result.exit_code == 1
        assert "Error" in result.output

    def test_run_without_max_children_uses_config_default(self) -> None:
        runner = CliRunner()
        mock_orchestrator = MagicMock()
        mock_orchestrator.run.return_value = MutationRunResult(total_mutants=1, killed=1)
        mock_config = MagicMock()
        mock_config.max_children = 2

        with (
            patch("mutmut_win.cli.load_config", return_value=mock_config),
            patch("mutmut_win.cli.MutationOrchestrator", return_value=mock_orchestrator),
            patch("mutmut_win.cli.PytestRunner"),
            patch("mutmut_win.cli.SpawnPoolExecutor"),
        ):
            result = runner.invoke(cli, ["run"])

        # model_copy should NOT be called when --max-children is not passed
        mock_config.model_copy.assert_not_called()
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# results command
# ---------------------------------------------------------------------------


class TestResultsCommand:
    def test_results_shows_summary(self) -> None:
        runner = CliRunner()
        all_results = [
            _make_result("a__mutmut_1", "killed", 1, 0.1),
            _make_result("a__mutmut_2", "survived", 0, 0.2),
            _make_result("a__mutmut_3", "timeout", 36, 1.0),
        ]
        with patch(
            "mutmut_win.cli._load_result_snapshot_or_exit",
            return_value=(None, all_results),
        ):
            result = runner.invoke(cli, ["results"])

        assert result.exit_code == 0
        assert "Total:      3" in result.output
        assert "Killed:     1" in result.output
        assert "Survived:   1" in result.output

    def test_results_marks_subset_score_not_release_ready(self) -> None:
        runner = CliRunner()
        rows = [_make_result("a__mutmut_1", "killed")]
        current, persisted_rows = _verified_snapshot(rows)
        subset = replace(current, is_full_run=False)

        with patch(
            "mutmut_win.cli._load_result_snapshot_or_exit",
            return_value=(subset, persisted_rows),
        ):
            result = runner.invoke(cli, ["results"])

        assert result.exit_code == 0
        assert "subset selection" in result.output
        assert "release-ready: no" in result.output
        assert "Displayed totals and score cover only this subset" in result.output

    def test_results_shows_no_results_message(self) -> None:
        runner = CliRunner()
        with patch(
            "mutmut_win.cli._load_result_snapshot_or_exit",
            return_value=(None, []),
        ):
            result = runner.invoke(cli, ["results"])

        assert result.exit_code == 0
        assert "No results found" in result.output

    def test_results_show_all_flag(self) -> None:
        runner = CliRunner()
        all_results = [
            _make_result("mod.fn__mutmut_1", "killed", 1, 0.1),
            _make_result("mod.fn__mutmut_2", "survived", 0, 0.2),
        ]
        with patch(
            "mutmut_win.cli._load_result_snapshot_or_exit",
            return_value=(None, all_results),
        ):
            result = runner.invoke(cli, ["results", "--all"])

        assert result.exit_code == 0
        assert "mod.fn__mutmut_1" in result.output
        assert "mod.fn__mutmut_2" in result.output

    def test_results_score_calculation(self) -> None:
        runner = CliRunner()
        all_results = [
            _make_result("a__mutmut_1", "killed", 1, 0.1),
            _make_result("a__mutmut_2", "killed", 1, 0.2),
            _make_result("a__mutmut_3", "survived", 0, 0.3),
            _make_result("a__mutmut_4", "skipped", 34, 0.0),
        ]
        with patch(
            "mutmut_win.cli._load_result_snapshot_or_exit",
            return_value=(None, all_results),
        ):
            result = runner.invoke(cli, ["results"])

        # 2 killed / (4 - 1 skipped) = 66.7%
        assert result.exit_code == 0
        assert "66.7%" in result.output

    def test_results_lists_surviving_mutants(self) -> None:
        runner = CliRunner()
        all_results = [
            _make_result("mod.fn__mutmut_5", "survived", 0, 0.1),
        ]
        with patch(
            "mutmut_win.cli._load_result_snapshot_or_exit",
            return_value=(None, all_results),
        ):
            result = runner.invoke(cli, ["results"])

        assert "mod.fn__mutmut_5" in result.output


# ---------------------------------------------------------------------------
# show command
# ---------------------------------------------------------------------------


class TestShowCommand:
    def test_show_exits_nonzero_when_no_mutants_dir(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        runner = CliRunner()
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(cli, ["show", "some.fn__mutmut_1"])

        assert result.exit_code != 0

    def test_show_exits_nonzero_when_mutant_not_found(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        runner = CliRunner()
        monkeypatch.chdir(tmp_path)
        mutants_dir = Path("mutants")
        mutants_dir.mkdir()
        (mutants_dir / "dummy.py").write_text("# no mutant here", encoding="utf-8")
        result = runner.invoke(cli, ["show", "missing.fn__mutmut_99"])

        assert result.exit_code != 0

    def test_show_prints_diff(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        runner = CliRunner()
        fake_diff = (
            "--- src/sample.py\n+++ src/sample.py\n@@ -1 +1 @@\n-    return 1\n+    return 2"
        )
        monkeypatch.chdir(tmp_path)
        Path("mutants").mkdir()
        with (
            patch("mutmut_win.cli.load_config"),
            # show resolves the pattern once and renders directly
            # (issue #127 / 360°-A9) — the seam is resolve+render now.
            patch(
                "mutmut_win.cli.resolve_mutant",
                return_value=("src.sample.x_foo__mutmut_1", MagicMock(path="src/sample.py")),
            ),
            patch("mutmut_win.cli.render_function_diff_bytes", return_value=fake_diff.encode()),
        ):
            result = runner.invoke(cli, ["show", "src.sample.x_foo__mutmut_1"])

        assert result.exit_code == 0
        # The output should contain diff markers
        assert "---" in result.output or "+++" in result.output or "src.sample" in result.output
        assert fake_diff.encode("utf-8") in result.stdout_bytes
        assert b"\r\n" not in result.stdout_bytes

    def test_show_refuses_stale_source_without_printing_a_diff(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        runner = CliRunner()
        monkeypatch.chdir(tmp_path)
        Path("mutants").mkdir()
        with (
            patch("mutmut_win.cli.load_config"),
            patch(
                "mutmut_win.cli.resolve_mutant",
                return_value=("src.sample.x_foo__mutmut_1", MagicMock(path="src/sample.py")),
            ),
            patch(
                "mutmut_win.cli.render_function_diff_bytes",
                side_effect=StaleStagingError(
                    "src/sample.py content cannot be proven to match the source used for "
                    "mutant generation — re-run 'mutmut-win run' before showing or "
                    "applying mutants."
                ),
            ),
        ):
            result = runner.invoke(cli, ["show", "src.sample.x_foo__mutmut_1"])

        assert result.exit_code == 1
        assert "before showing or applying" in result.output
        assert "--- a/" not in result.output


# ---------------------------------------------------------------------------
# apply command
# ---------------------------------------------------------------------------


class TestApplyCommand:
    def test_apply_exits_nonzero_when_no_mutants_dir(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        runner = CliRunner()
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(cli, ["apply", "some.fn__mutmut_1"])

        assert result.exit_code != 0

    def test_apply_exits_nonzero_when_mutant_not_found(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        runner = CliRunner()
        monkeypatch.chdir(tmp_path)
        Path("mutants").mkdir()
        result = runner.invoke(cli, ["apply", "missing.fn__mutmut_99"])

        assert result.exit_code != 0

    def test_apply_writes_mutant_to_source(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        runner = CliRunner()
        monkeypatch.chdir(tmp_path)
        Path("mutants").mkdir()
        with (
            patch("mutmut_win.cli.load_config"),
            patch(
                "mutmut_win.cli.resolve_mutant",
                return_value=("src.sample.x_foo__mutmut_1", MagicMock()),
            ),
            patch("mutmut_win.cli.apply_mutant") as mock_apply,
        ):
            result = runner.invoke(cli, ["apply", "src.sample.x_foo__mutmut_1"])

        assert result.exit_code == 0
        mock_apply.assert_called_once()
        # Check that the "Applied mutant" message appears
        assert "Applied mutant" in result.output


# ---------------------------------------------------------------------------
# browse command
# ---------------------------------------------------------------------------


class TestBrowseCommand:
    def test_browse_invokes_result_browser(self) -> None:
        runner = CliRunner()
        mock_app = MagicMock()
        mock_app_class = MagicMock(return_value=mock_app)

        with patch("mutmut_win.cli.ResultBrowser", mock_app_class):
            result = runner.invoke(cli, ["browse"])

        assert result.exit_code == 0
        mock_app_class.assert_called_once_with(show_killed=False)
        mock_app.run.assert_called_once()

    def test_browse_passes_show_killed_flag(self) -> None:
        runner = CliRunner()
        mock_app = MagicMock()
        mock_app_class = MagicMock(return_value=mock_app)

        with patch("mutmut_win.cli.ResultBrowser", mock_app_class):
            result = runner.invoke(cli, ["browse", "--show-killed"])

        assert result.exit_code == 0
        mock_app_class.assert_called_once_with(show_killed=True)

    def test_browse_exits_nonzero_when_run_raises(self) -> None:
        """If ResultBrowser.run() raises an unexpected error, exit is non-zero."""
        runner = CliRunner()
        mock_app = MagicMock()
        mock_app.run.side_effect = RuntimeError("textual error")
        mock_app_class = MagicMock(return_value=mock_app)

        with patch("mutmut_win.cli.ResultBrowser", mock_app_class):
            result = runner.invoke(cli, ["browse"])

        # CliRunner captures the exception; exit code will be 1
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# __main__ entry point
# ---------------------------------------------------------------------------


class TestTestsForMutantCommand:
    def test_shows_tests_for_known_mutant(self) -> None:
        runner = CliRunner()
        stats = MutmutStats(
            tests_by_mangled_function_name={"src.mod.x_foo": {"tests/t.py::test_a"}},
            duration_by_test={"tests/t.py::test_a": 0.1},
        )
        with patch("mutmut_win.cli.load_stats", return_value=stats):
            result = runner.invoke(cli, ["tests-for-mutant", "src.mod.x_foo__mutmut_1"])

        assert result.exit_code == 0
        assert "tests/t.py::test_a" in result.output

    def test_exits_nonzero_when_no_stats(self) -> None:
        runner = CliRunner()
        with patch("mutmut_win.cli.load_stats", return_value=None):
            result = runner.invoke(cli, ["tests-for-mutant", "src.mod.x_foo__mutmut_1"])

        assert result.exit_code == 1
        assert "No stats found" in result.output

    def test_shows_message_when_no_tests_found(self) -> None:
        runner = CliRunner()
        stats = MutmutStats(mapping_is_authoritative=True)
        with patch("mutmut_win.cli.load_stats", return_value=stats):
            result = runner.invoke(cli, ["tests-for-mutant", "src.mod.x_unknown__mutmut_1"])

        assert result.exit_code == 0
        assert "No tests found" in result.output

    def test_incomplete_mapping_reports_full_suite_not_no_tests(self) -> None:
        runner = CliRunner()
        stats = MutmutStats(mapping_is_authoritative=False)
        with patch("mutmut_win.cli.load_stats", return_value=stats):
            result = runner.invoke(cli, ["tests-for-mutant", "src.mod.x_unknown__mutmut_1"])

        assert result.exit_code == 0
        assert "mapping is incomplete" in result.output
        assert "full test suite" in result.output
        assert "No tests found" not in result.output


class TestTimeEstimatesCommand:
    def test_shows_estimates_for_all_results(self) -> None:
        runner = CliRunner()
        stats = MutmutStats(
            tests_by_mangled_function_name={"src.mod.x_foo": {"tests/t.py::test_a"}},
            duration_by_test={"tests/t.py::test_a": 0.5},
        )
        all_results = [_make_result("src.mod.x_foo__mutmut_1", "survived")]
        with (
            patch("mutmut_win.cli.load_stats", return_value=stats),
            patch("mutmut_win.cli._load_results_or_exit", return_value=all_results),
        ):
            result = runner.invoke(cli, ["time-estimates"])

        assert result.exit_code == 0
        assert "src.mod.x_foo__mutmut_1" in result.output

    def test_exits_nonzero_when_no_stats(self) -> None:
        runner = CliRunner()
        with patch("mutmut_win.cli.load_stats", return_value=None):
            result = runner.invoke(cli, ["time-estimates"])

        assert result.exit_code == 1

    def test_shows_no_tests_for_uncovered_mutant(self) -> None:
        runner = CliRunner()
        stats = MutmutStats(mapping_is_authoritative=True)
        all_results = [_make_result("src.mod.x_bar__mutmut_2", "survived")]
        with (
            patch("mutmut_win.cli.load_stats", return_value=stats),
            patch("mutmut_win.cli._load_results_or_exit", return_value=all_results),
        ):
            result = runner.invoke(cli, ["time-estimates"])

        assert result.exit_code == 0
        assert "<no tests>" in result.output

    def test_malformed_cached_mutant_name_degrades_to_zero_estimate(self) -> None:
        runner = CliRunner()
        stats = MutmutStats(mapping_is_authoritative=True)
        all_results = [_make_result("historical-corrupt-name", "survived")]
        with (
            patch("mutmut_win.cli.load_stats", return_value=stats),
            patch("mutmut_win.cli._load_results_or_exit", return_value=all_results),
        ):
            result = runner.invoke(cli, ["time-estimates"])

        assert result.exit_code == 0
        assert "<no tests>  historical-corrupt-name" in result.output

    def test_incomplete_mapping_estimates_full_suite(self) -> None:
        runner = CliRunner()
        stats = MutmutStats(
            mapping_is_authoritative=False,
            duration_by_test={"tests/t.py::one": 0.25, "tests/t.py::two": 0.75},
        )
        all_results = [_make_result("src.mod.x_bar__mutmut_2", "survived")]
        with (
            patch("mutmut_win.cli.load_stats", return_value=stats),
            patch("mutmut_win.cli._load_results_or_exit", return_value=all_results),
        ):
            result = runner.invoke(cli, ["time-estimates"])

        assert result.exit_code == 0
        assert "1000ms (full suite; mapping incomplete)" in result.output
        assert "<no tests>" not in result.output

    def test_filters_to_given_mutant_names(self) -> None:
        runner = CliRunner()
        stats = MutmutStats()
        all_results = [
            _make_result("src.a__mutmut_1", "survived"),
            _make_result("src.b__mutmut_2", "killed"),
        ]
        with (
            patch("mutmut_win.cli.load_stats", return_value=stats),
            patch("mutmut_win.cli._load_results_or_exit", return_value=all_results),
        ):
            result = runner.invoke(cli, ["time-estimates", "src.a__mutmut_1"])

        assert result.exit_code == 0
        assert "src.a__mutmut_1" in result.output
        assert "src.b__mutmut_2" not in result.output


class TestExportCicdStatsCommand:
    def test_incomplete_live_basis_message_names_generic_type_checker(
        self,
        tmp_path: Path,
    ) -> None:
        from mutmut_win.cli import _stable_live_basis
        from mutmut_win.config import MutmutConfig
        from mutmut_win.exceptions import MutmutWinError
        from mutmut_win.stats import RunBasisEvidence

        config = MutmutConfig(type_check_command=["mypy", "--output=json", "src"])
        with (
            patch(
                "mutmut_win.cli.build_run_basis_evidence",
                return_value=RunBasisEvidence("a" * 64, False),
            ),
            pytest.raises(MutmutWinError, match="generic type_check_command"),
        ):
            _stable_live_basis(config, tmp_path / "cache.db")

    def test_exports_stats_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        runner = CliRunner()
        all_results = [
            _make_result("a__mutmut_1", "killed"),
            _make_result("a__mutmut_2", "survived"),
        ]
        mutants_dir = tmp_path / "mutants"
        mutants_dir.mkdir()

        monkeypatch.chdir(tmp_path)
        Path("mutants").mkdir(exist_ok=True)
        with (
            patch(
                "mutmut_win.cli._load_result_snapshot_or_exit",
                return_value=_verified_snapshot(all_results),
            ),
            patch("mutmut_win.cli._stable_live_basis", return_value=_VERIFIED_BASIS),
        ):
            result = runner.invoke(cli, ["export-cicd-stats"])

        assert result.exit_code == 0
        assert "mutmut-cicd-stats.json" in result.output

    def test_exits_nonzero_when_no_results(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        runner = CliRunner()
        monkeypatch.chdir(tmp_path)
        (tmp_path / "mutants").mkdir()
        with patch(
            "mutmut_win.cli._load_result_snapshot_or_exit",
            return_value=(None, []),
        ):
            result = runner.invoke(cli, ["export-cicd-stats"])

        assert result.exit_code == 1
        assert "No results found" in result.output

    def test_shows_score(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        runner = CliRunner()
        all_results = [
            _make_result("a__mutmut_1", "killed"),
            _make_result("a__mutmut_2", "killed"),
            _make_result("a__mutmut_3", "survived"),
        ]
        monkeypatch.chdir(tmp_path)
        Path("mutants").mkdir(exist_ok=True)
        with (
            patch(
                "mutmut_win.cli._load_result_snapshot_or_exit",
                return_value=_verified_snapshot(all_results),
            ),
            patch("mutmut_win.cli._stable_live_basis", return_value=_VERIFIED_BASIS),
        ):
            result = runner.invoke(cli, ["export-cicd-stats"])

        assert result.exit_code == 0
        assert "Score:" in result.output

    def test_subset_run_cannot_replace_full_run_export_authority(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        runner = CliRunner()
        all_results = [_make_result("a__mutmut_1", "killed")]
        current, rows = _verified_snapshot(all_results)
        subset = replace(current, is_full_run=False)
        monkeypatch.chdir(tmp_path)
        artifact = tmp_path / "mutants" / "mutmut-cicd-stats.json"
        artifact.parent.mkdir()
        artifact.write_text('{"score": 100.0}\n', encoding="utf-8")

        with (
            patch(
                "mutmut_win.cli._load_result_snapshot_or_exit",
                return_value=(subset, rows),
            ),
            patch("mutmut_win.cli._stable_live_basis") as live_basis,
        ):
            result = runner.invoke(cli, ["export-cicd-stats"])

        assert result.exit_code == 1
        assert "subset selection" in result.output
        assert "cannot authorize a full-run CI/CD score" in result.output
        assert not artifact.exists()
        live_basis.assert_not_called()


class TestMainEntryPoint:
    def test_main_module_imports_cli(self) -> None:
        """Verify __main__.py exports the cli object."""
        import mutmut_win.__main__ as main_module

        assert hasattr(main_module, "cli")

    def test_cli_is_click_group(self) -> None:
        import click

        assert isinstance(cli, click.Group)

    def test_cli_has_expected_commands(self) -> None:
        expected = {
            "run",
            "results",
            "show",
            "apply",
            "browse",
            "tests-for-mutant",
            "time-estimates",
            "export-cicd-stats",
        }
        assert expected.issubset(set(cli.commands.keys()))


class TestVersionFlag:
    def test_version_flag_shows_version(self) -> None:
        """F8: --version flag outputs the package version."""
        from mutmut_win import __version__

        runner = CliRunner()
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert __version__ in result.output

    def test_version_flag_exits_zero(self) -> None:
        """F8: --version flag exits with code 0."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Browser import test
# ---------------------------------------------------------------------------


class TestBrowserImport:
    def test_result_browser_importable(self) -> None:
        from mutmut_win.browser import ResultBrowser

        assert ResultBrowser is not None

    def test_result_browser_instantiable(self) -> None:
        from mutmut_win.browser import ResultBrowser

        app = ResultBrowser(show_killed=False)
        assert app is not None
        assert app._show_killed is False

    def test_result_browser_show_killed(self) -> None:
        from mutmut_win.browser import ResultBrowser

        app = ResultBrowser(show_killed=True)
        assert app._show_killed is True

    @pytest.mark.parametrize("show_killed", [True, False])
    def test_result_browser_parametrized(self, show_killed: bool) -> None:
        from mutmut_win.browser import ResultBrowser

        app = ResultBrowser(show_killed=show_killed)
        assert app._show_killed == show_killed
