"""Unit tests for the crash-recoverable workspace run lock."""

from __future__ import annotations

import hashlib
import json
import os
import socket
import subprocess
from dataclasses import asdict, replace
from pathlib import Path

import psutil
import pytest

import mutmut_win.atomic_file as atomic_file_module
import mutmut_win.process.run_lock as run_lock_module
from mutmut_win.process.run_lock import (
    DatabaseRunLocks,
    RunLockCorruptError,
    RunLockHeldError,
    RunLockUnverifiableError,
    WorkspaceRunLock,
    database_lock_paths_for_db,
    run_lock_path_for_db,
)


def _write_owner(path: Path, owner: run_lock_module.RunLockOwner) -> None:
    path.write_text(json.dumps(asdict(owner)), encoding="utf-8")


def _symlink_file_or_skip(link: Path, target: Path) -> None:
    try:
        link.symlink_to(target)
    except OSError as exc:
        pytest.skip(f"file symlinks are unavailable on this host: {exc}")


def test_context_publishes_pid_and_start_time_then_cleans_owner_file(tmp_path: Path) -> None:
    path = tmp_path / ".mutmut-run.lock"
    lock = WorkspaceRunLock(path)

    with lock as acquired:
        assert acquired is lock
        assert lock.acquired is True
        assert lock.owner is not None
        assert lock.owner.pid == os.getpid()
        assert lock.owner.process_start_time == pytest.approx(
            psutil.Process(os.getpid()).create_time()
        )
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["state"] == "acquired"
        assert payload["pid"] == os.getpid()
        assert payload["process_start_time"] > 0

    assert lock.acquired is False
    assert lock.owner is None
    assert not path.exists()
    # The stable guard inode is intentionally retained to prevent two owners
    # from locking different inodes during an unlink/recreate race.
    assert lock.guard_path.is_file()


def test_context_releases_and_cleans_up_when_body_raises(tmp_path: Path) -> None:
    path = tmp_path / "run.lock"
    lock = WorkspaceRunLock(path)

    with pytest.raises(ValueError, match="body failed"), lock:
        raise ValueError("body failed")

    assert lock.acquired is False
    assert not path.exists()
    with WorkspaceRunLock(path):
        assert path.is_file()


def test_cleanup_is_bound_to_absolute_path_when_cwd_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "workspace"
    elsewhere = tmp_path / "elsewhere"
    workspace.mkdir()
    elsewhere.mkdir()
    monkeypatch.chdir(workspace)
    lock = WorkspaceRunLock(Path("run.lock"))

    with lock:
        assert lock.path == workspace / "run.lock"
        monkeypatch.chdir(elsewhere)

    assert not (workspace / "run.lock").exists()
    assert not (elsewhere / "run.lock").exists()


def test_second_owner_is_rejected_with_pid_and_start_diagnostics(tmp_path: Path) -> None:
    path = tmp_path / "run.lock"
    first = WorkspaceRunLock(path)
    second = WorkspaceRunLock(path)

    with first, pytest.raises(RunLockHeldError) as exc_info:
        second.acquire()

    error = exc_info.value
    assert error.owner is not None
    assert error.owner.pid == os.getpid()
    assert error.owner.process_start_time > 0
    assert f"PID {os.getpid()}" in str(error)
    assert "process started" in str(error)


def test_dead_pid_record_is_safely_reclaimed(tmp_path: Path) -> None:
    path = tmp_path / "run.lock"
    dead_owner = replace(
        run_lock_module._current_owner(),
        pid=2_147_483_647,
        process_start_time=1.0,
    )
    _write_owner(path, dead_owner)

    with WorkspaceRunLock(path) as lock:
        assert lock.owner is not None
        assert lock.owner.pid == os.getpid()
        assert lock.owner.token != dead_owner.token

    assert not path.exists()


def test_reused_pid_with_different_start_time_proves_old_identity_dead(tmp_path: Path) -> None:
    path = tmp_path / "run.lock"
    current = run_lock_module._current_owner()
    reused_pid_owner = replace(
        current,
        process_start_time=current.process_start_time - 100.0,
    )
    _write_owner(path, reused_pid_owner)

    with WorkspaceRunLock(path) as lock:
        assert lock.owner is not None
        assert lock.owner.token != reused_pid_owner.token


