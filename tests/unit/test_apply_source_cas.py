"""Compare-and-swap source protection during apply (M-005/M-114, issue #148)."""

from __future__ import annotations

from pathlib import Path

import pytest

from mutmut_win.atomic_file import AtomicPreconditionError, atomic_replace_if_unchanged
from mutmut_win.config import MutmutConfig
from mutmut_win.exceptions import StaleStagingError
from mutmut_win.mutant_diff import apply_mutant

_SOURCE = "def add(a, b):\n    return a + b\n"


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

        real_parse = md.parse_module_preserving_newlines
        call_count = 0

        def racing_parse(text: str):
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
