"""Compare-and-swap source protection during apply (M-005/M-114, issue #148)."""

from __future__ import annotations

import ctypes
import ctypes.wintypes
from pathlib import Path
from unittest.mock import patch

import pytest

from mutmut_win.atomic_file import (
    AtomicPreconditionError,
    UnsafeAtomicWriteError,
    atomic_replace_if_unchanged,
)
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


class TestCasInterruptRecovery:
    """S3-013: cancellation preserves source ownership and reports recovery."""

    @pytest.mark.parametrize("phase", ["verification", "insertion"])
    @pytest.mark.parametrize("interrupt_type", [KeyboardInterrupt, SystemExit])
    def test_interrupt_restores_source_before_publication(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        phase: str,
        interrupt_type: type[BaseException],
    ) -> None:
        """Cancellation at either pre-publication phase restores the original leaf."""
        source = tmp_path / "source.py"
        backup = tmp_path / "source.py.bak"
        source.write_bytes(b"ORIGINAL")
        backup.write_bytes(b"ORIGINAL")
        original_identity = (source.stat().st_dev, source.stat().st_ino)
        interrupted = interrupt_type("controlled cancellation")
        real_read = Path.read_bytes
        real_rename = Path.rename

        def read_at_phase(path: Path) -> bytes:
            if phase == "verification" and path.name.endswith(".mutmut-displaced"):
                raise interrupted
            return real_read(path)

        def rename_at_phase(path: Path, destination: Path) -> Path:
            if phase == "insertion" and ".mutmut-atomic-" in path.name and destination == source:
                raise interrupted
            return real_rename(path, destination)

        with monkeypatch.context() as patcher:
            patcher.setattr(Path, "read_bytes", read_at_phase)
            patcher.setattr(Path, "rename", rename_at_phase)
            with pytest.raises(interrupt_type) as caught:
                atomic_replace_if_unchanged(
                    source, b"MUTATED", expected=b"ORIGINAL", backup_path=backup
                )

        assert caught.value is interrupted
        assert source.exists(), "interruption left the normal source path absent"
        assert source.read_bytes() == backup.read_bytes() == b"ORIGINAL"
        assert (source.stat().st_dev, source.stat().st_ino) == original_identity
        assert set(tmp_path.iterdir()) == {source, backup}
        assert str(source) in " ".join(getattr(caught.value, "__notes__", []))

    @pytest.mark.parametrize("foreign_source", [False, True])
    def test_interrupted_restore_names_actual_surviving_original(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, foreign_source: bool
    ) -> None:
        """A blocked restoration retains the original and any foreign recreated source."""
        source = tmp_path / "source.py"
        backup = tmp_path / "source.py.bak"
        source.write_bytes(b"ORIGINAL")
        backup.write_bytes(b"ORIGINAL")
        real_read = Path.read_bytes

        def read_then_interrupt(path: Path) -> bytes:
            if path.name.endswith(".mutmut-displaced"):
                if foreign_source:
                    source.write_bytes(b"FOREIGN")
                raise KeyboardInterrupt("controlled cancellation")
            return real_read(path)

        real_rename = Path.rename

        def prevent_restore(path: Path, destination: Path) -> Path:
            if not foreign_source and path.name.endswith(".mutmut-displaced"):
                raise PermissionError("controlled restoration denial")
            return real_rename(path, destination)

        with monkeypatch.context() as patcher:
            patcher.setattr(Path, "read_bytes", read_then_interrupt)
            patcher.setattr(Path, "rename", prevent_restore)
            with pytest.raises(KeyboardInterrupt) as caught:
                atomic_replace_if_unchanged(
                    source, b"MUTATED", expected=b"ORIGINAL", backup_path=backup
                )

        displaced = list(tmp_path.glob(".*.mutmut-displaced"))
        assert len(displaced) == 1
        assert displaced[0].read_bytes() == backup.read_bytes() == b"ORIGINAL"
        assert source.exists() is foreign_source
        if foreign_source:
            assert source.read_bytes() == b"FOREIGN"
        assert list(tmp_path.glob(".*.mutmut-atomic-*.tmp")) == []
        notes = " ".join(getattr(caught.value, "__notes__", []))
        assert str(displaced[0]) in notes

    def test_cli_interrupt_reports_actual_recovery_without_applied_success(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The public apply command must expose recovery information on cancellation."""
        from click.testing import CliRunner

        from mutmut_win.cli import cli

        name, _config, source = _setup_apply_project(tmp_path, monkeypatch)
        before = source.read_bytes()
        real_read = Path.read_bytes

        def interrupt_displaced_read(path: Path) -> bytes:
            if path.name.endswith(".mutmut-displaced"):
                raise KeyboardInterrupt("controlled cancellation")
            return real_read(path)

        with monkeypatch.context() as patcher:
            patcher.setattr(Path, "read_bytes", interrupt_displaced_read)
            outcome = CliRunner().invoke(cli, ["apply", name])

        assert outcome.exit_code != 0
        assert "Applied mutant" not in outcome.output
        assert source.exists(), "CLI cancellation left the source absent"
        assert source.read_bytes() == before
        assert "restored" in outcome.stderr
        assert "src" in outcome.stderr and "mod.py" in outcome.stderr


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


class TestBackupPromotionAndRecovery:
    """AR-06 / C-002: reliable promotion into the known backup and a visible
    recovery path for every CAS/publication failure."""

    def test_promotion_into_existing_backup_leaves_no_residue(self, tmp_path: Path) -> None:
        """A pre-existing backup receives the displaced inode, no residue.

        Windows rename onto the existing backup used to fail silently and
        strand the true pre-apply content under a random sibling name while
        the known backup kept stale bytes.
        """
        target = tmp_path / "file.txt"
        backup = tmp_path / "file.bak"
        target.write_bytes(b"original")
        backup.write_bytes(b"stale older backup")

        result = atomic_replace_if_unchanged(
            target, b"replaced", expected=b"original", backup_path=backup
        )

        assert result is True
        assert target.read_bytes() == b"replaced"
        assert backup.read_bytes() == b"original"
        assert [p for p in tmp_path.iterdir() if p != target and p != backup] == []

    def test_late_share_delete_writer_bytes_land_in_named_backup(self, tmp_path: Path) -> None:
        """A retained FILE_SHARE_DELETE writer stays findable in the backup.

        The writer keeps its handle across the displacement and writes into
        the displaced inode after stage-4 verification; promotion must move
        that inode — late bytes included — onto the named backup path.
        """
        target = tmp_path / "source.py"
        backup = target.with_name(target.name + ".mutmut-orig.bak")
        target.write_bytes(b"original")
        backup.write_bytes(b"pre-written backup")
        late = b"late writer bytes"
        handle = _open_share_delete_writer(target)
        real_rename = Path.rename
        try:

            def racing_rename(source_path: Path, destination: Path) -> Path:
                result = real_rename(source_path, destination)
                if destination == target and "mutmut-atomic" in source_path.name:
                    # After the insertion rename (stage 5, past stage 4):
                    # write through the retained handle into the displaced
                    # inode, then let promotion run.
                    _write_via_handle(handle, late)
                return result

            with patch.object(Path, "rename", autospec=True, side_effect=racing_rename):
                result = atomic_replace_if_unchanged(
                    target, b"mutated", expected=b"original", backup_path=backup
                )

            assert result is True
            assert target.read_bytes() == b"mutated"
            assert backup.read_bytes() == late
            residue = [p for p in tmp_path.iterdir() if p != target and p != backup]
            assert residue == [], f"unexpected siblings: {residue}"
        finally:
            _KERNEL32.CloseHandle(handle)

    def test_promotion_failure_preserves_bytes_and_names_location(self, tmp_path: Path) -> None:
        """A failed promotion keeps the original and names where it is."""
        target = tmp_path / "file.txt"
        backup = tmp_path / "file.bak"
        target.write_bytes(b"original")
        backup.write_bytes(b"pre-written backup")
        real_replace = Path.replace

        def failing_promotion(source_path: Path, destination: Path) -> Path:
            if "mutmut-displaced" in source_path.name:
                raise PermissionError("promotion blocked")
            return real_replace(source_path, destination)

        with (
            patch.object(Path, "replace", autospec=True, side_effect=failing_promotion),
            pytest.raises(UnsafeAtomicWriteError, match="preserved at") as excinfo,
        ):
            atomic_replace_if_unchanged(
                target, b"replaced", expected=b"original", backup_path=backup
            )

        assert target.read_bytes() == b"replaced"
        displaced = list(tmp_path.glob(".*.mutmut-displaced"))
        assert len(displaced) == 1
        assert displaced[0].read_bytes() == b"original"
        assert str(displaced[0].resolve()) in str(excinfo.value)
        assert backup.read_bytes() == b"pre-written backup"

    def test_failed_restoration_names_surviving_location(self, tmp_path: Path) -> None:
        """When the displaced file cannot be restored, the error says so.

        A stage-4 content change whose restoration rename fails must keep
        the bytes under the displacement path and explicitly report the
        failed restoration plus the surviving location.
        """
        target = tmp_path / "source.py"
        target.write_bytes(b"original")
        real_rename = Path.rename

        def racing_rename(source_path: Path, destination: Path) -> Path:
            if source_path == target and "mutmut-displaced" in destination.name:
                target.write_bytes(b"foreign late write")
                return real_rename(source_path, destination)
            if "mutmut-displaced" in source_path.name and destination == target:
                raise PermissionError("restoration blocked")
            return real_rename(source_path, destination)

        with (
            patch.object(Path, "rename", autospec=True, side_effect=racing_rename),
            pytest.raises(AtomicPreconditionError, match="restoration failed") as excinfo,
        ):
            atomic_replace_if_unchanged(target, b"mutated", expected=b"original")

        displaced = list(tmp_path.glob(".*.mutmut-displaced"))
        assert len(displaced) == 1
        assert displaced[0].read_bytes() == b"foreign late write"
        assert str(displaced[0].resolve()) in str(excinfo.value)
        assert list(tmp_path.glob(".*.mutmut-atomic-*.tmp")) == []

    def test_stage1_abort_leaves_existing_backup_untouched(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A stage-1 abort has written nothing at all — not even the backup.

        apply used to write .mutmut-orig.bak before its stage-1 re-read, so
        an abort claimed 'nothing was overwritten' while a pre-existing
        backup from an earlier session had already been replaced.
        """
        mutant_name, config, source_path = _setup_apply_project(tmp_path, monkeypatch)
        backup = source_path.with_name(source_path.name + ".mutmut-orig.bak")
        backup.write_bytes(b"precious older backup")
        foreign = b"def add(a, b):\n    return a ** b  # raced before stage 1\n"

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

        with pytest.raises(StaleStagingError, match="nothing was written"):
            apply_mutant(mutant_name, config)

        assert backup.read_bytes() == b"precious older backup"
        assert source_path.read_bytes() == foreign
        assert list(source_path.parent.glob(".*.mutmut-atomic-*.tmp")) == []

    def test_apply_promotion_failure_reports_location(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """apply surfaces a promotion failure with the surviving location.

        The mutant IS applied at that point; hiding the stranded original
        behind a suppressed error (or reporting clean success) would break
        the recovery contract.
        """
        from mutmut_win.exceptions import MutmutWinError

        mutant_name, config, source_path = _setup_apply_project(tmp_path, monkeypatch)
        backup = source_path.with_name(source_path.name + ".mutmut-orig.bak")
        original_bytes = source_path.read_bytes()
        real_replace = Path.replace

        def failing_promotion(source_path: Path, destination: Path) -> Path:
            if "mutmut-displaced" in source_path.name:
                raise PermissionError("promotion blocked")
            return real_replace(source_path, destination)

        with (
            patch.object(Path, "replace", autospec=True, side_effect=failing_promotion),
            pytest.raises(MutmutWinError, match="preserved at") as excinfo,
        ):
            apply_mutant(mutant_name, config)

        # The publication itself succeeded; the original survives under the
        # named displacement path, not silently lost.
        displaced = list(source_path.parent.glob(".*.mutmut-displaced"))
        assert len(displaced) == 1
        assert displaced[0].read_bytes() == original_bytes
        assert displaced[0].name in str(excinfo.value)
        assert backup.read_bytes() == original_bytes


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

    def test_cli_names_recovery_location_on_foreign_recreate(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Foreign recreate: the CLI message names the surviving location.

        AR-06 / C-002: when a foreign writer recreates the path during
        displacement, the original survives only under its displacement
        path — the apply-level error translation must carry that exact
        location through to the visible CLI message.
        """
        from click.testing import CliRunner

        from mutmut_win.cli import cli

        mutant_name, config, source_path = _setup_apply_project(tmp_path, monkeypatch)
        recreated = b"def add(a, b):\n    return a % b  # recreated\n"
        original_bytes = source_path.read_bytes()
        source_name = source_path.name
        real_rename = Path.rename

        def racing_rename(source_path: Path, destination: Path) -> Path:
            result = real_rename(source_path, destination)
            if source_path.name == source_name and "mutmut-displaced" in destination.name:
                source_path.write_bytes(recreated)
            return result

        with (
            patch("mutmut_win.cli.load_config", return_value=config),
            patch.object(Path, "rename", autospec=True, side_effect=racing_rename),
        ):
            result = CliRunner().invoke(cli, ["apply", mutant_name])

        assert result.exit_code == 1, result.output
        assert "Applied mutant" not in result.output
        assert source_path.read_bytes() == recreated
        survivors = list(source_path.parent.glob(".*.mutmut-displaced"))
        assert len(survivors) == 1
        assert survivors[0].read_bytes() == original_bytes
        # The actual surviving location is named in the visible output.
        assert survivors[0].name in result.output
