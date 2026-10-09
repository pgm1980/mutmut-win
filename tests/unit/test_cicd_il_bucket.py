"""Legacy loop classifications count as timeouts in every reporting channel.

The existing ``killed_by_infinite_loop`` JSON field is retained as a diagnostic
subset of timeouts, without granting historical CPU heuristics kill authority.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from click.testing import CliRunner

import mutmut_win.cli as cli_module
from mutmut_win.db import create_db, load_results, start_run
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
    def test_s3_legacy_loop_result_is_a_conservative_timeout(self) -> None:
        """S3-003: old heuristic kills remain visible without inflating the score."""
        stats = compute_cicd_stats([("a", "killed"), ("b", "killed_by_infinite_loop")])
        assert stats.killed == 1
        assert stats.timeout == 1
        assert stats.killed_by_infinite_loop == 1
        assert stats.score == 50.0

    def test_il_kills_count_as_killed(self) -> None:
        stats = compute_cicd_stats(_RESULTS)
        assert stats.killed == 1
        assert stats.timeout == 1
        assert stats.killed_by_infinite_loop == 1

    def test_score_matches_the_results_channel(self) -> None:
        # One proven kill, one legacy timeout and one survivor: 1 of 3.
        stats = compute_cicd_stats(_RESULTS)
        assert stats.score == pytest.approx(100.0 / 3.0)

    def test_json_export_surfaces_the_il_field(self, tmp_path: Path) -> None:
        save_cicd_stats(_RESULTS, mutants_dir=tmp_path)
        payload = json.loads((tmp_path / "mutmut-cicd-stats.json").read_text(encoding="utf-8"))
        assert payload["killed"] == 1
        assert payload["timeout"] == 1
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
        start_run(db_path, [f"pkg.x_f__mutmut_{index}" for index in range(1, 4)])
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
        assert summary.score == pytest.approx(100.0 / 3.0)
        assert summary.killed == 1
        assert summary.timeout == 1

        # Channel 2: `results` command on the same DB.
        monkeypatch.setattr(cli_module, "DEFAULT_DB_PATH", db_path)
        output = CliRunner().invoke(cli_module.results, []).output
        assert "Killed:     1" in output
        assert "Score:      33.3%" in output
        assert "counted as timeouts" in output

        # Channel 3: CICD export from the same DB rows.
        rows = load_results(db_path)
        cicd = compute_cicd_stats([(r.mutant_name, r.status) for r in rows])
        assert cicd.score == pytest.approx(100.0 / 3.0)
        assert cicd.killed_by_infinite_loop == 1
