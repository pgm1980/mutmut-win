"""Tests for the CICD IL bucket (Issue #86, audit A3-OS-002).

``compute_cicd_stats`` had no case for ``killed_by_infinite_loop``: IL kills
counted into ``total`` but no bucket, deflating the exported score (verified
33.3 % vs the 66.7 % the ``results`` command reports on identical data).
IL kills now count as ``killed`` (matching the run gate and ``results``) and
are additionally surfaced in an explicit ``killed_by_infinite_loop`` field.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from click.testing import CliRunner

import mutmut_win.cli as cli_module
from mutmut_win.db import create_db, load_results
from mutmut_win.models import MutationRunResult, TaskCompleted
from mutmut_win.orchestrator import _update_summary_and_persist
from mutmut_win.stats import compute_cicd_stats, save_cicd_stats

if TYPE_CHECKING:
    from pathlib import Path

_RESULTS: list[tuple[str, str | None]] = [
    ("m1", "killed"),
    ("m2", "killed_by_infinite_loop"),
    ("m3", "survived"),
]


class TestCicdIlBucket:
    def test_il_kills_count_as_killed(self) -> None:
        stats = compute_cicd_stats(_RESULTS)
        assert stats.killed == 2  # was 1 before #86
        assert stats.killed_by_infinite_loop == 1

    def test_score_matches_the_results_channel(self) -> None:
        # The run gate and `results` count IL as a kill: 2 of 3 = 66.7 %.
        stats = compute_cicd_stats(_RESULTS)
        assert stats.score == pytest.approx(200.0 / 3.0)

    def test_json_export_surfaces_the_il_field(self, tmp_path: Path) -> None:
        save_cicd_stats(_RESULTS, mutants_dir=tmp_path)
        payload = json.loads((tmp_path / "mutmut-cicd-stats.json").read_text(encoding="utf-8"))
        assert payload["killed"] == 2
        assert payload["killed_by_infinite_loop"] == 1


class TestThreeChannelConsistency:
    """One run, three reporting channels, one score.

    Drives the same three task outcomes (killed / IL-killed / survived)
    through the real plumbing of every channel: the run gate
    (``MutationRunResult`` via the orchestrator), the ``results`` CLI
    command, and the CICD JSON export.
    """

    def test_all_channels_report_the_same_score(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        db_path = tmp_path / "results.sqlite"
        create_db(db_path)
        summary = MutationRunResult(total_mutants=3)
        events = [
            TaskCompleted(mutant_name="pkg.x_f__mutmut_1", worker_pid=1, exit_code=1, duration=0.1),
            TaskCompleted(
                mutant_name="pkg.x_f__mutmut_2", worker_pid=1, exit_code=38, duration=60.0
            ),
            TaskCompleted(mutant_name="pkg.x_f__mutmut_3", worker_pid=1, exit_code=0, duration=0.1),
        ]
        for event in events:
            _update_summary_and_persist(event, summary, db_path, {})

        # Channel 1: run gate (orchestrator summary).
        assert summary.score == pytest.approx(200.0 / 3.0)

        # Channel 2: `results` command on the same DB.
        monkeypatch.setattr(cli_module, "DEFAULT_DB_PATH", db_path)
        output = CliRunner().invoke(cli_module.results, []).output
        assert "Killed:     2  (incl. 1 infinite-loop)" in output
        assert "Score:      66.7%" in output

        # Channel 3: CICD export from the same DB rows.
        rows = load_results(db_path)
        cicd = compute_cicd_stats([(r.mutant_name, r.status) for r in rows])
        assert cicd.score == pytest.approx(200.0 / 3.0)
        assert cicd.killed_by_infinite_loop == 1
