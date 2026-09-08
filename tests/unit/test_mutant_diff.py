"""Unit tests for mutmut_win.mutant_diff.

Tests cover find_mutant, read_mutants_module, read_orig_module,
find_top_level_function_or_method, read_original_function,
read_mutant_function, get_diff_for_mutant, and apply_mutant.
"""

from __future__ import annotations

import codecs
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import libcst as cst
import pytest

from mutmut_win.constants import Profile
from mutmut_win.exceptions import StaleStagingError
from mutmut_win.file_setup import create_mutants_for_file
from mutmut_win.models import SourceFileMutationData
from mutmut_win.mutant_diff import (
    apply_mutant,
    find_mutant,
    find_top_level_function_or_method,
    get_diff_for_mutant,
    read_mutant_function,
    read_mutants_module,
    read_orig_module,
    read_original_function,
    render_function_diff,
    render_function_diff_bytes,
)
from mutmut_win.mutation import mutate_file_contents
from mutmut_win.test_mapping import function_definition_location_from_key

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

_ORIG_SOURCE = """\
def x_foo__mutmut_orig() -> int:
    return 1

def x_foo__mutmut_1() -> int:
    return 2
"""

_PLAIN_SOURCE = """\
def foo() -> int:
    return 1
"""


def _make_config(paths: list[str] | None = None) -> MagicMock:
    """Return a minimal MutmutConfig mock."""
    cfg = MagicMock()
    cfg.paths_to_mutate = paths or ["src/"]
    cfg.should_ignore_for_mutation.return_value = False
    return cfg


# ---------------------------------------------------------------------------
# read_mutants_module
# ---------------------------------------------------------------------------


class TestReadMutantsModule:
    def test_reads_file_under_mutants_dir(self, tmp_path: Path) -> None:
        mutants = tmp_path / "mutants" / "src"
        mutants.mkdir(parents=True)
        (mutants / "mod.py").write_text(_ORIG_SOURCE, encoding="utf-8")

        import os

        orig = Path.cwd()
        os.chdir(tmp_path)
        try:
            module = read_mutants_module(Path("src/mod.py"))
        finally:
            os.chdir(orig)

        assert isinstance(module, cst.Module)

    def test_accepts_str_path(self, tmp_path: Path) -> None:
        mutants = tmp_path / "mutants"
        mutants.mkdir()
        (mutants / "mod.py").write_text("x = 1\n", encoding="utf-8")

        import os

        orig = Path.cwd()
        os.chdir(tmp_path)
        try:
            module = read_mutants_module("mod.py")
        finally:
            os.chdir(orig)

        assert isinstance(module, cst.Module)


# ---------------------------------------------------------------------------
# read_orig_module
# ---------------------------------------------------------------------------


class TestReadOrigModule:
    def test_reads_source_file(self, tmp_path: Path) -> None:
        src = tmp_path / "src" / "mod.py"
        src.parent.mkdir(parents=True)
        src.write_text(_PLAIN_SOURCE, encoding="utf-8")

        module = read_orig_module(src)
        assert isinstance(module, cst.Module)

    def test_accepts_str_path(self, tmp_path: Path) -> None:
        src = tmp_path / "mod.py"
        src.write_text(_PLAIN_SOURCE, encoding="utf-8")

        module = read_orig_module(str(src))
        assert isinstance(module, cst.Module)


# ---------------------------------------------------------------------------
# find_top_level_function_or_method
# ---------------------------------------------------------------------------


class TestFindTopLevelFunctionOrMethod:
    def test_finds_top_level_function(self) -> None:
        module = cst.parse_module("def foo() -> int:\n    return 1\n")
        result = find_top_level_function_or_method(module, "foo")
        assert result is not None
        assert result.name.value == "foo"

    def test_finds_method_in_class(self) -> None:
        source = "class MyClass:\n    def bar(self) -> None:\n        pass\n"
        module = cst.parse_module(source)
        result = find_top_level_function_or_method(module, "bar")
        assert result is not None
        assert result.name.value == "bar"

    def test_returns_none_for_missing(self) -> None:
        module = cst.parse_module("x = 1\n")
        result = find_top_level_function_or_method(module, "missing")
        assert result is None

    def test_uses_trailing_component_after_dot(self) -> None:
        module = cst.parse_module("def baz() -> None:\n    pass\n")
        result = find_top_level_function_or_method(module, "some.module.baz")
        assert result is not None
        assert result.name.value == "baz"


