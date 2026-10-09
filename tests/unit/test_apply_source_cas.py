"""Compare-and-swap source protection during apply (M-005/M-114, issue #148)."""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import stat
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import BaseModel, Field

import mutmut_win.atomic_file as atomic_module
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


class _LeafSnapshot(BaseModel):
    """Bind bytes, identity and Windows attributes without changing the leaf."""

    content: bytes
    device: int
    inode: int
    mode: int
    attributes: int


def _snapshot_leaf(path: Path) -> _LeafSnapshot:
    current = path.lstat()
    return _LeafSnapshot(
        content=path.read_bytes(),
        device=current.st_dev,
        inode=current.st_ino,
        mode=current.st_mode,
        attributes=current.st_file_attributes,
    )


class _RetryCalls(BaseModel):
    """Record requested delays independently of wall-clock scheduling."""

    delays: list[float] = Field(default_factory=list)


class _HeldSibling(BaseModel):
    """Bind the actual private sibling observed before insertion."""

    path: Path | None = None
    identity: tuple[int, int] | None = None


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
        assert "src" in outcome.stderr
        assert "mod.py" in outcome.stderr

    @pytest.mark.parametrize("phase", ["displacement", "insertion", "promotion"])
    @pytest.mark.parametrize("late_write", [False, True])
    def test_interrupt_after_rename_effect_preserves_original_identity(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, phase: str, late_write: bool
    ) -> None:
        """Real rename effects and retained-handle writes determine recovery state."""
        source = tmp_path / "source.py"
        backup = tmp_path / "source.py.bak"
        source.write_bytes(b"ORIGINAL")
        backup.write_bytes(b"ORIGINAL")
        original_identity = (source.stat().st_dev, source.stat().st_ino)
        handle = _open_share_delete_writer(source)
        interrupted = KeyboardInterrupt("cancel after actual rename")
        real_rename = Path.rename
        real_replace = Path.replace

        def cancel_after_effect() -> None:
            if late_write:
                _write_via_handle(handle, b"LATE-WRITER")
            raise interrupted

        def rename_then_interrupt(path: Path, destination: Path) -> Path:
            result = real_rename(path, destination)
            if (phase == "displacement" and destination.name.endswith(".mutmut-displaced")) or (
                phase == "insertion" and ".mutmut-atomic-" in path.name and destination == source
            ):
                cancel_after_effect()
            return result

        def promote_then_interrupt(path: Path, destination: Path) -> Path:
            result = real_replace(path, destination)
            if phase == "promotion" and path.name.endswith(".mutmut-displaced"):
                cancel_after_effect()
            return result

        try:
            with monkeypatch.context() as patcher:
                patcher.setattr(Path, "rename", rename_then_interrupt)
                patcher.setattr(Path, "replace", promote_then_interrupt)
                with pytest.raises(KeyboardInterrupt) as caught:
                    atomic_replace_if_unchanged(
                        source, b"MUTATED", expected=b"ORIGINAL", backup_path=backup
                    )
        finally:
            _KERNEL32.CloseHandle(handle)

        assert caught.value is interrupted
        displaced = list(tmp_path.glob(".*.mutmut-displaced"))
        if phase == "displacement":
            recovery = source
            assert displaced == []
        elif phase == "insertion":
            assert len(displaced) == 1
            recovery = displaced[0]
            assert source.read_bytes() == b"MUTATED"
        else:
            recovery = backup
            assert displaced == []
            assert source.read_bytes() == b"MUTATED"
        assert recovery.read_bytes() == (b"LATE-WRITER" if late_write else b"ORIGINAL")
        assert (recovery.stat().st_dev, recovery.stat().st_ino) == original_identity
        assert str(recovery) in " ".join(getattr(interrupted, "__notes__", []))
        assert set(tmp_path.iterdir()) == {source, backup, *displaced}

    def test_interrupt_does_not_restore_foreign_displacement_leaf(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A real displaced-name replacement is not granted original ownership."""
        source = tmp_path / "source.py"
        backup = tmp_path / "source.py.bak"
        saved = tmp_path / "saved-original"
        source.write_bytes(b"ORIGINAL")
        backup.write_bytes(b"ORIGINAL")
        real_read = Path.read_bytes

        def swap_then_interrupt(path: Path) -> bytes:
            if path.name.endswith(".mutmut-displaced"):
                path.rename(saved)
                path.write_bytes(b"FOREIGN")
                raise KeyboardInterrupt("cancel after foreign replacement")
            return real_read(path)

        with monkeypatch.context() as patcher:
            patcher.setattr(Path, "read_bytes", swap_then_interrupt)
            with pytest.raises(KeyboardInterrupt) as caught:
                atomic_replace_if_unchanged(
                    source, b"MUTATED", expected=b"ORIGINAL", backup_path=backup
                )

        displaced = list(tmp_path.glob(".*.mutmut-displaced"))
        assert len(displaced) == 1
        assert displaced[0].read_bytes() == b"FOREIGN"
        assert not source.exists()
        assert saved.read_bytes() == backup.read_bytes() == b"ORIGINAL"
        assert "could not be verified" in " ".join(getattr(caught.value, "__notes__", []))
        assert set(tmp_path.iterdir()) == {backup, saved, *displaced}

    def test_real_nonsharing_handle_blocks_restore_and_keeps_recovery_visible(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A real open CRT handle denies rename until after the cancellation returns."""
        from contextlib import ExitStack

        source = tmp_path / "source.py"
        source.write_bytes(b"ORIGINAL")
        real_read = Path.read_bytes
        with ExitStack() as held_files:

            def hold_then_interrupt(path: Path) -> bytes:
                if path.name.endswith(".mutmut-displaced"):
                    held_files.enter_context(path.open("rb"))
                    raise KeyboardInterrupt("cancel with retained nonsharing handle")
                return real_read(path)

            with monkeypatch.context() as patcher:
                patcher.setattr(Path, "read_bytes", hold_then_interrupt)
                with pytest.raises(KeyboardInterrupt) as caught:
                    atomic_replace_if_unchanged(source, b"MUTATED", expected=b"ORIGINAL")

            displaced = list(tmp_path.glob(".*.mutmut-displaced"))
            assert len(displaced) == 1
            assert not source.exists()
            assert displaced[0].read_bytes() == b"ORIGINAL"
            assert str(displaced[0]) in " ".join(getattr(caught.value, "__notes__", []))
            assert set(tmp_path.iterdir()) == {*displaced}


class TestReadonlyApplyAndPromotion:
    """S3-014: early readonly rejection and bounded backup promotion."""

    @pytest.mark.parametrize("cli_mode", [False, True])
    @pytest.mark.parametrize("readonly_leaf", ["source-no-backup", "source", "backup"])
    def test_readonly_rejection_preserves_source_and_backup(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        readonly_leaf: str,
        cli_mode: bool,
    ) -> None:
        from click.testing import CliRunner

        from mutmut_win.cli import cli
        from mutmut_win.exceptions import MutmutWinError

        name, config, source = _setup_apply_project(tmp_path, monkeypatch)
        backup = source.with_name(source.name + ".mutmut-orig.bak")
        if readonly_leaf != "source-no-backup":
            backup.write_bytes(b"OLDER BACKUP MUST STAY")
        readonly = backup if readonly_leaf == "backup" else source
        readonly.chmod(stat.S_IREAD)
        source_before = _snapshot_leaf(source)
        backup_before = _snapshot_leaf(backup) if backup.exists() else None
        try:
            if cli_mode:
                result = CliRunner().invoke(cli, ["apply", name])
                assert result.exit_code == 1
                assert "Applied mutant" not in result.output
                diagnostic = result.stderr
            else:
                with pytest.raises((OSError, MutmutWinError)) as caught:
                    apply_mutant(name, config)
                diagnostic = str(caught.value)
            assert _snapshot_leaf(source) == source_before
            assert (_snapshot_leaf(backup) if backup.exists() else None) == backup_before
            assert "read-only" in diagnostic
            assert str(readonly) in diagnostic
            assert list(source.parent.glob(".*.mutmut-*")) == []
        finally:
            for owned in (source, backup):
                if owned.exists():
                    owned.chmod(stat.S_IWRITE)

    @pytest.mark.parametrize("release", [False, True])
    def test_real_backup_handle_has_bounded_promotion_retry(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, release: bool
    ) -> None:
        source = tmp_path / "source.py"
        backup = tmp_path / "source.py.bak"
        source.write_bytes(b"ORIGINAL")
        backup.write_bytes(b"STABLE BACKUP")
        before = _snapshot_leaf(source)
        backup_before = _snapshot_leaf(backup)
        calls = _RetryCalls()
        with backup.open("rb") as held:

            def release_during_wait(seconds: float) -> None:
                calls.delays.append(seconds)
                if release:
                    held.close()

            monkeypatch.setattr(atomic_module.time, "sleep", release_during_wait)
            if release:
                assert atomic_replace_if_unchanged(
                    source, b"MUTATED", expected=b"ORIGINAL", backup_path=backup
                )
            else:
                with pytest.raises(atomic_module.AtomicBackupPromotionError) as caught:
                    atomic_replace_if_unchanged(
                        source, b"MUTATED", expected=b"ORIGINAL", backup_path=backup
                    )
                displaced = list(tmp_path.glob(".*.mutmut-displaced"))
                assert len(displaced) == 1
                assert _snapshot_leaf(displaced[0]) == before
                assert _snapshot_leaf(backup) == backup_before
                assert str(displaced[0]) in str(caught.value)
                assert isinstance(caught.value.__cause__, PermissionError)
        assert source.read_bytes() == b"MUTATED"
        assert calls.delays == ([0.01] if release else [0.01, 0.02, 0.05, 0.1])
        if release:
            assert _snapshot_leaf(backup) == before
            assert set(tmp_path.iterdir()) == {source, backup}

    def test_real_backup_handle_released_by_timer(self, tmp_path: Path) -> None:
        """A real sharing violation is retried until an independently timed release."""
        from threading import Timer

        source = tmp_path / "source.py"
        backup = tmp_path / "source.py.bak"
        source.write_bytes(b"ORIGINAL")
        backup.write_bytes(b"STABLE BACKUP")
        real_replace = Path.replace
        with backup.open("rb") as held:
            timer = Timer(0.05, held.close)

            def start_timer_after_failure(path: Path, destination: Path) -> Path:
                try:
                    return real_replace(path, destination)
                except PermissionError:
                    if timer.ident is None:
                        timer.start()
                    raise

            try:
                with patch.object(
                    Path, "replace", autospec=True, side_effect=start_timer_after_failure
                ):
                    assert atomic_replace_if_unchanged(
                        source, b"MUTATED", expected=b"ORIGINAL", backup_path=backup
                    )
                assert timer.ident is not None
            finally:
                timer.cancel()
                if timer.ident is not None:
                    timer.join(timeout=2)
                assert not timer.is_alive()
        assert source.read_bytes() == b"MUTATED"
        assert backup.read_bytes() == b"ORIGINAL"
        assert set(tmp_path.iterdir()) == {source, backup}

    @pytest.mark.parametrize("foreign_backup", [False, True])
    def test_promotion_wait_keeps_late_writer_and_foreign_backup(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, foreign_backup: bool
    ) -> None:
        """Waiting cannot replace a new backup owner or lose late original-handle bytes."""
        source = tmp_path / "source.py"
        backup = tmp_path / "source.py.bak"
        saved_backup = tmp_path / "saved-backup"
        source.write_bytes(b"ORIGINAL")
        backup.write_bytes(b"STABLE BACKUP")
        original_identity = (source.stat().st_dev, source.stat().st_ino)
        writer = _open_share_delete_writer(source)
        calls = _RetryCalls()
        try:
            with backup.open("rb") as held:

                def change_during_wait(seconds: float) -> None:
                    calls.delays.append(seconds)
                    held.close()
                    _write_via_handle(writer, b"LATE ORIGINAL")
                    if foreign_backup:
                        backup.rename(saved_backup)
                        backup.write_bytes(b"FOREIGN BACKUP")

                monkeypatch.setattr(atomic_module.time, "sleep", change_during_wait)
                if foreign_backup:
                    with pytest.raises(
                        atomic_module.AtomicBackupPromotionError, match="backup changed"
                    ):
                        atomic_replace_if_unchanged(
                            source, b"MUTATED", expected=b"ORIGINAL", backup_path=backup
                        )
                else:
                    assert atomic_replace_if_unchanged(
                        source, b"MUTATED", expected=b"ORIGINAL", backup_path=backup
                    )
        finally:
            _KERNEL32.CloseHandle(writer)
        assert calls.delays == [0.01]
        assert source.read_bytes() == b"MUTATED"
        recovery = next(tmp_path.glob(".*.mutmut-displaced")) if foreign_backup else backup
        assert recovery.read_bytes() == b"LATE ORIGINAL"
        assert (recovery.stat().st_dev, recovery.stat().st_ino) == original_identity
        if foreign_backup:
            assert backup.read_bytes() == b"FOREIGN BACKUP"
            assert saved_backup.read_bytes() == b"STABLE BACKUP"
        else:
            assert set(tmp_path.iterdir()) == {source, backup}


class TestCasFailedInsertionCleanup:
    """S3-018: report actual restoration and clean only a verified own temp."""

    @pytest.mark.parametrize("release", [False, True])
    def test_failed_insertion_retries_cleanup_and_reports_real_paths(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, release: bool
    ) -> None:
        from contextlib import ExitStack

        source = tmp_path / "source.py"
        backup = tmp_path / "source.py.bak"
        source.write_bytes(b"ORIGINAL")
        backup.write_bytes(b"STABLE BACKUP")
        source_before = _snapshot_leaf(source)
        backup_before = _snapshot_leaf(backup)
        state = _HeldSibling()
        calls = _RetryCalls()
        real_check = atomic_module._checked_temp
        with ExitStack() as held:

            def hold_temp(path: Path, identity: tuple[int, int]) -> None:
                real_check(path, identity)
                state.path, state.identity = path, identity
                held.enter_context(path.open("rb"))

            def release_after_insertion_failed(seconds: float) -> None:
                # Cleanup must start only after insertion failed and restoration ran.
                assert _snapshot_leaf(source) == source_before
                assert list(tmp_path.glob(".*.mutmut-displaced")) == []
                calls.delays.append(seconds)
                if release:
                    held.close()

            monkeypatch.setattr(atomic_module, "_checked_temp", hold_temp)
            monkeypatch.setattr(atomic_module.time, "sleep", release_after_insertion_failed)
            with pytest.raises(OSError, match="cannot insert replacement") as caught:
                atomic_replace_if_unchanged(
                    source, b"MUTATED", expected=b"ORIGINAL", backup_path=backup
                )
            assert _snapshot_leaf(source) == source_before
            assert _snapshot_leaf(backup) == backup_before
            diagnostic = str(caught.value)
            assert f"restored to {source}" in diagnostic
            assert "cannot insert replacement" in diagnostic
            assert "WinError 32" in diagnostic
            cause: BaseException = caught.value
            while cause.__cause__ is not None:
                cause = cause.__cause__
            assert isinstance(cause, PermissionError)
            assert cause.winerror == 32
            assert calls.delays == ([0.01] if release else [0.01, 0.02, 0.05, 0.1])
            assert state.path is not None
            if release:
                assert set(tmp_path.iterdir()) == {source, backup}
            else:
                assert state.path.read_bytes() == b"MUTATED"
                assert (state.path.stat().st_dev, state.path.stat().st_ino) == state.identity
                assert f"owned temporary file remains at {state.path}" in diagnostic

    def test_cleanup_retry_preserves_readonly_foreign_recreate(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from contextlib import ExitStack

        source = tmp_path / "source.py"
        saved = tmp_path / "saved-owned-temp"
        source.write_bytes(b"ORIGINAL")
        state = _HeldSibling()
        real_check = atomic_module._checked_temp
        with ExitStack() as held:

            def hold_temp(path: Path, identity: tuple[int, int]) -> None:
                real_check(path, identity)
                state.path, state.identity = path, identity
                held.enter_context(path.open("rb"))

            def replace_with_foreign(_seconds: float) -> None:
                assert source.read_bytes() == b"ORIGINAL"
                held.close()
                assert state.path is not None
                state.path.rename(saved)
                state.path.write_bytes(b"FOREIGN")
                state.path.chmod(stat.S_IREAD)

            monkeypatch.setattr(atomic_module, "_checked_temp", hold_temp)
            monkeypatch.setattr(atomic_module.time, "sleep", replace_with_foreign)
            with pytest.raises(OSError, match="cannot insert replacement"):
                atomic_replace_if_unchanged(source, b"MUTATED", expected=b"ORIGINAL")
        assert state.path is not None
        try:
            assert state.path.read_bytes() == b"FOREIGN"
            assert state.path.stat().st_file_attributes & stat.FILE_ATTRIBUTE_READONLY
            assert saved.read_bytes() == b"MUTATED"
            assert source.read_bytes() == b"ORIGINAL"
        finally:
            state.path.chmod(stat.S_IWRITE)

    def test_cli_reports_persistent_owned_temp_and_restored_source(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from contextlib import ExitStack

        from click.testing import CliRunner

        from mutmut_win.cli import cli

        name, _config, source = _setup_apply_project(tmp_path, monkeypatch)
        before = _snapshot_leaf(source)
        state = _HeldSibling()
        real_check = atomic_module._checked_temp
        with ExitStack() as held:

            def hold_source_temp(path: Path, identity: tuple[int, int]) -> None:
                real_check(path, identity)
                if path.name.startswith(f".{source.name}.mutmut-atomic-"):
                    state.path, state.identity = path, identity
                    held.enter_context(path.open("rb"))

            monkeypatch.setattr(atomic_module, "_checked_temp", hold_source_temp)
            result = CliRunner().invoke(cli, ["apply", name])
            assert result.exit_code == 1
            assert "Applied mutant" not in result.output
            assert _snapshot_leaf(source) == before
            assert state.path is not None
            assert state.path.exists()
            assert "restored to" in result.stderr
            assert f"owned temporary file remains at {state.path}" in result.stderr
            assert "cannot insert replacement" in result.stderr


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
