"""Compare-and-swap source protection during apply (M-005/M-114, issue #148)."""

from __future__ import annotations

import ctypes
import ctypes.wintypes
from pathlib import Path
from unittest.mock import patch

import pytest

from mutmut_win.atomic_file import AtomicPreconditionError, atomic_replace_if_unchanged
from mutmut_win.config import MutmutConfig
from mutmut_win.exceptions import StaleStagingError
from mutmut_win.mutant_diff import apply_mutant

_SOURCE = "def add(a, b):\n    return a + b\n"

# Win32 bindings for the retained-handle race model (AR-17): a writer that
# opened the target before displacement with FILE_SHARE_DELETE keeps writing
# into the displaced inode.  Same signature discipline as
# tests/unit/windows_fs_util.py / mutmut_win.process.job_object (AR-13):
# without argtypes/restype ctypes defaults to c_int and truncates 64-bit
# HANDLE values.
_KERNEL32 = ctypes.WinDLL("kernel32", use_last_error=True)
_KERNEL32.CreateFileW.argtypes = [
    ctypes.wintypes.LPCWSTR,  # lpFileName
    ctypes.wintypes.DWORD,  # dwDesiredAccess
    ctypes.wintypes.DWORD,  # dwShareMode
    ctypes.wintypes.LPVOID,  # lpSecurityAttributes
    ctypes.wintypes.DWORD,  # dwCreationDisposition
    ctypes.wintypes.DWORD,  # dwFlagsAndAttributes
    ctypes.wintypes.HANDLE,  # hTemplateFile
]
_KERNEL32.CreateFileW.restype = ctypes.wintypes.HANDLE
_KERNEL32.CloseHandle.argtypes = [ctypes.wintypes.HANDLE]  # hObject
_KERNEL32.CloseHandle.restype = ctypes.wintypes.BOOL
_KERNEL32.SetFilePointerEx.argtypes = [
    ctypes.wintypes.HANDLE,  # hFile
    ctypes.wintypes.LARGE_INTEGER,  # liDistanceToMove
    ctypes.POINTER(ctypes.wintypes.LARGE_INTEGER),  # lpNewFilePointer
    ctypes.wintypes.DWORD,  # dwMoveMethod
]
_KERNEL32.SetFilePointerEx.restype = ctypes.wintypes.BOOL
_KERNEL32.SetEndOfFile.argtypes = [ctypes.wintypes.HANDLE]  # hFile
_KERNEL32.SetEndOfFile.restype = ctypes.wintypes.BOOL
_KERNEL32.WriteFile.argtypes = [
    ctypes.wintypes.HANDLE,  # hFile
    ctypes.c_void_p,  # lpBuffer
    ctypes.wintypes.DWORD,  # nNumberOfBytesToWrite
    ctypes.POINTER(ctypes.wintypes.DWORD),  # lpNumberOfBytesWritten
    ctypes.c_void_p,  # lpOverlapped
]
_KERNEL32.WriteFile.restype = ctypes.wintypes.BOOL

_GENERIC_WRITE = 0x40000000
_FILE_SHARE_READ = 0x1
_FILE_SHARE_WRITE = 0x2
_FILE_SHARE_DELETE = 0x4
_OPEN_EXISTING = 3
_FILE_BEGIN = 0
_INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value


def _open_share_delete_writer(path: Path) -> int:
    """Open *path* for writing while granting rename/delete sharing."""
    handle = _KERNEL32.CreateFileW(
        str(path),
        _GENERIC_WRITE,
        _FILE_SHARE_READ | _FILE_SHARE_WRITE | _FILE_SHARE_DELETE,
        None,
        _OPEN_EXISTING,
        0,
        None,
    )
    if handle is None or handle == _INVALID_HANDLE_VALUE:
        error_code = ctypes.get_last_error()
        msg = f"CreateFileW failed for share-delete writer (error {error_code})"
        raise OSError(error_code, msg, str(path), error_code)
    return int(handle)


