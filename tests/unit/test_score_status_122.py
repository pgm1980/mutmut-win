"""Issue #122 (external QA SCO-001, SCO-002, SCO-003): score/status consistency.

SCO-002 — ``skipped`` (exit 34) had NO producer anywhere; the documented
status was unreachable. Producer (maintainer decision): mutants that
exist in the current staging but were excluded by this run's name filter
are persisted as ``skipped`` — only when no DB row exists yet (a real
verdict is never overwritten, #96 history rule).

SCO-001 — the export console line printed "(N killed / M total)" where
N/M is NOT the score — readers verified the score with the wrong
denominator. It now prints the scoreable denominator.

SCO-003 — ``results`` folded ``caught by type check`` into "Killed"
while the run summary and the CI JSON keep it separate; ``results`` now
renders its own ``Type-check:`` line.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

if TYPE_CHECKING:
    from pathlib import Path

import pytest
from click.testing import CliRunner

from mutmut_win.cli import cli
from mutmut_win.constants import EXIT_CODE_SKIPPED
from mutmut_win.db import load_results, save_result
from mutmut_win.models import MutationResult
from mutmut_win.orchestrator import _persist_skipped_mutants
from mutmut_win.stats import CicdStats, compute_cicd_stats

# ---------------------------------------------------------------------------
# SCO-002 — the skipped producer
# ---------------------------------------------------------------------------


class TestSkippedProducer:
    def test_writes_skipped_for_rowless_names(self, tmp_path: Path) -> None:
        db = tmp_path / "db.sqlite"
        _persist_skipped_mutants(db, {"pkg.x_a__mutmut_1", "pkg.x_a__mutmut_2"})
        rows = {r.mutant_name: r for r in load_results(db)}
        assert rows["pkg.x_a__mutmut_1"].status == "skipped"
        assert rows["pkg.x_a__mutmut_1"].exit_code == EXIT_CODE_SKIPPED
        assert len(rows) == 2

    def test_never_overwrites_existing_verdicts(self, tmp_path: Path) -> None:
        """#96 history rule: a real verdict (and even a prior marker) stays."""
        db = tmp_path / "db.sqlite"
        save_result(db, "pkg.x_a__mutmut_1", "killed", 1, 0.5)
        _persist_skipped_mutants(db, {"pkg.x_a__mutmut_1", "pkg.x_a__mutmut_2"})
        rows = {r.mutant_name: r for r in load_results(db)}
        assert rows["pkg.x_a__mutmut_1"].status == "killed"  # untouched
        assert rows["pkg.x_a__mutmut_2"].status == "skipped"

    def test_empty_set_is_a_noop(self, tmp_path: Path) -> None:
        db = tmp_path / "db.sqlite"
        _persist_skipped_mutants(db, set())
        assert not db.exists()

    def test_skipped_is_not_reusable(self) -> None:
        """A later run targeting the mutant must dispatch it for real."""
        from mutmut_win.orchestrator import REUSABLE_STATUSES

        assert "skipped" not in REUSABLE_STATUSES


class TestSkippedProducerWiring:
    def test_name_filtered_run_marks_the_rest_skipped(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """End to end through the orchestrator: a subset run produces
        'skipped' rows for the staged-but-filtered-out mutants."""
        from mutmut_win.config import MutmutConfig
        from mutmut_win.orchestrator import MutationOrchestrator

        monkeypatch.chdir(tmp_path)
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "mod.py").write_text(
            "def add(a, b):\n    return a + b\n", encoding="utf-8"
        )
        runner = MagicMock()
        runner.run_clean_test.return_value = 0
        runner.run_stats.return_value = None
        runner.collect_tests.return_value = []
        runner.run_forced_fail.return_value = 1
        runner.last_forced_fail_attributed = True
        executor = MagicMock()
        executor.get_events.return_value = iter([])
        db = tmp_path / "db.sqlite"
        orch = MutationOrchestrator(
            MutmutConfig(paths_to_mutate=["src"], max_children=1),
            runner=runner,
            executor=executor,
            db_path=db,
            mutant_names=("mod.x_add__mutmut_1",),
        )
        orch.run()
        rows = load_results(db)
        skipped = [r for r in rows if r.status == "skipped"]
        assert skipped, "filtered-out mutants must surface as 'skipped'"
        assert all(r.mutant_name != "mod.x_add__mutmut_1" for r in skipped)


