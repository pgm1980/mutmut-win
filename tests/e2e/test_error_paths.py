"""E2E: error paths and campaign interruption/resume (T2, TM-09).

Includes the Campaign-E2E: a real run is hard-killed mid-dispatch after a
verdict threshold, then restarted — the restarted run must REUSE the prior
verdicts (issue #195 / M-147 end-to-end proof) and still complete.  The
counter-probe invalidates the cache via a changed test basis.
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from tests.e2e.e2e_util import (
    SIMPLE_LIB,
    cache_db,
    copy_project,
    kill_process_tree,
    latest_run_row,
    run_cli,
    run_planned_total,
    run_reused_count,
    run_verdict_counts,
    start_run,
    wait_for_verdicts,
)

pytestmark = [pytest.mark.e2e, pytest.mark.slow]

_VERDICT_THRESHOLD = 3
_CAMPAIGN_BUDGET_SECONDS = 600


def test_e1_missing_tests_reports_clean_error(tmp_path: Path) -> None:
    """A tests-dir without tests fails with a defined message, no traceback."""

    project = copy_project(SIMPLE_LIB, tmp_path)
    (project / "tests" / "test_simple.py").unlink()

    result = run_cli(project, "run", "--no-progress")
    assert result.returncode != 0
    combined = result.stdout + result.stderr
    assert "Traceback (most recent call last)" not in combined


def test_e2_corrupt_cache_db_fails_closed_with_domain_error(tmp_path: Path) -> None:
    """A corrupted cache DB surfaces as domain error (exit 1), no traceback."""

    project = copy_project(SIMPLE_LIB, tmp_path)
    assert run_cli(project, "run", "--no-progress").returncode == 0

    with closing(sqlite3.connect(cache_db(project))) as conn:
        # The modern read path serves the run tables when a run header
        # exists; corrupt the row the reader actually parses.
        conn.execute("UPDATE mutation_run_mutant SET forensics = 'not-json'")
        conn.commit()

    result = run_cli(project, "results")
    assert result.returncode == 1
    combined = result.stdout + result.stderr
    assert "Traceback (most recent call last)" not in combined
    assert "corrupt" in combined.lower() or "invalid persisted data" in combined


def test_e3_campaign_interrupted_run_reuses_verdicts_on_restart(tmp_path: Path) -> None:
    """TM-09 Campaign-E2E: kill mid-dispatch, restart, verdicts are reused."""

    project = copy_project(SIMPLE_LIB, tmp_path)

    process = start_run(project)
    verdicts = wait_for_verdicts(
        project, _VERDICT_THRESHOLD, process, budget_seconds=_CAMPAIGN_BUDGET_SECONDS
    )
    assert process.poll() is None, "the first run must still be alive at kill time"
    assert verdicts >= _VERDICT_THRESHOLD, (
        f"expected at least {_VERDICT_THRESHOLD} verdicts before the kill, got {verdicts}"
    )
    kill_process_tree(process)

    resumed = run_cli(project, "run", "--no-progress")
    assert resumed.returncode == 0, f"stdout:\n{resumed.stdout}\nstderr:\n{resumed.stderr}"

    latest = latest_run_row(project)
    assert latest is not None
    assert latest[1] == "completed"
    reused = run_reused_count(project)
    assert reused >= _VERDICT_THRESHOLD, (
        f"restart must reuse at least {_VERDICT_THRESHOLD} prior verdicts "
        f"(issue #195 / M-147), reused={reused}"
    )
    counts = run_verdict_counts(project)
    assert sum(counts.values()) == run_planned_total(project), (
        "the resumed campaign must still deliver every verdict"
    )


def test_e4_changed_test_basis_invalidates_verdict_cache(tmp_path: Path) -> None:
    """TM-09 counter-probe: a changed test basis must prevent reuse."""

    project = copy_project(SIMPLE_LIB, tmp_path)

    process = start_run(project)
    verdicts = wait_for_verdicts(
        project, _VERDICT_THRESHOLD, process, budget_seconds=_CAMPAIGN_BUDGET_SECONDS
    )
    assert verdicts >= _VERDICT_THRESHOLD
    kill_process_tree(process)

    extra_test = project / "tests" / "test_extra_e4.py"
    extra_test.write_text("def test_extra_e4_bounds():\n    assert 2 + 2 == 4\n", encoding="utf-8")

    resumed = run_cli(project, "run", "--no-progress")
    assert resumed.returncode == 0, f"stdout:\n{resumed.stdout}\nstderr:\n{resumed.stderr}"
    assert run_reused_count(project) == 0, (
        "a changed test basis must invalidate the verdict cache (TM-09 counter-probe)"
    )


def test_e5_unsuitable_timeout_diagnoses_hang_with_frame(tmp_path: Path) -> None:
    """TM-10 at product level: a hanging suite is a diagnosed timeout, not a kill."""

    project = tmp_path / "hang_project"
    (project / "src" / "hanglib").mkdir(parents=True)
    (project / "src" / "hanglib" / "__init__.py").write_text(
        "def add(a, b):\n    return a + b\n", encoding="utf-8"
    )
    (project / "tests").mkdir()
    (project / "tests" / "test_hang.py").write_text(
        "import time\n\ntime.sleep(600)\n", encoding="utf-8"
    )
    (project / "pyproject.toml").write_text(
        "[tool.mutmut]\n"
        'paths-to-mutate = ["src/hanglib/"]\n'
        'tests-dir = ["tests/"]\n'
        "max-children = 2\n"
        "clean-run-timeout = 25\n",
        encoding="utf-8",
    )

    result = run_cli(project, "run", "--no-progress", timeout=180)
    assert result.returncode != 0
    combined = result.stdout + result.stderr
    assert "timed out" in combined.lower(), f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    assert "Traceback (most recent call last)" not in combined
    assert "clean_run_timeout" in combined, (
        "the product error must name the configuring knob (TM-10: "
        "configurable, diagnosed timeout — the frame-level proof lives in "
        f"tests/unit/test_forced_fail_hang_194.py); stdout:\n{result.stdout}"
    )