def test_live_pid_metadata_is_not_taken_over_even_when_guard_is_free(tmp_path: Path) -> None:
    path = tmp_path / "run.lock"
    live_owner = run_lock_module._current_owner()
    _write_owner(path, live_owner)

    with pytest.raises(RunLockHeldError) as exc_info:
        WorkspaceRunLock(path).acquire()

    assert exc_info.value.owner == live_owner
    assert json.loads(path.read_text(encoding="utf-8"))["token"] == live_owner.token


def test_remote_host_pid_is_unverifiable_and_never_reclaimed(tmp_path: Path) -> None:
    path = tmp_path / "run.lock"
    remote_owner = replace(
        run_lock_module._current_owner(),
        hostname=f"not-{socket.gethostname()}",
    )
    _write_owner(path, remote_owner)

    with pytest.raises(RunLockUnverifiableError):
        WorkspaceRunLock(path).acquire()


def test_access_denied_owner_probe_is_never_guessed_stale(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "run.lock"
    owner = run_lock_module._current_owner()
    _write_owner(path, owner)

    def deny_access(pid: int) -> psutil.Process:
        raise psutil.AccessDenied(pid)

    monkeypatch.setattr(run_lock_module.psutil, "Process", deny_access)

    with pytest.raises(RunLockUnverifiableError):
        WorkspaceRunLock(path).acquire()


@pytest.mark.parametrize(
    "payload",
    [
        b"not json",
        b"{}",
        b"[]",
        b"",
        json.dumps(
            {
                "version": 1,
                "state": "acquired",
                "pid": True,
                "process_start_time": 1,
                "acquired_at": "now",
                "hostname": "host",
                "token": "token",
            }
        ).encode(),
    ],
)
def test_corrupt_or_ambiguous_owner_is_never_reclaimed(tmp_path: Path, payload: bytes) -> None:
    path = tmp_path / "run.lock"
    path.write_bytes(payload)

    with pytest.raises(RunLockCorruptError, match="automatic takeover refused"):
        WorkspaceRunLock(path).acquire()

    assert path.read_bytes() == payload


def test_release_is_idempotent(tmp_path: Path) -> None:
    lock = WorkspaceRunLock(tmp_path / "run.lock").acquire()
    lock.release()
    lock.release()
    assert lock.acquired is False


def test_missing_parent_is_not_created_implicitly(tmp_path: Path) -> None:
    lock = WorkspaceRunLock(tmp_path / "missing" / "run.lock")
    with pytest.raises(run_lock_module.RunLockError, match="parent directory does not exist"):
        lock.acquire()
    assert not (tmp_path / "missing").exists()


def test_owner_symlink_is_not_resolved_or_read(tmp_path: Path) -> None:
    external = tmp_path / "external-owner.txt"
    external_payload = b"external owner bytes must stay untouched"
    external.write_bytes(external_payload)
    owner_path = tmp_path / "run.lock"
    _symlink_file_or_skip(owner_path, external)

    lock = WorkspaceRunLock(owner_path)

    assert lock.path == owner_path.absolute()
    assert lock.path != external.resolve()
    with pytest.raises(
        RunLockCorruptError,
        match=r"owner metadata.*(?:symlink|reparse)",
    ):
        lock.acquire()
    assert external.read_bytes() == external_payload
    assert owner_path.is_symlink()


def test_guard_symlink_is_not_opened_or_initialized(tmp_path: Path) -> None:
    owner_path = tmp_path / "run.lock"
    guard_path = owner_path.with_name(f"{owner_path.name}.guard")
    external = tmp_path / "external-guard.txt"
    external_payload = b"valuable external guard bytes"
    external.write_bytes(external_payload)
    _symlink_file_or_skip(guard_path, external)

    with pytest.raises(RunLockCorruptError, match=r"guard.*(?:symlink|reparse)"):
        WorkspaceRunLock(owner_path).acquire()

    assert external.read_bytes() == external_payload
    assert guard_path.is_symlink()
    assert not owner_path.exists()


def test_guard_hardlink_is_rejected_before_initial_byte_write(tmp_path: Path) -> None:
    owner_path = tmp_path / "run.lock"
    guard_path = owner_path.with_name(f"{owner_path.name}.guard")
    external = tmp_path / "external-guard.txt"
    external_payload = b"valuable external hardlink bytes"
    external.write_bytes(external_payload)
    try:
        os.link(external, guard_path)
    except OSError as exc:
        pytest.skip(f"hard links are unavailable on this filesystem: {exc}")

    assert external.stat().st_nlink > 1
    with pytest.raises(RunLockCorruptError, match=r"guard.*hard links"):
        WorkspaceRunLock(owner_path).acquire()

    assert external.read_bytes() == external_payload
    assert guard_path.read_bytes() == external_payload
    assert not owner_path.exists()


def test_owner_hardlink_is_rejected_before_metadata_read(tmp_path: Path) -> None:
    owner_path = tmp_path / "run.lock"
    external = tmp_path / "external-owner.txt"
    external_payload = b"valuable external owner hardlink bytes"
    external.write_bytes(external_payload)
    try:
        os.link(external, owner_path)
    except OSError as exc:
        pytest.skip(f"hard links are unavailable on this filesystem: {exc}")

    with pytest.raises(RunLockCorruptError, match=r"owner metadata.*hard links"):
        WorkspaceRunLock(owner_path).acquire()

    assert external.read_bytes() == external_payload
    assert owner_path.read_bytes() == external_payload


def test_owner_parent_swap_cleans_external_atomic_sibling(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    staging = tmp_path / "staging"
    original = tmp_path / "original-staging"
    outside = tmp_path / "outside"
    staging.mkdir()
    outside.mkdir()
    probe = tmp_path / "directory-symlink-probe"
    try:
        probe.symlink_to(outside, target_is_directory=True)
        probe.unlink()
    except OSError as exc:
        pytest.skip(f"directory symlinks are unavailable on this host: {exc}")

    real_open = atomic_file_module._open_random_sibling
    swapped = False

    def swap_parent_then_open(path: Path) -> tuple[int, Path, tuple[int, int]]:
        nonlocal swapped
        if not swapped:
            staging.rename(original)
            staging.symlink_to(outside, target_is_directory=True)
            swapped = True
        return real_open(path)

    monkeypatch.setattr(atomic_file_module, "_open_random_sibling", swap_parent_then_open)

    with pytest.raises(RunLockCorruptError, match=r"owner metadata publication.*parent"):
        run_lock_module._write_owner(staging / "run.lock", run_lock_module._current_owner())

    assert swapped is True
    assert list(outside.iterdir()) == []


def test_guard_post_open_check_rejects_hardlink_swap_before_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner_path = tmp_path / "run.lock"
    guard_path = owner_path.with_name(f"{owner_path.name}.guard")
    external = tmp_path / "external-after-precheck.txt"
    external_payload = b"post-open verification protects these bytes"
    external.write_bytes(external_payload)
    real_open = os.open
    swapped = False

    def swap_before_open(
        path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        flags: int,
        mode: int = 0o777,
    ) -> int:
        nonlocal swapped
        if not swapped and Path(os.fsdecode(path)) == guard_path:
            swapped = True
            os.link(external, guard_path)
        return real_open(path, flags, mode)

    monkeypatch.setattr(os, "open", swap_before_open)

    with pytest.raises(RunLockCorruptError, match=r"guard.*single-link"):
        WorkspaceRunLock(owner_path).acquire()

    assert swapped is True
    assert external.read_bytes() == external_payload
    assert guard_path.read_bytes() == external_payload


def test_guard_is_reverified_after_successful_os_lock_before_owner_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner_path = tmp_path / "run.lock"
    real_try_lock = run_lock_module._try_lock_guard
    real_verify = run_lock_module._verify_open_leaf
    verification_count = 0
    lock_succeeded = False

    def tracked_try_lock(fd: int) -> bool:
        nonlocal lock_succeeded
        lock_succeeded = real_try_lock(fd)
        return lock_succeeded

    def simulate_post_lock_swap(fd: int, path: Path, *, label: str) -> os.stat_result:
        nonlocal verification_count
        verification_count += 1
        if lock_succeeded and verification_count == 2:
            raise RunLockCorruptError(
                f"unsafe workspace run-lock {label} at {path}: leaf changed during open"
            )
        return real_verify(fd, path, label=label)

    monkeypatch.setattr(run_lock_module, "_try_lock_guard", tracked_try_lock)
    monkeypatch.setattr(run_lock_module, "_verify_open_leaf", simulate_post_lock_swap)

    with pytest.raises(RunLockCorruptError, match=r"guard.*leaf changed during open"):
        WorkspaceRunLock(owner_path).acquire()

    assert lock_succeeded is True
    assert verification_count == 2
    assert not owner_path.exists()
    # The descriptor was unlocked and closed on the fail-closed path.
    with WorkspaceRunLock(owner_path):
        assert owner_path.is_file()


def test_guard_is_reverified_after_successful_stale_owner_retry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner_path = tmp_path / "run.lock"
    dead_owner = replace(
        run_lock_module._current_owner(),
        pid=2_147_483_647,
        process_start_time=1.0,
    )
    _write_owner(owner_path, dead_owner)
    lock_attempts = iter((False, True))
    successful_retry = False
    real_verify = run_lock_module._verify_open_leaf
    post_retry_verification_seen = False

    def retry_once(_fd: int) -> bool:
        nonlocal successful_retry
        result = next(lock_attempts)
        successful_retry = result
        return result

    def simulate_retry_swap(fd: int, path: Path, *, label: str) -> os.stat_result:
        nonlocal post_retry_verification_seen
        if successful_retry:
            post_retry_verification_seen = True
            raise RunLockCorruptError(
                f"unsafe workspace run-lock {label} at {path}: leaf changed during open"
            )
        return real_verify(fd, path, label=label)

    monkeypatch.setattr(run_lock_module, "_try_lock_guard", retry_once)
    monkeypatch.setattr(run_lock_module, "_verify_open_leaf", simulate_retry_swap)
    monkeypatch.setattr(run_lock_module.time, "sleep", lambda _seconds: None)

    with pytest.raises(RunLockCorruptError, match=r"guard.*leaf changed during open"):
        WorkspaceRunLock(owner_path).acquire()

    assert post_retry_verification_seen is True
    assert json.loads(owner_path.read_text(encoding="utf-8"))["token"] == dead_owner.token


@pytest.mark.skipif(os.name != "nt", reason="Windows Junction regression")
@pytest.mark.parametrize("redirected_leaf", ["owner", "guard"])
def test_windows_reparse_leaf_is_rejected_without_touching_target(
    tmp_path: Path,
    redirected_leaf: str,
) -> None:
    owner_path = tmp_path / "run.lock"
    guard_path = owner_path.with_name(f"{owner_path.name}.guard")
    redirected_path = owner_path if redirected_leaf == "owner" else guard_path
    external_dir = tmp_path / f"external-{redirected_leaf}"
    external_dir.mkdir()
    sentinel = external_dir / "valuable.txt"
    sentinel.write_bytes(b"external reparse target bytes")
    cmd_executable = Path(os.environ.get("COMSPEC", r"C:\Windows\System32\cmd.exe"))
    created = subprocess.run(  # noqa: S603 - cmd builtin creates the test Junction
        [
            cmd_executable,
            "/d",
            "/u",
            "/c",
            "mklink",
            "/J",
            str(redirected_path),
            str(external_dir),
        ],
        capture_output=True,
        encoding="utf-16-le",
        errors="replace",
        check=False,
    )
    if created.returncode != 0:
        pytest.skip(f"could not create Junction: {created.stdout}{created.stderr}")

    try:
        with pytest.raises(RunLockCorruptError, match=redirected_leaf):
            WorkspaceRunLock(owner_path).acquire()
        sentinel_payload = sentinel.read_bytes()
    finally:
        if redirected_path.exists() and redirected_path.is_junction():
            redirected_path.rmdir()

    assert sentinel_payload == b"external reparse target bytes"


def test_db_lock_path_is_bound_to_canonical_workspace_without_resolving_database(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path.resolve()
    monkeypatch.chdir(workspace)
    cache = tmp_path / ".mutmut-cache"
    cache.mkdir()
    db_path = cache / "mutmut-cache.db"
    path_type = type(db_path)
    real_resolve = path_type.resolve
    resolved_paths: list[Path] = []

    def tracked_resolve(self: Path, *args: object, **kwargs: object) -> Path:
        resolved_paths.append(self)
        return real_resolve(self, *args, **kwargs)

    monkeypatch.setattr(path_type, "resolve", tracked_resolve)

    lock_path = run_lock_path_for_db(db_path)

    expected_digest = hashlib.sha256(str(workspace).casefold().encode("utf-8")).hexdigest()[:16]
    assert lock_path == workspace / f".mutmut-win-{expected_digest}.run.lock"
    assert db_path.absolute() not in resolved_paths
    assert cache.absolute() not in resolved_paths
    assert workspace in resolved_paths


def test_workspace_lock_path_does_not_follow_database_symlink(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    cache = tmp_path / ".mutmut-cache"
    cache.mkdir()
    external_dir = tmp_path / "external-state"
    external_dir.mkdir()
    external_db = external_dir / "valuable.db"
    external_payload = b"external database bytes"
    external_db.write_bytes(external_payload)
    db_path = cache / "mutmut-cache.db"
    _symlink_file_or_skip(db_path, external_db)

    lock_path = run_lock_path_for_db(db_path)

    workspace = tmp_path.resolve()
    expected_digest = hashlib.sha256(str(workspace).casefold().encode("utf-8")).hexdigest()[:16]
    assert lock_path == tmp_path / f".mutmut-win-{expected_digest}.run.lock"
    assert lock_path.parent != external_dir
    assert external_db.read_bytes() == external_payload


def test_different_and_hardlink_aliased_databases_share_workspace_lock_domain(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    first_db = tmp_path / "state-a" / "cache.db"
    second_db = tmp_path / "state-b" / "other.db"

    workspace_lock_path = run_lock_path_for_db(first_db)
    assert run_lock_path_for_db(second_db) == workspace_lock_path

    first_db.parent.mkdir()
    first_db.write_bytes(b"database placeholder")
    hardlink_alias = tmp_path / "state-b" / "cache-hardlink.db"
    hardlink_alias.parent.mkdir()
    try:
        os.link(first_db, hardlink_alias)
    except OSError as exc:
        pytest.skip(f"hard links are unavailable on this filesystem: {exc}")

    assert first_db.stat().st_ino == hardlink_alias.stat().st_ino
    assert run_lock_path_for_db(hardlink_alias) == workspace_lock_path


def test_workspace_lock_path_fails_closed_when_workspace_cannot_be_canonicalized(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    path_type = type(tmp_path)

    def fail_resolve(self: Path, *_args: object, **_kwargs: object) -> Path:
        raise OSError(f"cannot resolve {self}")

    monkeypatch.setattr(path_type, "resolve", fail_resolve)

    with pytest.raises(run_lock_module.RunLockError, match="cannot canonicalize"):
        run_lock_path_for_db(tmp_path / "custom.db")

    assert list(tmp_path.glob(".mutmut-win-*.run.lock*")) == []


def test_database_lock_domains_cover_canonical_path_and_hardlink_identity(
    tmp_path: Path,
) -> None:
    first_db = tmp_path / "workspace-a" / "cache.db"
    alias_db = tmp_path / "workspace-b" / "alias.db"
    first_db.parent.mkdir()
    alias_db.parent.mkdir()
    first_db.write_bytes(b"sqlite identity placeholder")
    try:
        os.link(first_db, alias_db)
    except OSError as exc:
        pytest.skip(f"hard links are unavailable on this filesystem: {exc}")

    first_paths = database_lock_paths_for_db(first_db)
    alias_paths = database_lock_paths_for_db(alias_db)

    assert len(first_paths) == 2
    assert len(alias_paths) == 2
    assert first_paths[0] != alias_paths[0]
    assert first_paths[1] == alias_paths[1]


def test_absolute_database_uses_same_lock_domain_from_different_workspaces(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_a = tmp_path / "workspace-a"
    workspace_b = tmp_path / "workspace-b"
    database = tmp_path / "shared" / "cache.db"
    workspace_a.mkdir()
    workspace_b.mkdir()
    database.parent.mkdir()
    database.write_bytes(b"sqlite identity placeholder")

    monkeypatch.chdir(workspace_a)
    first_paths = database_lock_paths_for_db(database)
    monkeypatch.chdir(workspace_b)
    second_paths = database_lock_paths_for_db(database)

    assert first_paths == second_paths


def test_database_lock_rejects_hardlink_alias_while_original_is_held(
    tmp_path: Path,
) -> None:
    first_db = tmp_path / "workspace-a" / "cache.db"
    alias_db = tmp_path / "workspace-b" / "alias.db"
    first_db.parent.mkdir()
    alias_db.parent.mkdir()
    first_db.write_bytes(b"sqlite identity placeholder")
    try:
        os.link(first_db, alias_db)
    except OSError as exc:
        pytest.skip(f"hard links are unavailable on this filesystem: {exc}")

    with DatabaseRunLocks(first_db), pytest.raises(RunLockHeldError):
        DatabaseRunLocks(alias_db).acquire()

    with DatabaseRunLocks(alias_db) as replacement:
        assert replacement.acquired is True
