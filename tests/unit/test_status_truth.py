"""Tests for status truth (Issue #91, audit A2-EW-020/A4-QX-025/A2-EW-004/A4-UI-009).

The exit-code map carried a dead duplicate key, Windows crash codes fell
into "suspicious", collection-error kills vanished into the
"interrupted by user" black hole, and two statuses counted in the score
denominator without incrementing any bucket.  #91 makes the map true,
the summary buckets complete (with a catch-all and a sum invariant), the
score formula count the full kill class, and `results` render every
bucket that occurs.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from click.testing import CliRunner

import mutmut_win.cli as cli_module
import mutmut_win.constants as constants_module
from mutmut_win.constants import emoji_by_status, status_by_exit_code
from mutmut_win.db import create_db, save_result, start_run
from mutmut_win.models import MutationRunResult, TaskCompleted
from mutmut_win.orchestrator import _increment_summary, _update_summary_and_persist
from mutmut_win.stats import compute_cicd_stats


class TestExitCodeMap:
    def test_no_duplicate_keys_in_the_dict_literal(self) -> None:
        # EW-020: `-24` appeared twice — the first mapping ("killed") was
        # dead code.  Guard structurally via AST so the dict can never grow
        # a silent duplicate again.
        source = Path(constants_module.__file__).read_text(encoding="utf-8")
        duplicates: list[object] = []
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Dict):
                keys = [
                    ast.literal_eval(k)
                    for k in node.keys
                    if k is not None and isinstance(k, (ast.Constant, ast.UnaryOp))
                ]
                duplicates.extend(k for k in set(keys) if keys.count(k) > 1)
        assert not duplicates, f"duplicate dict keys in constants.py: {duplicates}"

    def test_sigxcpu_maps_to_timeout(self) -> None:
        assert status_by_exit_code[-24] == "timeout"

    def test_collection_error_exit_is_a_kill(self) -> None:
        # QX-025: pytest exit 2 in a worker is, for all practical purposes,
        # a collection error caused by the mutant (import-breaking mutation)
        # — an observable behaviour change, i.e. a kill.  Design CoT in the
        # sprint backlog; forensics travel via the captured log tail.
        assert status_by_exit_code[2] == "killed"

    @pytest.mark.parametrize(
        "ntstatus",
        [
            0xC0000005,  # access violation
            0xC00000FD,  # stack overflow (the endless-recursion mutant case)
            0xC0000409,  # stack buffer overrun
        ],
    )
    def test_windows_crash_codes_are_segfaults(self, ntstatus: int) -> None:
        # EW-020: GetExitCodeProcess yields the unsigned DWORD form.
        assert status_by_exit_code[ntstatus] == "segfault"


class TestSummaryBuckets:
    def test_every_known_status_lands_in_a_bucket(self) -> None:
        # EW-004 sum invariant: no status may count toward the total without
        # incrementing a visible bucket.
        summary = MutationRunResult(total_mutants=len(emoji_by_status))
        for status in emoji_by_status:
            _increment_summary(summary, status)
        bucket_sum = (
            summary.killed
            + summary.survived
            + summary.timeout
            + summary.suspicious
            + summary.skipped
            + summary.no_tests
            + summary.segfault
            + summary.type_check_caught
        )
        assert bucket_sum == len(emoji_by_status)

    def test_segfault_status_increments_its_own_bucket(self) -> None:
        summary = MutationRunResult(total_mutants=1)
        _increment_summary(summary, "segfault")
        assert summary.segfault == 1
        assert summary.killed == 0  # buckets stay disjoint

    def test_unknown_status_counts_as_suspicious_and_warns(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        summary = MutationRunResult(total_mutants=1)
        _increment_summary(summary, "definitely-not-a-status")
        assert summary.suspicious == 1
        assert "definitely-not-a-status" in capsys.readouterr().out


class TestScoreFormula:
    def test_score_counts_the_full_kill_class(self) -> None:
        # Numerator = killed + type_check_caught + segfault; buckets disjoint.
        summary = MutationRunResult(
            total_mutants=4, killed=1, type_check_caught=1, segfault=1, survived=1
        )
        assert summary.score == pytest.approx(75.0)

    def test_cicd_score_counts_segfault(self) -> None:
        stats = compute_cicd_stats([("m1", "killed"), ("m2", "segfault"), ("m3", "survived")])
        assert stats.segfault == 1
        assert stats.killed == 1  # disjoint — segfault is not folded into killed
        assert stats.score == pytest.approx(200.0 / 3.0)


class TestThreeChannelSegfaultConsistency:
    def test_all_channels_agree_on_a_segfault_kill(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        db_path = tmp_path / "results.sqlite"
        create_db(db_path)
        start_run(db_path, [f"pkg.x_f__mutmut_{index}" for index in range(1, 4)])
        summary = MutationRunResult(total_mutants=3)
        for name, code in [
            ("pkg.x_f__mutmut_1", 1),
            ("pkg.x_f__mutmut_2", 0xC0000005),
            ("pkg.x_f__mutmut_3", 0),
        ]:
            event = TaskCompleted(mutant_name=name, worker_pid=1, exit_code=code, duration=0.1)
            _update_summary_and_persist(event, summary, db_path, {})

        # Channel 1: run gate.
        assert summary.segfault == 1
        assert summary.score == pytest.approx(200.0 / 3.0)

        # Channel 2: results CLI on the same DB.
        monkeypatch.setattr(cli_module, "DEFAULT_DB_PATH", db_path)
        output = CliRunner().invoke(cli_module.results, []).output
        assert "egfault" in output  # a visible segfault line (UI-009)
        assert "Score:      66.7%" in output

        # Channel 3: CICD export from the same rows.
        from mutmut_win.db import load_results

        rows = load_results(db_path)
        cicd = compute_cicd_stats([(r.mutant_name, r.status) for r in rows])
        assert cicd.score == pytest.approx(200.0 / 3.0)


class TestResultsRendersEveryBucket:
    def test_segfault_and_not_checked_rows_are_visible(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # UI-009: these statuses counted in Total (and the denominator)
        # but appeared in no line of the output.
        db_path = tmp_path / "results.sqlite"
        create_db(db_path)
        save_result(db_path, "pkg.x_f__mutmut_1", "killed", 1, 0.1)
        save_result(db_path, "pkg.x_f__mutmut_2", "segfault", 3221225477, 0.1)
        save_result(db_path, "pkg.x_f__mutmut_3", "not checked", None, None)
        save_result(db_path, "pkg.x_f__mutmut_4", "check was interrupted by user", 2, 0.1)

        monkeypatch.setattr(cli_module, "DEFAULT_DB_PATH", db_path)
        result = CliRunner().invoke(cli_module.results, [])
        assert result.exit_code == 0, result.output
        out = result.output
        assert "egfault" in out
        assert "ot checked" in out
        assert "nterrupted" in out  # legacy rows from pre-v2.9 runs stay visible
        assert "Total:      4" in out
        # Issue #115 / A4-UI-015: labels wider than the field width get a
        # separating space too — no "user:1" squeeze.
        assert "Check was interrupted by user: 1" in out
