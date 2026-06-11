"""Tests for source protection (Issue #75, audit cluster C1).

Two destructive findings:
- A3-CM-001: ``Path("mutants") / <absolute path>`` discards the left operand,
  so absolute ``paths_to_mutate`` made ``create_mutants_for_file`` write the
  trampoline code INTO the original source file.
- A4-UI-001/002/003: ``apply`` patched the first function with a matching
  name (wrong class), flipped LF->CRLF for the whole file, and wrote without
  backup/atomicity/staleness check.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest
from pydantic import ValidationError

from mutmut_win.config import MutmutConfig
from mutmut_win.file_setup import create_mutants_for_file, get_mutant_name
from mutmut_win.mutant_diff import apply_mutant

# ---------------------------------------------------------------------------
# Layer 1: config validator (A3-CM-001)
# ---------------------------------------------------------------------------


class TestAbsolutePathsToMutateRejected:
    def test_absolute_path_outside_cwd_rejected(self) -> None:
        outside = "C:\\definitely\\not\\under\\cwd" if os.name == "nt" else "/definitely/not/cwd"
        with pytest.raises(ValidationError, match="absolute"):
            MutmutConfig(paths_to_mutate=[outside])

    def test_absolute_path_under_cwd_is_relativized(self) -> None:
        absolute_src = str(Path.cwd() / "src")
        cfg = MutmutConfig(paths_to_mutate=[absolute_src])
        assert cfg.paths_to_mutate == ["src"]

    def test_relative_paths_unchanged(self) -> None:
        cfg = MutmutConfig(paths_to_mutate=["src/", "lib"])
        assert cfg.paths_to_mutate == ["src/", "lib"]


# ---------------------------------------------------------------------------
# Layer 2: write guard in create_mutants_for_file (defends the CLI
# model_copy bypass, A3-CM-004, and any future caller)
# ---------------------------------------------------------------------------


class TestWriteGuard:
    def test_refuses_to_overwrite_the_source_file(self, tmp_path: Path) -> None:
        source = "def f():\n    return 1\n"
        src_file = tmp_path / "mod.py"
        src_file.write_text(source, encoding="utf-8")

        # output_path == filename is exactly what Path("mutants")/<abs> yields.
        with pytest.raises(ValueError, match="source file itself"):
            create_mutants_for_file(src_file, src_file)

        assert src_file.read_text(encoding="utf-8") == source  # untouched


# ---------------------------------------------------------------------------
# apply safety (A4-UI-001/002/003)
# ---------------------------------------------------------------------------


def _setup_two_class_project(tmp_path: Path, newline: str = "\n") -> tuple[str, MutmutConfig]:
    """Create src/mod.py with A.greet + B.greet, generate real mutants, and
    return (qualified B-mutant name, config).  CWD must already be tmp_path."""
    source = (
        f"class A:{newline}"
        f"    def greet(self):{newline}"
        f'        return "aaa"{newline}'
        f"{newline}"
        f"class B:{newline}"
        f"    def greet(self):{newline}"
        f'        return "bbb"{newline}'
    )
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "mod.py").write_bytes(source.encode("utf-8"))
    mutants_out = tmp_path / "mutants" / "src"
    mutants_out.mkdir(parents=True)

    names, _warns = create_mutants_for_file(
        Path("src/mod.py"), Path("mutants/src/mod.py")
    )
    b_local = next(n for n in names if "ǁBǁ" in n)
    qualified = get_mutant_name(Path("src/mod.py"), b_local)
    cfg = MutmutConfig(paths_to_mutate=["src"], tests_dir=["tests/"])
    return qualified, cfg


class TestApplySafety:
    def test_apply_patches_the_correct_class(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        b_mutant, cfg = _setup_two_class_project(tmp_path)

        apply_mutant(b_mutant, cfg)

        content = (tmp_path / "src" / "mod.py").read_text(encoding="utf-8")
        assert '"aaa"' in content  # A.greet untouched
        assert '"bbb"' not in content  # B.greet mutated

    def test_apply_preserves_lf_line_endings(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        b_mutant, cfg = _setup_two_class_project(tmp_path, newline="\n")

        apply_mutant(b_mutant, cfg)

        raw = (tmp_path / "src" / "mod.py").read_bytes()
        assert b"\r\n" not in raw

    def test_apply_preserves_crlf_line_endings(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        b_mutant, cfg = _setup_two_class_project(tmp_path, newline="\r\n")

        apply_mutant(b_mutant, cfg)

        raw = (tmp_path / "src" / "mod.py").read_bytes()
        assert b"\r\n" in raw
        assert b"\n" not in raw.replace(b"\r\n", b"")  # no bare LF mixed in

    def test_apply_creates_backup_with_original_content(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        b_mutant, cfg = _setup_two_class_project(tmp_path)
        original = (tmp_path / "src" / "mod.py").read_bytes()

        apply_mutant(b_mutant, cfg)

        backup = tmp_path / "src" / "mod.py.mutmut-orig.bak"
        assert backup.exists()
        assert backup.read_bytes() == original

    def test_apply_refuses_stale_mutants(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        b_mutant, cfg = _setup_two_class_project(tmp_path)
        src_file = tmp_path / "src" / "mod.py"
        before = src_file.read_bytes()

        # Source modified AFTER the mutants were generated -> staging stale.
        future = time.time() + 60
        os.utime(src_file, (future, future))

        with pytest.raises(RuntimeError, match="re-run"):
            apply_mutant(b_mutant, cfg)
        assert src_file.read_bytes() == before  # untouched
