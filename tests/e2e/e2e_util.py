"""Shared harness for product E2E tests (tests/e2e, marker ``e2e``).

Drives the real ``mutmut-win`` CLI as a subprocess against isolated copies
of the bundled fixture projects — the same provenance as
``tests/integration/test_e2e_pipeline_validation.py``, extended for the
E2E tier: modern run-table inspection, campaign control (poll + hard kill)
and CLI follow-up commands on the persisted database.
"""

from __future__ import annotations

import contextlib
import shutil
import sqlite3
import subprocess
import sys
import time
from contextlib import closing
from pathlib import Path

_E2E_PROJECTS_DIR = Path(__file__).parent.parent / "e2e_projects"
SIMPLE_LIB = _E2E_PROJECTS_DIR / "simple_lib"
MY_LIB = _E2E_PROJECTS_DIR / "my_lib"
PY314_FEATURES = _E2E_PROJECTS_DIR / "py3_14_features"
SOURCE_LAYOUT = _E2E_PROJECTS_DIR / "source_layout"
CONFIG_FIXTURE = _E2E_PROJECTS_DIR / "config"
MUTATE_ONLY_COVERED = _E2E_PROJECTS_DIR / "mutate_only_covered_lines"
PYDANTIC_HEAVY = _E2E_PROJECTS_DIR / "pydantic_heavy"


def copy_project(src: Path, tmp_path: Path) -> Path:
    """Copy a fixture project into *tmp_path* and return the destination."""

    dst = tmp_path / src.name
    shutil.copytree(src, dst)
    return dst


def run_cli(project_dir: Path, *args: str, timeout: int = 900) -> subprocess.CompletedProcess[str]:
    """Run ``python -m mutmut_win <args>`` inside *project_dir*."""

    return subprocess.run(  # noqa: S603
        [sys.executable, "-m", "mutmut_win", *args],
        cwd=project_dir,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )


def start_run(project_dir: Path) -> subprocess.Popen[str]:
    """Start ``mutmut-win run`` asynchronously inside *project_dir*."""

    return subprocess.Popen(
        [sys.executable, "-m", "mutmut_win", "run", "--no-progress"],
        cwd=project_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding="utf-8",
        errors="replace",
    )


def kill_process_tree(process: subprocess.Popen[str]) -> None:
    """Hard-kill *process* and its descendants (campaign interruption)."""

    import psutil

    try:
        parent = psutil.Process(process.pid)
        children = parent.children(recursive=True)
    except psutil.NoSuchProcess:
        children = []
    for child in children:
        with contextlib.suppress(psutil.NoSuchProcess, psutil.AccessDenied):
            child.kill()
    with contextlib.suppress(psutil.NoSuchProcess, psutil.AccessDenied):
        process.kill()
    process.wait(timeout=30)


def cache_db(project_dir: Path) -> Path:
    return project_dir / ".mutmut-cache" / "mutmut-cache.db"


def _connect_readonly(project_dir: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{cache_db(project_dir)}?mode=ro", uri=True)


def latest_run_row(project_dir: Path) -> tuple[str, str] | None:
    """Return ``(run_id, status)`` of the newest persisted run, or None."""

    if not cache_db(project_dir).exists():
        return None
    with closing(_connect_readonly(project_dir)) as conn:
        row = conn.execute(
            "SELECT run_id, status FROM mutation_run ORDER BY sequence DESC LIMIT 1"
        ).fetchone()
    return (row[0], row[1]) if row else None


def run_verdict_counts(project_dir: Path) -> dict[str, int]:
    """Aggregate the newest run's verdict statuses (modern run tables)."""

    latest = latest_run_row(project_dir)
    if latest is None:
        return {}
    run_id = latest[0]
    with closing(_connect_readonly(project_dir)) as conn:
        rows = conn.execute(
            "SELECT result_status, COUNT(*) FROM mutation_run_mutant"
            " WHERE run_id = ? AND result_status IS NOT NULL GROUP BY result_status",
            (run_id,),
        ).fetchall()
    return dict(rows)


def run_planned_total(project_dir: Path) -> int:
    """Number of planned mutants in the newest run."""

    latest = latest_run_row(project_dir)
    if latest is None:
        return 0
    with closing(_connect_readonly(project_dir)) as conn:
        (total,) = conn.execute(
            "SELECT COUNT(*) FROM mutation_run_mutant WHERE run_id = ?",
            (latest[0],),
        ).fetchone()
    return int(total)


def run_reused_count(project_dir: Path) -> int:
    """Number of reused verdict rows in the newest run (#195 proof)."""

    latest = latest_run_row(project_dir)
    if latest is None:
        return 0
    with closing(_connect_readonly(project_dir)) as conn:
        (reused,) = conn.execute(
            "SELECT COUNT(*) FROM mutation_run_mutant WHERE run_id = ? AND reused = 1",
            (latest[0],),
        ).fetchone()
    return int(reused)


def completed_verdict_count(project_dir: Path) -> int:
    """Verdicts of the newest run (any status) — the campaign progress meter."""

    latest = latest_run_row(project_dir)
    if latest is None:
        return 0
    with closing(_connect_readonly(project_dir)) as conn:
        (count,) = conn.execute(
            "SELECT COUNT(*) FROM mutation_run_mutant"
            " WHERE run_id = ? AND result_status IS NOT NULL",
            (latest[0],),
        ).fetchone()
    return int(count)


def wait_for_verdicts(
    project_dir: Path, threshold: int, process: subprocess.Popen[str], budget_seconds: int = 600
) -> int:
    """Poll the cache DB until *threshold* verdicts exist or budget expires."""

    deadline = time.monotonic() + budget_seconds
    while time.monotonic() < deadline:
        if process.poll() is not None:
            break
        if completed_verdict_count(project_dir) >= threshold:
            return completed_verdict_count(project_dir)
        time.sleep(2)
    return completed_verdict_count(project_dir)


def legacy_statuses(project_dir: Path) -> dict[str, str]:
    """``{mutant_name: status}`` from the legacy ``mutant`` cache table."""

    if not cache_db(project_dir).exists():
        return {}
    with closing(_connect_readonly(project_dir)) as conn:
        rows = conn.execute("SELECT mutant_name, status FROM mutant").fetchall()
    return dict(rows)


def killed_mutant_name(project_dir: Path) -> str | None:
    """A mutant the newest run reported as killed (for ``apply``/``show``)."""

    latest = latest_run_row(project_dir)
    if latest is None:
        return None
    with closing(_connect_readonly(project_dir)) as conn:
        row = conn.execute(
            "SELECT mutant_name FROM mutation_run_mutant"
            " WHERE run_id = ? AND result_status = 'killed' ORDER BY ordinal LIMIT 1",
            (latest[0],),
        ).fetchone()
    return row[0] if row else None
