"""S3-053/054: exact JSON data on narrow streams and honest syntax previews."""

from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner
from hypothesis import given, settings, strategies as st

from mutmut_win.cli import cli
from mutmut_win.models import GenerationDegradation, MutationRunResult


def _write_project(workspace: Path, *, healthy: bool, broken: bool, excluded: bool = False) -> None:
    exclusion = 'do_not_mutate = ["src/*broken.py"]\n' if excluded else ""
    (workspace / "pyproject.toml").write_text(
        '[tool.mutmut]\npaths_to_mutate = ["src"]\n' + exclusion, encoding="utf-8"
    )
    if healthy:
        (workspace / "src" / "calc.py").write_text(
            "def increment(value: int) -> int:\n    return value + 1\n", encoding="utf-8"
        )
    if broken:
        (workspace / "src" / "漢_broken.py").write_text(
            "def broken(:\n    pass\n", encoding="utf-8"
        )


@pytest.mark.parametrize("encoding", ["ascii", "cp1252", "utf-8"])
def test_json_result_preserves_unicode_on_strict_streams(
    isolated_cli_workspace: Path, monkeypatch: pytest.MonkeyPatch, encoding: str
) -> None:
    """Real Click output must preserve Unicode data without replacing characters."""
    _write_project(isolated_cli_workspace, healthy=True, broken=False)

    @settings(max_examples=12, deadline=None)
    @given(detail=st.text(alphabet=st.characters(exclude_categories=("Cs",)), max_size=40))
    def check_roundtrip(detail: str) -> None:
        expected = MutationRunResult(
            total_mutants=5,
            degraded_files=[
                GenerationDegradation(
                    path="src/漢_😀.py", reason="unsupported_source_syntax", detail=detail
                )
            ],
        )
        buffer = io.BytesIO()
        stderr = io.StringIO()
        with io.TextIOWrapper(buffer, encoding=encoding, errors="strict") as stdout:
            with (
                monkeypatch.context() as context,
                patch("mutmut_win.cli.MutationOrchestrator.dry_run", return_value=expected),
            ):
                context.setattr("sys.stdout", stdout)
                context.setattr("sys.stderr", stderr)
                cli.main(["run", "--dry-run", "--output", "json"], standalone_mode=False)
                stdout.flush()
                actual = MutationRunResult.model_validate_json(buffer.getvalue().decode(encoding))
            assert actual == expected

    check_roundtrip()


@pytest.mark.parametrize(
    ("healthy", "broken", "excluded", "expected_degradations"),
    [
        pytest.param(False, True, False, 1, id="only-unparsable"),
        pytest.param(True, True, False, 1, id="mixed"),
        pytest.param(True, False, False, 0, id="healthy"),
        pytest.param(True, True, True, 0, id="explicit-exclusion"),
    ],
)
def test_dry_run_reports_actual_syntax_degradations(
    isolated_cli_workspace: Path,
    healthy: bool,
    broken: bool,
    excluded: bool,
    expected_degradations: int,
) -> None:
    """Actual parsing reports omissions while exclusions remain intentional."""
    _write_project(isolated_cli_workspace, healthy=healthy, broken=broken, excluded=excluded)
    result = CliRunner().invoke(cli, ["run", "--dry-run", "--output", "json"])
    assert result.exit_code == 0, result.output
    payload = MutationRunResult.model_validate_json(result.stdout)
    assert (payload.total_mutants > 0) is healthy
    assert payload.execution_basis_complete is False
    assert len(payload.degraded_files) == expected_degradations
    if expected_degradations:
        degradation = payload.degraded_files[0]
        assert Path(degradation.path) == Path("src/漢_broken.py")
        assert degradation.reason == "unsupported_source_syntax"
        assert "Syntax Error" in degradation.detail
        assert "could not mutate" in result.stderr
    else:
        assert "could not mutate" not in result.stderr
    assert not (isolated_cli_workspace / "mutants").exists()
    assert not (isolated_cli_workspace / ".mutmut-cache.db").exists()


def test_dry_run_degradation_cannot_authorize_score(
    isolated_cli_workspace: Path,
) -> None:
    """The independent score guard rejects a preview before generation."""
    _write_project(isolated_cli_workspace, healthy=True, broken=True)
    result = CliRunner().invoke(cli, ["run", "--dry-run", "--output", "json", "--min-score", "80"])
    assert result.exit_code == 2
    assert "dry-run" in result.stderr
    assert "min-score" in result.stderr
