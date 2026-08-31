"""Adversarial DB pathname, corruption, and release-state regressions."""

from __future__ import annotations

import contextlib
import os
import sqlite3
from dataclasses import replace
from pathlib import Path

import pytest
from click.testing import CliRunner

from mutmut_win.cli import cli
from mutmut_win.config import MutmutConfig
from mutmut_win.db import (
    CorruptCacheError,
    MutationRunState,
    RunBasisIncompleteness,
    RunMutationResult,
    RunStateError,
    create_db,
    finish_run,
    invalidate_latest_run_evidence,
    known_run_basis_incompleteness,
    load_current_run,
    load_latest_run_results,
    load_results,
    save_result,
    start_run,
)
from mutmut_win.exceptions import UnsafeWorkspaceStateError
from mutmut_win.stats import canonical_run_basis_config


def _raw_tables(path: Path) -> set[str]:
    with contextlib.closing(sqlite3.connect(path)) as connection:
        return {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }


def test_custom_database_hardlink_is_rejected_without_external_migration(
    tmp_path: Path,
) -> None:
    external = tmp_path / "external.db"
    with contextlib.closing(sqlite3.connect(external)) as connection:
        connection.execute("CREATE TABLE sentinel (value TEXT)")
        connection.execute("INSERT INTO sentinel VALUES ('untouched')")
        connection.commit()
    alias = tmp_path / "custom" / "cache.db"
    alias.parent.mkdir()
    try:
        os.link(external, alias)
    except OSError as exc:
        pytest.skip(f"hard links are unavailable on this filesystem: {exc}")

    with pytest.raises(UnsafeWorkspaceStateError, match="hardlink"):
        create_db(alias)

    assert _raw_tables(external) == {"sentinel"}


def test_custom_database_redirected_parent_is_rejected_before_directory_creation(
    tmp_path: Path,
) -> None:
    external = tmp_path / "external"
    external.mkdir()
    redirected = tmp_path / "redirected"
    try:
        redirected.symlink_to(external, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"directory symlinks are unavailable on this host: {exc}")

    with pytest.raises(UnsafeWorkspaceStateError, match=r"symlink|junction|reparse"):
        create_db(redirected / "nested" / "cache.db")

    assert not (external / "nested").exists()


