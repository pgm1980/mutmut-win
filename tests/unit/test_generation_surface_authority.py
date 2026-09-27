"""Mutation-surface authority: --min-score and CI/CD export fail closed (M-003, #145).

The CLI score gate treats a degraded mutation surface as the FIRST check
under ``--min-score`` (before the generic basis-incomplete check), so a run
whose surface is incomplete can never pass the gate — independent of the
``execution_basis_complete`` flag (defence in depth).  Without ``--min-score``
the run stays a diagnostic Exit 0 with the additive JSON field.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from click.testing import CliRunner
from pydantic import ValidationError

from mutmut_win.cli import _mutation_surface_report, cli
from mutmut_win.models import GenerationDegradation, MutationRunResult

if TYPE_CHECKING:
    from pathlib import Path

_DEGRADED = [
    GenerationDegradation(
        path="src/broken.py",
        reason="unsupported_source_syntax",
        detail="Unsupported syntax in src/broken.py, skipping",
    )
]


def _result(**overrides: object) -> MutationRunResult:
    defaults: dict[str, object] = {
        "total_mutants": 4,
        "killed": 4,
        "survived": 0,
        "execution_basis_complete": True,
        "degraded_files": list(_DEGRADED),
    }
    defaults.update(overrides)
    return MutationRunResult.model_validate(defaults)


@pytest.fixture
def cli_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Minimal workspace so config validation passes before the mocked run."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    return tmp_path


class TestMutationSurfaceReport:
    def test_empty_surface_yields_none(self) -> None:
        assert _mutation_surface_report([]) is None

    def test_report_shape(self) -> None:
        report = _mutation_surface_report(_DEGRADED)
        assert report is not None
        lines = report.splitlines()
        assert lines[0] == "Mutation surface incomplete — 1 file(s) could not be mutated:"
        assert lines[1] == "  - src/broken.py (unsupported_source_syntax)"
        assert lines[-1].startswith("Exclude them via do_not_mutate")
        assert len(lines) == 3

    def test_order_preserved(self) -> None:
        degraded = [
            GenerationDegradation(path="b.py", reason="generated_code_invalid", detail="d2"),
            GenerationDegradation(path="a.py", reason="cst_validation_error", detail="d1"),
        ]
        report = _mutation_surface_report(degraded)
        assert report is not None
        lines = report.splitlines()
        assert lines[1].startswith("  - b.py")
        assert lines[2].startswith("  - a.py")


class TestScoreGateFailsClosedOnDegradedSurface:
    def test_degraded_surface_with_min_score_exits_1(
        self,
        monkeypatch: pytest.MonkeyPatch,
        cli_project: Path,  # noqa: ARG002
    ) -> None:
        monkeypatch.setattr(
            "mutmut_win.cli.MutationOrchestrator.run",
            lambda _self: _result(),
            raising=True,
        )
        result = CliRunner().invoke(cli, ["run", "--min-score", "50"])

        assert result.exit_code == 1
        assert "Mutation surface incomplete" in result.stderr
        assert "src/broken.py (unsupported_source_syntax)" in result.stderr
        assert "do_not_mutate" in result.stderr
        assert "Score gate failed closed." in result.stderr
        # The specific report takes precedence over the generic basis text.
        assert "not all execution inputs could be fingerprinted" not in result.stderr

    def test_degraded_surface_with_basis_incomplete_still_specific(
        self,
        monkeypatch: pytest.MonkeyPatch,
        cli_project: Path,  # noqa: ARG002
    ) -> None:
        monkeypatch.setattr(
            "mutmut_win.cli.MutationOrchestrator.run",
            lambda _self: _result(execution_basis_complete=False),
            raising=True,
        )
        result = CliRunner().invoke(cli, ["run", "--min-score", "50"])

        assert result.exit_code == 1
        assert "Mutation surface incomplete" in result.stderr

    def test_degraded_surface_without_min_score_is_diagnostic_exit_0(
        self,
        monkeypatch: pytest.MonkeyPatch,
        cli_project: Path,  # noqa: ARG002
    ) -> None:
        monkeypatch.setattr(
            "mutmut_win.cli.MutationOrchestrator.run",
            lambda _self: _result(),
            raising=True,
        )
        result = CliRunner().invoke(cli, ["run"])

        assert result.exit_code == 0

    def test_json_output_contains_degraded_files_field(
        self,
        monkeypatch: pytest.MonkeyPatch,
        cli_project: Path,  # noqa: ARG002
    ) -> None:
        monkeypatch.setattr(
            "mutmut_win.cli.MutationOrchestrator.run",
            lambda _self: _result(),
            raising=True,
        )
        result = CliRunner().invoke(cli, ["run", "--output", "json"])

        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["degraded_files"][0]["path"] == "src/broken.py"
        assert payload["degraded_files"][0]["reason"] == "unsupported_source_syntax"


class TestModelContract:
    def test_result_roundtrip_with_degraded_files(self) -> None:
        original = _result()
        clone = MutationRunResult.model_validate_json(original.model_dump_json())
        assert clone == original
        assert len(clone.degraded_files) == 1

    def test_old_json_without_field_validates_to_empty(self) -> None:
        raw = json.loads(_result().model_dump_json())
        raw.pop("degraded_files")
        clone = MutationRunResult.model_validate(raw)
        assert clone.degraded_files == []

    def test_degradation_model_is_frozen_and_closed(self) -> None:
        entry = GenerationDegradation(path="x.py", reason="generated_code_invalid", detail="d")
        with pytest.raises(ValidationError):
            entry.reason = "unsupported_source_syntax"
        with pytest.raises(ValidationError):
            GenerationDegradation(path="x.py", reason="not_a_reason", detail="d")
