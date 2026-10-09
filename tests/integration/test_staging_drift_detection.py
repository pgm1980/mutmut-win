"""Integration: staging drift detection — file changes during dispatch abort the run (GAP-4)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from typing import TYPE_CHECKING

import pytest
from pydantic import BaseModel

from mutmut_win.db import load_current_run, load_results

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.integration, pytest.mark.slow]


class _PhaseEvidence(BaseModel):
    """Bind an observed dispatched mutant to its persisted run identity."""

    run_id: str
    status: str
    mutant_name: str
    worker_pid: int
    planned_names: tuple[str, ...]


def _setup_project(tmp: Path) -> Path:
    project = tmp / "proj"
    src = project / "src" / "pkg"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    tests = project / "tests"
    tests.mkdir()
    (tests / "test_f.py").write_text(
        "import os\nimport time\nfrom pathlib import Path\n"
        "def test_f():\n"
        "    token = os.environ.get('MUTANT_UNDER_TEST', '')\n"
        "    marker = os.environ.get('S3_DRIFT_DISPATCH_MARKER')\n"
        "    if marker and token and token not in {'stats', 'fail'}:\n"
        "        Path(marker).write_text(str(os.getpid()) + '\\n' + token + '\\n', "
        "encoding='utf-8')\n"
        "        release = Path(os.environ['S3_DRIFT_RELEASE'])\n"
        "        deadline = time.monotonic() + 60\n"
        "        while not release.exists():\n"
        "            assert time.monotonic() < deadline, 'dispatch barrier timed out'\n"
        "            time.sleep(0.01)\n"
        "    from pkg import f\n"
        "    assert f() == 1\n",
        encoding="utf-8",
    )
    (project / "pyproject.toml").write_text(
        '[tool.mutmut]\npaths_to_mutate=["src/"]\ntests_dir=["tests/"]\n'
        "max_children=1\ntimeout_multiplier=30.0\n",
        encoding="utf-8",
    )
    return project


def _export(project: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "mutmut_win", "export-cicd-stats"],
        cwd=project,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        check=False,
    )


class TestStagingDrift:
    def test_source_change_during_run_is_detected(self, tmp_path: Path) -> None:
        """Source drift during proven dispatch revokes the same run's authority."""
        project = _setup_project(tmp_path)
        marker = tmp_path / "dispatched.txt"
        release = tmp_path / "release.txt"
        log = tmp_path / "drift-run.log"
        environment = os.environ.copy()
        environment["S3_DRIFT_DISPATCH_MARKER"] = str(marker)
        environment["S3_DRIFT_RELEASE"] = str(release)
        database = project / ".mutmut-cache" / "mutmut-cache.db"
        with log.open("w", encoding="utf-8") as output:
            proc = subprocess.Popen(
                [sys.executable, "-m", "mutmut_win", "run", "--no-progress", "--min-score", "100"],
                cwd=project,
                env=environment,
                stdout=output,
                stderr=subprocess.STDOUT,
            )
            try:
                deadline = time.monotonic() + 180
                while True:
                    observed = marker.read_text(encoding="utf-8") if marker.exists() else ""
                    if observed.endswith("\n") and len(observed.splitlines()) == 2:
                        break
                    assert proc.poll() is None, log.read_text(encoding="utf-8")
                    assert time.monotonic() < deadline, "No actual mutant dispatch observed"
                    time.sleep(0.05)

                worker, token = observed.splitlines()
                before = load_current_run(database)
                assert before is not None
                assert before.status == "running"
                assert before.finished_at is None
                assert before.plan_finalized
                assert token in before.pending_names
                assert (project / "mutants" / "src" / "pkg" / "__init__.py").is_file()
                phase = _PhaseEvidence(
                    run_id=before.run_id,
                    status=before.status,
                    mutant_name=token,
                    worker_pid=int(worker),
                    planned_names=before.planned_names,
                )
                assert phase.worker_pid > 0
                (tmp_path / "dispatch-before-drift.json").write_text(
                    phase.model_dump_json(indent=2), encoding="utf-8"
                )
                source = project / "src" / "pkg" / "__init__.py"
                assert source.read_text(encoding="utf-8") == "def f():\n    return 1\n"
                source.write_text("def f():\n    return 42\n", encoding="utf-8")
                release.write_text("continue", encoding="utf-8")
                proc.wait(timeout=600)
            finally:
                release.write_text("continue", encoding="utf-8")
                if proc.poll() is None:
                    proc.kill()
                    proc.wait(timeout=30)

        diagnostic = log.read_text(encoding="utf-8")
        assert proc.returncode == 1, diagnostic
        assert "inputs changed during the mutation run" in diagnostic
        assert "recorded as failed and cannot authorize CI/CD export" in diagnostic
        after = load_current_run(database)
        assert after is not None
        assert after.run_id == before.run_id
        assert after.status == "failed"
        assert after.finished_at is not None
        assert after.planned_names == before.planned_names
        assert after.completed_names
        assert not after.pending_names
        # Immutable current-run rows retain diagnostic history. Reuse consumes
        # the historical cache, whose capabilities must all have been revoked.
        cached_rows = load_results(database)
        assert {row.mutant_name for row in cached_rows} == set(after.planned_names)
        assert all(row.tests_fingerprint is None for row in cached_rows)
        (tmp_path / "dispatch-after-drift.json").write_text(
            _PhaseEvidence(
                run_id=after.run_id,
                status=after.status,
                mutant_name=token,
                worker_pid=int(worker),
                planned_names=after.planned_names,
            ).model_dump_json(indent=2),
            encoding="utf-8",
        )
        export = _export(project)
        assert export.returncode == 1, export.stdout + export.stderr
        assert "status=failed" in export.stderr
        assert "CI/CD export failed closed" in export.stderr
        assert not (project / "mutants" / "mutmut-cicd-stats.json").exists()

    def test_no_drift_completes_normally(self, tmp_path: Path) -> None:
        """Unchanged workspace: run completes without false-positive drift."""

        project = _setup_project(tmp_path)
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "mutmut_win",
                "run",
                "--no-progress",
                "--min-score",
                "100",
                "--output",
                "json",
            ],
            cwd=project,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=600,
            check=False,
        )
        assert result.returncode == 0, (
            f"No-drift run must succeed.\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
        payload = json.loads(result.stdout)
        assert payload["total_mutants"] > 0
        assert payload["score"] == 100.0
        assert payload["execution_basis_complete"] is True
        current = load_current_run(project / ".mutmut-cache" / "mutmut-cache.db")
        assert current is not None
        assert current.status == "completed"
        assert not current.pending_names
        assert len(current.completed_names) == payload["total_mutants"]
        export = _export(project)
        assert export.returncode == 0, export.stdout + export.stderr
        assert (project / "mutants" / "mutmut-cicd-stats.json").is_file()
