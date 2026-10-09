"""Concurrent uv hardlinks must not invalidate unchanged dependency bytes."""

import ctypes
import hashlib
import msvcrt
import os
import stat
from contextlib import contextmanager
from ctypes import wintypes
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from mutmut_win.stats import _hash_context_file

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path
    from typing import BinaryIO


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
    # Native metadata updates can share a ctime tick; the real link delta is
    # the event proof, and the completion/strictness assertions remain exact.
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
            # A size change is observable even when the native clock has not
            # advanced; no source bytes have been read at this hook yet.
            source.write_bytes(b"value = 430\n")
        observed.append(result)
        return result

    monkeypatch.setattr(os, "fstat", fstat_with_concurrent_write)
    assert not _hash_context_file(hashlib.sha256(), source, label="dependency", seen=set())
    assert source.read_bytes() == b"value = 430\n"


@pytest.mark.parametrize("via_alias", [False, True], ids=["source-write", "alias-write"])
@pytest.mark.parametrize("link_churn", [False, True], ids=["no-churn", "with-churn"])
@pytest.mark.parametrize("iteration", range(10))
def test_write_after_read_with_restored_mtime_never_authorizes_old_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    via_alias: bool,
    link_churn: bool,
    iteration: int,
) -> None:
    """Detect same-size replacement after the first full content read."""
    source = tmp_path / f"dependency-{iteration}.py"
    source.write_bytes(b"value = 42\n")
    alias = tmp_path / "existing-alias.py"
    alias.hardlink_to(source)
    original = source.stat()
    real_fstat = os.fstat
    calls = 0
    observations: list[os.stat_result] = []

    def mutate_after_read(file_descriptor: int) -> os.stat_result:
        nonlocal calls
        calls += 1
        if calls == 2:
            (alias if via_alias else source).write_bytes(b"value = 43\n")
            os.utime(source, ns=(original.st_atime_ns, original.st_mtime_ns))
            if link_churn:
                (tmp_path / "new-environment.py").hardlink_to(source)
        observed = real_fstat(file_descriptor)
        observations.append(observed)
        return observed

    monkeypatch.setattr(os, "fstat", mutate_after_read)
    complete = _hash_context_file(hashlib.sha256(), source, label="source", seen=set())
    assert not complete, [
        (item.st_ino, item.st_size, item.st_mtime_ns, item.st_ctime_ns, item.st_nlink)
        for item in observations
    ]
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


@pytest.mark.parametrize("attribute_step", [2, 4, 5], ids=["first-read", "recheck", "rebound"])
def test_native_hidden_attribute_with_link_churn_is_not_neutral(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, attribute_step: int
) -> None:
    """A metadata bit absent from st_mode must remain bound to the first bytes."""
    source = tmp_path / "dependency.py"
    source.write_bytes(b"value = 42\n")
    original_attributes = source.stat().st_file_attributes
    set_attributes = ctypes.WinDLL("kernel32", use_last_error=True).SetFileAttributesW
    set_attributes.argtypes = [wintypes.LPCWSTR, wintypes.DWORD]
    set_attributes.restype = wintypes.BOOL
    real_fstat = os.fstat
    calls = 0

    def alter_attributes(file_descriptor: int) -> os.stat_result:
        nonlocal calls
        calls += 1
        if calls == 2:
            (tmp_path / "new-environment.py").hardlink_to(source)
        if calls == attribute_step:
            assert set_attributes(str(source), original_attributes | stat.FILE_ATTRIBUTE_HIDDEN)
        return real_fstat(file_descriptor)

    monkeypatch.setattr(os, "fstat", alter_attributes)
    try:
        assert not _hash_context_file(hashlib.sha256(), source, label="source", seen=set())
    finally:
        assert set_attributes(str(source), original_attributes)


@pytest.mark.parametrize("fault", ["first-error", "recheck-error", "both-short"])
def test_each_complete_content_read_is_required(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault: str
) -> None:
    """Read failures and two matching incomplete streams cannot establish a basis."""
    import mutmut_win.stats as stats_module

    source = tmp_path / "dependency.py"
    source.write_bytes(b"value = 42\n")
    real_open = stats_module._open_for_hash
    opens = 0

    @contextmanager
    def controlled_open(path: Path) -> Iterator[BinaryIO]:
        nonlocal opens
        opens += 1
        with real_open(path) as stream:
            wrapped = MagicMock(wraps=stream)
            if fault == "both-short":
                wrapped.read.side_effect = [b"value", b""]
            elif (fault == "first-error" and opens == 1) or (
                fault == "recheck-error" and opens == 2
            ):
                wrapped.read.side_effect = OSError("native stream read failed")
            yield wrapped

    monkeypatch.setattr(stats_module, "_open_for_hash", controlled_open)
    seen: set[Path] = set()
    assert not _hash_context_file(hashlib.sha256(), source, label="source", seen=seen)
    assert not seen
    assert opens <= 3


