"""Issue #117 (closure dossier): --treat-timeout-as-kill deprecation.

The Sprint-23 stopgap flag (Bug #71: Hypothesis suites turn
infinite-loop mutations into TIMEOUT) is superseded by true
infinite-loop detection (v2.5.0, honest since v2.8.0). Decision closed
with this issue: deprecate now — warn on use, stay functional through
2.x — remove in a future major release.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from mutmut_win.cli import cli
from mutmut_win.models import MutationResult


def _results_rows() -> list[MutationResult]:
    return [
        MutationResult(mutant_name="m1", status="killed"),
        MutationResult(mutant_name="m2", status="timeout"),
    ]


class TestDeprecationNotice:
    def test_results_with_flag_warns(self) -> None:
        with patch("mutmut_win.cli.load_results", return_value=_results_rows()):
            result = CliRunner().invoke(cli, ["results", "--treat-timeout-as-kill"])
        assert result.exit_code == 0
        assert "deprecated" in result.output
        assert "infinite-loop detection" in result.output

    def test_results_without_flag_stays_silent(self) -> None:
        with patch("mutmut_win.cli.load_results", return_value=_results_rows()):
            result = CliRunner().invoke(cli, ["results"])
        assert result.exit_code == 0
        assert "deprecated" not in result.output

    def test_run_with_flag_warns(self) -> None:
        mock_orchestrator = MagicMock()
        from mutmut_win.models import MutationRunResult

        mock_orchestrator.run.return_value = MutationRunResult()
        with (
            patch("mutmut_win.cli.load_config", return_value=MagicMock(max_children=2)),
            patch("mutmut_win.cli.MutationOrchestrator", return_value=mock_orchestrator),
            patch("mutmut_win.cli.PytestRunner"),
            patch("mutmut_win.cli.SpawnPoolExecutor"),
        ):
            result = CliRunner().invoke(cli, ["run", "--treat-timeout-as-kill"])
        assert result.exit_code == 0
        assert "deprecated" in result.output

    def test_flag_remains_functional(self) -> None:
        """Deprecated, NOT removed — the displayed score still shifts."""
        with patch("mutmut_win.cli.load_results", return_value=_results_rows()):
            result = CliRunner().invoke(cli, ["results", "--treat-timeout-as-kill"])
        assert "100.0%" in result.output  # timeout counted as kill

    def test_help_marks_the_flag_deprecated(self) -> None:
        result = CliRunner().invoke(cli, ["results", "--help"])
        assert "DEPRECATED" in result.output
