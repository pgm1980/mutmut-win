"""Unit tests for mutmut_win.mutant_diff.

Tests cover find_mutant, read_mutants_module, read_orig_module,
find_top_level_function_or_method, read_original_function,
read_mutant_function, get_diff_for_mutant, and apply_mutant.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import libcst as cst
import pytest

from mutmut_win.mutant_diff import (
    apply_mutant,
    find_mutant,
    find_top_level_function_or_method,
    get_diff_for_mutant,
    read_mutant_function,
    read_mutants_module,
    read_orig_module,
    read_original_function,
)

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

            # Write mutants file with both _orig and _1 variants.
            # CST function names: "x_foo__mutmut_orig" and "x_foo__mutmut_1"
            # (not prefixed with module path — those are just Python function names).
            mutant_source = """\
def x_foo__mutmut_orig() -> int:
    return 1

def x_foo__mutmut_1() -> int:
    return 2
"""
            (mutants_src / "mod.py").write_text(mutant_source, encoding="utf-8")

            # Write meta so find_mutant can locate it.
            meta_path = tmp_path / "mutants" / "src" / "mod.py.meta"
            meta_path.write_text(
                json.dumps({"exit_code_by_key": {"mod.x_foo__mutmut_1": 0}}),
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
            (mutants_src / "mod.py").write_text(mutant_source, encoding="utf-8")

            meta_path = tmp_path / "mutants" / "src" / "mod.py.meta"
            meta_path.write_text(
                json.dumps({"exit_code_by_key": {"mod.x_foo__mutmut_1": 0}}),
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
