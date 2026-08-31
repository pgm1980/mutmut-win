"""CLI contracts for the mandatory Windows process-containment boundary."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from mutmut_win.cli import cli
from mutmut_win.config import MutmutConfig
from mutmut_win.exceptions import ProcessContainmentError
from mutmut_win.models import MutationRunResult

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture(autouse=True)
def isolated_workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep real-run lock acquisition away from the repository workspace."""
    monkeypatch.chdir(tmp_path)


@pytest.fixture
def empty_config() -> MutmutConfig:
    """Avoid coupling these CLI contracts to source discovery."""
    return MutmutConfig(paths_to_mutate=[])


def test_dry_run_does_not_construct_process_executor(empty_config: MutmutConfig) -> None:
    orchestrator = MagicMock()
    orchestrator.dry_run.return_value = MutationRunResult()

    with (
        patch("mutmut_win.cli.load_config", return_value=empty_config),
        patch("mutmut_win.cli.PytestRunner"),
        patch("mutmut_win.cli.SpawnPoolExecutor") as executor_type,
        patch("mutmut_win.cli.MutationOrchestrator", return_value=orchestrator) as orch_type,
    ):
        result = CliRunner().invoke(cli, ["run", "--dry-run"])

    assert result.exit_code == 0
    executor_type.assert_not_called()
    assert orch_type.call_args.kwargs["executor"] is None
    orchestrator.dry_run.assert_called_once_with()


@pytest.mark.parametrize("output_args", [(), ("--output", "json")])
def test_executor_containment_failure_is_a_clean_domain_error(
    empty_config: MutmutConfig,
    output_args: tuple[str, ...],
) -> None:
    with (
        patch("mutmut_win.cli.load_config", return_value=empty_config),
        patch("mutmut_win.cli.PytestRunner"),
        patch(
            "mutmut_win.cli.SpawnPoolExecutor",
            side_effect=ProcessContainmentError("Windows Job Object unavailable"),
        ),
        patch("mutmut_win.cli.MutationOrchestrator") as orchestrator_type,
    ):
        result = CliRunner().invoke(cli, ["run", *output_args])

    assert result.exit_code == 1
    assert "Traceback" not in result.output
    orchestrator_type.assert_not_called()
    if output_args:
        assert json.loads(result.stdout) == {
            "error": "Error: Windows Job Object unavailable",
            "exit_code": 1,
        }
        assert "Error: Windows Job Object unavailable" in result.stderr
    else:
        assert "Error: Windows Job Object unavailable" in result.output


def test_executor_containment_failure_has_traceback_in_debug_mode(
    empty_config: MutmutConfig,
) -> None:
    with (
        patch("mutmut_win.cli.load_config", return_value=empty_config),
        patch("mutmut_win.cli.PytestRunner"),
        patch(
            "mutmut_win.cli.SpawnPoolExecutor",
            side_effect=ProcessContainmentError("Windows Job Object unavailable"),
        ),
    ):
        result = CliRunner().invoke(cli, ["run", "--debug"])

    assert result.exit_code == 1
    assert "Traceback (most recent call last)" in result.output
    assert "ProcessContainmentError: Windows Job Object unavailable" in result.output
