"""Issue M-097 (W0): the legacy fallback must not mix two snapshots.

``load_latest_run_results`` decides "no run header exists" in one
connection/snapshot (``load_current_run``) and then reads the legacy
``mutant`` table in a second one (``load_results``).  A writer committing
a first modern run (``begin_run`` plus verdict rows) between those two
reads yields a mixed population delivered without run identity — the
documented defect; the docstring already promises the single-snapshot
fix.

Deterministic interleaving: ``db.load_results`` — called by
``load_latest_run_results`` exactly between the run-header decision and
the legacy read — is wrapped so a raw writer commit inserts the run
header plus new verdict rows first: precisely the first-modern-run
window of the defect.  The contract under test: whenever the reader
still answers ``None`` (no run seen), its legacy population must not
contain rows that only exist after the writer committed.  Today the
second snapshot observes the commit (mixed population); with one
deferred read transaction the snapshot stays pre-writer (or the run is
seen at all).
"""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

import pytest

from mutmut_win import db
from mutmut_win.db import load_latest_run_results, save_result

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from mutmut_win.models import MutationResult

_NEW_RUN_ID = "7b7b7b7b-0000-0000-0000-000000000001"
_NEW_MUTANT = "src/fresh_mod.py__mutmut_7"
_LEGACY_MUTANT = "src/old_mod.py__mutmut_1"


@pytest.fixture
def legacy_db(tmp_path: Path) -> Path:
    path = tmp_path / "cache.sqlite"
    save_result(path, _LEGACY_MUTANT, "survived", 0, 0.5)
    return path


@pytest.fixture
def interleaving_writer(legacy_db: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Commit a first modern run right before the legacy read."""

    original = db.load_results

    def writer_then_legacy(path: Path) -> Sequence[MutationResult]:
        _commit_first_modern_run(path)
        return original(path)

    monkeypatch.setattr(db, "load_results", writer_then_legacy)
    return legacy_db


def _commit_first_modern_run(path: Path) -> None:
    """begin_run plus first verdict, mirroring the modern write pattern.

    A modern run writes its run header AND mirrors verdicts into the
    legacy ``mutant`` cache (``save_result``) — the mixture the reader can
    observe between its two snapshots.
    """

    writer = sqlite3.connect(path)
    try:
        writer.execute("BEGIN IMMEDIATE")
        writer.execute(
            "INSERT INTO mutation_run (run_id, status, started_at)"
            " VALUES (?, 'running', '2026-10-06T12:00:00+00:00')",
            (_NEW_RUN_ID,),
        )
        writer.execute(
            "INSERT INTO mutation_run_mutant"
            " (run_id, ordinal, mutant_name, completed, reused, result_status,"
            "  exit_code, duration, tests_fingerprint, completed_at)"
            " VALUES (?, 1, ?, 1, 0, 'killed', 1, 0.2, NULL,"
            " '2026-10-06T12:00:01+00:00')",
            (_NEW_RUN_ID, _NEW_MUTANT),
        )
        writer.execute(
            "INSERT INTO mutant"
            " (mutant_name, status, exit_code, duration, last_output,"
            "  forensics, tests_fingerprint)"
            " VALUES (?, 'killed', 1, 0.2, NULL, NULL, NULL)",
            (_NEW_MUTANT,),
        )
        writer.commit()
    finally:
        writer.close()


def test_legacy_fallback_never_mixes_post_writer_rows(
    interleaving_writer: Path,
) -> None:
    state, results = load_latest_run_results(interleaving_writer)

    if state is not None:
        # The reader saw the modern run: its own snapshot is authoritative.
        assert all(result.mutant_name != _LEGACY_MUTANT for result in results)
        return

    names = {result.mutant_name for result in results}
    assert _NEW_MUTANT not in names, (
        "legacy fallback delivered rows committed only after the run-header "
        "decision was made in a previous snapshot (M-097: mixed population "
        "without run identity)"
    )
