"""S3-020: zero collected tests cannot authorize a mutation score."""

from typing import TYPE_CHECKING

import pytest
from click.testing import CliRunner
from hypothesis import given
from hypothesis import strategies as st

from mutmut_win.cli import cli
from mutmut_win.models import MutationRunResult
from mutmut_win.orchestrator import MutationOrchestrator
from mutmut_win.stats import CicdStats

if TYPE_CHECKING:
    from pathlib import Path


@given(killed=st.integers(0, 12), no_tests=st.integers(1, 12), skipped=st.integers(0, 5))
def test_historical_diagnostic_score_contract_is_preserved(
    killed: int, no_tests: int, skipped: int
) -> None:
    """Historical diagnostic percentages stay readable without gate authority."""
    total = killed + no_tests + skipped
    run = MutationRunResult(total_mutants=total, killed=killed, no_tests=no_tests, skipped=skipped)
    aggregate = CicdStats(total=total, killed=killed, no_tests=no_tests, skipped=skipped)
    expected = 100.0 if killed else 0.0
    assert run.score == pytest.approx(expected)
    assert aggregate.scoreable == killed
    assert aggregate.score == pytest.approx(expected)


@pytest.mark.parametrize("threshold", [0, 80])
@pytest.mark.parametrize("no_tests", [0, 1])
def test_min_score_requires_test_evidence_even_at_zero_threshold(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, threshold: int, no_tests: int
) -> None:
    """The gate rejects an unresolved population and accepts the healthy arm."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "sample.py").write_text("def value():\n    return 1\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        '[tool.mutmut]\npaths_to_mutate = ["sample.py"]\n', encoding="utf-8"
    )
    summary = MutationRunResult(
        total_mutants=2, killed=2 - no_tests, no_tests=no_tests, execution_basis_complete=True
    )
    monkeypatch.setattr(MutationOrchestrator, "run", lambda _: summary)
    result = CliRunner().invoke(cli, ["run", "--min-score", str(threshold), "--output", "json"])
    if no_tests:
        assert result.exit_code == 1, result.output
        assert "no_tests" in result.stderr
        assert "score gate failed closed" in result.stderr
    else:
        assert result.exit_code == 0, result.output
        assert '"score": 100.0' in result.stdout
