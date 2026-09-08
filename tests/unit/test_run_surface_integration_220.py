"""Integration pins for MW220-020/021 run locking and run identity."""

from __future__ import annotations

import contextlib
import hashlib
import os
import sqlite3
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner
from textual.widgets import DataTable, Static

import mutmut_win.stats as stats_module
from mutmut_win.browser import ResultBrowser
from mutmut_win.cli import cli
from mutmut_win.config import MutmutConfig
from mutmut_win.db import (
    DEFAULT_DB_PATH,
    finish_run,
    load_current_run,
    load_results,
    save_result,
    start_run,
    validate_cache_path,
)
from mutmut_win.exceptions import (
    AmbiguousMutantNameError,
    CleanTestFailedError,
    OrchestratorError,
    UnsafeWorkspaceStateError,
)
from mutmut_win.models import (
    MutationRunResult,
    MutationTask,
    SourceFileMutationData,
)
from mutmut_win.orchestrator import MutationOrchestrator
from mutmut_win.process.run_lock import (
    DatabaseRunLocks,
    RunLockHeldError,
    WorkspaceRunLock,
    run_lock_path_for_db,
)
from mutmut_win.stats import (
    RunBasisEvidence,
    build_run_basis_fingerprint,
    canonical_run_basis_config,
    save_cicd_stats,
)


def _orchestrator(tmp_path: Path) -> MutationOrchestrator:
    return MutationOrchestrator(
        MutmutConfig(),
        runner=MagicMock(),
        executor=MagicMock(),
        db_path=tmp_path / ".mutmut-cache" / "mutmut-cache.db",
    )


def _tasks(*names: str) -> list[MutationTask]:
    return [MutationTask(mutant_name=name) for name in names]


def test_interrupted_pipeline_persists_completed_and_pending_current_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    orchestrator = _orchestrator(tmp_path)

    def pipeline() -> MutationRunResult:
        orchestrator._start_current_run(_tasks("m1", "m2"))
        save_result(orchestrator._db_path, "m1", "killed", 1, 0.1)
        return MutationRunResult(
            total_mutants=2,
            killed=1,
            unchecked=1,
            was_interrupted=True,
        )

    monkeypatch.setattr(orchestrator, "_run_pipeline", pipeline)

    result = orchestrator.run()
    current = load_current_run(orchestrator._db_path)

    assert result.was_interrupted is True
    assert current is not None
    assert current.status == "interrupted"
    assert current.completed_names == ("m1",)
    assert current.pending_names == ("m2",)


