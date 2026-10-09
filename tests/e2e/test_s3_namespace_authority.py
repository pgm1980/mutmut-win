"""S3-005: a namespace collision cannot authorize a run or CI export."""

from typing import TYPE_CHECKING

import pytest
from pydantic import BaseModel, ConfigDict

from tests.e2e.e2e_util import run_cli

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.e2e, pytest.mark.slow]


class MeasuredScore(BaseModel):
    """Read independently asserted score and basis evidence from the CLI."""

    total_mutants: int
    killed: int
    score: float
    execution_basis_complete: bool


class GenerationRefusal(BaseModel):
    """A generation error must not contain an authoritative score payload."""

    model_config = ConfigDict(extra="forbid")
    error: str
    exit_code: int


def test_collision_revokes_run_and_export_after_healthy_control(tmp_path: Path) -> None:
    """Real CLI preserves a healthy score, then refuses a colliding global."""
    project = tmp_path / "namespace-project"
    package = project / "src" / "pkg"
    package.mkdir(parents=True)
    (project / "tests").mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    source_path = package / "mod.py"
    source = "ordinary_value = 7\ndef value():\n    return 1\ndef other():\n    return 2\n"
    source_path.write_text(source, encoding="utf-8")
    (project / "tests" / "test_value.py").write_text(
        "from pkg.mod import value, other\n"
        "def test_values():\n    assert value() == 1\n    assert other() == 2\n",
        encoding="utf-8",
    )
    (project / "pyproject.toml").write_text(
        '[tool.mutmut]\npaths_to_mutate=["src/pkg"]\ntests_dir=["tests"]\n'
        "mutate_only_covered_lines=false\nmax_children=1\n"
        '[tool.pytest.ini_options]\npythonpath=["src"]\n',
        encoding="utf-8",
    )
    arguments = ("run", "--no-progress", "--output", "json", "--min-score", "100")
    healthy = run_cli(project, *arguments)
    (tmp_path / "healthy.stdout.log").write_text(healthy.stdout, encoding="utf-8")
    (tmp_path / "healthy.stderr.log").write_text(healthy.stderr, encoding="utf-8")
    assert healthy.returncode == 0, healthy.stderr
    measured = MeasuredScore.model_validate_json(healthy.stdout)
    assert measured.total_mutants > 0
    assert measured.killed == measured.total_mutants
    assert measured.score == 100.0
    assert measured.execution_basis_complete
    healthy_export = run_cli(project, "export-cicd-stats")
    assert healthy_export.returncode == 0, healthy_export.stderr
    artifact = project / "mutants" / "mutmut-cicd-stats.json"
    assert artifact.is_file()
    (tmp_path / "healthy-export.json").write_bytes(artifact.read_bytes())

    source_path.write_text(
        source.replace("ordinary_value", "x_value__mutmut_shadow"), encoding="utf-8"
    )
    original_bytes = source_path.read_bytes()
    refused = run_cli(project, *arguments)
    (tmp_path / "collision.stdout.log").write_text(refused.stdout, encoding="utf-8")
    (tmp_path / "collision.stderr.log").write_text(refused.stderr, encoding="utf-8")
    assert refused.returncode == 1, refused.stderr
    error = GenerationRefusal.model_validate_json(refused.stdout)
    assert error.exit_code == 1
    assert "trampoline namespace" in error.error
    assert "generation blocked" in error.error
    assert "Traceback (most recent call last)" not in refused.stderr
    assert source_path.read_bytes() == original_bytes
    rejected_export = run_cli(project, "export-cicd-stats")
    (tmp_path / "collision-export.stderr.log").write_text(rejected_export.stderr, encoding="utf-8")
    assert rejected_export.returncode == 1, rejected_export.stdout
    assert "failed closed" in rejected_export.stderr
    assert not artifact.exists()
    assert source_path.read_bytes() == original_bytes
