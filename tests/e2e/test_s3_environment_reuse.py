"""S3-001: actual CLI reuse cannot retain kills across unknown input drift."""

from typing import TYPE_CHECKING

import pytest
from pydantic import BaseModel

from tests.e2e.e2e_util import latest_run_row, run_cli, run_verdict_counts

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.e2e, pytest.mark.slow]


class ReportedRun(BaseModel):
    """Validate reported fields without recomputing the product's score."""

    total_mutants: int
    killed: int
    survived: int
    timeout: int
    unchecked: int
    score: float
    run_aborted: bool
    was_interrupted: bool
    execution_basis_complete: bool


def test_unknown_input_drift_revokes_kills_but_unchanged_context_reuses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """S3-001 binds actual stored verdicts, CLI score and minimum-score exit."""
    project = tmp_path / "environment-project"
    package = project / "src" / "pkg"
    package.mkdir(parents=True)
    (project / "tests").mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "mod.py").write_text("def value():\n    return 1\n", encoding="utf-8")
    (project / "tests" / "test_value.py").write_text(
        "import os\nfrom pkg.mod import value\n"
        "def test_value():\n"
        "    result = value()\n"
        "    if os.environ.get('STRICT_TESTS') == '1':\n"
        "        assert result == 1\n",
        encoding="utf-8",
    )
    (project / "pyproject.toml").write_text(
        '[tool.mutmut]\npaths_to_mutate=["src/pkg"]\ntests_dir=["tests"]\n'
        "mutate_only_covered_lines=false\nmax_children=1\n"
        '[tool.pytest.ini_options]\npythonpath=["src"]\n',
        encoding="utf-8",
    )
    arguments = ("run", "--no-progress", "--output", "json", "--min-score", "80")
    previous_run_id: str | None = None
    for label, strict, expected_kills, expected_exit, extra in (
        ("strict", "1", 3, 0, ()),
        ("same-strict", "1", 3, 0, ()),
        ("changed-lax", "0", 0, 1, ()),
        ("fresh-lax", "0", 0, 1, ("--rerun-all",)),
    ):
        monkeypatch.setenv("STRICT_TESTS", strict)
        result = run_cli(project, *arguments, *extra)
        (tmp_path / f"{label}.stdout.log").write_text(result.stdout, encoding="utf-8")
        (tmp_path / f"{label}.stderr.log").write_text(result.stderr, encoding="utf-8")
        assert result.returncode == expected_exit, result.stderr
        reported = ReportedRun.model_validate_json(result.stdout)
        assert reported.total_mutants == 3
        assert reported.killed == expected_kills
        assert reported.survived == 3 - expected_kills
        assert reported.score == (100.0 if expected_kills else 0.0)
        assert reported.timeout == reported.unchecked == 0
        assert reported.execution_basis_complete
        assert not reported.run_aborted
        assert not reported.was_interrupted
        latest = latest_run_row(project)
        assert latest is not None
        assert latest[0] != previous_run_id
        assert latest[1] == "completed"
        previous_run_id = latest[0]
        counts = run_verdict_counts(project)
        assert sum(counts.values()) == 3
        assert counts.get("killed", 0) == expected_kills
        assert counts.get("survived", 0) == 3 - expected_kills
        if label == "same-strict":
            assert "Reused 3 cached verdicts" in result.stderr
        elif label == "changed-lax":
            assert "Reused 3 cached verdicts" not in result.stderr
