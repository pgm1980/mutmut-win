"""Concurrent uv hardlinks must not invalidate unchanged dependency bytes."""

import hashlib
import os
import stat
from pathlib import Path

import pytest

from mutmut_win.stats import _hash_context_file


@pytest.mark.parametrize("remove_alias", [False, True], ids=["add-link", "remove-link"])
@pytest.mark.parametrize("strict_staging", [False, True], ids=["dependency", "staging"])
def test_real_hardlink_during_hash_preserves_dependency_basis(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    remove_alias: bool,
    strict_staging: bool,
) -> None:
    """Change only native link metadata between two stats of the same handle."""
    source = tmp_path / "dependency.py"
    source.write_bytes(b"value = 42\n")
    alias = tmp_path / "another-environment.py"
    if remove_alias:
        alias.hardlink_to(source)
    before_hash = hashlib.sha256()
    assert _hash_context_file(
        before_hash, source, label="dependency", seen=set(), hash_link_count=strict_staging
    )
    real_fstat = os.fstat
    observed: list[os.stat_result] = []

    def fstat_with_concurrent_alias(file_descriptor: int) -> os.stat_result:
        result = real_fstat(file_descriptor)
        if not observed:
            if remove_alias:
                alias.unlink()
            else:
                alias.hardlink_to(source)
        observed.append(result)
        return result

    monkeypatch.setattr(os, "fstat", fstat_with_concurrent_alias)
    after_hash = hashlib.sha256()
    complete = _hash_context_file(
        after_hash, source, label="dependency", seen=set(), hash_link_count=strict_staging
    )
    assert observed[0].st_ino == observed[1].st_ino
    assert observed[0].st_ctime_ns != observed[1].st_ctime_ns
    assert observed[0].st_nlink != observed[1].st_nlink
    assert source.read_bytes() == b"value = 42\n"
    assert complete is not strict_staging
    if complete:
        assert before_hash.hexdigest() == after_hash.hexdigest()


def test_real_content_change_during_dependency_hash_stays_incomplete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ignoring unrelated aliases must not accept an actual concurrent write."""
    source = tmp_path / "dependency.py"
    source.write_bytes(b"value = 42\n")
    real_fstat = os.fstat
    observed: list[os.stat_result] = []

    def fstat_with_concurrent_write(file_descriptor: int) -> os.stat_result:
        result = real_fstat(file_descriptor)
        if not observed:
            source.write_bytes(b"value = 43\n")
        observed.append(result)
        return result

    monkeypatch.setattr(os, "fstat", fstat_with_concurrent_write)
    assert not _hash_context_file(hashlib.sha256(), source, label="dependency", seen=set())
    assert source.read_bytes() == b"value = 43\n"


@pytest.mark.parametrize("via_alias", [False, True], ids=["source-write", "alias-write"])
@pytest.mark.parametrize("link_churn", [False, True], ids=["no-churn", "with-churn"])
def test_write_after_read_with_restored_mtime_never_authorizes_old_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    via_alias: bool,
    link_churn: bool,
) -> None:
    """Detect same-size replacement after the first full content read."""
    source = tmp_path / "dependency.py"
    source.write_bytes(b"value = 42\n")
    alias = tmp_path / "existing-alias.py"
    alias.hardlink_to(source)
    original = source.stat()
    real_fstat = os.fstat
    calls = 0

    def mutate_after_read(file_descriptor: int) -> os.stat_result:
        nonlocal calls
        calls += 1
        if calls == 2:
            (alias if via_alias else source).write_bytes(b"value = 43\n")
            os.utime(source, ns=(original.st_atime_ns, original.st_mtime_ns))
            if link_churn:
                (tmp_path / "new-environment.py").hardlink_to(source)
        return real_fstat(file_descriptor)

    monkeypatch.setattr(os, "fstat", mutate_after_read)
    assert not _hash_context_file(hashlib.sha256(), source, label="source", seen=set())
    assert calls >= 3
    assert source.read_bytes() == b"value = 43\n"
    assert source.stat().st_mtime_ns == original.st_mtime_ns


def test_native_readonly_change_after_read_remains_incomplete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A relevant native attribute change is not treated as link-only churn."""
    source = tmp_path / "dependency.py"
    source.write_bytes(b"value = 42\n")
    real_fstat = os.fstat
    calls = 0

    def change_mode_after_read(file_descriptor: int) -> os.stat_result:
        nonlocal calls
        calls += 1
        if calls == 2:
            source.chmod(stat.S_IREAD)
            (tmp_path / "another-environment.py").hardlink_to(source)
        return real_fstat(file_descriptor)

    monkeypatch.setattr(os, "fstat", change_mode_after_read)
    try:
        assert not _hash_context_file(hashlib.sha256(), source, label="source", seen=set())
    finally:
        source.chmod(stat.S_IREAD | stat.S_IWRITE)


def test_unchanged_native_file_has_stable_complete_digest(tmp_path: Path) -> None:
    """The ordinary no-race path retains its exact canonical digest."""
    source = tmp_path / "dependency.py"
    source.write_bytes(b"value = 42\n")
    first, second = hashlib.sha256(), hashlib.sha256()
    assert _hash_context_file(first, source, label="source", seen=set())
    assert _hash_context_file(second, source, label="source", seen=set())
    assert first.digest() == second.digest()