@pytest.mark.parametrize("fault", ["write", "truncate", "link"])
def test_drift_during_the_fresh_read_remains_incomplete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault: str
) -> None:
    """A third observation never excuses instability during the second read."""
    source = tmp_path / "dependency.py"
    source.write_bytes(b"value = 42\n")
    original_mtime = source.stat().st_mtime_ns
    real_fstat = os.fstat
    observations = 0

    def alter_second_read(file_descriptor: int) -> os.stat_result:
        nonlocal observations
        observations += 1
        if observations == 4:
            if fault == "link":
                (tmp_path / "concurrent.py").hardlink_to(source)
            elif fault == "truncate":
                source.write_bytes(b"value")
            else:
                source.write_bytes(b"value = 43\n")
            if fault != "link":
                # This arm promises observable metadata drift during H2;
                # the separate H1/H2 mismatch matrix covers restored mtimes.
                os.utime(source, ns=(source.stat().st_atime_ns, original_mtime + 1_000_000_000))
        return real_fstat(file_descriptor)

    monkeypatch.setattr(os, "fstat", alter_second_read)
    assert not _hash_context_file(hashlib.sha256(), source, label="source", seen=set())


@pytest.mark.parametrize("link_change", [False, True], ids=["unchanged", "new-hardlink"])
def test_hashing_uses_two_content_reads_and_three_fresh_handles(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, link_change: bool
) -> None:
    """Default and link-recovery paths share one bounded counterread budget."""
    import mutmut_win.stats as stats_module

    source = tmp_path / "dependency.py"
    content = b"value = 42\n" * 200_000
    source.write_bytes(content)
    reference = hashlib.sha256()
    assert _hash_context_file(reference, source, label="source", seen=set())
    real_open = stats_module._open_for_hash
    real_fstat = os.fstat
    byte_counts: list[int] = []
    read_counts: list[int] = []
    observations = 0

    @contextmanager
    def counted_open(path: Path) -> Iterator[BinaryIO]:
        index = len(byte_counts)
        byte_counts.append(0)
        read_counts.append(0)
        with real_open(path) as stream:
            wrapped = MagicMock(wraps=stream)

            def counted_read(size: int) -> bytes:
                chunk = stream.read(size)
                byte_counts[index] += len(chunk)
                read_counts[index] += 1
                return chunk

            wrapped.read.side_effect = counted_read
            yield wrapped

    def add_link(file_descriptor: int) -> os.stat_result:
        nonlocal observations
        observations += 1
        if link_change and observations == 2:
            (tmp_path / "new-environment.py").hardlink_to(source)
        return real_fstat(file_descriptor)

    monkeypatch.setattr(stats_module, "_open_for_hash", counted_open)
    monkeypatch.setattr(os, "fstat", add_link)
    observed = hashlib.sha256()
    assert _hash_context_file(observed, source, label="source", seen=set())
    assert observed.digest() == reference.digest()
    assert byte_counts == [len(content), len(content), 0]
    assert read_counts == [4, 4, 0]
    assert observations == 5


@pytest.mark.parametrize("replace_path", [False, True], ids=["stable-path", "replace-path"])
def test_native_path_replacement_before_final_rebound_is_detected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, replace_path: bool
) -> None:
    """The last observation must reopen the lexical path after both content reads."""
    import mutmut_win.stats as stats_module

    source = tmp_path / "dependency.py"
    replacement = tmp_path / "replacement.py"
    source.write_bytes(b"value = 42\n")
    replacement.write_bytes(source.read_bytes())
    original = source.stat()
    os.utime(replacement, ns=(original.st_atime_ns, original.st_mtime_ns))
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_file = kernel32.CreateFileW
    create_file.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    create_file.restype = wintypes.HANDLE
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = [wintypes.HANDLE]
    close_handle.restype = wintypes.BOOL
    opens = 0

    @contextmanager
    def shared_delete_open(path: Path) -> Iterator[BinaryIO]:
        nonlocal opens
        opens += 1
        if replace_path and opens == 3:
            path.rename(tmp_path / "displaced.py")
            replacement.rename(path)
        # FILE_SHARE_DELETE makes the real native rebind possible while H1/H2
        # still own their handles; the production comparison code is unchanged.
        handle = create_file(str(path), 0x80000000, 0x7, None, 3, 0x80, None)
        assert handle not in (None, ctypes.c_void_p(-1).value)
        try:
            descriptor = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY | os.O_NOINHERIT)
        except BaseException:
            close_handle(handle)
            raise
        try:
            stream = os.fdopen(descriptor, "rb")
        except BaseException:
            os.close(descriptor)
            raise
        with stream:
            yield stream

    monkeypatch.setattr(stats_module, "_open_for_hash", shared_delete_open)
    complete = _hash_context_file(hashlib.sha256(), source, label="source", seen=set())
    assert complete is (not replace_path)
    assert opens == 3
    assert (source.stat().st_ino != original.st_ino) is replace_path
    assert source.read_bytes() == b"value = 42\n"
