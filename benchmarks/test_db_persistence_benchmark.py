"""Benchmark: batched vs per-row result persistence (issue #132 / 360°-C1).

Run with: ``uv run pytest benchmarks/ --benchmark-only``

The mass-persist paths (skipped exclusions, no-test verdicts, type-check
kills) used to call ``save_result`` per mutant — connect + create_db PRAGMA
+ commit for every row. ``save_results`` does the same batch over ONE
connection. This file is the timing evidence the #132 acceptance criteria
ask for.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from mutmut_win.db import save_result, save_results

if TYPE_CHECKING:
    from pathlib import Path

    import pytest_benchmark.fixture

_N_ROWS = 300


def _rows(n: int = _N_ROWS) -> list[tuple[str, str, int, None, None, None, None]]:
    return [(f"pkg.mod.x_f__mutmut_{i}", "skipped", 34, None, None, None, None) for i in range(n)]


def test_per_row_persistence(
    benchmark: pytest_benchmark.fixture.BenchmarkFixture, tmp_path: Path
) -> None:
    rows = _rows()

    def loop_of_single_saves() -> None:
        db = tmp_path / "single.db"
        db.unlink(missing_ok=True)
        for name, status, exit_code, duration, last_output, forensics, fp in rows:
            save_result(db, name, status, exit_code, duration, last_output, forensics, fp)

    benchmark(loop_of_single_saves)


def test_batched_persistence(
    benchmark: pytest_benchmark.fixture.BenchmarkFixture, tmp_path: Path
) -> None:
    rows = _rows()

    def one_batched_save() -> None:
        db = tmp_path / "batch.db"
        db.unlink(missing_ok=True)
        save_results(db, rows)

    benchmark(one_batched_save)
