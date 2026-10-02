"""Issue #120 (external QA RUN-002, CLI-001, CLI-002, CFG-001): CLI/config contract.

RUN-002 — a ``--paths-to-mutate`` subset run narrowed the staging and the
stale-result purge then deleted every DB row outside the given paths;
the README-recommended targeted workflow silently destroyed full-run
history. Any path override now counts as a subset run (purge off).

CLI-002 — a typo'd path yielded "No mutants generated." with exit 0: a
false CI success. A missing mutation root is a configuration error.

CLI-001 — ``--min-score 150`` ran the full (hours-long) suite before the
gate trivially failed; range validation now happens upfront.

CFG-001 — invalid ``[tool.mutmut]`` values exited 1 with a 47-line
traceback while CLI flags with the SAME rules exited 2 cleanly; ``run``
now loads its config through the same exit-2 helper as show/apply.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from mutmut_win.cli import cli
from mutmut_win.models import MutationRunResult

pytestmark = pytest.mark.usefixtures("isolated_cli_workspace")

if TYPE_CHECKING:
    from pathlib import Path


def _invoke_run(*args: str, src_paths: list[str] | None = None) -> tuple[Any, MagicMock]:
    """Invoke ``run`` with runner/executor/orchestrator mocked out."""
    orchestrator_cls = MagicMock()
    orchestrator = MagicMock()
    # Non-empty all-killed result: the score gate passes for any threshold.
    orchestrator.run.return_value = MutationRunResult(
        total_mutants=10,
        killed=10,
        execution_basis_complete=True,
    )
    orchestrator.dry_run.return_value = MutationRunResult(total_mutants=10)
    orchestrator_cls.return_value = orchestrator
    config = MagicMock(max_children=2, debug=False)
    config.paths_to_mutate = src_paths if src_paths is not None else []
    config.model_dump.return_value = {}
    with (
        patch("mutmut_win.cli.load_config", return_value=config),
        patch("mutmut_win.cli.MutationOrchestrator", orchestrator_cls),
        patch("mutmut_win.cli.PytestRunner"),
        patch("mutmut_win.cli.SpawnPoolExecutor"),
    ):
        result = CliRunner().invoke(cli, ["run", *args])
    return result, orchestrator_cls


# ---------------------------------------------------------------------------
# RUN-002 — path overrides are subset runs (no purge)
# ---------------------------------------------------------------------------


class TestSubsetPurgeWiring:
    def _purge_flag(self, orchestrator_cls: MagicMock) -> bool:
        assert orchestrator_cls.call_count == 1
        return bool(orchestrator_cls.call_args.kwargs["purge_stale_results"])

    def _full_run_flag(self, orchestrator_cls: MagicMock) -> bool:
        assert orchestrator_cls.call_count == 1
        return bool(orchestrator_cls.call_args.kwargs["is_full_run"])

    @pytest.mark.parametrize(
        "selection",
        [
            ("pkg.x_f__mutmut_1",),
            ("--paths-to-mutate", "src/one.py"),
            ("--since-commit", "HEAD~1"),
        ],
    )
    def test_subset_selection_cannot_authorize_min_score(
        self,
        selection: tuple[str, ...],
    ) -> None:
        result, orchestrator_cls = _invoke_run("--min-score", "100", *selection)

        assert result.exit_code == 2
        assert "--min-score requires a full unfiltered run" in result.output
        orchestrator_cls.assert_not_called()

    def test_plain_run_purges(self) -> None:
        result, orch = _invoke_run()
        assert result.exit_code == 0, result.output
        assert self._purge_flag(orch) is True
        assert self._full_run_flag(orch) is True

    def test_paths_override_disables_purge(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """RUN-002: the staging holds only the override slice — purging
        against it would delete every result outside the slice."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "mod.py").write_text("def f():\n    return 1\n", encoding="utf-8")
        result, orch = _invoke_run("--paths-to-mutate", "mod.py")
        assert result.exit_code == 0, result.output
        assert self._purge_flag(orch) is False
        assert self._full_run_flag(orch) is False

    def test_name_filter_disables_purge(self) -> None:
        """Regression pin — name-pattern subsets were already correct."""
        result, orch = _invoke_run("pkg.mod.x_f__mutmut_1")
        assert result.exit_code == 0, result.output
        assert self._purge_flag(orch) is False
        assert self._full_run_flag(orch) is False


