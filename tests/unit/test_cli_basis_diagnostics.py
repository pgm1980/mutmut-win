"""Opt-in diagnostics must preserve the CLI result and configuration."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from mutmut_win.basis_diagnostics import observed_sha256, snapshot
from mutmut_win.cli import cli
from mutmut_win.config import MutmutConfig
from mutmut_win.models import MutationRunResult
from mutmut_win.stats import RunBasisEvidence

pytestmark = pytest.mark.usefixtures("isolated_cli_workspace")


def test_diagnostics_preserves_json_stdout_and_validated_config(tmp_path: Path) -> None:
    output = tmp_path / "observations.json"
    config = MutmutConfig()
    config_before = config.model_dump()
    orchestrator = MagicMock()

    @snapshot
    def basis() -> RunBasisEvidence:
        return RunBasisEvidence(observed_sha256(b"fixture", stream="basis").hexdigest(), True)

    def execute() -> MutationRunResult:
        basis()
        assert not output.exists()
        return MutationRunResult(total_mutants=1, killed=1)

    orchestrator.run.side_effect = execute
    with (
        patch("mutmut_win.cli.load_config", return_value=config),
        patch("mutmut_win.cli.MutationOrchestrator", return_value=orchestrator) as constructor,
        patch("mutmut_win.cli.PytestRunner"),
        patch("mutmut_win.cli.SpawnPoolExecutor"),
    ):
        result = CliRunner().invoke(
            cli, ["run", "--output", "json", "--basis-diagnostics", str(output)]
        )
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["total_mutants"] == 1
    assert constructor.call_args.args[0].model_dump() == config_before
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["diagnostics_complete"]
    assert len(report["snapshots"]) == 1


@pytest.mark.parametrize("destination", ["relative.json", "inside-project"])
def test_invalid_diagnostic_destination_rejected_before_force_cleanup(destination: str) -> None:
    staging = Path("mutants")
    staging.mkdir()
    marker = staging / "preserve.txt"
    marker.write_text("keep", encoding="utf-8")
    output = (
        Path("report.json").absolute() if destination == "inside-project" else Path(destination)
    )
    with patch("mutmut_win.cli.MutationOrchestrator") as orchestrator:
        result = CliRunner().invoke(cli, ["run", "--force", "--basis-diagnostics", str(output)])
    assert result.exit_code == 2
    assert "--basis-diagnostics" in result.stderr
    assert marker.read_text(encoding="utf-8") == "keep"
    orchestrator.assert_not_called()
    assert not output.exists()