# ---------------------------------------------------------------------------
# SCO-001 — export console line uses the scoreable denominator
# ---------------------------------------------------------------------------


class TestExportDenominatorLine:
    def test_properties_back_the_score_formula(self) -> None:
        stats = CicdStats(total=78, killed=40, no_tests=22, survived=16)
        assert stats.scoreable == 56
        assert stats.effective_killed == 40
        assert stats.score == pytest.approx(40 / 56 * 100.0)

    def test_console_line_shows_scoreable_not_total(self) -> None:
        rows = (
            [MutationResult(mutant_name=f"k{i}", status="killed") for i in range(40)]
            + [MutationResult(mutant_name=f"n{i}", status="no tests") for i in range(22)]
            + [MutationResult(mutant_name=f"s{i}", status="survived") for i in range(16)]
        )
        with (
            patch("mutmut_win.cli.load_results", return_value=rows),
            patch("mutmut_win.cli.save_cicd_stats") as mock_save,
        ):
            mock_save.return_value = compute_cicd_stats([(r.mutant_name, r.status) for r in rows])
            result = CliRunner().invoke(cli, ["export-cicd-stats"])
        assert result.exit_code == 0
        assert "40 killed / 56 scoreable" in result.output
        assert "/ 78" not in result.output  # the misleading raw total is gone


# ---------------------------------------------------------------------------
# SCO-003 — results renders Type-check separately (one scheme everywhere)
# ---------------------------------------------------------------------------


class TestResultsTypeCheckLine:
    def _rows(self) -> list[MutationResult]:
        return [
            MutationResult(mutant_name="k1", status="killed"),
            MutationResult(mutant_name="k2", status="killed"),
            MutationResult(mutant_name="il1", status="killed_by_infinite_loop"),
            MutationResult(mutant_name="tc1", status="caught by type check"),
            MutationResult(mutant_name="s1", status="survived"),
        ]

    def test_type_check_has_its_own_line(self) -> None:
        with patch("mutmut_win.cli.load_results", return_value=self._rows()):
            result = CliRunner().invoke(cli, ["results"])
        assert result.exit_code == 0
        assert "Type-check:  1" in result.output

    def test_killed_excludes_type_check(self) -> None:
        """run summary: Killed=3 (2 plain + 1 IL) and Type-check separate —
        results must agree instead of printing Killed=4."""
        with patch("mutmut_win.cli.load_results", return_value=self._rows()):
            result = CliRunner().invoke(cli, ["results"])
        assert "Killed:     3  (incl. 1 infinite-loop)" in result.output

    def test_score_still_counts_the_kill_class(self) -> None:
        """Presentation changes, the formula does not: (2+1+1)/5 = 80%."""
        with patch("mutmut_win.cli.load_results", return_value=self._rows()):
            result = CliRunner().invoke(cli, ["results"])
        assert "Score:      80.0%" in result.output

    def test_three_channels_agree_with_skipped_rows(self) -> None:
        """SCO-002 + #91: with skipped > 0 the DB-wide channels stay
        consistent — skipped leaves the denominator in both."""
        rows = [
            *self._rows(),
            MutationResult(mutant_name="sk1", status="skipped", exit_code=EXIT_CODE_SKIPPED),
        ]
        cicd = compute_cicd_stats([(r.mutant_name, r.status) for r in rows])
        assert cicd.skipped == 1
        assert cicd.scoreable == 5  # 6 total - 1 skipped
        assert cicd.score == pytest.approx(80.0)
        with patch("mutmut_win.cli.load_results", return_value=rows):
            result = CliRunner().invoke(cli, ["results"])
        assert "Skipped:    1" in result.output
        assert "Score:      80.0%" in result.output
