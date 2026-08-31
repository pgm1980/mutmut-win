"""Regression tests for MW220-021 persistent per-run identity."""

from __future__ import annotations

import contextlib
import sqlite3
import threading
from dataclasses import FrozenInstanceError
from typing import TYPE_CHECKING
from uuid import UUID

import pytest

from mutmut_win.config import MutmutConfig
from mutmut_win.db import (
    RunStateError,
    begin_run,
    finish_run,
    invalidate_latest_run_evidence,
    load_current_run,
    load_results,
    mark_reused_results,
    save_result,
    save_results,
    set_run_plan,
    start_run,
)
from mutmut_win.models import MutationResult
from mutmut_win.stats import canonical_run_basis_config

if TYPE_CHECKING:
    from pathlib import Path


def _result(name: str, *, status: str = "killed") -> MutationResult:
    return MutationResult(
        mutant_name=name,
        status=status,
        exit_code=1,
        duration=0.25,
        last_output="boom",
        forensics={"confidence": 0.9},
        tests_fingerprint="fp",
    )


def test_old_cache_migrates_without_becoming_a_current_run(tmp_path: Path) -> None:
    db_path = tmp_path / "old.db"
    with contextlib.closing(sqlite3.connect(db_path)) as conn:
        conn.execute(
            "CREATE TABLE mutant ("
            "mutant_name TEXT PRIMARY KEY, status TEXT NOT NULL, "
            "exit_code INTEGER, duration REAL)"
        )
        conn.execute("INSERT INTO mutant VALUES ('old-mutant', 'survived', 0, 1.0)")
        conn.commit()

    assert load_current_run(db_path) is None
    [historic] = load_results(db_path)
    assert historic.mutant_name == "old-mutant"

    with contextlib.closing(sqlite3.connect(db_path)) as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
    assert {"mutant", "mutation_run", "mutation_run_mutant"} <= tables


def test_pre_plan_attempt_is_durable_and_cannot_claim_completion(tmp_path: Path) -> None:
    db_path = tmp_path / "cache.db"

    run_id = begin_run(db_path)

    current = load_current_run(db_path)
    assert current is not None
    assert current.run_id == run_id
    assert current.status == "running"
    assert current.plan_finalized is False
    assert current.universe_fingerprint is None
    assert current.planned_names == ()
    with pytest.raises(RunStateError, match="already running"):
        begin_run(db_path)
    with pytest.raises(RunStateError, match="no finalized mutation plan"):
        finish_run(db_path, run_id, "completed")

    finish_run(db_path, run_id, "failed")
    failed = load_current_run(db_path)
    assert failed is not None
    assert failed.status == "failed"
    assert failed.plan_finalized is False


def test_set_run_plan_is_exactly_once_ordered_and_fingerprinted(tmp_path: Path) -> None:
    db_path = tmp_path / "cache.db"
    run_id = begin_run(db_path)

    set_run_plan(
        db_path,
        run_id,
        ["m2", "m1"],
        generation_fingerprint="generation-v1",
    )

    current = load_current_run(db_path)
    assert current is not None
    assert current.plan_finalized is True
    assert current.planned_names == ("m2", "m1")
    assert current.pending_names == ("m2", "m1")
    assert current.universe_fingerprint is not None
    assert len(current.universe_fingerprint) == 64
    assert current.plan_digest is not None
    assert len(current.plan_digest) == 64
    with pytest.raises(RunStateError, match="already has a finalized plan"):
        set_run_plan(db_path, run_id, ["replacement"])