def _write_via_handle(handle: int, data: bytes) -> None:
    """Truncate and rewrite through an open handle, Win32 errors preserved."""
    if not _KERNEL32.SetFilePointerEx(handle, ctypes.wintypes.LARGE_INTEGER(0), None, _FILE_BEGIN):
        raise ctypes.WinError(ctypes.get_last_error())
    if not _KERNEL32.SetEndOfFile(handle):
        raise ctypes.WinError(ctypes.get_last_error())
    written = ctypes.wintypes.DWORD(0)
    buffer = ctypes.create_string_buffer(data)
    if not _KERNEL32.WriteFile(handle, buffer, len(data), ctypes.byref(written), None):
        raise ctypes.WinError(ctypes.get_last_error())
    if written.value != len(data):
        msg = f"short Win32 write: {written.value} of {len(data)} bytes"
        raise OSError(msg)


def _setup_apply_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[str, MutmutConfig, Path]:
    """Create src/mod.py, generate one mutant, return (name, config, path)."""
    from mutmut_win.file_setup import copy_src_dir, create_mutants_for_file, get_mutant_name

    monkeypatch.chdir(tmp_path)
    src = tmp_path / "src" / "mod.py"
    src.parent.mkdir()
    src.write_text(_SOURCE, encoding="utf-8")
    config = MutmutConfig(paths_to_mutate=["src"], max_children=1)
    copy_src_dir(config)
    names, _warns, _fast = create_mutants_for_file(Path("src/mod.py"), Path("mutants/src/mod.py"))
    assert names
    qualified = get_mutant_name(Path("src/mod.py"), names[0])
    return qualified, config, src


