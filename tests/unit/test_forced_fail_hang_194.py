"""Issue #194 (TM-10): a hanging phase child must be diagnosable, fast.

The original forced-fail hang (import-phase retry loop swallowing the fail
sentinel) is healed at the current stand — the sentinel propagates through
the trampolines (manual receipt, glm-followup).  What remains of #194 is the
liveness contract: a phase child that hangs anywhere (collection, conftest
import, test body) burns the full wall-clock budget with an empty or
frame-less tail.  The phase guard therefore arms a faulthandler dump
deadline shortly before the wall-clock kill, so the captured tail names the
hang frame; the verdict stays timeout (36) — a hang is never attributed as
a kill.
"""

from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING

from mutmut_win.config import MutmutConfig
from mutmut_win.process.worker import (
    PYTEST_PHASE_GUARD_PLUGIN,
    apply_pytest_boundary_environment,
    prepare_pytest_phase_guard,
)
from mutmut_win.pytest_boundary import prepare_pytest_boundary
from mutmut_win.runner import PytestRunner

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

_PHASE_BUDGET_SECONDS = 20


def _staging_with(workspace: Path, module_body: str) -> Path:
    staging = workspace / "mutants"
    tests = staging / "tests"
    tests.mkdir(parents=True, exist_ok=True)
    (tests / "test_phase.py").write_text(module_body, encoding="utf-8")
    return staging


def _phase_env(staging: Path, workspace: Path) -> dict[str, str]:
    env = os.environ.copy()
    env.pop("PYTEST_ADDOPTS", None)
    env.pop("PYTHONPATH", None)
    boundary = prepare_pytest_boundary(
        project_root=workspace,
        staging_root=staging,
        tests_dir=["tests"],
    )
    apply_pytest_boundary_environment(boundary, env)
    # Publish the guard plugin once; the phase run itself re-verifies it
    # (M-011 verify-only pass inside _run_phase_process).
    prepare_pytest_phase_guard(env, staging)
    return env


def _run_phase(env: dict[str, str], budget: int) -> tuple[int, str | None]:
    runner = PytestRunner(
        MutmutConfig(
            paths_to_mutate=["src"],
            tests_dir=["tests"],
            forced_fail_timeout=budget,
            clean_run_timeout=budget,
        )
    )
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "-p",
        PYTEST_PHASE_GUARD_PLUGIN,
        "-q",
        "-x",
        "--tb=line",
        "-rfE",
        "tests/test_phase.py",
    ]
    exit_code = runner._run_phase(
        "forced-fail verification",
        cmd,
        env,
        timeout=budget,
        timeout_hint="forced_fail_timeout",
    )
    return exit_code, runner._last_diagnostic_output


def test_hanging_import_is_diagnosed_as_timeout_with_named_frame(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A module-import hang stays a timeout verdict and names its frame."""

    workspace = tmp_path / "ws"
    workspace.mkdir()
    staging = _staging_with(workspace, "import time\ntime.sleep(600)\n")
    monkeypatch.chdir(workspace)
    env = _phase_env(staging, workspace)

    exit_code, tail = _run_phase(env, _PHASE_BUDGET_SECONDS)

    assert exit_code == 36, "a hang must stay a timeout verdict, never a kill"
    assert tail is not None, "the captured tail must be published on timeout"
    assert "Timeout" in tail, (
        "the faulthandler dump header must reach the captured tail (issue #194: hang diagnosis)"
    )
    assert "test_phase.py" in tail, "the dump must name the hanging frame's file (issue #194)"


def test_healthy_phase_finishes_without_dump_noise(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A healthy phase is unaffected: exit 0 and no dump in the tail."""

    workspace = tmp_path / "ws"
    workspace.mkdir()
    staging = _staging_with(workspace, "def test_ok():\n    assert True\n")
    monkeypatch.chdir(workspace)
    env = _phase_env(staging, workspace)

    exit_code, _tail = _run_phase(env, 60)

    assert exit_code == 0