# ---------------------------------------------------------------------------
# read_original_function
# ---------------------------------------------------------------------------


class TestReadOriginalFunction:
    def test_extracts_orig_copy_and_renames(self) -> None:
        # Mutant name format: "<module>.<mangled_name>__mutmut_<n>"
        # mangled_name_from_mutant_name("src.mod.x_foo__mutmut_1") → "src.mod.x_foo"
        # rpartition(".") → ("src.mod", ".", "x_foo") → "x_foo".startswith("x_") → name = "foo"
        # orig_copy name in CST: "x_foo__mutmut_orig"
        source = """\
def x_foo__mutmut_orig() -> int:
    return 1

def x_foo__mutmut_1() -> int:
    return 2
"""
        module = cst.parse_module(source)
        result = read_original_function(module, "src.mod.x_foo__mutmut_1")
        assert isinstance(result, cst.FunctionDef)
        assert result.name.value == "foo"

    def test_raises_file_not_found_when_missing(self) -> None:
        module = cst.parse_module("x = 1\n")
        with pytest.raises(FileNotFoundError, match="Could not find original function"):
            read_original_function(module, "mod.x_baz__mutmut_1")


# ---------------------------------------------------------------------------
# read_mutant_function
# ---------------------------------------------------------------------------


class TestReadMutantFunction:
    def test_extracts_mutant_and_renames(self) -> None:
        source = """\
def x_foo__mutmut_orig() -> int:
    return 1

def x_foo__mutmut_1() -> int:
    return 2
"""
        module = cst.parse_module(source)
        result = read_mutant_function(module, "src.mod.x_foo__mutmut_1")
        assert isinstance(result, cst.FunctionDef)
        assert result.name.value == "foo"

    def test_raises_file_not_found_when_missing(self) -> None:
        module = cst.parse_module("x = 1\n")
        with pytest.raises(FileNotFoundError, match="Could not find mutant function"):
            read_mutant_function(module, "mod.x_baz__mutmut_1")


# ---------------------------------------------------------------------------
# find_mutant
# ---------------------------------------------------------------------------


class TestFindMutant:
    def test_finds_mutant_in_source_file_data(self, tmp_path: Path) -> None:
        import os

        orig = Path.cwd()
        os.chdir(tmp_path)
        try:
            mutants_dir = tmp_path / "mutants"
            mutants_dir.mkdir()
            src_dir = tmp_path / "src"
            src_dir.mkdir()
            src_file = src_dir / "mod.py"
            src_file.write_text(_PLAIN_SOURCE, encoding="utf-8")

            # Write meta file so SourceFileMutationData.load() finds the mutant.
            # Mutant key uses dotted format: mod.x_foo__mutmut_1 (strip "src." prefix).
            meta_path = mutants_dir / "src" / "mod.py.meta"
            meta_path.parent.mkdir(parents=True)
            meta_path.write_text(
                json.dumps({"exit_code_by_key": {"mod.x_foo__mutmut_1": 0}}),
                encoding="utf-8",
            )

            config = _make_config(paths=["src/"])
            with patch(
                "mutmut_win.mutant_diff.walk_source_files",
                return_value=[Path("src/mod.py")],
            ):
                result = find_mutant("mod.x_foo__mutmut_1", config)

            assert Path(result.path) == Path("src/mod.py")
        finally:
            os.chdir(orig)

    def test_raises_when_not_found(self, tmp_path: Path) -> None:
        import os

        orig = Path.cwd()
        os.chdir(tmp_path)
        try:
            (tmp_path / "mutants").mkdir()
            config = _make_config()
            with (
                patch("mutmut_win.mutant_diff.walk_source_files", return_value=[]),
                pytest.raises(FileNotFoundError, match="Could not find mutant"),
            ):
                find_mutant("mod.x_missing__mutmut_1", config)
        finally:
            os.chdir(orig)


