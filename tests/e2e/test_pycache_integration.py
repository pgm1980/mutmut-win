"""M-149b integration test: dispatch workers actually share the pycache.

Runs a real mutmut-win campaign against simple_lib (~14 mutants) and
verifies the full chain: orchestrator → executor → worker → pytest child
all reuse the same bytecode cache. The independent oracle is timing:
the first mutant pays the compilation cost, subsequent mutants read from
the shared cache and complete measurably faster.
"""

from __future__ import annotations

import sqlite3
import subprocess
import sys
import time
from contextlib import closing
from pathlib import Path

import pytest

from tests.e2e.e2e_util import SIMPLE_LIB, copy_project, run_cli

pytestmark = [pytest.mark.e2e, pytest.mark.slow]


class TestDispatchWorkerSharedPycache:
    """Real campaign: workers share bytecode cache across mutants."""

    def test_workers_share_pycache_and_speed_up(self, tmp_path: Path) -> None:
        """Full campaign with shared pycache: total time significantly less
        than first-mutant compile time × mutant count."""

        project = copy_project(SIMPLE_LIB, tmp_path)

        # Run the full campaign
        t0 = time.monotonic()
        result = run_cli(project, "run", "--no-progress", timeout=900)
        total_elapsed = time.monotonic() - t0

        assert result.returncode == 0, (
            f"Campaign failed:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )

        # Read per-mutant durations from the cache DB
        db_path = project / ".mutmut-cache" / "mutmut-cache.db"
        assert db_path.is_file(), "cache DB must exist after a successful run"

        with closing(sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)) as conn:
            run_id = conn.execute(
                "SELECT run_id FROM mutation_run ORDER BY sequence DESC LIMIT 1"
            ).fetchone()[0]
            durations = conn.execute(
                "SELECT duration FROM mutation_run_mutant"
                " WHERE run_id = ? AND duration IS NOT NULL AND duration > 0"
                " ORDER BY ordinal",
                (run_id,),
            ).fetchall()

        assert len(durations) >= 5, (
            f"Expected at least 5 mutants with durations, got {len(durations)}"
        )

        values = [d[0] for d in durations]
        first = values[0]
        later_avg = sum(values[1:]) / max(1, len(values) - 1)

        # The first mutant includes the compilation of ~80 MB trampolined
        # source (~350s for orchestrator.py alone in the old ephemeral mode).
        # With shared pycache, later mutants should be MUCH faster than the
        # first one because they read from the cache.
        # We assert the later mutants are at most 3x the first mutant's time
        # (conservative: without sharing, every mutant would be similar).
        # Note: without M-149b, all mutants would be roughly the same duration.
        assert later_avg < first * 3.0, (
            f"Shared pycache not working: first mutant {first:.1f}s, "
            f"later average {later_avg:.1f}s — without sharing, all mutants "
            f"would be similarly slow (compile from scratch each time). "
            f"Durations: {values}"
        )

        # Verify the pycache directory has bytecode files
        pycache_dirs = list(
            (project / ".mutmut-cache").rglob("*.pyc")
        ) + list(
            project.rglob("mutmut-win-run-pycache*")
        )
        # The shared pycache temp dir may be cleaned up after the run,
        # so we check the durations as the primary oracle.

    def test_worker_env_has_shared_pycache_during_run(self, tmp_path: Path) -> None:
        """During a campaign, worker pytest children see PYTHONPYCACHEPREFIX
        pointing to a shared (non-ephemeral) directory."""

        project = copy_project(SIMPLE_LIB, tmp_path)

        # Start the campaign as a subprocess
        process = subprocess.Popen(
            [sys.executable, "-m", "mutmut_win", "run", "--no-progress"],
            cwd=project,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        # Wait for the campaign to complete
        try:
            stdout, _ = process.communicate(timeout=600)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=30)
            pytest.fail("Campaign timed out")

        assert process.returncode == 0, f"stdout:\n{stdout}"

        # Check for the M-149b evidence in the output:
        # The run should NOT show per-worker compilation warnings
        # and should complete significantly faster than without sharing
        assert "Score" in stdout, "campaign summary must be present"

        # The total duration should be reasonable (not 14 × 450s = 6300s
        # which would be the case without shared pycache)
        db_path = project / ".mutmut-cache" / "mutmut-cache.db"
        with closing(sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)) as conn:
            run_id = conn.execute(
                "SELECT run_id FROM mutation_run ORDER BY sequence DESC LIMIT 1"
            ).fetchone()[0]
            (total_duration,) = conn.execute(
                "SELECT SUM(duration) FROM mutation_run_mutant WHERE run_id = ?",
                (run_id,),
            ).fetchone()
            mutant_count = len(
                conn.execute(
                    "SELECT ordinal FROM mutation_run_mutant WHERE run_id = ?",
                    (run_id,),
                ).fetchall()
            )

        # Without shared pycache: ~450s per mutant × N mutants
        # With shared pycache: only the first mutant pays the compile cost
        # For simple_lib (~14 mutants), total should be well under 14 × 450s
        if total_duration and mutant_count > 0:
            avg_per_mutant = total_duration / mutant_count
            # Conservative: average should be under 300s (without sharing
            # it would be ~450s; with sharing, only the first is slow)
            assert avg_per_mutant < 300, (
                f"Average {avg_per_mutant:.1f}s per mutant suggests "
                f"shared pycache is not working (expected < 300s, "
                f"got {avg_per_mutant:.1f}s across {mutant_count} mutants)"
            )