class TestDryRunMinScoreConflict:
    """M-073: ``--dry-run --min-score`` is an options conflict (exit 2).

    A dry-run preview executes no tests, so ``MutationOrchestrator.dry_run``
    returns a result whose ``execution_basis_complete`` stays ``False``.
    The score gate therefore used to fail AFTER the preview with the
    misleading runtime diagnosis "Execution basis incomplete" (exit 1)
    instead of rejecting the incompatible request upfront like the subset
    selection conflict below.
    """

    def test_dry_run_with_min_score_is_a_usage_error(self) -> None:
        result, orchestrator_cls = _invoke_run("--dry-run", "--min-score", "50")

        assert result.exit_code == 2
        assert "--dry-run" in result.stderr
        assert "cannot be combined" in result.stderr
        orchestrator_cls.assert_not_called()

    def test_dry_run_with_min_score_json_error_object(self) -> None:
        result, _orch = _invoke_run("--output", "json", "--dry-run", "--min-score", "50")

        payload = json.loads(result.stdout)
        assert payload["exit_code"] == 2
        assert "--dry-run" in payload["error"]
        assert "cannot be combined" in result.stderr

    def test_dry_run_with_min_score_and_force_keeps_staging(
        self,
        isolated_cli_workspace: Path,
    ) -> None:
        staging = isolated_cli_workspace / "mutants"
        staging.mkdir()
        marker = staging / "marker.txt"
        marker.write_text("staging evidence", encoding="utf-8")

        result, _orch = _invoke_run("--dry-run", "--min-score", "50", "--force")

        assert result.exit_code == 2
        assert marker.read_text(encoding="utf-8") == "staging evidence"
        # The workspace lock was released with the exit: a follow-up --force
        # run acquires it and removes the untouched staging.
        follow_up, _orch = _invoke_run("--force")
        assert follow_up.exit_code == 0, follow_up.output
        assert "Removed mutants/" in follow_up.output
        assert not staging.exists()

    def test_plain_dry_run_still_succeeds(self) -> None:
        result, _orch = _invoke_run("--dry-run")

        assert result.exit_code == 0, result.output


# ---------------------------------------------------------------------------
# CLI-001 — --min-score range validation
# ---------------------------------------------------------------------------


class TestMinScoreRange:
    def test_above_100_is_rejected_upfront(self) -> None:
        result, orch = _invoke_run("--min-score", "150")
        assert result.exit_code == 2
        assert orch.call_count == 0  # no work before the rejection
        assert "150" in result.output

    def test_negative_is_rejected_upfront(self) -> None:
        result, orch = _invoke_run("--min-score", "-5")
        assert result.exit_code == 2
        assert orch.call_count == 0

    def test_boundaries_are_accepted(self) -> None:
        for value in ("0", "100"):
            result, _orch = _invoke_run("--min-score", value)
            assert result.exit_code == 0, result.output

    @pytest.mark.parametrize("value", ["nan", "NaN", "inf", "+inf", "-inf"])
    def test_non_finite_values_are_rejected_upfront(self, value: str) -> None:
        """NaN made every ``score < threshold`` comparison false."""
        result, orch = _invoke_run("--min-score", value)
        assert result.exit_code == 2
        assert orch.call_count == 0
        assert "finite" in result.output.lower() or "range" in result.output.lower()


# ---------------------------------------------------------------------------
# CLI-002 — missing mutation paths are configuration errors
# ---------------------------------------------------------------------------


class TestPathExistence:
    def test_nonexistent_override_exits_2(self) -> None:
        result, orch = _invoke_run("--paths-to-mutate", "does_not_exist/")
        assert result.exit_code == 2
        assert "does_not_exist" in result.output
        assert orch.call_count == 0

    def test_nonexistent_config_path_exits_2(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / "pyproject.toml").write_text(
            '[tool.mutmut]\npaths_to_mutate = ["vanished/"]\n', encoding="utf-8"
        )
        result = CliRunner().invoke(cli, ["run", "--dry-run"])
        assert result.exit_code == 2
        assert "vanished" in result.output

    def test_existing_paths_pass(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / "mod.py").write_text("def f():\n    return 1\n", encoding="utf-8")
        result, _orch = _invoke_run("--paths-to-mutate", "mod.py")
        assert result.exit_code == 0, result.output


# ---------------------------------------------------------------------------
# CFG-001 — config errors exit 2 with the compact message
# ---------------------------------------------------------------------------


class TestConfigErrorContract:
    @pytest.mark.parametrize(
        "toml_value",
        [
            "max_children = 0",
            "max_stack_depth = 0",
            'max_children = "viele"',
        ],
    )
    def test_invalid_toml_value_exits_2_without_traceback(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, toml_value: str
    ) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / "src").mkdir()
        (tmp_path / "pyproject.toml").write_text(
            f'[tool.mutmut]\npaths_to_mutate = ["src/"]\n{toml_value}\n',
            encoding="utf-8",
        )
        result = CliRunner().invoke(cli, ["run", "--dry-run"])
        assert result.exit_code == 2, result.output
        assert "Traceback" not in result.output
        assert "Invalid [tool.mutmut] configuration" in result.output
