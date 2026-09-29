"""CLI contracts for the mandatory Windows process-containment boundary."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from mutmut_win.cli import cli
from mutmut_win.config import MutmutConfig
from mutmut_win.exceptions import ProcessContainmentError
from mutmut_win.models import MutationRunResult


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


@pytest.mark.skipif(os.name != "nt", reason="Windows Junction regression")
def test_show_refuses_redirected_mutants_root_without_touching_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """M-026: ``show`` is a reader and rejects redirected state roots.

    A Junction'd ``mutants/`` used to pass the plain ``is_dir()`` check, so
    the healing metadata walk could delete an external ``<source>.py.meta``
    through it. Like run/apply/export, show now fails closed first.
    """
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "external"
    (target / "src").mkdir(parents=True)
    corrupt_payload = b"\xffnot json\x00"
    corrupt_sidecar = target / "src" / "mod.py.meta"
    corrupt_sidecar.write_bytes(corrupt_payload)
    junction = tmp_path / "mutants"
    cmd_executable = Path(os.environ.get("COMSPEC", r"C:\Windows\System32\cmd.exe"))
    created = subprocess.run(  # noqa: S603 - cmd builtin creates the test Junction
        [cmd_executable, "/d", "/u", "/c", "mklink", "/J", str(junction), str(target)],
        capture_output=True,
        encoding="utf-16-le",
        errors="replace",
        check=False,
    )
    if created.returncode != 0:
        pytest.skip(f"could not create Junction: {created.stdout}{created.stderr}")

    try:
        result = CliRunner().invoke(cli, ["show", "mod.x_f__mutmut_1"])
        sidecar_exists = corrupt_sidecar.exists()
        sidecar_bytes = corrupt_sidecar.read_bytes() if sidecar_exists else None
    finally:
        # Remove the Junction itself, never its target, so tmp_path cleanup
        # stays unambiguous.
        if junction.exists() and junction.is_junction():
            junction.rmdir()

    assert result.exit_code == 1
    assert "Refusing show" in result.output
    assert "link, junction" in result.output
    assert sidecar_exists
    assert sidecar_bytes == corrupt_payload