def test_pipeline_exception_is_failed_without_masking_original(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    orchestrator = _orchestrator(tmp_path)

    def pipeline() -> MutationRunResult:
        orchestrator._start_current_run(_tasks("m1"))
        raise CleanTestFailedError("clean proof failed")

    monkeypatch.setattr(orchestrator, "_run_pipeline", pipeline)

    with pytest.raises(CleanTestFailedError, match="clean proof failed"):
        orchestrator.run()

    current = load_current_run(orchestrator._db_path)
    assert current is not None
    assert current.status == "failed"
    assert current.pending_names == ("m1",)


@pytest.mark.parametrize("finalize_plan", [False, True])
def test_keyboard_interrupt_is_persisted_as_interrupted_in_every_pipeline_phase(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    finalize_plan: bool,
) -> None:
    monkeypatch.chdir(tmp_path)
    orchestrator = _orchestrator(tmp_path)

    def pipeline() -> MutationRunResult:
        if finalize_plan:
            orchestrator._start_current_run(_tasks("m1", "m2"))
        raise KeyboardInterrupt

    monkeypatch.setattr(orchestrator, "_run_pipeline", pipeline)

    with pytest.raises(KeyboardInterrupt):
        orchestrator.run()

    current = load_current_run(orchestrator._db_path)
    assert current is not None
    assert current.status == "interrupted"
    assert current.plan_finalized is finalize_plan
    assert current.pending_names == (("m1", "m2") if finalize_plan else ())


def test_failure_before_generation_plan_replaces_old_completed_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    db_path = tmp_path / ".mutmut-cache" / "mutmut-cache.db"
    old_run_id = start_run(db_path, ["old-mutant"])
    save_result(db_path, "old-mutant", "survived", 0, 0.1)
    finish_run(db_path, old_run_id, "completed")
    artifact = tmp_path / "mutants" / "mutmut-cicd-stats.json"
    artifact.parent.mkdir()
    artifact.write_text('{"stale": true}\n', encoding="utf-8")
    orchestrator = _orchestrator(tmp_path)
    monkeypatch.setattr(
        orchestrator,
        "_run_pipeline",
        MagicMock(side_effect=OrchestratorError("generation failed before plan")),
    )

    with pytest.raises(OrchestratorError, match="generation failed before plan"):
        orchestrator.run()

    current = load_current_run(db_path)
    assert current is not None
    assert current.run_id != old_run_id
    assert current.status == "failed"
    assert current.plan_finalized is False
    assert current.planned_names == ()
    assert not artifact.exists()

    exported = CliRunner().invoke(cli, ["export-cicd-stats"])
    assert exported.exit_code == 1
    assert not artifact.exists()


def test_hard_exit_before_generation_plan_remains_visible_and_blocks_stale_export(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    db_path = tmp_path / ".mutmut-cache" / "mutmut-cache.db"
    artifact = tmp_path / "mutants" / "mutmut-cicd-stats.json"
    artifact.parent.mkdir()
    artifact.write_text('{"stale": true}\n', encoding="utf-8")
    script = "\n".join(
        [
            "import os, sys",
            "from pathlib import Path",
            "from mutmut_win.config import MutmutConfig",
            "from mutmut_win.orchestrator import MutationOrchestrator",
            "orchestrator = MutationOrchestrator(",
            "    MutmutConfig(), runner=object(), executor=object(), db_path=Path(sys.argv[1])",
            ")",
            "orchestrator._run_pipeline = lambda: os._exit(91)",
            "orchestrator.run()",
        ]
    )

    crashed = subprocess.run(  # noqa: S603 - current interpreter and fixed test script
        [sys.executable, "-c", script, str(db_path)],
        cwd=tmp_path,
        check=False,
    )

    assert crashed.returncode == 91
    current = load_current_run(db_path)
    assert current is not None
    assert current.status == "running"
    assert current.plan_finalized is False
    assert current.finished_at is None
    assert not artifact.exists()

    exported = CliRunner().invoke(cli, ["export-cicd-stats"])
    assert exported.exit_code == 1
    assert not artifact.exists()


def test_false_complete_is_downgraded_to_failed_and_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    orchestrator = _orchestrator(tmp_path)

    def pipeline() -> MutationRunResult:
        orchestrator._start_current_run(_tasks("m1", "m2"))
        save_result(orchestrator._db_path, "m1", "killed", 1, 0.1)
        return MutationRunResult(total_mutants=2, killed=1)

    monkeypatch.setattr(orchestrator, "_run_pipeline", pipeline)

    with pytest.raises(OrchestratorError, match="could not finalize"):
        orchestrator.run()

    current = load_current_run(orchestrator._db_path)
    assert current is not None
    assert current.status == "failed"
    assert current.pending_names == ("m2",)


def test_exclusive_takeover_closes_prior_hard_crash_before_new_plan(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    db_path = tmp_path / ".mutmut-cache" / "mutmut-cache.db"
    old_run_id = start_run(db_path, ["old-pending"])
    save_result(
        db_path,
        "old-pending",
        "killed",
        1,
        0.1,
        tests_fingerprint="f" * 64,
    )
    orchestrator = _orchestrator(tmp_path)

    def pipeline() -> MutationRunResult:
        orchestrator._start_current_run([])
        return MutationRunResult(total_mutants=0)

    monkeypatch.setattr(orchestrator, "_run_pipeline", pipeline)
    orchestrator.run()

    with contextlib.closing(sqlite3.connect(db_path)) as conn:
        rows = conn.execute("SELECT run_id, status FROM mutation_run ORDER BY sequence").fetchall()
    assert rows[0] == (old_run_id, "aborted")
    assert rows[1][1] == "aborted"
    [historical] = load_results(db_path)
    assert historical.tests_fingerprint is None


def test_force_cannot_delete_shared_state_while_workspace_lock_is_held(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    sentinel = tmp_path / "mutants" / "keep.txt"
    sentinel.parent.mkdir()
    sentinel.write_text("owned by active run", encoding="utf-8")

    with WorkspaceRunLock(run_lock_path_for_db(DEFAULT_DB_PATH)):
        result = CliRunner().invoke(cli, ["run", "--force"])

    assert result.exit_code == 1
    assert "workspace run lock is held" in result.output
    assert sentinel.read_text(encoding="utf-8") == "owned by active run"


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        (["apply", "some-mutant"], "workspace run lock is held"),
        (["export-cicd-stats"], "consistent state"),
    ],
)
def test_apply_and_export_share_the_canonical_database_lock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    command: list[str],
    expected: str,
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "mutants").mkdir()

    with WorkspaceRunLock(run_lock_path_for_db(DEFAULT_DB_PATH)):
        result = CliRunner().invoke(cli, command)

    assert result.exit_code == 1
    assert expected in result.output


def test_direct_api_and_custom_database_paths_use_one_workspace_lock_domain(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    db_path = tmp_path / "shared" / "cache.db"
    db_path.parent.mkdir()
    relative_alias = Path("shared") / "cache.db"
    different_db = tmp_path / "other-state" / "independent-cache.db"
    assert run_lock_path_for_db(relative_alias) == run_lock_path_for_db(db_path)
    assert run_lock_path_for_db(different_db) == run_lock_path_for_db(db_path)
    if os.name == "nt":
        default_db = tmp_path / ".mutmut-cache" / "cache.db"
        default_db.parent.mkdir()
        case_alias = tmp_path / ".MUTMUT-CACHE" / "cache.db"
        assert run_lock_path_for_db(default_db) == run_lock_path_for_db(case_alias)
    orchestrator = MutationOrchestrator(
        MutmutConfig(),
        runner=MagicMock(),
        executor=MagicMock(),
        db_path=db_path,
    )

    with (
        WorkspaceRunLock(run_lock_path_for_db(different_db)),
        pytest.raises(RunLockHeldError, match="workspace run lock is held"),
    ):
        orchestrator.run()

    assert not db_path.exists()


def test_shared_hardlink_database_is_rejected_without_foreign_run_invalidation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_a = tmp_path / "workspace-a"
    workspace_b = tmp_path / "workspace-b"
    workspace_a.mkdir()
    workspace_b.mkdir()
    database = workspace_a / "shared.db"
    run_id = start_run(database, ["still-running"])
    alias = workspace_b / "shared-alias.db"
    try:
        os.link(database, alias)
    except OSError as exc:
        pytest.skip(f"hard links are unavailable on this filesystem: {exc}")

    monkeypatch.chdir(workspace_a)
    with (
        WorkspaceRunLock(run_lock_path_for_db(database)),
        DatabaseRunLocks(database),
    ):
        monkeypatch.chdir(workspace_b)
        contender = MutationOrchestrator(
            MutmutConfig(),
            runner=MagicMock(),
            executor=MagicMock(),
            db_path=alias,
        )
        with pytest.raises(UnsafeWorkspaceStateError, match="hardlink"):
            contender.run()

        alias.unlink()
        current = load_current_run(database)
        assert current is not None
        assert current.run_id == run_id
        assert current.status == "running"

    finish_run(database, run_id, "aborted")


@pytest.mark.skipif(os.name != "nt", reason="Windows Junction regression")
def test_force_refuses_junction_root_without_touching_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "junction-target"
    target.mkdir()
    sentinel = target / "valuable.txt"
    sentinel.write_text("must survive", encoding="utf-8")
    junction = tmp_path / ".mutmut-cache"
    cmd_executable = Path(os.environ.get("COMSPEC", r"C:\Windows\System32\cmd.exe"))
    created = subprocess.run(  # noqa: S603 - cmd builtin creates the test Junction
        [cmd_executable, "/d", "/u", "/c", "mklink", "/J", str(junction), str(target)],
        capture_output=True,
        encoding="utf-16-le",
        errors="replace",
        check=False,
    )
    if created.returncode != 0:
        pytest.skip(f"could not create Junction: {created.stdout}{created.stderr}")

    try:
        assert run_lock_path_for_db(junction / "mutmut-cache.db") == run_lock_path_for_db(
            target / "mutmut-cache.db"
        )
        result = CliRunner().invoke(cli, ["run", "--force"])
        sentinel_content = sentinel.read_text(encoding="utf-8")
        target_lock_artifacts = list(target.glob(".mutmut-win-*.run.lock*"))
    finally:
        # Remove the Junction itself, never its target, so tmp_path cleanup is unambiguous.
        if junction.exists() and junction.is_junction():
            junction.rmdir()

    assert result.exit_code == 1
    assert "Refusing --force cleanup" in result.output
    assert sentinel_content == "must survive"
    assert target_lock_artifacts == []


@pytest.mark.skipif(os.name != "nt", reason="Windows Junction regression")
@pytest.mark.parametrize("root_name", [".mutmut-cache", "mutants"])
@pytest.mark.parametrize(
    "command",
    [
        ["run"],
        ["apply", "pkg.mod.x_f__mutmut_1"],
        ["export-cicd-stats"],
    ],
)
def test_state_commands_refuse_redirected_roots_before_lock_or_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    root_name: str,
    command: list[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    target = tmp_path / f"{root_name.strip('.')}-target"
    target.mkdir()
    sentinel = target / "valuable.txt"
    sentinel.write_text("must survive", encoding="utf-8")
    junction = tmp_path / root_name
    cmd_executable = Path(os.environ.get("COMSPEC", r"C:\Windows\System32\cmd.exe"))
    created = subprocess.run(  # noqa: S603 - cmd builtin creates the test Junction
        [cmd_executable, "/d", "/u", "/c", "mklink", "/J", str(junction), str(target)],
        capture_output=True,
        encoding="utf-16-le",
        errors="replace",
        check=False,
    )
    if created.returncode != 0:
        pytest.skip(f"could not create Junction: {created.stdout}{created.stderr}")

    try:
        result = CliRunner().invoke(cli, command)
        target_entries = sorted(path.name for path in target.iterdir())
        workspace_lock_artifacts = list(tmp_path.glob(".mutmut-win-*.run.lock*"))
    finally:
        # Remove the Junction itself, never its target.
        if junction.exists() and junction.is_junction():
            junction.rmdir()

    assert result.exit_code == 1
    assert "Refusing workspace state access" in result.output
    assert sentinel.read_text(encoding="utf-8") == "must survive"
    assert target_entries == ["valuable.txt"]
    assert workspace_lock_artifacts == []


@pytest.mark.skipif(os.name != "nt", reason="Windows Junction regression")
def test_snapshot_loader_refuses_redirected_cache_before_schema_migration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "cache-target"
    target.mkdir()
    external_db = target / "mutmut-cache.db"
    with contextlib.closing(sqlite3.connect(external_db)) as conn:
        conn.execute(
            "CREATE TABLE mutant ("
            "mutant_name TEXT PRIMARY KEY, status TEXT NOT NULL, "
            "exit_code INTEGER, duration REAL)"
        )
        conn.commit()
    junction = tmp_path / ".mutmut-cache"
    cmd_executable = Path(os.environ.get("COMSPEC", r"C:\Windows\System32\cmd.exe"))
    created = subprocess.run(  # noqa: S603 - cmd builtin creates the test Junction
        [cmd_executable, "/d", "/u", "/c", "mklink", "/J", str(junction), str(target)],
        capture_output=True,
        encoding="utf-16-le",
        errors="replace",
        check=False,
    )
    if created.returncode != 0:
        pytest.skip(f"could not create Junction: {created.stdout}{created.stderr}")

    try:
        with pytest.raises(UnsafeWorkspaceStateError, match="Refusing workspace state access"):
            load_current_run(DEFAULT_DB_PATH)
        result = CliRunner().invoke(cli, ["results"])
        with contextlib.closing(sqlite3.connect(external_db)) as conn:
            columns = {row[1] for row in conn.execute("PRAGMA table_info(mutant)").fetchall()}
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }
    finally:
        if junction.exists() and junction.is_junction():
            junction.rmdir()

    assert result.exit_code == 1
    assert "Refusing workspace state access" in result.output
    assert columns == {"mutant_name", "status", "exit_code", "duration"}
    assert tables == {"mutant"}


@pytest.mark.parametrize(
    "cache_name",
    ["mutmut-cache.db", "mutmut-cache.db-journal", "mutmut-cache.db-wal"],
)
def test_default_cache_rejects_hardlinked_database_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    cache_name: str,
) -> None:
    monkeypatch.chdir(tmp_path)
    cache_root = tmp_path / ".mutmut-cache"
    cache_root.mkdir()
    external = tmp_path / f"external-{cache_name}"
    external.write_bytes(b"valuable external bytes")
    os.link(external, cache_root / cache_name)

    with pytest.raises(UnsafeWorkspaceStateError, match="hardlink"):
        validate_cache_path(DEFAULT_DB_PATH)

    assert external.read_bytes() == b"valuable external bytes"


def test_default_cache_rejects_database_file_symlink_when_supported(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    cache_root = tmp_path / ".mutmut-cache"
    cache_root.mkdir()
    external = tmp_path / "external.db"
    external.write_bytes(b"valuable external bytes")
    linked = cache_root / "mutmut-cache.db"
    try:
        linked.symlink_to(external)
    except OSError as exc:
        pytest.skip(f"file symlink unavailable: {exc}")

    with pytest.raises(UnsafeWorkspaceStateError, match="link"):
        validate_cache_path(DEFAULT_DB_PATH)

    assert external.read_bytes() == b"valuable external bytes"


@pytest.mark.parametrize(
    "command",
    [
        ["run"],
        ["apply", "pkg.mod.x_f__mutmut_1"],
        ["export-cicd-stats"],
    ],
)
def test_cli_rejects_database_symlink_before_deriving_external_lock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    command: list[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    cache_root = tmp_path / ".mutmut-cache"
    cache_root.mkdir()
    (tmp_path / "mutants").mkdir()
    external_root = tmp_path.parent / f"{tmp_path.name}-external-cache"
    external_root.mkdir()
    external_db = external_root / "external.db"
    external_db.write_bytes(b"valuable external bytes")
    linked_db = cache_root / "mutmut-cache.db"
    try:
        linked_db.symlink_to(external_db)
    except OSError as exc:
        external_db.unlink()
        external_root.rmdir()
        pytest.skip(f"file symlink unavailable: {exc}")

    try:
        result = CliRunner().invoke(cli, command)
        external_lock_artifacts = list(external_root.glob(".mutmut-win-*.run.lock*"))
        external_bytes = external_db.read_bytes()
    finally:
        with contextlib.suppress(FileNotFoundError):
            linked_db.unlink()
        for artifact in external_root.glob(".mutmut-win-*.run.lock*"):
            artifact.unlink()
        external_db.unlink()
        external_root.rmdir()

    assert result.exit_code == 1
    assert "link" in result.output.lower()
    assert external_lock_artifacts == []
    assert external_bytes == b"valuable external bytes"


def test_direct_orchestrator_validates_default_cache_before_lock_derivation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    cache_root = tmp_path / ".mutmut-cache"
    cache_root.mkdir()
    external = tmp_path / "external.db"
    external.write_bytes(b"valuable external bytes")
    os.link(external, cache_root / "mutmut-cache.db")

    with pytest.raises(UnsafeWorkspaceStateError, match="hardlink"):
        _orchestrator(tmp_path).run()

    assert external.read_bytes() == b"valuable external bytes"
    assert list(tmp_path.glob(".mutmut-win-*.run.lock*")) == []


def test_empty_read_only_results_does_not_create_cache_or_lock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(cli, ["results"])

    assert result.exit_code == 0
    assert "No results found" in result.output
    assert not (tmp_path / ".mutmut-cache").exists()
    assert list(tmp_path.glob(".mutmut-win-*.run.lock*")) == []


def _persist_verified_completed_run(tmp_path: Path) -> tuple[Path, MutmutConfig]:
    source = tmp_path / "src" / "module.py"
    test_file = tmp_path / "tests" / "test_module.py"
    source.parent.mkdir(exist_ok=True)
    test_file.parent.mkdir(exist_ok=True)
    source.write_text("def value():\n    return 1\n", encoding="utf-8")
    test_file.write_text("def test_value():\n    assert True\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        '[tool.mutmut]\npaths_to_mutate = ["src"]\ntests_dir = ["tests"]\n',
        encoding="utf-8",
    )
    config = MutmutConfig(paths_to_mutate=["src"], tests_dir=["tests"])
    (tmp_path / "mutants").mkdir()
    db_path = tmp_path / ".mutmut-cache" / "mutmut-cache.db"
    database = db_path.absolute()
    excluded = (
        database,
        Path(f"{database}-journal"),
        Path(f"{database}-wal"),
        Path(f"{database}-shm"),
    )
    fingerprint = build_run_basis_fingerprint(config, excluded_paths=excluded)
    run_id = start_run(
        db_path,
        ["pkg.module.x_value__mutmut_1"],
        basis_fingerprint=fingerprint,
        basis_config_json=canonical_run_basis_config(config),
        is_full_run=True,
    )
    save_result(db_path, "pkg.module.x_value__mutmut_1", "killed", 1, 0.1)
    finish_run(db_path, run_id, "completed")
    return db_path, config


@pytest.mark.parametrize(
    ("relative_path", "replacement"),
    [
        ("src/module.py", "def value():\n    return 2\n"),
        ("tests/test_module.py", "def test_value():\n    assert False\n"),
        ("pyproject.toml", '[tool.mutmut]\npaths_to_mutate = ["other"]\n'),
    ],
)
def test_cicd_export_requires_live_source_test_and_config_basis(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    relative_path: str,
    replacement: str,
) -> None:
    monkeypatch.chdir(tmp_path)
    _persist_verified_completed_run(tmp_path)

    initial = CliRunner().invoke(cli, ["export-cicd-stats"])
    artifact = tmp_path / "mutants" / "mutmut-cicd-stats.json"
    assert initial.exit_code == 0, initial.output
    assert artifact.is_file()

    (tmp_path / relative_path).write_text(replacement, encoding="utf-8")
    stale = CliRunner().invoke(cli, ["export-cicd-stats"])

    assert stale.exit_code == 1
    assert "inputs changed since the latest mutation run" in stale.output, stale.output
    assert not artifact.exists()


def test_modern_completed_run_without_basis_cannot_authorize_cicd_export(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    db_path = tmp_path / ".mutmut-cache" / "mutmut-cache.db"
    run_id = start_run(db_path, ["m1"])
    save_result(db_path, "m1", "killed", 1, 0.1)
    finish_run(db_path, run_id, "completed")
    artifact = tmp_path / "mutants" / "mutmut-cicd-stats.json"
    artifact.parent.mkdir()
    artifact.write_text('{"stale": true}\n', encoding="utf-8")

    exported = CliRunner().invoke(cli, ["export-cicd-stats"])

    assert exported.exit_code == 1
    assert "predates verifiable source/test/config evidence" in exported.output
    assert not artifact.exists()


def test_initial_run_basis_must_be_a_stable_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    orchestrator = _orchestrator(tmp_path)

    with (
        patch(
            "mutmut_win.orchestrator.build_run_basis_evidence",
            side_effect=[
                RunBasisEvidence("a" * 64, True),
                RunBasisEvidence("b" * 64, True),
            ],
        ),
        pytest.raises(OrchestratorError, match="changed while their run basis"),
    ):
        orchestrator.run()

    assert load_current_run(orchestrator._db_path) is None


def test_initial_ambient_basis_instability_runs_without_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    orchestrator = _orchestrator(tmp_path)
    first = RunBasisEvidence("a" * 64, True, "c" * 64, True)
    second = RunBasisEvidence("b" * 64, True, "c" * 64, True)

    def pipeline() -> MutationRunResult:
        orchestrator._start_current_run(_tasks("m1"))
        save_result(
            orchestrator._db_path,
            "m1",
            "killed",
            1,
            0.1,
            tests_fingerprint="f" * 64,
        )
        return MutationRunResult(total_mutants=1, killed=1)

    monkeypatch.setattr(orchestrator, "_run_pipeline", pipeline)
    with patch(
        "mutmut_win.orchestrator.build_run_basis_evidence",
        side_effect=[first, second, second, second],
    ):
        result = orchestrator.run()

    current = load_current_run(orchestrator._db_path)
    assert current is not None
    assert current.status == "completed"
    assert current.basis_fingerprint is None
    assert current.basis_config_json is None
    assert current.evidence_invalidated is True
    assert result.execution_basis_complete is False
    [historical] = load_results(orchestrator._db_path)
    assert historical.tests_fingerprint is None


def test_pipeline_sys_path_mutation_is_restored_before_completion_basis(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    orchestrator = _orchestrator(tmp_path)
    original = sys.path.copy()
    observed: list[tuple[str, ...]] = []

    def evidence(*_args: object, **_kwargs: object) -> RunBasisEvidence:
        observed.append(tuple(sys.path))
        return RunBasisEvidence("a" * 64, True)

    def pipeline() -> MutationRunResult:
        sys.path.insert(0, str(tmp_path / "mutants"))
        orchestrator._start_current_run(_tasks("m1"))
        save_result(orchestrator._db_path, "m1", "killed", 1, 0.1)
        return MutationRunResult(total_mutants=1, killed=1)

    monkeypatch.setattr("mutmut_win.orchestrator.build_run_basis_evidence", evidence)
    monkeypatch.setattr(orchestrator, "_run_pipeline", pipeline)

    result = orchestrator.run()

    assert sys.path == original
    assert observed == [tuple(original)] * 4
    assert result.execution_basis_complete is True


def test_incomplete_execution_basis_runs_without_reuse_but_cannot_authorize_export(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    orchestrator = _orchestrator(tmp_path)

    def pipeline() -> MutationRunResult:
        orchestrator._start_current_run(_tasks("m1"))
        save_result(
            orchestrator._db_path,
            "m1",
            "killed",
            1,
            0.1,
            tests_fingerprint="f" * 64,
        )
        return MutationRunResult(total_mutants=1, killed=1)

    monkeypatch.setattr(
        "mutmut_win.orchestrator.build_run_basis_evidence",
        lambda *_args, **_kwargs: RunBasisEvidence("a" * 64, False),
    )
    monkeypatch.setattr(orchestrator, "_run_pipeline", pipeline)

    result = orchestrator.run()

    current = load_current_run(orchestrator._db_path)
    assert current is not None
    assert current.status == "completed"
    assert current.basis_fingerprint is None
    assert current.basis_config_json is None
    assert result.execution_basis_complete is False
    exported = CliRunner().invoke(cli, ["export-cicd-stats"])
    assert exported.exit_code == 1
    assert "evidence was invalidated" in exported.output


def test_mid_run_source_drift_is_recorded_failed_not_completed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    source = tmp_path / "src" / "module.py"
    tests = tmp_path / "tests"
    source.parent.mkdir()
    tests.mkdir()
    source.write_text("def value():\n    return 1\n", encoding="utf-8")
    (tests / "test_module.py").write_text("def test_value():\n    assert True\n", encoding="utf-8")
    orchestrator = _orchestrator(tmp_path)

    def pipeline() -> MutationRunResult:
        orchestrator._start_current_run(_tasks("m1"))
        save_result(orchestrator._db_path, "m1", "killed", 1, 0.1)
        source.write_text("def value():\n    return 2\n", encoding="utf-8")
        return MutationRunResult(total_mutants=1, killed=1)

    monkeypatch.setattr(orchestrator, "_run_pipeline", pipeline)

    with pytest.raises(OrchestratorError, match="changed during the mutation run"):
        orchestrator.run()

    current = load_current_run(orchestrator._db_path)
    assert current is not None
    assert current.status == "failed"
    [historical] = load_results(orchestrator._db_path)
    assert historical.tests_fingerprint is None


def test_mid_run_ambient_drift_preserves_results_without_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    orchestrator = _orchestrator(tmp_path)
    initial = RunBasisEvidence("a" * 64, True, "c" * 64, True)
    ambient_changed = RunBasisEvidence("b" * 64, True, "c" * 64, True)

    def pipeline() -> MutationRunResult:
        orchestrator._start_current_run(_tasks("m1"))
        save_result(
            orchestrator._db_path,
            "m1",
            "killed",
            1,
            0.1,
            tests_fingerprint="f" * 64,
        )
        return MutationRunResult(total_mutants=1, killed=1)

    monkeypatch.setattr(orchestrator, "_run_pipeline", pipeline)
    with patch(
        "mutmut_win.orchestrator.build_run_basis_evidence",
        side_effect=[initial, initial, ambient_changed, ambient_changed],
    ):
        result = orchestrator.run()

    current = load_current_run(orchestrator._db_path)
    assert current is not None
    assert current.status == "completed"
    assert current.evidence_invalidated is True
    assert current.basis_fingerprint is None
    assert current.basis_config_json is None
    assert result.execution_basis_complete is False
    [current_result] = current.completed_results
    assert current_result.tests_fingerprint is None
    [historical] = load_results(orchestrator._db_path)
    assert historical.tests_fingerprint is None
    exported = CliRunner().invoke(cli, ["export-cicd-stats"])
    assert exported.exit_code == 1
    assert "evidence was invalidated" in exported.output


def test_ambient_deauthorization_failure_leaves_run_recoverable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    orchestrator = _orchestrator(tmp_path)
    initial = RunBasisEvidence("a" * 64, True, "c" * 64, True)
    ambient_changed = RunBasisEvidence("b" * 64, True, "c" * 64, True)

    def pipeline() -> MutationRunResult:
        orchestrator._start_current_run(_tasks("m1"))
        save_result(
            orchestrator._db_path,
            "m1",
            "killed",
            1,
            0.1,
            tests_fingerprint="f" * 64,
        )
        return MutationRunResult(total_mutants=1, killed=1)

    monkeypatch.setattr(orchestrator, "_run_pipeline", pipeline)
    with (
        patch(
            "mutmut_win.orchestrator.build_run_basis_evidence",
            side_effect=[initial, initial, ambient_changed, ambient_changed],
        ),
        patch(
            "mutmut_win.orchestrator.deauthorize_active_run_evidence",
            side_effect=sqlite3.OperationalError("deauthorization unavailable"),
        ),
        pytest.raises(OrchestratorError, match="remains running for revoke-first recovery"),
    ):
        orchestrator.run()

    current = load_current_run(orchestrator._db_path)
    assert current is not None
    assert current.status == "running"


def test_revocation_failure_leaves_run_recoverable_instead_of_terminal_poison(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    orchestrator = _orchestrator(tmp_path)
    monkeypatch.setattr(
        "mutmut_win.orchestrator.build_run_basis_evidence",
        lambda *_args, **_kwargs: RunBasisEvidence("a" * 64, True),
    )

    def failing_pipeline() -> MutationRunResult:
        orchestrator._start_current_run(_tasks("m1"))
        save_result(
            orchestrator._db_path,
            "m1",
            "killed",
            1,
            0.1,
            tests_fingerprint="f" * 64,
        )
        raise OrchestratorError("late pipeline failure")

    monkeypatch.setattr(orchestrator, "_run_pipeline", failing_pipeline)
    with (
        patch(
            "mutmut_win.orchestrator.invalidate_cached_reuse_for_run",
            side_effect=sqlite3.OperationalError("revocation unavailable"),
        ),
        pytest.raises(OrchestratorError, match="late pipeline failure"),
    ):
        orchestrator.run()

    abandoned = load_current_run(orchestrator._db_path)
    assert abandoned is not None
    assert abandoned.status == "running"
    [temporarily_poisoned] = load_results(orchestrator._db_path)
    assert temporarily_poisoned.tests_fingerprint == "f" * 64

    successor = _orchestrator(tmp_path)

    def empty_pipeline() -> MutationRunResult:
        successor._start_current_run([])
        return MutationRunResult(total_mutants=0)

    monkeypatch.setattr(successor, "_run_pipeline", empty_pipeline)
    successor.run()

    [recovered] = load_results(orchestrator._db_path)
    assert recovered.tests_fingerprint is None


def test_successful_apply_invalidates_latest_run_and_removes_export_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    db_path = tmp_path / ".mutmut-cache" / "mutmut-cache.db"
    run_id = start_run(db_path, ["pkg.mod.x_f__mutmut_1"])
    save_result(db_path, "pkg.mod.x_f__mutmut_1", "survived", 0, 0.1)
    finish_run(db_path, run_id, "completed")
    artifact = tmp_path / "mutants" / "mutmut-cicd-stats.json"
    artifact.parent.mkdir()
    artifact.write_text('{"stale": true}\n', encoding="utf-8")

    with (
        patch("mutmut_win.cli.load_config", return_value=MutmutConfig()),
        patch(
            "mutmut_win.cli.resolve_mutant",
            return_value=("pkg.mod.x_f__mutmut_1", MagicMock()),
        ),
        patch("mutmut_win.cli.apply_mutant") as apply_mock,
    ):
        applied = CliRunner().invoke(cli, ["apply", "pkg.mod.x_f__mutmut_1"])

    current = load_current_run(db_path)
    exported = CliRunner().invoke(cli, ["export-cicd-stats"])

    assert applied.exit_code == 0
    apply_mock.assert_called_once()
    assert current is not None
    assert current.status == "completed"
    assert current.evidence_invalidated is True
    assert not artifact.exists()
    assert exported.exit_code == 1
    assert "evidence was invalidated" in exported.output


def test_apply_purges_legacy_evidence_before_source_change_and_export_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    db_path = tmp_path / ".mutmut-cache" / "mutmut-cache.db"
    mutant_name = "pkg.mod.x_f__mutmut_1"
    save_result(db_path, mutant_name, "killed", 1, 0.1)
    mutants_dir = tmp_path / "mutants"
    mutants_dir.mkdir()

    # A database predating run identity has no mutation_run row. Historical
    # rows remain visible to diagnostic commands, but can never authorize a
    # CI gate because no source/test/config basis was persisted with them.
    before_apply = CliRunner().invoke(cli, ["export-cicd-stats"])
    artifact = mutants_dir / "mutmut-cicd-stats.json"
    assert before_apply.exit_code == 1
    assert "Legacy mutation results have no verifiable run basis" in before_apply.output
    assert not artifact.exists()
    assert load_current_run(db_path) is None

    def source_change(_mutant_name: str, _config: MutmutConfig) -> None:
        # The authority must already be gone when the irreversible source
        # operation begins, not merely cleaned up after it succeeds.
        assert load_results(db_path) == []
        assert not artifact.exists()

    with (
        patch("mutmut_win.cli.load_config", return_value=MutmutConfig()),
        patch("mutmut_win.cli.resolve_mutant", return_value=(mutant_name, MagicMock())),
        patch("mutmut_win.cli.apply_mutant", side_effect=source_change) as apply_mock,
    ):
        applied = CliRunner().invoke(cli, ["apply", mutant_name])

    after_apply = CliRunner().invoke(cli, ["export-cicd-stats"])

    assert applied.exit_code == 0
    apply_mock.assert_called_once()
    assert load_current_run(db_path) is None
    assert load_results(db_path) == []
    assert after_apply.exit_code == 1
    assert "No results found" in after_apply.output
    assert not artifact.exists()


def test_failed_apply_conservatively_invalidates_evidence_and_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    db_path = tmp_path / ".mutmut-cache" / "mutmut-cache.db"
    run_id = start_run(db_path, ["pkg.mod.x_f__mutmut_1"])
    save_result(db_path, "pkg.mod.x_f__mutmut_1", "survived", 0, 0.1)
    finish_run(db_path, run_id, "completed")
    artifact = tmp_path / "mutants" / "mutmut-cicd-stats.json"
    artifact.parent.mkdir()
    artifact.write_text('{"trusted": true}\n', encoding="utf-8")

    with (
        patch("mutmut_win.cli.load_config", return_value=MutmutConfig()),
        patch(
            "mutmut_win.cli.resolve_mutant",
            return_value=("pkg.mod.x_f__mutmut_1", MagicMock()),
        ),
        patch(
            "mutmut_win.cli.apply_mutant",
            side_effect=FileNotFoundError("mutant missing"),
        ),
    ):
        applied = CliRunner().invoke(cli, ["apply", "pkg.mod.x_f__mutmut_1"])

    current = load_current_run(db_path)
    assert applied.exit_code == 1
    assert current is not None
    assert current.evidence_invalidated is True
    assert not artifact.exists()


@pytest.mark.parametrize(
    "resolution_error",
    [
        FileNotFoundError("mutant missing"),
        AmbiguousMutantNameError("pattern matches two mutants"),
    ],
)
def test_unresolved_apply_preserves_run_evidence_and_ci_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    resolution_error: Exception,
) -> None:
    monkeypatch.chdir(tmp_path)
    db_path = tmp_path / ".mutmut-cache" / "mutmut-cache.db"
    run_id = start_run(
        db_path,
        ["pkg.mod.x_f__mutmut_1"],
        basis_fingerprint="a" * 64,
        basis_config_json=canonical_run_basis_config(MutmutConfig()),
        is_full_run=True,
    )
    save_result(db_path, "pkg.mod.x_f__mutmut_1", "survived", 0, 0.1)
    finish_run(db_path, run_id, "completed")
    artifact = tmp_path / "mutants" / "mutmut-cicd-stats.json"
    artifact.parent.mkdir()
    artifact.write_text('{"trusted": true}\n', encoding="utf-8")

    with (
        patch("mutmut_win.cli.load_config", return_value=MutmutConfig()),
        patch("mutmut_win.cli.resolve_mutant", side_effect=resolution_error),
        patch("mutmut_win.cli.invalidate_latest_run_evidence") as invalidate,
        patch("mutmut_win.cli.apply_mutant") as apply_mock,
    ):
        applied = CliRunner().invoke(cli, ["apply", "pkg.mod.*"])

    current = load_current_run(db_path)
    assert applied.exit_code == 1
    assert current is not None
    assert current.evidence_invalidated is False
    assert artifact.read_text(encoding="utf-8") == '{"trusted": true}\n'
    invalidate.assert_not_called()
    apply_mock.assert_not_called()


def test_apply_does_not_touch_source_when_evidence_invalidation_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    artifact = tmp_path / "mutants" / "mutmut-cicd-stats.json"
    artifact.parent.mkdir()
    artifact.write_text('{"trusted": true}\n', encoding="utf-8")

    with (
        patch("mutmut_win.cli.load_config", return_value=MutmutConfig()),
        patch(
            "mutmut_win.cli.resolve_mutant",
            return_value=("pkg.mod.x_f__mutmut_1", MagicMock()),
        ),
        patch(
            "mutmut_win.cli.invalidate_latest_run_evidence",
            side_effect=UnsafeWorkspaceStateError("database unavailable"),
        ),
        patch("mutmut_win.cli.apply_mutant") as apply_mock,
    ):
        applied = CliRunner().invoke(cli, ["apply", "pkg.mod.x_f__mutmut_1"])

    assert applied.exit_code == 1
    assert "database unavailable" in applied.output
    apply_mock.assert_not_called()
    assert artifact.read_text(encoding="utf-8") == '{"trusted": true}\n'


def test_results_and_export_use_current_run_not_historical_cache(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    db_path = tmp_path / ".mutmut-cache" / "mutmut-cache.db"
    save_result(db_path, "historic", "survived", 0, 0.2)
    start_run(db_path, ["m1", "m2"])
    save_result(db_path, "m1", "killed", 1, 0.1)

    displayed = CliRunner().invoke(cli, ["results", "--all"])
    exported = CliRunner().invoke(cli, ["export-cicd-stats"])

    assert displayed.exit_code == 0
    assert "Run status: running (1 completed, 1 pending" in displayed.output
    assert "m1: killed" in displayed.output
    assert "m2: not checked" in displayed.output
    assert "historic" not in displayed.output
    assert exported.exit_code == 1
    assert "CI/CD export failed closed" in exported.output


def test_browser_overlays_current_snapshot_on_stale_meta(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    db_path = tmp_path / ".mutmut-cache" / "mutmut-cache.db"
    generated = tmp_path / "mutants" / "src" / "mod.py"
    generated.parent.mkdir(parents=True)
    generated.write_text("def value():\n    return 1\n", encoding="utf-8")
    sfd = SourceFileMutationData(
        path="src/mod.py",
        exit_code_by_key={"historic": 0, "m1": 0, "m2": 1},
        source_hash="a" * 64,
        generation_fingerprint="b" * 64,
        generated_hash=hashlib.sha256(generated.read_bytes()).hexdigest(),
    )
    sfd.save()
    save_result(db_path, "historic", "survived", 0, 0.2)
    run_id = start_run(db_path, ["m1", "m2"])
    save_result(db_path, "m1", "killed", 1, 0.1)

    app = ResultBrowser(db_path=db_path)
    app._read_data()

    assert set(app._db_results) == {"m1", "m2"}
    assert app._db_results["m1"].status == "killed"
    assert app._db_results["m2"].status == "not checked"
    [(_loaded_path, (_loaded_sfd, counts))] = app._source_data.items()
    assert counts == {"killed": 1, "not checked": 1}
    assert app._unmapped_current_names == set()

    # Keep the DB transition valid for test cleanup/readers that inspect it.
    finish_run(db_path, run_id, "aborted")


def test_browser_keeps_partial_metadata_and_surfaces_unmapped_current_names(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    db_path = tmp_path / ".mutmut-cache" / "mutmut-cache.db"
    generated = tmp_path / "mutants" / "src" / "partial.py"
    generated.parent.mkdir(parents=True)
    generated.write_text("def value():\n    return 1\n", encoding="utf-8")
    SourceFileMutationData(
        path="src/partial.py",
        exit_code_by_key={"m1": 0, "historic": 0},
        source_hash="a" * 64,
        generation_fingerprint="b" * 64,
        generated_hash=hashlib.sha256(generated.read_bytes()).hexdigest(),
    ).save()
    run_id = start_run(db_path, ["m1", "m2"])
    save_result(db_path, "m1", "survived", 0, 0.1)

    app = ResultBrowser(db_path=db_path)
    app._read_data()

    assert set(app._db_results) == {"m1", "m2"}
    assert {Path(path) for path in app._source_data} == {Path("src/partial.py")}
    assert app._unmapped_current_names == {"m2"}
    finish_run(db_path, run_id, "aborted")


@pytest.mark.asyncio
async def test_browser_all_missing_metadata_has_one_row_and_run_status(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    db_path = tmp_path / ".mutmut-cache" / "mutmut-cache.db"
    run_id = start_run(db_path, ["m1", "m2"])
    save_result(db_path, "m1", "killed", 1, 0.1)
    finish_run(db_path, run_id, "interrupted")
    app = ResultBrowser(db_path=db_path)

    async with app.run_test():
        files = app.query_one("#files", DataTable)
        banner = app.query_one("#run_status", Static)
        assert files.row_count == 1
        assert {key.value for key in files.rows} == {"__unmapped__"}
        assert str(files.get_row("__unmapped__")[0]) == "(metadata missing)"
        rendered_status = str(banner.render())
        assert "status=interrupted" in rendered_status
        assert "completed=1/2" in rendered_status
        assert "pending=1" in rendered_status


def test_atomic_cicd_export_preserves_previous_artifact_on_write_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mutants_dir = tmp_path / "mutants"
    mutants_dir.mkdir()
    artifact = mutants_dir / "mutmut-cicd-stats.json"
    original = b'{"trusted": true}\n'
    artifact.write_bytes(original)

    def fail_serialization(_payload: object, *, indent: int) -> str:
        del indent
        raise OSError("simulated CI artifact write failure")

    monkeypatch.setattr(stats_module.json, "dumps", fail_serialization)

    with pytest.raises(OSError, match="simulated CI artifact write failure"):
        save_cicd_stats([("m1", "killed")], mutants_dir)

    assert artifact.read_bytes() == original
    assert list(mutants_dir.glob(".mutmut-cicd-stats.json.*.tmp")) == []