def test_new_database_is_exclusively_precreated_before_sqlite_connect(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = tmp_path / "nested" / "cache.db"
    real_connect = sqlite3.connect
    observations: list[tuple[int, int]] = []

    def checked_connect(path: object, *args: object, **kwargs: object) -> sqlite3.Connection:
        prepared = Path(os.fspath(path))
        metadata = prepared.lstat()
        observations.append((metadata.st_nlink, metadata.st_size))
        return real_connect(path, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(sqlite3, "connect", checked_connect)

    create_db(database)

    assert observations == [(1, 0)]
    assert database.is_file()


def test_database_identity_swap_during_connect_fails_before_external_schema_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = tmp_path / "cache.db"
    create_db(database)
    external = tmp_path / "external.db"
    with contextlib.closing(sqlite3.connect(external)) as connection:
        connection.execute("CREATE TABLE sentinel (value TEXT)")
        connection.commit()
    real_connect = sqlite3.connect

    def swapping_connect(path: object, *args: object, **kwargs: object) -> sqlite3.Connection:
        database.unlink()
        os.link(external, database)
        return real_connect(path, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(sqlite3, "connect", swapping_connect)

    with pytest.raises(UnsafeWorkspaceStateError, match=r"changed identity|hardlink"):
        create_db(database)

    database.unlink()
    monkeypatch.setattr(sqlite3, "connect", real_connect)
    assert _raw_tables(external) == {"sentinel"}


def test_sidecar_swap_after_connect_fails_before_schema_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = tmp_path / "cache.db"
    create_db(database)
    sentinel = tmp_path / "sentinel.bin"
    sentinel.write_bytes(b"valuable external bytes")
    sidecar = Path(f"{database}-wal")
    real_connect = sqlite3.connect

    def swapping_connect(path: object, *args: object, **kwargs: object) -> sqlite3.Connection:
        connection = real_connect(path, *args, **kwargs)  # type: ignore[arg-type]
        os.link(sentinel, sidecar)
        return connection

    monkeypatch.setattr(sqlite3, "connect", swapping_connect)

    with pytest.raises(UnsafeWorkspaceStateError, match=r"sidecar.*hardlink"):
        create_db(database)

    sidecar.unlink()
    assert sentinel.read_bytes() == b"valuable external bytes"


def test_load_results_turns_invalid_json_into_corrupt_cache_error(tmp_path: Path) -> None:
    database = tmp_path / "cache.db"
    save_result(database, "m1", "killed", 1, 0.1, forensics={"ok": True})
    with contextlib.closing(sqlite3.connect(database)) as connection:
        connection.execute("UPDATE mutant SET forensics = 'not-json'")
        connection.commit()

    with pytest.raises(CorruptCacheError, match=r"forensics.*valid JSON"):
        load_results(database)


def test_load_results_turns_pydantic_value_failure_into_corrupt_cache_error(
    tmp_path: Path,
) -> None:
    database = tmp_path / "cache.db"
    save_result(database, "m1", "killed", 1, 0.1)
    with contextlib.closing(sqlite3.connect(database)) as connection:
        connection.execute("UPDATE mutant SET duration = -1")
        connection.commit()

    with pytest.raises(CorruptCacheError, match="duration"):
        load_results(database)


def test_load_results_rejects_unknown_legacy_verdict_status(tmp_path: Path) -> None:
    database = tmp_path / "cache.db"
    save_result(database, "m1", "killed", 1, 0.1)
    with contextlib.closing(sqlite3.connect(database)) as connection:
        connection.execute("UPDATE mutant SET status = 'looks-green'")
        connection.commit()

    with pytest.raises(CorruptCacheError, match="unknown persisted mutation status"):
        load_results(database)


def test_save_result_rejects_unknown_status_before_database_creation(tmp_path: Path) -> None:
    database = tmp_path / "cache.db"

    with pytest.raises(ValueError, match="unknown mutation result status"):
        save_result(database, "m1", "looks-green", 0, 0.1)

    assert not database.exists()


def test_active_run_rejects_legacy_non_verdict_as_completion(tmp_path: Path) -> None:
    database = tmp_path / "cache.db"
    start_run(database, ["m1"])

    with pytest.raises(RunStateError, match="not a completed verdict"):
        save_result(database, "m1", "not checked", None, None)

    current = load_current_run(database)
    assert current is not None
    assert current.pending_names == ("m1",)


def test_load_current_run_rejects_corrupt_snapshot_json(tmp_path: Path) -> None:
    database = tmp_path / "cache.db"
    run_id = start_run(database, ["m1"])
    save_result(database, "m1", "killed", 1, 0.1, forensics={"ok": True})
    finish_run(database, run_id, "completed")
    with contextlib.closing(sqlite3.connect(database)) as connection:
        connection.execute(
            "UPDATE mutation_run_mutant SET forensics = 'not-json' WHERE run_id = ?",
            (run_id,),
        )
        connection.commit()

    with pytest.raises(CorruptCacheError, match=r"forensics.*valid JSON"):
        load_current_run(database)


def test_load_current_run_rejects_unknown_run_verdict_status(tmp_path: Path) -> None:
    database = tmp_path / "cache.db"
    run_id = start_run(database, ["m1"])
    save_result(database, "m1", "killed", 1, 0.1)
    finish_run(database, run_id, "completed")
    with contextlib.closing(sqlite3.connect(database)) as connection:
        connection.execute(
            "UPDATE mutation_run_mutant SET result_status = 'looks-green' WHERE run_id = ?",
            (run_id,),
        )
        connection.commit()

    with pytest.raises(CorruptCacheError, match="unknown persisted mutation status"):
        load_current_run(database)


@pytest.mark.parametrize(
    ("planned_names", "plan_finalized", "expected"),
    [
        ([], 0, "finalized mutation plan"),
        (["m1"], 1, "contains pending mutants"),
    ],
)
def test_load_current_run_rejects_impossible_completed_plan_state(
    tmp_path: Path,
    planned_names: list[str],
    plan_finalized: int,
    expected: str,
) -> None:
    database = tmp_path / "cache.db"
    run_id = start_run(database, planned_names)
    with contextlib.closing(sqlite3.connect(database)) as connection:
        connection.execute(
            """
            UPDATE mutation_run
            SET status = 'completed',
                finished_at = '2026-01-01T00:01:00+00:00',
                plan_finalized = ?
            WHERE run_id = ?
            """,
            (plan_finalized, run_id),
        )
        connection.commit()

    with pytest.raises(CorruptCacheError, match=expected):
        load_current_run(database)


def test_load_current_run_rejects_invalid_sqlite_run_semantics(tmp_path: Path) -> None:
    database = tmp_path / "cache.db"
    run_id = start_run(database, [])
    with contextlib.closing(sqlite3.connect(database)) as connection:
        connection.execute("PRAGMA ignore_check_constraints = ON")
        connection.execute(
            "UPDATE mutation_run SET status = 'impossible' WHERE run_id = ?",
            (run_id,),
        )
        connection.commit()

    with pytest.raises(CorruptCacheError, match="unknown run status"):
        load_current_run(database)


def test_load_current_run_rejects_invalid_persisted_basis_config(tmp_path: Path) -> None:
    database = tmp_path / "cache.db"
    config_json = canonical_run_basis_config(MutmutConfig())
    run_id = start_run(
        database,
        [],
        basis_fingerprint="a" * 64,
        basis_config_json=config_json,
    )
    finish_run(database, run_id, "completed")
    with contextlib.closing(sqlite3.connect(database)) as connection:
        connection.execute(
            "UPDATE mutation_run SET basis_config_json = '{}' WHERE run_id = ?",
            (run_id,),
        )
        connection.commit()

    with pytest.raises(CorruptCacheError, match="complete effective MutmutConfig"):
        load_current_run(database)


def test_load_latest_run_results_wraps_pydantic_validation_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    completed = RunMutationResult(
        mutant_name="m1",
        status="killed",
        exit_code=1,
        duration=-1.0,
        last_output=None,
        forensics=None,
        tests_fingerprint=None,
        reused=False,
        completed_at="2026-01-01T00:01:00+00:00",
    )
    current = MutationRunState(
        run_id="run",
        status="completed",
        started_at="2026-01-01T00:00:00+00:00",
        finished_at="2026-01-01T00:01:00+00:00",
        planned_names=("m1",),
        completed_results=(completed,),
        completed_names=("m1",),
        pending_names=(),
    )
    monkeypatch.setattr("mutmut_win.db.load_current_run", lambda _path: current)

    with pytest.raises(CorruptCacheError, match="failed validation"):
        load_latest_run_results(tmp_path / "cache.db")


def test_results_cli_renders_corrupt_cache_as_domain_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    database = tmp_path / ".mutmut-cache" / "mutmut-cache.db"
    save_result(database, "m1", "killed", 1, 0.1)
    with contextlib.closing(sqlite3.connect(database)) as connection:
        connection.execute("UPDATE mutant SET forensics = 'not-json'")
        connection.commit()

    rendered = CliRunner().invoke(cli, ["results"])

    assert rendered.exit_code == 1
    assert "contains invalid persisted data" in rendered.output
    assert "Traceback" not in rendered.output


def test_cicd_export_rejects_corrupt_verdict_and_removes_stale_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    database = tmp_path / ".mutmut-cache" / "mutmut-cache.db"
    run_id = start_run(database, ["m1"])
    save_result(database, "m1", "killed", 1, 0.1)
    finish_run(database, run_id, "completed")
    with contextlib.closing(sqlite3.connect(database)) as connection:
        connection.execute(
            "UPDATE mutation_run_mutant SET result_status = 'looks-green' WHERE run_id = ?",
            (run_id,),
        )
        connection.commit()
    artifact = tmp_path / "mutants" / "mutmut-cicd-stats.json"
    artifact.parent.mkdir()
    artifact.write_text('{"score": 100.0}', encoding="utf-8")

    rendered = CliRunner().invoke(cli, ["export-cicd-stats"])

    assert rendered.exit_code == 1
    assert "unknown persisted mutation status" in rendered.output
    assert "Traceback" not in rendered.output
    assert not artifact.exists()


def test_results_marks_invalidated_evidence_not_release_ready(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    database = tmp_path / ".mutmut-cache" / "mutmut-cache.db"
    run_id = start_run(database, ["m1"])
    save_result(database, "m1", "killed", 1, 0.1)
    finish_run(database, run_id, "completed")
    invalidate_latest_run_evidence(database)

    rendered = CliRunner().invoke(cli, ["results"])

    assert rendered.exit_code == 0
    assert "Evidence invalidated: yes; release-ready: no" in rendered.output


def test_legacy_generic_type_checker_basis_is_known_incomplete_and_disclosed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    database = tmp_path / ".mutmut-cache" / "mutmut-cache.db"
    config = MutmutConfig(type_check_command=["uv", "run", "mypy", "--output=json", "src"])
    run_id = start_run(
        database,
        ["m1"],
        basis_fingerprint="a" * 64,
        basis_config_json=canonical_run_basis_config(config),
    )
    save_result(database, "m1", "killed", 1, 0.1)
    finish_run(database, run_id, "completed")

    current = load_current_run(database)
    assert current is not None
    assert (
        known_run_basis_incompleteness(current) is RunBasisIncompleteness.GENERIC_TYPE_CHECK_COMMAND
    )

    rendered = CliRunner().invoke(cli, ["results"])

    assert rendered.exit_code == 0
    assert "generic type_check_command" in rendered.output
    assert "execution basis incomplete; release-ready: no" in rendered.output


def test_known_run_basis_incompleteness_treats_malformed_config_as_unsafe() -> None:
    config = MutmutConfig()
    current = MutationRunState(
        run_id="run",
        status="completed",
        started_at="2026-01-01T00:00:00+00:00",
        finished_at="2026-01-01T00:00:01+00:00",
        planned_names=(),
        completed_results=(),
        completed_names=(),
        pending_names=(),
        basis_fingerprint="a" * 64,
        basis_config_json=canonical_run_basis_config(config),
    )

    malformed = replace(current, basis_config_json="{")
    missing = replace(current, basis_fingerprint=None, basis_config_json=None)

    assert known_run_basis_incompleteness(current) is None
    assert known_run_basis_incompleteness(malformed) is RunBasisIncompleteness.MALFORMED
    assert known_run_basis_incompleteness(missing) is RunBasisIncompleteness.MISSING


def test_results_rejects_malformed_persisted_basis_config_prominently(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    database = tmp_path / ".mutmut-cache" / "mutmut-cache.db"
    run_id = start_run(
        database,
        ["m1"],
        basis_fingerprint="a" * 64,
        basis_config_json=canonical_run_basis_config(MutmutConfig()),
    )
    save_result(database, "m1", "killed", 1, 0.1)
    finish_run(database, run_id, "completed")
    with contextlib.closing(sqlite3.connect(database)) as connection:
        connection.execute(
            "UPDATE mutation_run SET basis_config_json = ? WHERE run_id = ?",
            ("{", run_id),
        )
        connection.commit()

    rendered = CliRunner().invoke(cli, ["results"])

    assert rendered.exit_code == 1
    assert "invalid run basis" in rendered.output
    assert "valid JSON" in rendered.output
    assert "Traceback" not in rendered.output


def _completed_two_mutant_run(database: Path) -> str:
    run_id = start_run(database, ["killed-mutant", "survived-mutant"])
    save_result(database, "killed-mutant", "killed", 1, 0.1)
    save_result(database, "survived-mutant", "survived", 0, 0.1)
    finish_run(database, run_id, "completed")
    return run_id


@pytest.mark.parametrize("tamper", ["delete", "reorder", "exchange"])
def test_load_current_run_revalidates_exact_ordered_plan_digest(
    tmp_path: Path,
    tamper: str,
) -> None:
    database = tmp_path / "cache.db"
    run_id = _completed_two_mutant_run(database)
    with contextlib.closing(sqlite3.connect(database)) as connection:
        if tamper == "delete":
            connection.execute(
                "DELETE FROM mutation_run_mutant WHERE run_id = ? AND mutant_name = ?",
                (run_id, "survived-mutant"),
            )
        elif tamper == "reorder":
            connection.execute(
                "UPDATE mutation_run_mutant SET ordinal = 2 WHERE run_id = ? AND ordinal = 0",
                (run_id,),
            )
            connection.execute(
                "UPDATE mutation_run_mutant SET ordinal = 0 WHERE run_id = ? AND ordinal = 1",
                (run_id,),
            )
            connection.execute(
                "UPDATE mutation_run_mutant SET ordinal = 1 WHERE run_id = ? AND ordinal = 2",
                (run_id,),
            )
        else:
            connection.execute(
                "UPDATE mutation_run_mutant SET mutant_name = '__temporary__' "
                "WHERE run_id = ? AND mutant_name = 'killed-mutant'",
                (run_id,),
            )
            connection.execute(
                "UPDATE mutation_run_mutant SET mutant_name = 'killed-mutant' "
                "WHERE run_id = ? AND mutant_name = 'survived-mutant'",
                (run_id,),
            )
            connection.execute(
                "UPDATE mutation_run_mutant SET mutant_name = 'survived-mutant' "
                "WHERE run_id = ? AND mutant_name = '__temporary__'",
                (run_id,),
            )
        connection.commit()

    with pytest.raises(CorruptCacheError, match=r"ordered mutation plan.*digest"):
        load_current_run(database)


def test_load_current_run_rejects_noncontiguous_plan_ordinal(tmp_path: Path) -> None:
    database = tmp_path / "cache.db"
    run_id = _completed_two_mutant_run(database)
    with contextlib.closing(sqlite3.connect(database)) as connection:
        connection.execute(
            "UPDATE mutation_run_mutant SET ordinal = 5 "
            "WHERE run_id = ? AND mutant_name = 'survived-mutant'",
            (run_id,),
        )
        connection.commit()

    with pytest.raises(CorruptCacheError, match=r"stored plan ordinal 5.*expected 1"):
        load_current_run(database)


def test_cicd_export_rejects_deleted_plan_row_and_removes_stale_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    database = tmp_path / ".mutmut-cache" / "mutmut-cache.db"
    run_id = _completed_two_mutant_run(database)
    with contextlib.closing(sqlite3.connect(database)) as connection:
        connection.execute(
            "DELETE FROM mutation_run_mutant WHERE run_id = ? AND mutant_name = ?",
            (run_id, "survived-mutant"),
        )
        connection.commit()
    artifact = tmp_path / "mutants" / "mutmut-cicd-stats.json"
    artifact.parent.mkdir()
    artifact.write_text('{"score": 100.0}', encoding="utf-8")

    rendered = CliRunner().invoke(cli, ["export-cicd-stats"])

    assert rendered.exit_code == 1
    assert "ordered mutation plan does not match its persisted digest" in rendered.output
    assert not artifact.exists()


def test_cicd_export_rejects_missing_migrated_plan_digest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    database = tmp_path / ".mutmut-cache" / "mutmut-cache.db"
    run_id = start_run(database, ["killed-mutant"])
    save_result(database, "killed-mutant", "killed", 1, 0.1)
    finish_run(database, run_id, "completed")
    with contextlib.closing(sqlite3.connect(database)) as connection:
        connection.execute(
            "UPDATE mutation_run SET plan_digest = NULL WHERE run_id = ?",
            (run_id,),
        )
        connection.commit()

    rendered = CliRunner().invoke(cli, ["export-cicd-stats"])

    assert rendered.exit_code == 1
    assert "predates verifiable ordered-plan evidence" in rendered.output
    assert not (tmp_path / "mutants" / "mutmut-cicd-stats.json").exists()


def _two_completed_run_headers(database: Path) -> tuple[str, str]:
    first = start_run(database, ["first-mutant"])
    save_result(database, "first-mutant", "killed", 1, 0.1)
    finish_run(database, first, "completed")
    second = start_run(database, ["second-mutant"])
    save_result(database, "second-mutant", "survived", 0, 0.1)
    finish_run(database, second, "completed")
    return first, second


def test_load_current_run_rejects_orphan_plan_after_latest_header_rollback(
    tmp_path: Path,
) -> None:
    database = tmp_path / "cache.db"
    _first, second = _two_completed_run_headers(database)
    with contextlib.closing(sqlite3.connect(database)) as connection:
        connection.execute("DELETE FROM mutation_run WHERE run_id = ?", (second,))
        connection.commit()

    with pytest.raises(CorruptCacheError, match="without a matching run header"):
        load_current_run(database)


def test_cicd_export_rejects_header_high_water_rollback_and_removes_stale_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    database = tmp_path / ".mutmut-cache" / "mutmut-cache.db"
    _first, second = _two_completed_run_headers(database)
    with contextlib.closing(sqlite3.connect(database)) as connection:
        connection.execute("DELETE FROM mutation_run_mutant WHERE run_id = ?", (second,))
        connection.execute("DELETE FROM mutation_run WHERE run_id = ?", (second,))
        connection.commit()
    artifact = tmp_path / "mutants" / "mutmut-cicd-stats.json"
    artifact.parent.mkdir()
    artifact.write_text('{"score": 100.0}', encoding="utf-8")

    rendered = CliRunner().invoke(cli, ["export-cicd-stats"])

    assert rendered.exit_code == 1
    assert "disagrees with high-water mark" in rendered.output
    assert not artifact.exists()


@pytest.mark.skipif(os.name != "posix", reason="POSIX permits replacing an open DB pathname")
def test_load_current_run_rejects_permanent_path_swap_after_final_query(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = tmp_path / "cache.db"
    _completed_two_mutant_run(database)
    replacement = tmp_path / "replacement.db"
    create_db(replacement)
    real_connect = sqlite3.connect
    swapped = False

    class SwappingConnection:
        def __init__(self, connection: sqlite3.Connection) -> None:
            self._connection = connection

        def execute(self, sql: str, *args: object) -> sqlite3.Cursor:
            nonlocal swapped
            cursor = self._connection.execute(sql, *args)
            if not swapped and "SELECT ordinal, mutant_name" in sql:
                replacement.replace(database)
                swapped = True
            return cursor

        def close(self) -> None:
            self._connection.close()

        def __getattr__(self, name: str) -> object:
            return getattr(self._connection, name)

    def swapping_connect(path: object, *args: object, **kwargs: object) -> object:
        return SwappingConnection(real_connect(path, *args, **kwargs))  # type: ignore[arg-type]

    monkeypatch.setattr(sqlite3, "connect", swapping_connect)

    with pytest.raises(UnsafeWorkspaceStateError, match="changed identity"):
        load_current_run(database)
    assert swapped is True