def test_invalid_plan_and_pre_plan_worker_result_leave_attempt_unchanged(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "cache.db"
    run_id = begin_run(db_path)

    with pytest.raises(ValueError, match="duplicate planned"):
        set_run_plan(db_path, run_id, ["m1", "m1"])
    with pytest.raises(RunStateError, match="was not planned"):
        save_result(db_path, "m1", "killed", 1, 0.1, require_planned=True)

    unchanged = load_current_run(db_path)
    assert unchanged is not None
    assert unchanged.plan_finalized is False
    assert unchanged.planned_names == ()
    assert load_results(db_path) == []

    # Both failures rolled back, so the legitimate plan can still be attached.
    set_run_plan(db_path, run_id, ["m1"])
    save_result(db_path, "m1", "killed", 1, 0.1, require_planned=True)
    finish_run(db_path, run_id, "completed")


def test_existing_run_schema_migrates_old_rows_as_finalized_plans(tmp_path: Path) -> None:
    db_path = tmp_path / "old-run.db"
    with contextlib.closing(sqlite3.connect(db_path)) as conn:
        conn.execute(
            "CREATE TABLE mutation_run ("
            "sequence INTEGER PRIMARY KEY AUTOINCREMENT, "
            "run_id TEXT NOT NULL UNIQUE, status TEXT NOT NULL, "
            "started_at TEXT NOT NULL, finished_at TEXT)"
        )
        conn.execute(
            "INSERT INTO mutation_run (run_id, status, started_at, finished_at) "
            "VALUES ('legacy-run', 'completed', '2026-01-01T00:00:00+00:00', "
            "'2026-01-01T00:01:00+00:00')"
        )
        conn.commit()

    current = load_current_run(db_path)

    assert current is not None
    assert current.run_id == "legacy-run"
    assert current.plan_finalized is True
    assert current.universe_fingerprint is None
    assert current.plan_digest is None
    assert current.basis_fingerprint is None
    assert current.basis_config_json is None
    assert current.evidence_invalidated is False

    with contextlib.closing(sqlite3.connect(db_path)) as conn:
        run_columns = {row[1] for row in conn.execute("PRAGMA table_info(mutation_run)").fetchall()}
    assert {
        "basis_fingerprint",
        "basis_config_json",
        "evidence_invalidated",
        "plan_digest",
    } <= run_columns


def test_run_basis_round_trips_with_the_modern_run_snapshot(tmp_path: Path) -> None:
    db_path = tmp_path / "cache.db"
    fingerprint = "1" * 64
    config_json = canonical_run_basis_config(
        MutmutConfig(paths_to_mutate=["src"], tests_dir=["tests"])
    )

    run_id = start_run(
        db_path,
        ["m1"],
        basis_fingerprint=fingerprint,
        basis_config_json=config_json,
    )
    current = load_current_run(db_path)

    assert current is not None
    assert current.run_id == run_id
    assert current.basis_fingerprint == fingerprint
    assert current.basis_config_json == config_json


@pytest.mark.parametrize(
    ("fingerprint", "config_json", "message"),
    [
        ("a" * 64, None, "supplied together"),
        (None, "{}", "supplied together"),
        ("A" * 64, "{}", "lowercase SHA-256"),
        ("a" * 64, "not-json", "valid JSON"),
        ("a" * 64, '{"b": 1, "a": 2}', "canonical JSON"),
    ],
)
def test_invalid_run_basis_is_rejected_before_database_creation(
    tmp_path: Path,
    fingerprint: str | None,
    config_json: str | None,
    message: str,
) -> None:
    db_path = tmp_path / "cache.db"

    with pytest.raises(ValueError, match=message):
        begin_run(
            db_path,
            basis_fingerprint=fingerprint,
            basis_config_json=config_json,
        )

    assert not db_path.exists()


def test_latest_run_evidence_can_be_invalidated_without_rewriting_verdicts(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "cache.db"
    run_id = start_run(db_path, ["m1"])
    save_result(db_path, "m1", "killed", 1, 0.1)
    finish_run(db_path, run_id, "completed")

    assert invalidate_latest_run_evidence(db_path) is True
    assert invalidate_latest_run_evidence(db_path) is True

    current = load_current_run(db_path)
    assert current is not None
    assert current.status == "completed"
    assert current.evidence_invalidated is True
    assert current.completed_names == ("m1",)
    assert current.completed_results[0].status == "killed"


def test_invalidating_missing_cache_does_not_create_it(tmp_path: Path) -> None:
    db_path = tmp_path / "missing" / "cache.db"

    assert invalidate_latest_run_evidence(db_path) is False
    assert not db_path.exists()
    assert not db_path.parent.exists()


def test_start_run_is_uuid_backed_running_plan_and_history_stays_pending(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "cache.db"
    save_result(db_path, "m1", "survived", 0, 1.0)

    run_id = start_run(db_path, ["m1", "m2"])

    assert UUID(run_id).version == 4
    current = load_current_run(db_path)
    assert current is not None
    assert current.run_id == run_id
    assert current.status == "running"
    assert current.finished_at is None
    assert current.planned_names == ("m1", "m2")
    assert current.completed_names == ()
    assert current.completed_results == ()
    assert current.pending_names == ("m1", "m2")
    with pytest.raises(FrozenInstanceError):
        current.status = "completed"  # type: ignore[misc]

    # A crash before finish leaves this durable active plan and cannot be
    # silently superseded by a second process/run.
    with pytest.raises(RunStateError, match="already running"):
        start_run(db_path, ["m3"])


def test_save_result_snapshots_only_names_planned_for_the_active_run(tmp_path: Path) -> None:
    db_path = tmp_path / "cache.db"
    start_run(db_path, ["planned", "pending"])

    save_result(
        db_path,
        "planned",
        "killed",
        1,
        0.5,
        last_output="failure",
        forensics={"cpu": 1.0},
        tests_fingerprint="tests-fp",
    )
    save_result(db_path, "not-planned", "survived", 0, 0.1)

    current = load_current_run(db_path)
    assert current is not None
    assert current.completed_names == ("planned",)
    assert current.pending_names == ("pending",)
    [completed] = current.completed_results
    assert completed.mutant_name == "planned"
    assert completed.status == "killed"
    assert completed.forensics == {"cpu": 1.0}
    assert completed.tests_fingerprint == "tests-fp"
    assert completed.reused is False
    assert {row.mutant_name for row in load_results(db_path)} == {
        "planned",
        "not-planned",
    }


def test_save_results_marks_planned_batch_and_completed_run(tmp_path: Path) -> None:
    db_path = tmp_path / "cache.db"
    run_id = start_run(db_path, ["m1", "m2"])

    save_results(
        db_path,
        [
            ("m1", "killed", 1, 0.1, None, None, "fp1"),
            ("unplanned", "survived", 0, 0.2, None, None, "fp-x"),
            ("m2", "survived", 0, 0.3, None, None, "fp2"),
        ],
    )
    finish_run(db_path, run_id, "completed")

    current = load_current_run(db_path)
    assert current is not None
    assert current.status == "completed"
    assert current.finished_at is not None
    assert current.completed_names == ("m1", "m2")
    assert current.pending_names == ()
    assert [result.status for result in current.completed_results] == ["killed", "survived"]
    assert {row.mutant_name for row in load_results(db_path)} == {"m1", "m2", "unplanned"}


def test_reuse_is_explicit_and_snapshotted_independently_from_cache(tmp_path: Path) -> None:
    db_path = tmp_path / "cache.db"
    cached = _result("m1", status="survived")
    save_result(
        db_path,
        cached.mutant_name,
        cached.status,
        cached.exit_code,
        cached.duration,
        cached.last_output,
        cached.forensics,
        cached.tests_fingerprint,
    )
    [loaded_cache_row] = load_results(db_path)
    run_id = start_run(db_path, ["m1"])

    # Merely loading the historical row does not make it current.
    before_reuse = load_current_run(db_path)
    assert before_reuse is not None
    assert before_reuse.pending_names == ("m1",)

    mark_reused_results(db_path, run_id, [loaded_cache_row])
    finish_run(db_path, run_id, "completed")
    save_result(db_path, "m1", "killed", 1, 9.0, tests_fingerprint="new-fp")

    current = load_current_run(db_path)
    assert current is not None
    [snapshot] = current.completed_results
    assert snapshot.status == "survived"
    assert snapshot.duration == pytest.approx(0.25)
    assert snapshot.tests_fingerprint == "fp"
    assert snapshot.reused is True
    [latest_cache_row] = load_results(db_path)
    assert latest_cache_row.status == "killed"


def test_reuse_batch_is_all_or_nothing_on_unplanned_name(tmp_path: Path) -> None:
    db_path = tmp_path / "cache.db"
    run_id = start_run(db_path, ["m1", "m2"])

    with pytest.raises(RunStateError, match="was not planned"):
        mark_reused_results(db_path, run_id, [_result("m1"), _result("ghost")])

    current = load_current_run(db_path)
    assert current is not None
    assert current.completed_names == ()
    assert current.pending_names == ("m1", "m2")


def test_run_id_mismatches_and_duplicate_completion_fail_closed(tmp_path: Path) -> None:
    db_path = tmp_path / "cache.db"
    run_id = start_run(db_path, ["m1"])

    with pytest.raises(RunStateError, match="mismatch"):
        mark_reused_results(db_path, "not-the-active-id", [])
    with pytest.raises(RunStateError, match="mismatch"):
        finish_run(db_path, "not-the-active-id", "aborted")

    save_result(db_path, "m1", "killed", 1, 0.1)
    with pytest.raises(RunStateError, match="already complete"):
        save_result(db_path, "m1", "survived", 0, 0.2)

    # The failed duplicate event rolled back its historical-cache overwrite.
    [cached] = load_results(db_path)
    assert cached.status == "killed"
    finish_run(db_path, run_id, "completed")


def test_finish_validates_status_and_preserves_pending_on_abort(tmp_path: Path) -> None:
    db_path = tmp_path / "cache.db"
    run_id = start_run(db_path, ["pending"])

    with pytest.raises(ValueError, match="invalid terminal"):
        finish_run(db_path, run_id, "running")
    with pytest.raises(RunStateError, match="1 pending"):
        finish_run(db_path, run_id, "completed")

    still_running = load_current_run(db_path)
    assert still_running is not None
    assert still_running.status == "running"
    assert still_running.pending_names == ("pending",)

    finish_run(db_path, run_id, "aborted")
    aborted = load_current_run(db_path)
    assert aborted is not None
    assert aborted.status == "aborted"
    assert aborted.finished_at is not None
    assert aborted.pending_names == ("pending",)
    with pytest.raises(RunStateError, match="no mutation run"):
        finish_run(db_path, run_id, "aborted")

    # A terminal run releases the one-active-run boundary.
    next_run_id = start_run(db_path, [])
    assert next_run_id != run_id


def test_duplicate_planned_names_are_rejected_before_writing(tmp_path: Path) -> None:
    db_path = tmp_path / "cache.db"
    with pytest.raises(ValueError, match="duplicate planned"):
        start_run(db_path, ["m1", "m1"])
    assert not db_path.exists()


def test_parallel_start_has_exactly_one_winner(tmp_path: Path) -> None:
    db_path = tmp_path / "cache.db"
    barrier = threading.Barrier(4)
    winners: list[str] = []
    errors: list[Exception] = []

    def worker(index: int) -> None:
        barrier.wait()
        try:
            winners.append(start_run(db_path, [f"m{index}"]))
        except Exception as exc:  # pragma: no cover - asserted below
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(index,)) for index in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(winners) == 1
    assert len(errors) == 3
    assert all(isinstance(error, RunStateError) for error in errors)
    current = load_current_run(db_path)
    assert current is not None
    assert current.run_id == winners[0]


def test_new_run_api_connections_close_even_on_state_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opened: list[object] = []
    closed: list[object] = []
    real_connect = sqlite3.connect

    class TrackingConnection:
        def __init__(self, conn: sqlite3.Connection) -> None:
            self._conn = conn

        def close(self) -> None:
            closed.append(self)
            self._conn.close()

        def __getattr__(self, name: str) -> object:
            return getattr(self._conn, name)

    def tracking_connect(*args: object, **kwargs: object) -> TrackingConnection:
        proxy = TrackingConnection(real_connect(*args, **kwargs))  # type: ignore[arg-type]
        opened.append(proxy)
        return proxy

    monkeypatch.setattr(sqlite3, "connect", tracking_connect)
    db_path = tmp_path / "cache.db"
    run_id = start_run(db_path, ["m1"])
    load_current_run(db_path)
    with pytest.raises(RunStateError):
        finish_run(db_path, "wrong-id", "failed")
    mark_reused_results(db_path, run_id, [_result("m1")])
    finish_run(db_path, run_id, "completed")

    assert opened
    assert len(closed) == len(opened)