# ---------------------------------------------------------------------------
# get_diff_for_mutant
# ---------------------------------------------------------------------------


class TestGetDiffForMutant:
    def test_returns_nonempty_diff(self, tmp_path: Path) -> None:
        import os

        orig = Path.cwd()
        os.chdir(tmp_path)
        try:
            mutants_src = tmp_path / "mutants" / "src"
            mutants_src.mkdir(parents=True)
            src_dir = tmp_path / "src"
            src_dir.mkdir()
            src_file = src_dir / "mod.py"
            src_file.write_text(_PLAIN_SOURCE, encoding="utf-8")

            # Write mutants file with both _orig and _1 variants.
            # CST function names: "x_foo__mutmut_orig" and "x_foo__mutmut_1"
            # (not prefixed with module path — those are just Python function names).
            mutant_source = """\
def x_foo__mutmut_orig() -> int:
    return 1

def x_foo__mutmut_1() -> int:
    return 2
"""
            staged_file = mutants_src / "mod.py"
            staged_file.write_text(mutant_source, encoding="utf-8")

            # Write meta so find_mutant can locate it.
            meta_path = tmp_path / "mutants" / "src" / "mod.py.meta"
            meta_path.write_text(
                json.dumps(
                    {
                        "exit_code_by_key": {"mod.x_foo__mutmut_1": 0},
                        "source_hash": hashlib.sha256(src_file.read_bytes()).hexdigest(),
                        "generated_hash": hashlib.sha256(staged_file.read_bytes()).hexdigest(),
                    }
                ),
                encoding="utf-8",
            )

            config = _make_config(paths=["src/"])
            with patch(
                "mutmut_win.mutant_diff.walk_source_files",
                return_value=[Path("src/mod.py")],
            ):
                diff = get_diff_for_mutant("mod.x_foo__mutmut_1", config)

            assert "---" in diff or "@@" in diff
        finally:
            os.chdir(orig)

    def test_raises_on_missing_mutant(self, tmp_path: Path) -> None:
        import os

        orig = Path.cwd()
        os.chdir(tmp_path)
        try:
            (tmp_path / "mutants").mkdir()
            config = _make_config()
            with (
                patch("mutmut_win.mutant_diff.walk_source_files", return_value=[]),
                pytest.raises(FileNotFoundError),
            ):
                get_diff_for_mutant("mod.x_missing__mutmut_99", config)
        finally:
            os.chdir(orig)


# ---------------------------------------------------------------------------
# apply_mutant
# ---------------------------------------------------------------------------


