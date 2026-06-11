"""Tests for IL-forensics persistence (Issue #85, audit A2-JT-004).

The worker built the forensics dict, ``TaskCompleted`` carried it,
``db.save_result`` had the parameter/column/migration — but the orchestrator
never passed ``event.forensics`` through, so the column was always NULL and
the documented post-hoc verifiability of IL verdicts did not exist.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from mutmut_win.db import create_db, load_results
from mutmut_win.models import MutationRunResult, TaskCompleted
from mutmut_win.orchestrator import _update_summary_and_persist

if TYPE_CHECKING:
    from pathlib import Path

_FORENSICS = {
    "cpu_pct_mean": 96.5,
    "cpu_pct_max": 99.0,
    "output_growth_bytes": 0,
    "running_ratio": 1.0,
    "samples_collected": 19,
    "window_seconds": 10.0,
    "last_output_tail": "test_spin ...",
    "confidence": "high",
}


class TestForensicsPersistence:
    def test_forensics_roundtrip_to_db(self, tmp_path: Path) -> None:
        db_path = tmp_path / "results.sqlite"
        create_db(db_path)
        summary = MutationRunResult(total_mutants=1)
        event = TaskCompleted(
            mutant_name="pkg.x_f__mutmut_1",
            worker_pid=1,
            exit_code=38,
            duration=60.0,
            forensics=_FORENSICS,
        )

        _update_summary_and_persist(event, summary, db_path, {})

        [row] = load_results(db_path)
        assert row.status == "killed_by_infinite_loop"
        assert row.forensics == _FORENSICS  # was always None before #85

    def test_missing_forensics_stays_null(self, tmp_path: Path) -> None:
        db_path = tmp_path / "results.sqlite"
        create_db(db_path)
        summary = MutationRunResult(total_mutants=1)
        event = TaskCompleted(
            mutant_name="pkg.x_f__mutmut_2", worker_pid=1, exit_code=1, duration=0.1
        )

        _update_summary_and_persist(event, summary, db_path, {})

        [row] = load_results(db_path)
        assert row.forensics is None
