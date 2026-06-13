"""End-to-end regression for source/-layout naming (issue #126 / 360°-A3).

Before the fix, ``get_mutant_name`` stripped only the ``src.`` prefix while
``source/`` was a fully supported staging root everywhere else: mutant names
carried a ``source.`` prefix that never matched ``orig.__module__``, so the
stats mapping came up empty and EVERY mutant of a source/-layout project was
reported as ``no tests`` (0 dispatched, nothing ever killed).

The fixture is deliberately import-only (no pip install): the staging puts
``mutants/source`` on the worker PYTHONPATH — exactly the mechanism whose
naming identity this test pins.
"""

from __future__ import annotations

import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

#: Absolute path to the bundled source/-layout fixture project.
_SOURCE_LAYOUT_DIR = Path(__file__).parent.parent / "e2e_projects" / "source_layout"


@pytest.fixture
def source_layout_project(tmp_path: Path) -> Path:
    """Copy the source_layout fixture into a fresh temp directory."""
    project_dir = tmp_path / "source_layout"
    shutil.copytree(_SOURCE_LAYOUT_DIR, project_dir)
    return project_dir


@pytest.mark.integration
@pytest.mark.slow
def test_source_layout_mutants_are_killed_not_untested(source_layout_project: Path) -> None:
    # S603: command list is fully controlled — no user input reaches this call
    result = subprocess.run(
        [sys.executable, "-m", "mutmut_win", "run", "--no-progress"],
        cwd=source_layout_project,
        capture_output=True,
        encoding="utf-8",
        timeout=300,
    )
    assert result.returncode == 0, f"run failed:\n{result.stdout}\n{result.stderr}"

    db_path = source_layout_project / ".mutmut-cache" / "mutmut-cache.db"
    assert db_path.exists(), "no result database written"
    rows = sqlite3.connect(db_path).execute("SELECT mutant_name, status FROM mutant").fetchall()
    assert rows, "no mutants recorded"

    statuses = [status for _name, status in rows]
    names = [name for name, _status in rows]
    # The A3 failure mode was a 100% 'no tests' wall — nothing dispatched.
    assert statuses.count("no tests") == 0, f"untested mutants under source/ layout: {rows}"
    assert any(status == "killed" for status in statuses), f"nothing killed: {rows}"
    # Names must be import-path identical: pkglib.…, never source.pkglib.…
    assert all(name.startswith("pkglib.") for name in names), names