class TestApplyMutant:
    def test_applies_mutant_to_source_file(self, tmp_path: Path) -> None:
        import os

        orig = Path.cwd()
        os.chdir(tmp_path)
        try:
            src_dir = tmp_path / "src"
            src_dir.mkdir()
            src_file = src_dir / "mod.py"
            # Original source contains the function that will be patched.
            src_file.write_text(_PLAIN_SOURCE, encoding="utf-8")

            mutants_src = tmp_path / "mutants" / "src"
            mutants_src.mkdir(parents=True)
            # Mutants file: x_foo__mutmut_orig has original body, x_foo__mutmut_1 has mutated body.
            mutant_source = """\
def x_foo__mutmut_orig() -> int:
    return 1

def x_foo__mutmut_1() -> int:
    return 2
"""
            staged_file = mutants_src / "mod.py"
            staged_file.write_text(mutant_source, encoding="utf-8")

            meta_path = tmp_path / "mutants" / "src" / "mod.py.meta"
            meta_path.write_text(
                json.dumps(
                    {
                        "exit_code_by_key": {"mod.x_foo__mutmut_1": 0},
                        "source_hash": hashlib.sha256(src_file.read_bytes()).hexdigest(),
                        "generated_hash": hashlib.sha256(staged_file.read_bytes()).hexdigest(),
                    }
                ),
                encoding="utf-8",
            )

            config = _make_config(paths=["src/"])
            with patch(
                "mutmut_win.mutant_diff.walk_source_files",
                return_value=[Path("src/mod.py")],
            ):
                apply_mutant("mod.x_foo__mutmut_1", config)

            result = src_file.read_text(encoding="utf-8")
            assert "return 2" in result
        finally:
            os.chdir(orig)

    @pytest.mark.parametrize("collision_name", ["f__mutmut", "_mutmut_target", "_mutmut"])
    def test_reserved_boundary_applies_to_exact_source_function(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        collision_name: str,
    ) -> None:
        """A delimiter formed across any generated boundary must stay reversible."""
        monkeypatch.chdir(tmp_path)
        source = f"""\
def f():
    return 100

def {collision_name}():
    return 1 + 1
"""
        source_path = tmp_path / "src" / "pkg__mutmut_tools" / "mod.py"
        source_path.parent.mkdir(parents=True)
        source_path.write_text(source, encoding="utf-8")

        generated, names = mutate_file_contents(
            "src/pkg__mutmut_tools/mod.py", source, active_profile=Profile.BASIC
        )
        qualified_prefix = "pkg__mutmut_tools.mod"
        target = next(
            name
            for name in names
            if function_definition_location_from_key(f"{qualified_prefix}.{name}").function_name
            == collision_name
        )
        assert target.startswith("xq_")

        mutant_path = tmp_path / "mutants" / "src" / "pkg__mutmut_tools" / "mod.py"
        mutant_path.parent.mkdir(parents=True)
        mutant_path.write_text(generated, encoding="utf-8")
        (mutant_path.parent / "mod.py.meta").write_text(
            json.dumps(
                {
                    "exit_code_by_key": {f"{qualified_prefix}.{target}": 0},
                    "source_hash": hashlib.sha256(source_path.read_bytes()).hexdigest(),
                    "generated_hash": hashlib.sha256(mutant_path.read_bytes()).hexdigest(),
                }
            ),
            encoding="utf-8",
        )

        config = _make_config(paths=["src/"])
        with patch(
            "mutmut_win.mutant_diff.walk_source_files",
            return_value=[Path("src/pkg__mutmut_tools/mod.py")],
        ):
            apply_mutant(f"{qualified_prefix}.{target}", config)

        applied = source_path.read_text(encoding="utf-8")
        assert "def f():\n    return 100" in applied
        assert applied != source

    def test_apply_preserves_pep263_source_encoding(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        source_text = (
            "# coding: cp1252\nLABEL = 'café'\n\ndef add(value=1):\n    return value + 1\n"
        )
        source_bytes = source_text.encode("cp1252")
        source_path = tmp_path / "src" / "legacy.py"
        source_path.parent.mkdir(parents=True)
        source_path.write_bytes(source_bytes)
        staged_path = tmp_path / "mutants" / "src" / "legacy.py"

        local_names, warnings, _ = create_mutants_for_file(
            source_path,
            staged_path,
            active_profile=Profile.BASIC,
        )
        assert local_names
        assert warnings == []
        metadata = SourceFileMutationData(path="src/legacy.py")
        metadata.load()
        mutant_name = next(iter(metadata.exit_code_by_key))
        config = _make_config(paths=["src/"])

        with patch(
            "mutmut_win.mutant_diff.walk_source_files",
            return_value=[Path("src/legacy.py")],
        ):
            apply_mutant(mutant_name, config)

        applied = source_path.read_bytes()
        assert applied != source_bytes
        assert b"coding: cp1252" in applied.splitlines()[0]
        assert b"caf\xe9" in applied
        assert b"caf\xc3\xa9" not in applied
        compile(applied, str(source_path), "exec")

    def test_raises_when_mutant_not_found(self, tmp_path: Path) -> None:
        import os

        orig = Path.cwd()
        os.chdir(tmp_path)
        try:
            (tmp_path / "mutants").mkdir()
            config = _make_config()
            with (
                patch("mutmut_win.mutant_diff.walk_source_files", return_value=[]),
                pytest.raises(FileNotFoundError),
            ):
                apply_mutant("mod.x_missing__mutmut_99", config)
        finally:
            os.chdir(orig)

    def test_apply_and_show_preserve_the_public_definition(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """MW221-005: private staging normalisation must not reach user code."""
        monkeypatch.chdir(tmp_path)
        source = """\
class C:
    # keep this leading comment
    @staticmethod
    def f(x: int = 5) -> int:
        return x + 1
"""
        expected = source.replace("return x + 1", "return x - 1")
        source_path = tmp_path / "src" / "mod.py"
        source_path.parent.mkdir(parents=True)
        source_path.write_text(source, encoding="utf-8")

        generated, local_names = mutate_file_contents(
            "src/mod.py",
            source,
            active_profile=Profile.BASIC,
        )
        mutant_name = f"mod.{local_names[0]}"
        staged_path = tmp_path / "mutants" / "src" / "mod.py"
        staged_path.parent.mkdir(parents=True)
        staged_path.write_text(generated, encoding="utf-8")
        staged_path.with_suffix(".py.meta").write_text(
            json.dumps(
                {
                    "exit_code_by_key": {mutant_name: None},
                    "source_hash": hashlib.sha256(source_path.read_bytes()).hexdigest(),
                    "generated_hash": hashlib.sha256(staged_path.read_bytes()).hexdigest(),
                }
            ),
            encoding="utf-8",
        )

        diff = render_function_diff("src/mod.py", mutant_name)
        assert "def f(x: int = 5) -> int:" in diff
        assert "-        return x + 1" in diff
        assert "+        return x - 1" in diff

        # Prove that the displayed diff is directly applicable to the real
        # source layout, including the indentation of a class method.
        git = shutil.which("git")
        if git is None:  # pragma: no cover - Git is part of the release toolchain
            pytest.skip("git is required for the patch-applicability regression test")
        patch_root = tmp_path / "patch-target"
        patch_source = patch_root / "src" / "mod.py"
        patch_source.parent.mkdir(parents=True)
        patch_source.write_text(source, encoding="utf-8")
        applied = subprocess.run(  # noqa: S603 - shutil.which resolves trusted Git
            [git, "-c", "core.autocrlf=false", "apply", "-"],
            cwd=patch_root,
            input=diff.encode("utf-8"),
            capture_output=True,
            check=False,
        )
        assert applied.returncode == 0, applied.stderr.decode(errors="replace")
        assert patch_source.read_text(encoding="utf-8") == expected

        config = _make_config(paths=["src/"])
        with patch(
            "mutmut_win.mutant_diff.walk_source_files",
            return_value=[Path("src/mod.py")],
        ):
            apply_mutant(mutant_name, config)

        assert source_path.read_text(encoding="utf-8") == expected
        namespace: dict[str, Any] = {}
        exec(  # noqa: S102  # nosemgrep - executes only the literal test fixture above
            compile(expected, "src/mod.py", "exec"), namespace
        )
        assert namespace["C"].f() == 4

    @pytest.mark.parametrize(
        ("newline", "trailing_newline"),
        [("\n", True), ("\r\n", True), ("\n", False)],
        ids=["lf", "crlf", "no-final-newline"],
    )
    def test_show_diff_is_git_applicable_without_newline_translation(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        newline: str,
        trailing_newline: bool,
    ) -> None:
        """MW221: redirected ``show`` patches retain source/EOF semantics."""
        monkeypatch.chdir(tmp_path)
        source = newline.join(("def f():", "    return True"))
        if trailing_newline:
            source += newline
        source_path = tmp_path / "src" / "mod.py"
        source_path.parent.mkdir(parents=True)
        source_path.write_bytes(source.encode("utf-8"))

        generated, local_names = mutate_file_contents(
            "src/mod.py", source, active_profile=Profile.BASIC
        )
        assert local_names == ["x_f__mutmut_1"]
        mutant_name = f"mod.{local_names[0]}"
        staged_path = tmp_path / "mutants" / "src" / "mod.py"
        staged_path.parent.mkdir(parents=True)
        staged_path.write_text(generated, encoding="utf-8", newline="")
        staged_path.with_suffix(".py.meta").write_text(
            json.dumps(
                {
                    "exit_code_by_key": {mutant_name: None},
                    "source_hash": hashlib.sha256(source_path.read_bytes()).hexdigest(),
                    "generated_hash": hashlib.sha256(staged_path.read_bytes()).hexdigest(),
                }
            ),
            encoding="utf-8",
        )

        diff = render_function_diff("src/mod.py", mutant_name)
        if not trailing_newline:
            assert diff.count("\\ No newline at end of file") == 2
        if newline == "\r\n":
            assert "-    return True\r\n" in diff
            assert "+    return False\r\n" in diff

        git = shutil.which("git")
        if git is None:  # pragma: no cover - Git is part of the release toolchain
            pytest.skip("git is required for the patch-applicability regression test")
        patch_root = tmp_path / "patch-target"
        patch_source = patch_root / "src" / "mod.py"
        patch_source.parent.mkdir(parents=True)
        patch_source.write_bytes(source.encode("utf-8"))
        applied = subprocess.run(  # noqa: S603 - shutil.which resolves trusted Git
            [git, "-c", "core.autocrlf=false", "apply", "-"],
            cwd=patch_root,
            input=diff.encode("utf-8"),
            capture_output=True,
            check=False,
        )
        assert applied.returncode == 0, applied.stderr.decode(errors="replace")
        expected = source.replace("return True", "return False")
        assert patch_source.read_bytes() == expected.encode("utf-8")

    @pytest.mark.parametrize(
        ("newline", "trailing_newline"),
        [("\n", True), ("\r\n", True), ("\n", False)],
        ids=["lf", "crlf", "no-final-newline"],
    )
    def test_native_show_stdout_is_a_git_applicable_patch(
        self,
        tmp_path: Path,
        newline: str,
        trailing_newline: bool,
    ) -> None:
        """Exercise the real Windows stdout path, not Click's in-memory runner."""
        source = newline.join(("def f():", "    return True"))
        if trailing_newline:
            source += newline
        source_path = tmp_path / "src" / "mod.py"
        source_path.parent.mkdir(parents=True)
        source_path.write_bytes(source.encode("utf-8"))
        (tmp_path / "pyproject.toml").write_text(
            '[tool.mutmut]\npaths_to_mutate = ["src/"]\n', encoding="utf-8"
        )

        generated, local_names = mutate_file_contents(
            "src/mod.py", source, active_profile=Profile.BASIC
        )
        mutant_name = f"mod.{local_names[0]}"
        staged_path = tmp_path / "mutants" / "src" / "mod.py"
        staged_path.parent.mkdir(parents=True)
        staged_path.write_text(generated, encoding="utf-8", newline="")
        staged_path.with_suffix(".py.meta").write_text(
            json.dumps(
                {
                    "exit_code_by_key": {mutant_name: None},
                    "source_hash": hashlib.sha256(source_path.read_bytes()).hexdigest(),
                    "generated_hash": hashlib.sha256(staged_path.read_bytes()).hexdigest(),
                }
            ),
            encoding="utf-8",
        )

        shown = subprocess.run(  # noqa: S603 - exact current interpreter
            [sys.executable, "-m", "mutmut_win", "show", mutant_name],
            cwd=tmp_path,
            capture_output=True,
            check=False,
        )
        assert shown.returncode == 0, shown.stderr.decode(errors="replace")
        assert b"--- a/src/mod.py\n" in shown.stdout
        if newline == "\n":
            assert b"\r\n" not in shown.stdout

        git = shutil.which("git")
        if git is None:  # pragma: no cover - Git is part of the release toolchain
            pytest.skip("git is required for the patch-applicability regression test")
        patch_root = tmp_path / "patch-target-native"
        patch_source = patch_root / "src" / "mod.py"
        patch_source.parent.mkdir(parents=True)
        patch_source.write_bytes(source.encode("utf-8"))
        checked = subprocess.run(  # noqa: S603 - shutil.which resolves trusted Git
            [git, "-c", "core.autocrlf=false", "apply", "--check", "-"],
            cwd=patch_root,
            input=shown.stdout,
            capture_output=True,
            check=False,
        )
        assert checked.returncode == 0, checked.stderr.decode(errors="replace")

    @pytest.mark.parametrize("source_encoding", ["cp1252", "utf-8-sig", "latin-1-nel"])
    def test_native_show_patch_preserves_pep263_hunk_bytes(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        source_encoding: str,
    ) -> None:
        """Patch hunks must match non-UTF-8 source bytes and an initial BOM."""
        monkeypatch.chdir(tmp_path)
        if source_encoding == "cp1252":
            source = "# coding: cp1252\ndef f():\n    label = 'café'\n    return True\n"
            source_bytes = source.encode("cp1252")
            payload_encoding = "cp1252"
        elif source_encoding == "latin-1-nel":
            source = "# coding: latin-1\ndef f():\n    label = 'a\x85b'\n    return True\n"
            payload_encoding = "latin-1"
            source_bytes = source.encode(payload_encoding)
        else:
            source = "def f():\n    return True\n"
            source_bytes = source.encode("utf-8-sig")
            payload_encoding = "utf-8-sig"
        source_path = tmp_path / "src" / "mod.py"
        source_path.parent.mkdir(parents=True)
        source_path.write_bytes(source_bytes)
        (tmp_path / "pyproject.toml").write_text(
            '[tool.mutmut]\npaths_to_mutate = ["src/"]\n', encoding="utf-8"
        )

        generated, local_names = mutate_file_contents(
            "src/mod.py", source, active_profile=Profile.BASIC
        )
        qualified_names = [f"mod.{name}" for name in local_names]
        staged_path = tmp_path / "mutants" / "src" / "mod.py"
        staged_path.parent.mkdir(parents=True)
        staged_path.write_bytes(generated.encode(payload_encoding))
        staged_path.with_suffix(".py.meta").write_text(
            json.dumps(
                {
                    "exit_code_by_key": dict.fromkeys(qualified_names),
                    "source_hash": hashlib.sha256(source_bytes).hexdigest(),
                    "generated_hash": hashlib.sha256(staged_path.read_bytes()).hexdigest(),
                }
            ),
            encoding="utf-8",
        )
        mutant_name = next(
            name
            for name in qualified_names
            if "+    return False" in render_function_diff("src/mod.py", name)
        )
        patch_bytes = render_function_diff_bytes("src/mod.py", mutant_name)
        if source_encoding == "cp1252":
            assert b"caf\xe9" in patch_bytes
            assert b"caf\xc3\xa9" not in patch_bytes
        elif source_encoding == "latin-1-nel":
            assert b"a\x85b" in patch_bytes
            assert b"@@ -3,2 +3,2 @@" in patch_bytes
        else:
            assert not patch_bytes.startswith(codecs.BOM_UTF8)
            assert b" \xef\xbb\xbfdef f():\n" in patch_bytes

        shown = subprocess.run(  # noqa: S603 - exact current interpreter
            [sys.executable, "-m", "mutmut_win", "show", mutant_name],
            cwd=tmp_path,
            capture_output=True,
            check=False,
        )
        assert shown.returncode == 0, shown.stderr.decode(errors="replace")
        assert shown.stdout.endswith(patch_bytes)

        git = shutil.which("git")
        if git is None:  # pragma: no cover - Git is part of the release toolchain
            pytest.skip("git is required for the patch-applicability regression test")
        patch_root = tmp_path / "patch-target-encoding"
        patch_source = patch_root / "src" / "mod.py"
        patch_source.parent.mkdir(parents=True)
        patch_source.write_bytes(source_bytes)
        checked = subprocess.run(  # noqa: S603 - shutil.which resolves trusted Git
            [git, "-c", "core.autocrlf=false", "apply", "--check", "-"],
            cwd=patch_root,
            input=shown.stdout,
            capture_output=True,
            check=False,
        )
        assert checked.returncode == 0, checked.stderr.decode(errors="replace")

    @pytest.mark.parametrize("consumer", ["show", "apply"])
    @pytest.mark.parametrize("metadata_state", ["mismatch", "missing"])
    def test_show_and_apply_require_exact_generated_staging_hash(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        consumer: str,
        metadata_state: str,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        source_path = tmp_path / "src" / "mod.py"
        source_path.parent.mkdir(parents=True)
        source_path.write_text(_PLAIN_SOURCE, encoding="utf-8")
        staged_path = tmp_path / "mutants" / "src" / "mod.py"
        staged_path.parent.mkdir(parents=True)
        staged_path.write_text(_ORIG_SOURCE, encoding="utf-8")
        metadata: dict[str, object] = {
            "exit_code_by_key": {"mod.x_foo__mutmut_1": 0},
            "source_hash": hashlib.sha256(source_path.read_bytes()).hexdigest(),
        }
        if metadata_state == "mismatch":
            metadata["generated_hash"] = hashlib.sha256(staged_path.read_bytes()).hexdigest()
            staged_path.write_text(
                _ORIG_SOURCE.replace("return 2", "return 999"),
                encoding="utf-8",
            )
        staged_path.with_suffix(".py.meta").write_text(
            json.dumps(metadata),
            encoding="utf-8",
        )

        def consume_staging() -> None:
            if consumer == "show":
                render_function_diff("src/mod.py", "mod.x_foo__mutmut_1")
            else:
                config = _make_config(paths=["src/"])
                with patch(
                    "mutmut_win.mutant_diff.walk_source_files",
                    return_value=[Path("src/mod.py")],
                ):
                    apply_mutant("mod.x_foo__mutmut_1", config)

        with pytest.raises(StaleStagingError, match="generated metadata"):
            consume_staging()

        assert source_path.read_text(encoding="utf-8") == _PLAIN_SOURCE
        assert not source_path.with_name("mod.py.mutmut-orig.bak").exists()

    def test_show_refuses_source_changed_after_mutant_generation(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A displayed, patchable diff must use the generation-time source."""
        monkeypatch.chdir(tmp_path)
        source = "def f(x: int = 1) -> int:\n    return x + 1\n"
        source_path = tmp_path / "src" / "mod.py"
        source_path.parent.mkdir(parents=True)
        source_path.write_text(source, encoding="utf-8")
        generated, local_names = mutate_file_contents(
            "src/mod.py",
            source,
            active_profile=Profile.BASIC,
        )
        mutant_name = f"mod.{local_names[0]}"
        staged_path = tmp_path / "mutants" / "src" / "mod.py"
        staged_path.parent.mkdir(parents=True)
        staged_path.write_text(generated, encoding="utf-8")
        staged_path.with_suffix(".py.meta").write_text(
            json.dumps(
                {
                    "exit_code_by_key": {mutant_name: None},
                    "source_hash": hashlib.sha256(source_path.read_bytes()).hexdigest(),
                    "generated_hash": hashlib.sha256(staged_path.read_bytes()).hexdigest(),
                }
            ),
            encoding="utf-8",
        )
        source_path.write_text(
            "def f(x: int = 99) -> int:\n    return x + 100\n",
            encoding="utf-8",
        )

        with pytest.raises(StaleStagingError, match="before showing or applying"):
            render_function_diff("src/mod.py", mutant_name)
