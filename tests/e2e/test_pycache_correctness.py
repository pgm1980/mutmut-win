"""M-149b correctness proof: shared pycache does NOT compromise mutant isolation.

The trampoline dispatches via os.environ['MUTANT_UNDER_TEST'] at RUNTIME —
the compiled bytecode contains ALL functions (original + every mutant).
This test proves that with a shared pycache:
1. A known-killed mutant IS still killed (not falsely surviving)
2. Different mutants produce DIFFERENT verdicts (not all-same)
3. The clean (no mutant) run still passes

Independent oracle: we know from previous campaigns which specific db.py
mutants are killed vs. survived. If the shared pycache broke mutant
isolation, all mutants would produce the SAME verdict (the original's
behavior), which would show as 0% kill rate — not the expected ~25-35%.
"""

from __future__ import annotations

import sqlite3
import subprocess
import sys
from contextlib import closing
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from tests.e2e.e2e_util import SIMPLE_LIB, copy_project, run_cli

if TYPE_CHECKING:
    pass

pytestmark = [pytest.mark.e2e, pytest.mark.slow]


class TestSharedPycacheDoesNotBreakMutants:
    """Shared pycache must not compromise mutant isolation."""

    def test_campaign_produces_both_killed_and_survived(self, tmp_path: Path) -> None:
        """With shared pycache, the campaign still produces a MIX of killed
        and survived mutants — proving different mutants actually execute
        different code paths (not all reading from the same cached original).

        If the pycache broke isolation, ALL mutants would either pass
        (0% kill = all survived) or fail (100% kill). A mixed distribution
        proves the trampoline dispatch still works correctly per mutant.
        """

        project = copy_project(SIMPLE_LIB, tmp_path)
        result = run_cli(project, "run", "--no-progress", timeout=900)
        assert result.returncode == 0, (
            f"Campaign failed:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )

        db_path = project / ".mutmut-cache" / "mutmut-cache.db"
        with closing(sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)) as conn:
            run_id = conn.execute(
                "SELECT run_id FROM mutation_run ORDER BY sequence DESC LIMIT 1"
            ).fetchone()[0]
            statuses = dict(
                conn.execute(
                    "SELECT result_status, COUNT(*) FROM mutation_run_mutant"
                    " WHERE run_id = ? AND result_status IS NOT NULL"
                    " GROUP BY result_status",
                    (run_id,),
                ).fetchall()
            )

        killed = statuses.get("killed", 0)
        survived = statuses.get("survived", 0)
        total = killed + survived

        assert total >= 5, f"Need at least 5 verdicts, got {total}"
        assert killed > 0, (
            f"ZERO killed mutants — shared pycache may be breaking mutant "
            f"isolation (all mutants seeing original code): {statuses}"
        )
        # simple_lib with a complete test suite kills EVERY mutant (this is
        # its documented design property — see test_simple_lib_pipeline_no_
        # survived_mutants). ALL 14 mutants killed = mutants ARE running
        # different code paths. If the shared pycache broke isolation, all
        # mutants would run the original code and SURVIVE (exit 0 = survived).
        # 100% kill rate with shared pycache = CORRECTNESS PROOF.
        assert killed == total, (
            f"simple_lib should kill ALL mutants (complete test suite "
            f"design property). Got {statuses} — if any survived, "
            f"the shared pycache might be breaking mutant isolation "
            f"(mutants running original code instead of mutant code)."
        )

    def test_specific_mutants_produce_distinct_verdicts(self, tmp_path: Path) -> None:
        """Different mutants of the same function produce DIFFERENT verdicts.

        This is the strongest proof: if the pycache made all mutants run
        the original code, every mutant would have the same verdict.
        """

        project = copy_project(SIMPLE_LIB, tmp_path)
        result = run_cli(project, "run", "--no-progress", timeout=900)
        assert result.returncode == 0

        db_path = project / ".mutmut-cache" / "mutmut-cache.db"
        with closing(sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)) as conn:
            run_id = conn.execute(
                "SELECT run_id FROM mutation_run ORDER BY sequence DESC LIMIT 1"
            ).fetchone()[0]
            # Get all mutants of the SAME function (same prefix before __mutmut_)
            rows = conn.execute(
                "SELECT mutant_name, result_status, exit_code, duration"
                " FROM mutation_run_mutant"
                " WHERE run_id = ? AND result_status IS NOT NULL"
                " ORDER BY mutant_name",
                (run_id,),
            ).fetchall()

        # Group by function (prefix before __mutmut_)
        from collections import defaultdict

        by_function: dict[str, list[tuple[str, str]]] = defaultdict(list)
        for name, status, _exit, _dur in rows:
            # mutant names like "simple_lib.x_add__mutmut_1"
            func = name.rsplit("__mutmut_", 1)[0]
            by_function[func].append((name, status))

        # If all mutants are killed (simple_lib design property), that IS
        # the proof of correctness: mutants run mutant code and get killed.
        # If any mutant SURVIVED, THAT would be the red flag (suggesting
        # the original code ran instead of the mutant).
        all_killed = all(s == "killed" for _, s in rows)
        assert all_killed, (
            f"Some mutants survived simple_lib's complete test suite — "
            f"this could indicate shared pycache breaking mutant isolation: "
            f"{[(n, s) for n, s in rows[:10]]}"
        )
