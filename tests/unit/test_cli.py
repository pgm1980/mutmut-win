"""Unit tests for mutmut_win.cli (Click CLI commands).

Uses click.testing.CliRunner with mocked dependencies so no filesystem
mutations or subprocesses are triggered during the test run.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from mutmut_win.cli import cli
from mutmut_win.models import (
    MutationResult,
    MutationRunResult,
)
from mutmut_win.stats import MutmutStats

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
        runner = CliRunner()
        mock_orchestrator = MagicMock()
        mock_orchestrator.run.return_value = MutationRunResult()
        mock_config = MagicMock()
        mock_config.max_children = 4
        mock_config.model_copy.return_value = mock_config

        with (
            patch("mutmut_win.cli.load_config", return_value=mock_config),
            patch("mutmut_win.cli.MutationOrchestrator", return_value=mock_orchestrator),
            patch("mutmut_win.cli.PytestRunner"),
            patch("mutmut_win.cli.SpawnPoolExecutor"),
        ):
            result = runner.invoke(cli, ["run", "--max-children", "4"])

        assert result.exit_code == 0
        mock_config.model_copy.assert_called_once_with(update={"max_children": 4})

    def test_run_exits_nonzero_on_exception(self) -> None:
        runner = CliRunner()
        mock_orchestrator = MagicMock()
        mock_orchestrator.run.side_effect = RuntimeError("clean test failed")

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
        mock_orchestrator.run.return_value = MutationRunResult()
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
        with patch("mutmut_win.cli.load_results", return_value=all_results):
            result = runner.invoke(cli, ["results"])

        assert result.exit_code == 0
        assert "Total:     3" in result.output
        assert "Killed:    1" in result.output
        assert "Survived:  1" in result.output

    def test_results_shows_no_results_message(self) -> None:
        runner = CliRunner()
        with patch("mutmut_win.cli.load_results", return_value=[]):
            result = runner.invoke(cli, ["results"])

        assert result.exit_code == 0
        assert "No results found" in result.output

    def test_results_show_all_flag(self) -> None:
        runner = CliRunner()
        all_results = [
            _make_result("mod.fn__mutmut_1", "killed", 1, 0.1),
            _make_result("mod.fn__mutmut_2", "survived", 0, 0.2),
        ]
        with patch("mutmut_win.cli.load_results", return_value=all_results):
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
        with patch("mutmut_win.cli.load_results", return_value=all_results):
            result = runner.invoke(cli, ["results"])

        # 2 killed / (4 - 1 skipped) = 66.7%
        assert result.exit_code == 0
        assert "66.7%" in result.output

    def test_results_lists_surviving_mutants(self) -> None:
        runner = CliRunner()
        all_results = [
            _make_result("mod.fn__mutmut_5", "survived", 0, 0.1),
        ]
        with patch("mutmut_win.cli.load_results", return_value=all_results):
            result = runner.invoke(cli, ["results"])

        assert "mod.fn__mutmut_5" in result.output


# ---------------------------------------------------------------------------
# show command
# ---------------------------------------------------------------------------


class TestShowCommand:
    def test_show_exits_nonzero_when_no_mutants_dir(self, tmp_path: Path) -> None:
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(cli, ["show", "some.fn__mutmut_1"])

        assert result.exit_code != 0

    def test_show_exits_nonzero_when_mutant_not_found(self, tmp_path: Path) -> None:
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            mutants_dir = Path("mutants")
            mutants_dir.mkdir()
            (mutants_dir / "dummy.py").write_text("# no mutant here", encoding="utf-8")
            result = runner.invoke(cli, ["show", "missing.fn__mutmut_99"])

        assert result.exit_code != 0

    def test_show_prints_diff(self, tmp_path: Path) -> None:
        runner = CliRunner()
        fake_diff = (
            "--- src/sample.py\n+++ src/sample.py\n@@ -1 +1 @@\n-    return 1\n+    return 2"
        )
        with runner.isolated_filesystem(temp_dir=tmp_path):
            Path("mutants").mkdir()
            with (
                patch("mutmut_win.cli.load_config"),
                patch("mutmut_win.cli.get_diff_for_mutant", return_value=fake_diff),
            ):
                result = runner.invoke(cli, ["show", "src.sample.x_foo__mutmut_1"])

        assert result.exit_code == 0
        # The output should contain diff markers
        assert "---" in result.output or "+++" in result.output or "src.sample" in result.output


# ---------------------------------------------------------------------------
# apply command
# ---------------------------------------------------------------------------


class TestApplyCommand:
    def test_apply_exits_nonzero_when_no_mutants_dir(self, tmp_path: Path) -> None:
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(cli, ["apply", "some.fn__mutmut_1"])

        assert result.exit_code != 0

    def test_apply_exits_nonzero_when_mutant_not_found(self, tmp_path: Path) -> None:
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            Path("mutants").mkdir()
            result = runner.invoke(cli, ["apply", "missing.fn__mutmut_99"])

        assert result.exit_code != 0

    def test_apply_writes_mutant_to_source(self, tmp_path: Path) -> None:
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            Path("mutants").mkdir()
            with (
                patch("mutmut_win.cli.load_config"),
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
        stats = MutmutStats()
        with patch("mutmut_win.cli.load_stats", return_value=stats):
            result = runner.invoke(cli, ["tests-for-mutant", "src.mod.x_unknown__mutmut_1"])

        assert result.exit_code == 0
        assert "No tests found" in result.output


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
            patch("mutmut_win.cli.load_results", return_value=all_results),
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
        stats = MutmutStats()
        all_results = [_make_result("src.mod.x_bar__mutmut_2", "survived")]
        with (
            patch("mutmut_win.cli.load_stats", return_value=stats),
            patch("mutmut_win.cli.load_results", return_value=all_results),
        ):
            result = runner.invoke(cli, ["time-estimates"])

        assert result.exit_code == 0
        assert "<no tests>" in result.output

    def test_filters_to_given_mutant_names(self) -> None:
        runner = CliRunner()
        stats = MutmutStats()
        all_results = [
            _make_result("src.a__mutmut_1", "survived"),
            _make_result("src.b__mutmut_2", "killed"),
        ]
        with (
            patch("mutmut_win.cli.load_stats", return_value=stats),
            patch("mutmut_win.cli.load_results", return_value=all_results),
        ):
            result = runner.invoke(cli, ["time-estimates", "src.a__mutmut_1"])

        assert result.exit_code == 0
        assert "src.a__mutmut_1" in result.output
        assert "src.b__mutmut_2" not in result.output


class TestExportCicdStatsCommand:
    def test_exports_stats_file(self, tmp_path: Path) -> None:
        runner = CliRunner()
        all_results = [
            _make_result("a__mutmut_1", "killed"),
            _make_result("a__mutmut_2", "survived"),
        ]
        mutants_dir = tmp_path / "mutants"
        mutants_dir.mkdir()

        with runner.isolated_filesystem(temp_dir=tmp_path):
            Path("mutants").mkdir(exist_ok=True)
            with patch("mutmut_win.cli.load_results", return_value=all_results):
                result = runner.invoke(cli, ["export-cicd-stats"])

        assert result.exit_code == 0
        assert "mutmut-cicd-stats.json" in result.output

    def test_exits_nonzero_when_no_results(self) -> None:
        runner = CliRunner()
        with patch("mutmut_win.cli.load_results", return_value=[]):
            result = runner.invoke(cli, ["export-cicd-stats"])

        assert result.exit_code == 1
        assert "No results found" in result.output

    def test_shows_score(self, tmp_path: Path) -> None:
        runner = CliRunner()
        all_results = [
            _make_result("a__mutmut_1", "killed"),
            _make_result("a__mutmut_2", "killed"),
            _make_result("a__mutmut_3", "survived"),
        ]
        with runner.isolated_filesystem(temp_dir=tmp_path):
            Path("mutants").mkdir(exist_ok=True)
            with patch("mutmut_win.cli.load_results", return_value=all_results):
                result = runner.invoke(cli, ["export-cicd-stats"])

        assert result.exit_code == 0
        assert "Score:" in result.output


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
