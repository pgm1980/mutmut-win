"""End-to-end integration tests for mutmut-win.

These tests copy the simple_lib fixture project into a temporary directory,
run the full mutation testing pipeline via the CLI, and verify that:
- Mutations were generated.
- At least one mutant was killed by the test suite.
- Results are persisted in the SQLite database.
"""

from __future__ import annotations

import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

#: Absolute path to the bundled E2E fixture project.
_SIMPLE_LIB_DIR = Path(__file__).parent.parent / "e2e_projects" / "simple_lib"


@pytest.fixture
def simple_lib_project(tmp_path: Path) -> Path:
    """Copy simple_lib fixture into a fresh temp directory.

    Returns:
        Path to the temporary project root.
    """
    project_dir = tmp_path / "simple_lib"
    shutil.copytree(_SIMPLE_LIB_DIR, project_dir)
    return project_dir


def _run_mutmut_win(project_dir: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run a mutmut-win sub-command in *project_dir*.

    Args:
        project_dir: Working directory for the subprocess.
        *args: CLI arguments passed after ``mutmut-win``.

    Returns:
        Completed process with stdout/stderr captured.
    """
    # S603: command list is fully controlled — no user input reaches this call
    return subprocess.run(  # noqa: S603
        [sys.executable, "-m", "mutmut_win", *args],
        cwd=project_dir,
        capture_output=True,
        encoding="utf-8",
        timeout=120,
    )


@pytest.mark.integration
@pytest.mark.slow
def test_e2e_mutations_generated_and_killed(simple_lib_project: Path) -> None:
    """Full pipeline: run mutation testing and verify results in the DB.

    Steps:
    1. Install simple_lib into the temp environment (editable).
    2. Run ``mutmut-win run`` inside the project directory.
    3. Read the SQLite database and assert that mutations were generated and
       that at least one mutant was killed.
    """
    # Install simple_lib so pytest can import it.
    install_result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-e", ".", "--quiet"],
        cwd=simple_lib_project,
        capture_output=True,
        encoding="utf-8",
        timeout=60,
    )
    assert install_result.returncode == 0, (
        f"pip install failed:\n{install_result.stdout}\n{install_result.stderr}"
    )

    # Run the full mutation testing pipeline.
    result = _run_mutmut_win(simple_lib_project, "run")

    # The run may legitimately exit non-zero if some mutants survive — that
    # is expected behaviour.  We only fail the test if the CLI itself crashed.
    assert result.returncode in {0, 1}, (
        f"mutmut-win run exited with unexpected code {result.returncode}.\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )

    # Verify the SQLite database was created and populated.
    db_path = simple_lib_project / ".mutmut-cache" / "mutmut-cache.db"
    assert db_path.exists(), (
        f"Cache database not found at {db_path}.\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute("SELECT mutant_name, status FROM mutant").fetchall()

    assert len(rows) > 0, "No mutation results found in the database."

    statuses = {row[1] for row in rows}

    # At least some mutants must have been evaluated (not just generated).
    assert statuses & {"killed", "survived", "timeout", "caught by type check"}, (
        f"No evaluated mutants found. Statuses present: {statuses}"
    )

    # With a complete test suite like simple_lib's, at least one mutant
    # should be killed.
    killed_count = sum(1 for _, status in rows if status in {"killed", "caught by type check"})
    assert killed_count > 0, (
        f"Expected at least one killed mutant, got 0.\n"
        f"All statuses: {statuses}\n"
        f"stdout:\n{result.stdout}"
    )


@pytest.mark.integration
@pytest.mark.slow
def test_e2e_results_command(simple_lib_project: Path) -> None:
    """Verify the ``results`` sub-command reads from the database correctly.

    Runs the pipeline first, then calls ``mutmut-win results`` and checks
    that the summary output contains expected fields.
    """
    # Install package so tests can import it.
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-e", ".", "--quiet"],
        cwd=simple_lib_project,
        capture_output=True,
        encoding="utf-8",
        timeout=60,
        check=True,
    )

    # Run mutation testing.
    _run_mutmut_win(simple_lib_project, "run")

    # Query results.
    result = _run_mutmut_win(simple_lib_project, "results")
    assert result.returncode == 0, f"mutmut-win results failed:\n{result.stdout}\n{result.stderr}"

    output = result.stdout
    assert "Total:" in output, f"Expected 'Total:' in output:\n{output}"
    assert "Killed:" in output, f"Expected 'Killed:' in output:\n{output}"
    assert "Score:" in output, f"Expected 'Score:' in output:\n{output}"