class TestApplySourceRace:
    def test_foreign_writer_during_parse_is_detected(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A writer between the staleness check and publication is caught."""
        mutant_name, config, source_path = _setup_apply_project(tmp_path, monkeypatch)

        foreign = b"def add(a, b):\n    return a * b  # foreign edit\n"

        import mutmut_win.mutant_diff as md
        from mutmut_win.mutation import parse_module_preserving_newlines

        real_parse = parse_module_preserving_newlines
        call_count = 0

        def racing_parse(text: str) -> object:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                source_path.write_bytes(foreign)
            return real_parse(text)

        monkeypatch.setattr(md, "parse_module_preserving_newlines", racing_parse)

        with pytest.raises(StaleStagingError, match="changed while applying"):
            apply_mutant(mutant_name, config)

        assert source_path.read_bytes() == foreign

    def test_stage1_catches_change_before_backup(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Stage 1: a writer between the check and the backup is caught."""
        mutant_name, config, source_path = _setup_apply_project(tmp_path, monkeypatch)

        foreign = b"def add(a, b):\n    return a - b  # stage1\n"

        import mutmut_win.atomic_file as af
        import mutmut_win.mutant_diff as md

        real_write = af.atomic_write_bytes
        backup_written = False

        def racing_write(path: Path, payload: bytes, **kwargs: object) -> None:
            nonlocal backup_written
            if str(path).endswith(".mutmut-orig.bak") and not backup_written:
                backup_written = True
                source_path.write_bytes(foreign)
            real_write(path, payload, **kwargs)  # type: ignore[arg-type]

        monkeypatch.setattr(md, "atomic_write_bytes", racing_write)

        with pytest.raises(StaleStagingError, match="changed while applying"):
            apply_mutant(mutant_name, config)

        assert source_path.read_bytes() == foreign


class TestAtomicReplaceIfUnchanged:
    """Direct tests for the CAS publication primitive."""

    def test_matching_expected_replaces(self, tmp_path: Path) -> None:
        target = tmp_path / "file.txt"
        target.write_bytes(b"old content")
        result = atomic_replace_if_unchanged(target, b"new content", expected=b"old content")
        assert result is True
        assert target.read_bytes() == b"new content"

    def test_mismatched_expected_raises(self, tmp_path: Path) -> None:
        target = tmp_path / "file.txt"
        target.write_bytes(b"foreign writer was here")
        with pytest.raises(AtomicPreconditionError, match="differ from expected"):
            atomic_replace_if_unchanged(target, b"new", expected=b"original")
        assert target.read_bytes() == b"foreign writer was here"

    def test_identical_payload_no_write(self, tmp_path: Path) -> None:
        target = tmp_path / "file.txt"
        target.write_bytes(b"same")
        result = atomic_replace_if_unchanged(target, b"same", expected=b"same")
        assert result is False
        assert target.read_bytes() == b"same"

    def test_displacement_sibling_not_py(self, tmp_path: Path) -> None:
        from mutmut_win.atomic_file import _displacement_sibling

        target = tmp_path / "source.py"
        sibling = _displacement_sibling(target)
        assert not sibling.name.casefold().endswith(".py")
        assert sibling.name.startswith(".source.py.")
        assert "mutmut-displaced" in sibling.name

    def test_backup_promotion(self, tmp_path: Path) -> None:
        target = tmp_path / "file.txt"
        backup = tmp_path / "file.bak"
        target.write_bytes(b"original")
        atomic_replace_if_unchanged(target, b"replaced", expected=b"original", backup_path=backup)
        assert target.read_bytes() == b"replaced"
        assert backup.read_bytes() == b"original"

    def test_no_leftover_siblings_on_success(self, tmp_path: Path) -> None:
        target = tmp_path / "file.txt"
        target.write_bytes(b"original")
        backup = tmp_path / "file.bak"
        atomic_replace_if_unchanged(target, b"replaced", expected=b"original", backup_path=backup)
        siblings = [p for p in tmp_path.iterdir() if p != target and p != backup]
        assert siblings == [], f"unexpected siblings: {siblings}"


class TestDisplacementRaceWindow:
    """Races INSIDE the displacement CAS core stretch (AR-17 / TQ-003 / M-005).

    Unlike the stage-1/parse-window tests above, every test here fails into
    the protocol after the target-identity capture.  A regression that
    removes the stage-4 displaced verification must turn the
    identity-capture and retained-handle tests RED — re-verify with the
    controlled in-memory stage-4 mutant from the AR-17 repro
    (glm-followup/ar17-repro.py); the historical ImportError red is NOT a
    behavioral reproduction.
    """

    def test_foreign_write_after_identity_capture_is_rejected_and_restored(
        self, tmp_path: Path
    ) -> None:
        """A foreign write between identity capture and displacement (stage 4).

        The displaced bytes no longer match *expected*, so the CAS must fail
        closed, restore the foreign bytes to the path and leave no residue.
        With stage 4 disabled the foreign bytes would be silently replaced
        by the payload.
        """
        target = tmp_path / "source.py"
        target.write_bytes(b"original")
        foreign = b"foreign bytes from a late editor"
        real_rename = Path.rename

        def racing_rename(source_path: Path, destination: Path) -> Path:
            if source_path == target and "mutmut-displaced" in destination.name:
                # In-place rewrite right before the displacement rename:
                # same inode, different bytes — only stage 4 can catch it.
                target.write_bytes(foreign)
            return real_rename(source_path, destination)

        with (
            patch.object(Path, "rename", autospec=True, side_effect=racing_rename),
            pytest.raises(AtomicPreconditionError),
        ):
            atomic_replace_if_unchanged(target, b"mutated", expected=b"original")

        assert target.read_bytes() == foreign
        assert list(tmp_path.glob(".*.mutmut-displaced")) == []
        assert list(tmp_path.glob(".*.mutmut-atomic-*.tmp")) == []

    def test_foreign_recreate_after_displacement_preserves_both_and_names_recovery_path(
        self, tmp_path: Path
    ) -> None:
        """A foreign writer recreates the path while it is displaced (stage 5).

        The recreated file must stay at the path, the displaced original must
        survive under its displacement path, and that exact path must be
        named in the error so operators can recover the original.
        """
        target = tmp_path / "source.py"
        target.write_bytes(b"original")
        recreated = b"recreated by a foreign writer"
        real_rename = Path.rename

        def racing_rename(source_path: Path, destination: Path) -> Path:
            result = real_rename(source_path, destination)
            if source_path == target and "mutmut-displaced" in destination.name:
                target.write_bytes(recreated)
            return result

        with (
            patch.object(Path, "rename", autospec=True, side_effect=racing_rename),
            pytest.raises(AtomicPreconditionError) as excinfo,
        ):
            atomic_replace_if_unchanged(target, b"mutated", expected=b"original")

        assert target.read_bytes() == recreated
        displaced = list(tmp_path.glob(".*.mutmut-displaced"))
        assert len(displaced) == 1
        assert displaced[0].read_bytes() == b"original"
        # The recovery location is named exactly (recovery-path contract).
        assert str(displaced[0].resolve()) in str(excinfo.value)
        assert list(tmp_path.glob(".*.mutmut-atomic-*.tmp")) == []

    def test_late_share_delete_writer_into_displaced_inode_is_rejected(
        self, tmp_path: Path
    ) -> None:
        """A retained FILE_SHARE_DELETE writer hits the displaced inode (stage 4).

        A writer that opened the target before displacement keeps its handle
        across the rename and writes new bytes into the displaced inode right
        after the displacement.  Stage 4 must reject the swap; the late bytes
        stay at the original path.  With stage 4 disabled the path would be
        replaced by the payload and the late bytes would survive only in an
        unreported randomly named sibling.
        """
        target = tmp_path / "source.py"
        target.write_bytes(b"original")
        late = b"late writer bytes"
        handle = _open_share_delete_writer(target)
        real_rename = Path.rename
        try:

            def racing_rename(source_path: Path, destination: Path) -> Path:
                result = real_rename(source_path, destination)
                if source_path == target and "mutmut-displaced" in destination.name:
                    # Write AFTER the displacement rename: the bytes land in
                    # the displaced inode, after identity capture.
                    _write_via_handle(handle, late)
                return result

            with (
                patch.object(Path, "rename", autospec=True, side_effect=racing_rename),
                pytest.raises(AtomicPreconditionError),
            ):
                atomic_replace_if_unchanged(target, b"mutated", expected=b"original")

            assert target.read_bytes() == late
            assert list(tmp_path.glob(".*.mutmut-displaced")) == []
            assert list(tmp_path.glob(".*.mutmut-atomic-*.tmp")) == []
        finally:
            _KERNEL32.CloseHandle(handle)


class TestApplyCliConflictReporting:
    """The apply CLI must not report an Applied success on a CAS conflict."""

    def test_cli_conflict_reports_no_applied_success(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """End-to-end: a race inside the CAS core exits 1 without 'Applied'.

        Uses the real apply_mutant path — only config loading is pinned to
        the fixture config; the race is injected at the displacement rename.
        """
        from click.testing import CliRunner

        from mutmut_win.cli import cli

        mutant_name, config, source_path = _setup_apply_project(tmp_path, monkeypatch)
        foreign = b"def add(a, b):\n    return a // b  # raced\n"
        source_name = source_path.name
        real_rename = Path.rename

        def racing_rename(source_path: Path, destination: Path) -> Path:
            # apply_mutant resolves the source relative to the project root,
            # so match by leaf name instead of path equality.
            if source_path.name == source_name and "mutmut-displaced" in destination.name:
                source_path.write_bytes(foreign)
            return real_rename(source_path, destination)

        with (
            patch("mutmut_win.cli.load_config", return_value=config),
            patch.object(Path, "rename", autospec=True, side_effect=racing_rename),
        ):
            result = CliRunner().invoke(cli, ["apply", mutant_name])

        assert result.exit_code == 1, result.output
        assert "Applied mutant" not in result.output
        assert "changed while applying" in result.output
        assert source_path.read_bytes() == foreign
