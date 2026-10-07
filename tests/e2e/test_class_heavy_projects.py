"""E2E: trampoline boundary for class-heavy projects (T8, TM-11).

The engine's own models/browser gates surfaced a trampoline boundary for
class-heavy modules (BLOCKED-GATES-MODELS-BROWSER.md, hypotheses H1-H4:
136/140 clean-run failures on trampolined pydantic models, 68x slowdown,
product code exonerated by mirror comparison).  TM-11 pins that boundary at
PROJECT level with a strict xfail: the class-heavy fixture's untrampolined
suite is green (mirror oracle, kept as a passing control), while the full
engine run against it is EXPECTED to fail.  ``strict=True`` makes the
boundary live: when a future engine version fixes the boundary, XPASS
fails this test and forces updating the documented status.

No pre-fix here by design (goal boundary): H1-H4 are reserved for the
external adversarial review.
"""

from __future__ import annotations

import subprocess
import sys
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from tests.e2e.e2e_util import PYDANTIC_HEAVY, copy_project, run_cli

pytestmark = [pytest.mark.e2e, pytest.mark.slow]


def test_pydantic_heavy_fixture_suite_is_green_untrampolined(tmp_path: Path) -> None:
    """Mirror oracle: the fixture's own suite passes without trampolines."""

    project = copy_project(PYDANTIC_HEAVY, tmp_path)
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"],
        cwd=project,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
        check=False,
    )
    assert result.returncode == 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    assert " failed" not in result.stdout


@pytest.mark.xfail(
    strict=True,
    reason=(
        "TM-11: trampoline boundary for class-heavy projects "
        "(pydantic BaseModel/computed_field/validators; engine-level evidence: "
        "BLOCKED-GATES-MODELS-BROWSER.md, H1-H4 reserved for the external review)"
    ),
)
def test_pydantic_heavy_full_engine_run_completes(tmp_path: Path) -> None:
    """The full engine run against the class-heavy fixture (expected xfail)."""

    project = copy_project(PYDANTIC_HEAVY, tmp_path)
    result = run_cli(project, "run", "--no-progress", timeout=900)
    assert result.returncode == 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
