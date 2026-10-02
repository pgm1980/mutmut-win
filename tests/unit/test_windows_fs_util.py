"""Self-tests for the Windows filesystem state helpers (AP-00 / Q-02)."""

from __future__ import annotations

import os
import stat
from typing import TYPE_CHECKING

import pytest

from tests.unit import windows_fs_util
from tests.unit.windows_fs_util import JunctionUnavailableError

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows-only filesystem states")


def test_readonly_leaf_blocks_writes_and_restores(tmp_path: Path) -> None:
    path = tmp_path / "leaf.txt"
    path.write_text("payload", encoding="utf-8")
    with windows_fs_util.readonly_leaf(path):
        assert path.stat().st_mode & stat.S_IWRITE == 0
        with pytest.raises(PermissionError):
            path.write_text("blocked", encoding="utf-8")
    assert path.stat().st_mode & stat.S_IWRITE != 0
    path.write_text("restored", encoding="utf-8")


def test_readonly_leaf_requires_existing_file(tmp_path: Path) -> None:
    with (
        pytest.raises(OSError, match="existing file"),
        windows_fs_util.readonly_leaf(tmp_path / "missing.txt"),
    ):
        pass


def test_make_junction_links_directory_tree(tmp_path: Path) -> None:
    target = tmp_path / "real-dir"
    (target / "nested").mkdir(parents=True)
    (target / "nested" / "file.txt").write_text("via junction", encoding="utf-8")
    link = tmp_path / "link-dir"

    try:
        windows_fs_util.make_junction(link, target)
    except JunctionUnavailableError as exc:  # host limitation, not a defect
        pytest.skip(f"junctions unavailable: {exc}")

    assert (link / "nested" / "file.txt").read_text(encoding="utf-8") == "via junction"
    assert link.is_dir()


def test_make_junction_requires_existing_target(tmp_path: Path) -> None:
    with pytest.raises(OSError, match="existing directory"):
        windows_fs_util.make_junction(tmp_path / "link", tmp_path / "no-such-target")


def test_byte_range_lock_blocks_second_lock(tmp_path: Path) -> None:
    import msvcrt

    path = tmp_path / "locked.bin"
    path.write_bytes(b"0123456789")
    with (
        windows_fs_util.byte_range_locked_file(path),
        path.open("r+b") as second,
        pytest.raises(PermissionError),
    ):
        # A freshly opened file sits at offset 0 — exactly where the holder
        # locked its byte.
        msvcrt.locking(second.fileno(), msvcrt.LK_NBLCK, 1)
    # After release the same lock must be acquirable again.
    with path.open("r+b") as third:
        third.seek(0)
        msvcrt.locking(third.fileno(), msvcrt.LK_NBLCK, 1)
        msvcrt.locking(third.fileno(), msvcrt.LK_UNLCK, 1)


def test_sharing_violation_holder_blocks_open(tmp_path: Path) -> None:
    path = tmp_path / "shared.txt"
    path.write_bytes(b"payload")
    with windows_fs_util.sharing_violation_holder(path):
        with pytest.raises(PermissionError) as excinfo, path.open("r+b"):
            pass
        # CPython 3.14 maps the sharing violation to EACCES; when the native
        # winerror is propagated it must be 32 (sharing) or 33 (lock).
        assert excinfo.value.winerror in (None, 32, 33)
    # Handle released: the open must succeed again.
    with path.open("r+b"):
        pass


def test_sharing_violation_second_holder_raises_winerror_32_before_yield(tmp_path: Path) -> None:
    """AR-13 (PERF-005/TQ-004): a second holder must fail before the context body.

    Without an explicit restype CreateFileW returned ``c_int(-1)`` while
    ``INVALID_HANDLE_VALUE`` is the unsigned pointer value, so the equality
    check never matched: the body was entered despite ERROR_SHARING_VIOLATION
    and the finally's CloseHandle(INVALID_HANDLE_VALUE) replaced the real
    error 32 with error 6.
    """
    path = tmp_path / "held.txt"
    path.write_bytes(b"payload")

    second_body_entered = False
    with (
        windows_fs_util.sharing_violation_holder(path),
        pytest.raises(OSError, match=r"sharing violation holder \(error 32\)") as excinfo,
        windows_fs_util.sharing_violation_holder(path),
    ):
        second_body_entered = True

    assert not second_body_entered, "second holder must fail before the context body"
    assert excinfo.value.winerror == 32, "ERROR_SHARING_VIOLATION must survive cleanup"


def test_sharing_violation_holder_native_signatures_declared() -> None:
    """CreateFileW/CloseHandle need pointer-width HANDLE signatures (AR-13).

    Mirrors the production contract pinned for ``job_object._kernel32``
    (audit A2-JT-006): ctypes defaults every untyped binding to ``c_int``,
    truncating 64-bit HANDLE values on Win64.
    """
    from ctypes import wintypes

    kernel32 = windows_fs_util._kernel32

    assert tuple(kernel32.CreateFileW.argtypes or ()) == (
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,  # lpSecurityAttributes (wintypes has no LPSECURITY_ATTRIBUTES on 3.14)
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    )
    assert kernel32.CreateFileW.restype is wintypes.HANDLE
    assert tuple(kernel32.CloseHandle.argtypes or ()) == (wintypes.HANDLE,)
    assert kernel32.CloseHandle.restype is wintypes.BOOL


def test_valid_holder_closes_acquired_handle_exactly_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AR-13 acceptance: close exactly the acquired 64-bit handle, exactly once.

    Spies on the module's own kernel32 binding: one CreateFileW, one
    successful CloseHandle with the full pointer-width value, and never a
    CloseHandle on INVALID_HANDLE_VALUE.
    """
    path = tmp_path / "held.txt"
    path.write_bytes(b"payload")

    kernel32 = windows_fs_util._kernel32
    real_create = kernel32.CreateFileW
    real_close = kernel32.CloseHandle
    create_results: list[object] = []
    close_results: list[tuple[object, object]] = []

    def spying_create(*args: object) -> object:
        result = real_create(*args)
        create_results.append(result)
        return result

    def spying_close(handle_value: object) -> object:
        result = real_close(handle_value)
        close_results.append((handle_value, result))
        return result

    monkeypatch.setattr(kernel32, "CreateFileW", spying_create)
    monkeypatch.setattr(kernel32, "CloseHandle", spying_close)

    with windows_fs_util.sharing_violation_holder(path):
        pass

    assert len(create_results) == 1
    acquired = create_results[0]
    assert isinstance(acquired, int)
    assert acquired != windows_fs_util._INVALID_HANDLE_VALUE
    assert close_results == [(acquired, 1)]


def test_sharing_violation_holder_repeated_use_leaks_no_handles(tmp_path: Path) -> None:
    """AR-13 acceptance: repeated acquire/release cycles must not leak handles."""
    import psutil

    path = tmp_path / "held.txt"
    path.write_bytes(b"payload")
    baseline = psutil.Process().num_handles()
    for _ in range(5):
        with windows_fs_util.sharing_violation_holder(path):
            pass
    assert psutil.Process().num_handles() <= baseline, "holder handles must be closed"


def test_near_max_length_path_reaches_component_limit(tmp_path: Path) -> None:
    path = windows_fs_util.near_max_length_path(tmp_path, suffix=".txt")
    assert len(path.name) == 255
    # The path must be creatable on NTFS (this is the state M-010 tests need).
    path.write_text("long name payload", encoding="utf-8")


def test_lone_surrogate_name_is_provided() -> None:
    name = windows_fs_util.lone_surrogate_name()
    assert "\udc80" in name
