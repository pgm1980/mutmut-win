"""E2E: browser/results/show/apply after a real campaign (GAP-5)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.e2e.e2e_util import (
    SIMPLE_LIB,
    copy_project,
    killed_mutant_name,
    run_cli,
)

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.e2e, pytest.mark.slow]


@pytest.fixture(scope="class")
def completed_campaign(tmp_path_factory: pytest.TempPathFactory) -> Path:
    project = copy_project(SIMPLE_LIB, tmp_path_factory.mktemp("browser-e2e"))
    result = run_cli(project, "run", "--no-progress", timeout=600)
    assert result.returncode == 0
    return project


class TestResultsAfterCampaign:
    def test_results_exit_zero_and_shows_mutants(self, completed_campaign: Path) -> None:
        result = run_cli(completed_campaign, "results")
        assert result.returncode == 0
        assert "Total" in result.stdout or "mutant" in result.stdout.lower()


class TestShowAfterCampaign:
    def test_show_known_mutant_produces_diff(self, completed_campaign: Path) -> None:
        mutant = killed_mutant_name(completed_campaign)
        assert mutant is not None
        result = run_cli(completed_campaign, "show", mutant)
        assert result.returncode == 0, (
            f"show must succeed.\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
        assert len(result.stdout.strip()) > 0, "show must produce output"


class TestApplyAfterCampaign:
    def test_apply_killed_mutant_changes_source(self, completed_campaign: Path) -> None:
        mutant = killed_mutant_name(completed_campaign)
        assert mutant is not None
        source_dir = completed_campaign / "src" / "simple_lib"
        before = {p.name: p.read_text(encoding="utf-8") for p in source_dir.glob("*.py")}

        result = run_cli(completed_campaign, "apply", mutant)
        assert result.returncode == 0

        after = {p.name: p.read_text(encoding="utf-8") for p in source_dir.glob("*.py")}
        changed = [n for n in before if before[n] != after.get(n)]
        assert changed, "apply must modify at least one source file"


class TestNoSurvivorsNoCrash:
    def test_results_with_zero_survivors_no_crash(self, completed_campaign: Path) -> None:
        """simple_lib kills all mutants → results/browse must not crash."""

        result = run_cli(completed_campaign, "results")
        assert result.returncode == 0
        assert "survived" not in result.stdout.lower() or "0" in result.stdout
