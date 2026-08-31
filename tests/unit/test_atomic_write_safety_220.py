"""Regression tests for sidecar-safe atomic workspace writes."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mutmut_win.atomic_file import (
    AtomicReplaceError,
    UnsafeAtomicWriteError,
    atomic_write_bytes,
    ensure_atomic_bytes,
)
from mutmut_win.models import SourceFileMutationData
from mutmut_win.mutant_diff import apply_mutant


def _make_link(link: Path, referent: Path, kind: str) -> None:
    if kind == "hardlink":
        os.link(referent, link)
        return
    try:
        link.symlink_to(referent)
    except OSError as exc:
        pytest.skip(f"symlinks are unavailable in this environment: {exc}")


def _assert_still_references(link: Path, referent: Path, kind: str) -> None:
    if kind == "hardlink":
        assert link.samefile(referent)
    else:
        assert link.is_symlink()
        assert link.resolve() == referent.resolve()


def _apply_project(tmp_path: Path) -> tuple[Path, bytes, MagicMock]:
    source = tmp_path / "src" / "mod.py"
    source.parent.mkdir(parents=True)
    original = b"def foo() -> int:\r\n    return 1\r\n"
    source.write_bytes(original)

    mutants = tmp_path / "mutants" / "src"
    mutants.mkdir(parents=True)
    (mutants / "mod.py").write_bytes(
        b"def x_foo__mutmut_orig() -> int:\r\n"
        b"    return 1\r\n\r\n"
        b"def x_foo__mutmut_1() -> int:\r\n"
        b"    return 2\r\n"
    )
    (mutants / "mod.py.meta").write_text(
        json.dumps(
            {
                "exit_code_by_key": {"mod.x_foo__mutmut_1": 0},
                "source_hash": hashlib.sha256(original).hexdigest(),
            }
        ),
        encoding="utf-8",
    )

    config = MagicMock()
    config.paths_to_mutate = ["src/"]
    config.should_ignore_for_mutation.return_value = False
    return source, original, config


@pytest.mark.parametrize("kind", ["hardlink", "symlink"])
def test_atomic_write_replaces_link_leaf_without_writing_referent(
    tmp_path: Path,
    kind: str,
) -> None:
    sentinel = tmp_path / "outside-sentinel.bin"
    sentinel.write_bytes(b"outside")
    target = tmp_path / "target.bin"
    _make_link(target, sentinel, kind)

    atomic_write_bytes(target, b"published")

    assert sentinel.read_bytes() == b"outside"
    assert target.read_bytes() == b"published"
    assert not target.is_symlink()
    assert not target.samefile(sentinel)


@pytest.mark.parametrize("kind", ["hardlink", "symlink"])
def test_idempotent_publish_never_accepts_an_identical_link_leaf(
    tmp_path: Path,
    kind: str,
) -> None:
    sentinel = tmp_path / "outside-sentinel.bin"
    sentinel.write_bytes(b"identical")
    target = tmp_path / "target.bin"
    _make_link(target, sentinel, kind)

    ensure_atomic_bytes(target, b"identical")

    assert sentinel.read_bytes() == b"identical"
    assert target.read_bytes() == b"identical"
    assert not target.is_symlink()
    assert not target.samefile(sentinel)


def test_idempotent_publish_accepts_replace_error_only_after_exact_verification(
    tmp_path: Path,
) -> None:
    target = tmp_path / "target.bin"
    target.write_bytes(b"identical winner")

    with (
        patch(
            "mutmut_win.atomic_file._regular_file_matches_bytes",
            side_effect=[False, True],
        ) as matches,
        patch(
            "mutmut_win.atomic_file.atomic_write_bytes",
            side_effect=AtomicReplaceError("simulated WinError 5"),
        ),
    ):
        ensure_atomic_bytes(target, b"identical winner")

    assert matches.call_count == 2


def test_idempotent_publish_does_not_replace_an_existing_exact_payload(
    tmp_path: Path,
) -> None:
    target = tmp_path / "target.bin"
    target.write_bytes(b"already published")

    with patch("mutmut_win.atomic_file.atomic_write_bytes") as strict_writer:
        ensure_atomic_bytes(target, b"already published")

    strict_writer.assert_not_called()


def test_idempotent_publish_preserves_replace_error_for_unverified_winner(
    tmp_path: Path,
) -> None:
    target = tmp_path / "target.bin"
    target.write_bytes(b"different winner")

    with (
        patch(
            "mutmut_win.atomic_file._regular_file_matches_bytes",
            side_effect=[False, False],
        ),
        patch(
            "mutmut_win.atomic_file.atomic_write_bytes",
            side_effect=AtomicReplaceError("simulated WinError 5"),
        ),
        pytest.raises(PermissionError, match="simulated WinError 5"),
    ):
        ensure_atomic_bytes(target, b"requested payload")


@pytest.mark.parametrize("kind", ["hardlink", "symlink"])
def test_meta_save_never_opens_predictable_tmp_sidecar(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    kind: str,
) -> None:
    monkeypatch.chdir(tmp_path)
    sentinel = tmp_path / "outside-meta-sentinel.json"
    sentinel.write_bytes(b"META-SENTINEL")
    predictable_tmp = tmp_path / "mutants" / "src" / "mod.py.meta.tmp"
    predictable_tmp.parent.mkdir(parents=True)
    _make_link(predictable_tmp, sentinel, kind)

    SourceFileMutationData(path="src/mod.py", exit_code_by_key={"mutant": 0}).save()

    assert sentinel.read_bytes() == b"META-SENTINEL"
    _assert_still_references(predictable_tmp, sentinel, kind)
    saved = json.loads((tmp_path / "mutants" / "src" / "mod.py.meta").read_text("utf-8"))
    assert saved["exit_code_by_key"] == {"mutant": 0}


@pytest.mark.parametrize("kind", ["hardlink", "symlink"])
def test_apply_replaces_backup_safely_and_ignores_predictable_apply_tmp(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    kind: str,
) -> None:
    monkeypatch.chdir(tmp_path)
    source, original, config = _apply_project(tmp_path)
    backup_sentinel = tmp_path / "outside-backup-sentinel.bin"
    apply_tmp_sentinel = tmp_path / "outside-apply-tmp-sentinel.bin"
    backup_sentinel.write_bytes(b"BACKUP-SENTINEL")
    apply_tmp_sentinel.write_bytes(b"APPLY-TMP-SENTINEL")
    backup = source.with_name(source.name + ".mutmut-orig.bak")
    predictable_tmp = source.with_name(source.name + ".mutmut-apply.tmp")
    _make_link(backup, backup_sentinel, kind)
    _make_link(predictable_tmp, apply_tmp_sentinel, kind)

    with patch(
        "mutmut_win.mutant_diff.walk_source_files",
        return_value=[Path("src/mod.py")],
    ):
        apply_mutant("mod.x_foo__mutmut_1", config)

    assert backup_sentinel.read_bytes() == b"BACKUP-SENTINEL"
    assert apply_tmp_sentinel.read_bytes() == b"APPLY-TMP-SENTINEL"
    assert backup.read_bytes() == original
    assert not backup.is_symlink()
    assert not backup.samefile(backup_sentinel)
    _assert_still_references(predictable_tmp, apply_tmp_sentinel, kind)
    assert source.read_bytes() == b"\r\ndef foo() -> int:\r\n    return 2\r\n"


def test_replace_failure_keeps_target_and_cleans_private_sibling(tmp_path: Path) -> None:
    target = tmp_path / "target.bin"
    target.write_bytes(b"original")

    with (
        patch.object(Path, "replace", autospec=True, side_effect=PermissionError("blocked")),
        pytest.raises(PermissionError, match="blocked"),
    ):
        atomic_write_bytes(target, b"replacement")

    assert target.read_bytes() == b"original"
    assert list(tmp_path.glob(".target.bin.mutmut-atomic-*.tmp")) == []


def test_apply_replace_failure_keeps_source_and_cleans_private_sibling(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    source, original, config = _apply_project(tmp_path)
    real_replace = Path.replace

    def fail_source_replace(temp: Path, destination: Path) -> Path:
        if Path(destination).resolve() == source.resolve():
            raise PermissionError("source replace blocked")
        return real_replace(temp, destination)

    with (
        patch.object(Path, "replace", autospec=True, side_effect=fail_source_replace),
        patch(
            "mutmut_win.mutant_diff.walk_source_files",
            return_value=[Path("src/mod.py")],
        ),
        pytest.raises(PermissionError, match="source replace blocked"),
    ):
        apply_mutant("mod.x_foo__mutmut_1", config)

    assert source.read_bytes() == original
    assert source.with_name(source.name + ".mutmut-orig.bak").read_bytes() == original
    assert list(source.parent.glob(".*.mutmut-atomic-*.tmp")) == []


def test_atomic_write_rejects_symlinked_parent(
    tmp_path: Path,
) -> None:
    real_parent = tmp_path / "outside"
    real_parent.mkdir()
    linked_parent = tmp_path / "linked"
    try:
        linked_parent.symlink_to(real_parent, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"directory symlinks are unavailable in this environment: {exc}")

    with pytest.raises(UnsafeAtomicWriteError, match=r"link indirection|reparse point"):
        atomic_write_bytes(linked_parent / "target.bin", b"must not escape")
    assert not (real_parent / "target.bin").exists()
