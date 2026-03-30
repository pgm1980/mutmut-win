"""Unit tests for mutmut_win.file_setup."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from mutmut_win.config import MutmutConfig
from mutmut_win.file_setup import (
    copy_also_copy_files,
    copy_src_dir,
    create_mutants_for_file,
    get_mutant_name,
    setup_source_paths,
    strip_prefix,
    walk_all_files,
    walk_source_files,
    write_all_mutants_to_file,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _config(**overrides: Any) -> MutmutConfig:
    defaults: dict[str, Any] = {"max_children": 1}
    defaults.update(overrides)
    return MutmutConfig(**defaults)


_SIMPLE_SOURCE = "def add(a, b):\n    return a + b\n"


# ---------------------------------------------------------------------------
# walk_all_files
# ---------------------------------------------------------------------------


class TestWalkAllFiles:
    def test_walks_directory(self, tmp_path: Path) -> None:
        (tmp_path / "a.py").write_text("", encoding="utf-8")
        (tmp_path / "b.txt").write_text("", encoding="utf-8")

        cfg = _config(paths_to_mutate=[str(tmp_path)])
        files = list(walk_all_files(cfg))
        filenames = [f for _, f in files]
        assert "a.py" in filenames
        assert "b.txt" in filenames

    def test_single_file_path(self, tmp_path: Path) -> None:
        f = tmp_path / "single.py"
        f.write_text("", encoding="utf-8")

        cfg = _config(paths_to_mutate=[str(f)])
        results = list(walk_all_files(cfg))
        assert len(results) == 1
        assert results[0] == ("", str(f))

    def test_nonexistent_path_yields_nothing(self, tmp_path: Path) -> None:
        cfg = _config(paths_to_mutate=[str(tmp_path / "does_not_exist")])
        results = list(walk_all_files(cfg))
        assert results == []

    def test_nested_directories(self, tmp_path: Path) -> None:
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "nested.py").write_text("", encoding="utf-8")

        cfg = _config(paths_to_mutate=[str(tmp_path)])
        files = list(walk_all_files(cfg))
        filenames = [f for _, f in files]
        assert "nested.py" in filenames


# ---------------------------------------------------------------------------
# walk_source_files
# ---------------------------------------------------------------------------


class TestWalkSourceFiles:
    def test_yields_only_py_files(self, tmp_path: Path) -> None:
        (tmp_path / "a.py").write_text("", encoding="utf-8")
        (tmp_path / "b.txt").write_text("", encoding="utf-8")
        (tmp_path / "c.pyi").write_text("", encoding="utf-8")

        cfg = _config(paths_to_mutate=[str(tmp_path)])
        paths = list(walk_source_files(cfg))
        names = [p.name for p in paths]
        assert "a.py" in names
        assert "b.txt" not in names
        assert "c.pyi" not in names

    def test_returns_path_objects(self, tmp_path: Path) -> None:
        (tmp_path / "x.py").write_text("", encoding="utf-8")
        cfg = _config(paths_to_mutate=[str(tmp_path)])
        paths = list(walk_source_files(cfg))
        assert all(isinstance(p, Path) for p in paths)


# ---------------------------------------------------------------------------
# copy_src_dir
# ---------------------------------------------------------------------------


class TestCopySrcDir:
    def test_copies_files_to_mutants_dir(self, tmp_path: Path) -> None:
        # Use a relative path for paths_to_mutate so copy_src_dir mirrors
        # it under mutants/<relative_path>/.
        src = tmp_path / "src_pkg"
        src.mkdir()
        (src / "foo.py").write_text(_SIMPLE_SOURCE, encoding="utf-8")

        original_cwd = Path.cwd()
        os.chdir(tmp_path)
        try:
            cfg = _config(paths_to_mutate=["src_pkg"])
            copy_src_dir(cfg)
            mutants_dir = tmp_path / "mutants"
            assert any(p.name == "foo.py" for p in mutants_dir.rglob("*.py"))
        finally:
            os.chdir(original_cwd)

    def test_skips_existing_files(self, tmp_path: Path) -> None:
        src = tmp_path / "src_pkg"
        src.mkdir()
        source_file = src / "bar.py"
        source_file.write_text(_SIMPLE_SOURCE, encoding="utf-8")

        original_cwd = Path.cwd()
        os.chdir(tmp_path)
        try:
            cfg = _config(paths_to_mutate=["src_pkg"])
            copy_src_dir(cfg)

            # Find the copied file and overwrite it with different content.
            targets = list((tmp_path / "mutants").rglob("bar.py"))
            assert targets
            targets[0].write_text("OVERWRITTEN", encoding="utf-8")

            # Second call should not overwrite.
            copy_src_dir(cfg)
            assert targets[0].read_text(encoding="utf-8") == "OVERWRITTEN"
        finally:
            os.chdir(original_cwd)


# ---------------------------------------------------------------------------
# copy_also_copy_files
# ---------------------------------------------------------------------------


class TestCopyAlsoCopyFiles:
    def test_copies_file(self, tmp_path: Path) -> None:
        # Use a relative path so the file is mirrored under mutants/<relpath>.
        extra = tmp_path / "extra.cfg"
        extra.write_text("[section]\nkey=val\n", encoding="utf-8")

        original_cwd = Path.cwd()
        os.chdir(tmp_path)
        try:
            # mutants/ must exist before copy_also_copy_files (copy_src_dir creates it).
            (tmp_path / "mutants").mkdir()
            cfg = _config(also_copy=["extra.cfg"])
            copy_also_copy_files(cfg)
            assert (tmp_path / "mutants" / "extra.cfg").exists()
        finally:
            os.chdir(original_cwd)

    def test_skips_nonexistent_path(self, tmp_path: Path) -> None:
        original_cwd = Path.cwd()
        os.chdir(tmp_path)
        try:
            cfg = _config(also_copy=["does_not_exist.cfg"])
            # Should not raise.
            copy_also_copy_files(cfg)
        finally:
            os.chdir(original_cwd)

    def test_copies_directory(self, tmp_path: Path) -> None:
        # Use a relative path for the directory.
        extra_dir = tmp_path / "extra_dir"
        extra_dir.mkdir()
        (extra_dir / "conf.txt").write_text("cfg", encoding="utf-8")

        original_cwd = Path.cwd()
        os.chdir(tmp_path)
        try:
            cfg = _config(also_copy=["extra_dir"])
            copy_also_copy_files(cfg)
            assert (tmp_path / "mutants" / "extra_dir" / "conf.txt").exists()
        finally:
            os.chdir(original_cwd)


# ---------------------------------------------------------------------------
# setup_source_paths
# ---------------------------------------------------------------------------


class TestSetupSourcePaths:
    def test_adds_mutants_paths_to_sys_path(self, tmp_path: Path) -> None:
        mutants_src = tmp_path / "mutants" / "src"
        mutants_src.mkdir(parents=True)

        original_cwd = Path.cwd()
        original_path = sys.path[:]
        os.chdir(tmp_path)
        try:
            setup_source_paths()
            inserted = [p for p in sys.path if "mutants" in p]
            assert any("src" in p for p in inserted)
        finally:
            os.chdir(original_cwd)
            sys.path[:] = original_path

    def test_removes_original_src_from_sys_path(self, tmp_path: Path) -> None:
        original_cwd = Path.cwd()
        original_path = sys.path[:]
        os.chdir(tmp_path)
        try:
            # Inject the 'src' path so setup_source_paths can remove it.
            src_abs = str((tmp_path / "src").absolute())
            sys.path.insert(0, src_abs)
            setup_source_paths()
            # The original src should be gone.
            assert src_abs not in sys.path
        finally:
            os.chdir(original_cwd)
            sys.path[:] = original_path


# ---------------------------------------------------------------------------
# strip_prefix
# ---------------------------------------------------------------------------


class TestStripPrefix:
    def test_strips_matching_prefix(self) -> None:
        assert strip_prefix("src.foo.bar", prefix="src.") == "foo.bar"

    def test_returns_unchanged_when_no_match(self) -> None:
        assert strip_prefix("foo.bar", prefix="src.") == "foo.bar"

    def test_empty_prefix(self) -> None:
        assert strip_prefix("anything", prefix="") == "anything"

    def test_empty_string(self) -> None:
        assert strip_prefix("", prefix="src.") == ""


# ---------------------------------------------------------------------------
# get_mutant_name
# ---------------------------------------------------------------------------


class TestGetMutantName:
    def test_basic_path(self) -> None:
        path = Path("src") / "my_lib" / "utils.py"
        result = get_mutant_name(path, "add__mutmut_1")
        assert result == "my_lib.utils.add__mutmut_1"

    def test_init_module_collapsed(self) -> None:
        path = Path("src") / "my_lib" / "__init__.py"
        result = get_mutant_name(path, "foo__mutmut_1")
        assert result == "my_lib.foo__mutmut_1"

    def test_no_src_prefix(self) -> None:
        path = Path("lib") / "utils.py"
        result = get_mutant_name(path, "func__mutmut_2")
        assert result == "lib.utils.func__mutmut_2"

    def test_deep_nesting(self) -> None:
        path = Path("src") / "a" / "b" / "c.py"
        result = get_mutant_name(path, "x__mutmut_3")
        assert result == "a.b.c.x__mutmut_3"


# ---------------------------------------------------------------------------
# write_all_mutants_to_file
# ---------------------------------------------------------------------------


class TestWriteAllMutantsToFile:
    def test_writes_mutated_output(self, tmp_path: Path) -> None:
        from io import StringIO

        buf = StringIO()
        names = write_all_mutants_to_file(
            out=buf,
            source=_SIMPLE_SOURCE,
            filename=tmp_path / "foo.py",
        )
        content = buf.getvalue()
        assert len(content) > 0
        assert len(names) > 0

    def test_returns_mutant_names_list(self, tmp_path: Path) -> None:
        from io import StringIO

        buf = StringIO()
        names = write_all_mutants_to_file(
            out=buf,
            source=_SIMPLE_SOURCE,
            filename=tmp_path / "foo.py",
        )
        assert isinstance(names, list)
        assert all(isinstance(n, str) for n in names)


# ---------------------------------------------------------------------------
# create_mutants_for_file
# ---------------------------------------------------------------------------


class TestCreateMutantsForFile:
    def test_creates_output_file(self, tmp_path: Path) -> None:
        src = tmp_path / "foo.py"
        src.write_text(_SIMPLE_SOURCE, encoding="utf-8")
        output = tmp_path / "mutants_foo.py"
        output.parent.mkdir(parents=True, exist_ok=True)

        names, warns = create_mutants_for_file(src, output)
        assert output.exists()
        assert len(names) > 0
        assert warns == []

    def test_returns_qualified_method_names(self, tmp_path: Path) -> None:
        src = tmp_path / "foo.py"
        src.write_text(_SIMPLE_SOURCE, encoding="utf-8")
        output = tmp_path / "foo_mutated.py"

        names, _ = create_mutants_for_file(src, output)
        # Each name should contain the mutmut marker.
        assert all("__mutmut_" in n for n in names)

    def test_no_mutants_for_trivial_code(self, tmp_path: Path) -> None:
        src = tmp_path / "trivial.py"
        src.write_text("x = 1\n", encoding="utf-8")
        output = tmp_path / "trivial_out.py"

        names, _ = create_mutants_for_file(src, output)
        # Trivial assignment may produce 0 or more mutants — just ensure
        # no exception is raised and the return types are correct.
        assert isinstance(names, list)

    def test_skips_if_source_unmodified(self, tmp_path: Path) -> None:
        """When the mutant file is newer than the source, skip re-generation."""
        src = tmp_path / "mod.py"
        src.write_text(_SIMPLE_SOURCE, encoding="utf-8")
        output = tmp_path / "mod_out.py"
        output.write_text(_SIMPLE_SOURCE, encoding="utf-8")

        # Make output much newer than source.
        future_mtime = src.stat().st_mtime + 3600
        os.utime(output, (future_mtime, future_mtime))

        names, _ = create_mutants_for_file(src, output)
        # Fast-path: returns empty list without re-generating.
        assert names == []

    def test_handles_syntax_error_gracefully(self, tmp_path: Path) -> None:
        src = tmp_path / "bad.py"
        # Intentionally invalid Python that libcst cannot parse.
        src.write_text("def broken(\n    pass\n", encoding="utf-8")
        output = tmp_path / "bad_out.py"

        # Should not raise; may return empty names with a warning.
        names, _warns = create_mutants_for_file(src, output)
        assert isinstance(names, list)

    def test_saves_meta_file(self, tmp_path: Path) -> None:
        original_cwd = Path.cwd()
        os.chdir(tmp_path)
        try:
            src = tmp_path / "meta_test.py"
            src.write_text(_SIMPLE_SOURCE, encoding="utf-8")
            output = tmp_path / "meta_out.py"

            names, _ = create_mutants_for_file(src, output)
            if names:
                # Meta file should be created relative to cwd.
                meta = Path("mutants") / (str(src) + ".meta")
                assert meta.exists()
        finally:
            os.chdir(original_cwd)
