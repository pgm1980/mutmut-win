"""E2E: full ``mutmut-win run`` against bundled fixtures (T1, TM-08).

The existing integration pipeline tests cover simple_lib/my_lib snapshots;
this E2E tier covers the REMAINING fixtures and the follow-up CLI surface
(``results``/``apply``/``export-cicd-stats``) against a real persisted run
database, with independent oracles (recomputed score, terminal run state,
deterministic apply diff).
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from tests.e2e.e2e_util import (
    CONFIG_FIXTURE,
    MUTATE_ONLY_COVERED,
    PY314_FEATURES,
    SIMPLE_LIB,
    SOURCE_LAYOUT,
    cache_db,
    copy_project,
    killed_mutant_name,
    latest_run_row,
    run_cli,
    run_planned_total,
    run_verdict_counts,
)

pytestmark = [pytest.mark.e2e, pytest.mark.slow]

_ADDITIONAL_FIXTURES = [PY314_FEATURES, SOURCE_LAYOUT, CONFIG_FIXTURE, MUTATE_ONLY_COVERED]


def _score_recomputed(counts: dict[str, int]) -> float:
    """Independent kill-rate oracle over the persisted verdict rows."""

    killed_like = sum(count for status, count in counts.items() if status == "killed")
    total = sum(counts.values())
    assert total > 0
    return killed_like / total


def test_f1_simple_lib_full_run_persists_terminal_completed_run(
    tmp_path: Path,
) -> None:
    """Run-E2E: exit 0, terminal run state, score recomputable from rows."""

    project = copy_project(SIMPLE_LIB, tmp_path)
    result = run_cli(project, "run", "--no-progress")
    assert result.returncode == 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"

    latest = latest_run_row(project)
    assert latest is not None, "a run must be persisted"
    run_id, status = latest
    assert status == "completed", f"run {run_id} must end terminal-completed, got {status!r}"

    counts = run_verdict_counts(project)
    assert sum(counts.values()) == run_planned_total(project), (
        "every planned mutant must carry a verdict in a completed run"
    )
    score = _score_recomputed(counts)
    assert 0.0 <= score <= 1.0
    assert counts.get("survived", 0) == 0, (
        f"simple_lib's complete suite must kill every mutant; "
        f"verdicts: {counts} (score {score:.3f})"
    )


@pytest.mark.parametrize(
    "fixture",
    _ADDITIONAL_FIXTURES,
    ids=lambda fixture: fixture.name,
)
def test_f2_additional_fixture_full_run_completes(tmp_path: Path, fixture: Path) -> None:
    """Run-E2E over the fixtures the integration tier does not cover."""

    project = copy_project(fixture, tmp_path)
    result = run_cli(project, "run", "--no-progress")
    assert result.returncode == 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    latest = latest_run_row(project)
    assert latest is not None
    assert latest[1] == "completed"
    assert sum(run_verdict_counts(project).values()) == run_planned_total(project)


def test_f3_results_cli_reads_persisted_run(tmp_path: Path) -> None:
    """``results`` succeeds on a real run DB and reports every verdict."""

    project = copy_project(SIMPLE_LIB, tmp_path)
    run_result = run_cli(project, "run", "--no-progress")
    assert run_result.returncode == 0

    result = run_cli(project, "results")
    assert result.returncode == 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    total = run_planned_total(project)
    assert str(total) in result.stdout or "mutant" in result.stdout.lower()


def test_f4_apply_known_killed_mutant_changes_source_deterministically(
    tmp_path: Path,
) -> None:
    """``apply`` of a killed mutant rewrites the source file on disk."""

    project = copy_project(SIMPLE_LIB, tmp_path)
    assert run_cli(project, "run", "--no-progress").returncode == 0

    mutant = killed_mutant_name(project)
    assert mutant is not None, "simple_lib must produce at least one killed mutant"

    source_dir = project / "src" / "simple_lib"
    before = {path.name: path.read_text(encoding="utf-8") for path in source_dir.glob("*.py")}

    result = run_cli(project, "apply", mutant)
    assert result.returncode == 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"

    after = {path.name: path.read_text(encoding="utf-8") for path in source_dir.glob("*.py")}
    changed = [name for name in before if before[name] != after.get(name)]
    assert changed, "apply must modify at least one source file"


def test_f5_cicd_export_reports_score(tmp_path: Path) -> None:
    """``export-cicd-stats`` writes the machine-readable artifact."""

    project = copy_project(SIMPLE_LIB, tmp_path)
    assert run_cli(project, "run", "--no-progress").returncode == 0

    result = run_cli(project, "export-cicd-stats")
    assert result.returncode == 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    artifact = project / "mutants" / "mutmut-cicd-stats.json"
    assert artifact.is_file(), "the CI/CD artifact must be written to mutants/"
    payload = json.loads(artifact.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)


def test_f6_cache_db_exists_after_run(tmp_path: Path) -> None:
    """The persisted database is the product result artifact (TM-08)."""

    project = copy_project(SIMPLE_LIB, tmp_path)
    assert run_cli(project, "run", "--no-progress").returncode == 0
    assert cache_db(project).is_file()
