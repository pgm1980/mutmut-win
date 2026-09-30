"""End-to-end regression for the name-consistency gate (M-053).

The M-053 finding: with ``paths_to_mutate = ["lib/pkg"]`` and
``extra_paths = ["lib"]`` the mutant names carry the unstripped ``lib.``
prefix while the tests import ``pkg.mod`` (``mutants/lib`` is on
PYTHONPATH).  Before the gate, every worker activated
``MUTANT_UNDER_TEST=lib.pkg.mod.x_double__mutmut_N``, the trampoline
built its prefix from the runtime module (``pkg.mod.``), silently ran the
original, and every mutant survived.  The run must now fail closed with
exit 1 BEFORE any dispatch.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

#: Absolute path to the bundled extra_paths-layout fixture project.
_EXTRA_PATHS_LAYOUT_DIR = Path(__file__).parent.parent / "e2e_projects" / "extra_paths_layout"


@pytest.fixture
def extra_paths_project(tmp_path: Path) -> Path:
    """Copy the extra_paths_layout fixture into a fresh temp directory."""
    project_dir = tmp_path / "extra_paths_layout"
    shutil.copytree(_EXTRA_PATHS_LAYOUT_DIR, project_dir)
    return project_dir


@pytest.mark.integration
@pytest.mark.slow
def test_divergent_extra_paths_layout_fails_closed(extra_paths_project: Path) -> None:
    # S603: command list is fully controlled — no user input reaches this call
    result = subprocess.run(
        [sys.executable, "-m", "mutmut_win", "run", "--no-progress"],
        cwd=extra_paths_project,
        capture_output=True,
        encoding="utf-8",
        timeout=300,
    )
    stderr = result.stderr
    # The domain-error channel: MutmutWinError -> "Error: ..." + exit 1.
    assert result.returncode == 1, f"run did not fail closed:\n{result.stdout}\n{stderr}"
    assert "Error:" in stderr
    assert "pkg.mod.x_double" in stderr  # runtime key recorded by the stats run
    assert "lib.pkg.mod.x_double" in stderr  # generated mutant key
    # The divergent layout was really staged: the mutated module carries a
    # trampoline, so the trigger of the finding was reachable.
    staged_mod = extra_paths_project / "mutants" / "lib" / "pkg" / "mod.py"
    assert staged_mod.exists(), "mutated module was not staged"
    assert "_mutmut" in staged_mod.read_text(encoding="utf-8")
