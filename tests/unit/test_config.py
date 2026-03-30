"""Tests for mutmut_win.config."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from mutmut_win.config import (
    MutmutConfig,
    _apply_default_also_copy,
    guess_paths_to_mutate,
    load_config,
)
from mutmut_win.exceptions import ConfigError


class TestMutmutConfig:
    def test_defaults(self) -> None:
        config = MutmutConfig()
        # paths_to_mutate is guessed from cwd; it should be non-empty
        assert len(config.paths_to_mutate) >= 1
        assert config.tests_dir == ["tests/"]
        assert config.do_not_mutate == []
        assert config.also_copy == []
        assert config.max_children >= 1
        assert config.timeout_multiplier == 30.0
        assert config.debug is False

    def test_string_coerced_to_list(self) -> None:
        config = MutmutConfig(paths_to_mutate="lib/")  # type: ignore[arg-type]
        assert config.paths_to_mutate == ["lib/"]

    def test_should_ignore_non_python(self) -> None:
        config = MutmutConfig()
        assert config.should_ignore_for_mutation("README.md") is True

    def test_should_ignore_matching_pattern(self) -> None:
        config = MutmutConfig(do_not_mutate=["**/migrations/*"])
        assert config.should_ignore_for_mutation("src/app/migrations/001.py") is True

    def test_should_not_ignore_python_file(self) -> None:
        config = MutmutConfig()
        assert config.should_ignore_for_mutation("src/app/main.py") is False

    @given(st.floats(min_value=0.01, max_value=1000.0))
    def test_valid_timeout_multiplier(self, multiplier: float) -> None:
        config = MutmutConfig(timeout_multiplier=multiplier)
        assert config.timeout_multiplier == multiplier

    def test_zero_timeout_multiplier_rejected(self) -> None:
        with pytest.raises(ValidationError):
            MutmutConfig(timeout_multiplier=0.0)

    def test_negative_max_children_rejected(self) -> None:
        with pytest.raises(ValidationError):
            MutmutConfig(max_children=0)


class TestLoadConfig:
    def test_load_from_empty_dir(self, tmp_path: Path) -> None:
        config = load_config(tmp_path)
        assert isinstance(config, MutmutConfig)
        # With no pyproject.toml, paths_to_mutate falls back to _guess_paths_safe()
        # which guesses from cwd; at minimum it should be non-empty.
        assert len(config.paths_to_mutate) >= 1

    def test_load_from_pyproject(self, tmp_path: Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            '[tool.mutmut]\npaths_to_mutate = ["lib/"]\ntimeout_multiplier = 5.0\n',
            encoding="utf-8",
        )
        config = load_config(tmp_path)
        assert config.paths_to_mutate == ["lib/"]
        assert config.timeout_multiplier == 5.0

    def test_load_ignores_missing_tool_mutmut(self, tmp_path: Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[tool.other]\nfoo = 1\n", encoding="utf-8")
        config = load_config(tmp_path)
        # With no [tool.mutmut] section, paths_to_mutate is guessed from cwd
        assert len(config.paths_to_mutate) >= 1

    def test_load_invalid_toml_raises(self, tmp_path: Path) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("this is not valid toml {{{{", encoding="utf-8")
        with pytest.raises(ConfigError, match="Failed to read"):
            load_config(tmp_path)

    def test_also_copy_defaults_appended_with_no_config(self, tmp_path: Path) -> None:
        """F1: load_config appends default also_copy entries even when no [tool.mutmut]."""
        config = load_config(tmp_path)
        assert "tests/" in config.also_copy
        assert "pyproject.toml" in config.also_copy
        assert "setup.cfg" in config.also_copy
        assert "pytest.ini" in config.also_copy
        assert ".gitignore" in config.also_copy

    def test_also_copy_defaults_appended_after_user_values(self, tmp_path: Path) -> None:
        """F1: user-provided also_copy entries are preserved; defaults appended after."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            '[tool.mutmut]\nalso_copy = ["custom/"]\n',
            encoding="utf-8",
        )
        config = load_config(tmp_path)
        assert config.also_copy[0] == "custom/"
        assert "tests/" in config.also_copy
        assert "pyproject.toml" in config.also_copy

    def test_also_copy_includes_test_py_files(self, tmp_path: Path) -> None:
        """F1: test*.py files in project root are included in also_copy defaults."""
        (tmp_path / "test_foo.py").write_text("# test", encoding="utf-8")
        config = load_config(tmp_path)
        also_copy_names = [Path(p).name for p in config.also_copy]
        assert "test_foo.py" in also_copy_names

    def test_load_from_setup_cfg_when_no_pyproject(self, tmp_path: Path) -> None:
        """F5: setup.cfg is read as fallback when pyproject.toml is absent."""
        setup_cfg = tmp_path / "setup.cfg"
        setup_cfg.write_text(
            "[mutmut]\npaths_to_mutate = src/\ntimeout_multiplier = 7.5\n",
            encoding="utf-8",
        )
        config = load_config(tmp_path)
        assert config.paths_to_mutate == ["src/"]
        assert config.timeout_multiplier == pytest.approx(7.5)

    def test_setup_cfg_multiline_paths(self, tmp_path: Path) -> None:
        """F5: multi-line setup.cfg values are split into lists."""
        setup_cfg = tmp_path / "setup.cfg"
        setup_cfg.write_text(
            "[mutmut]\npaths_to_mutate =\n    src/\n    lib/\n",
            encoding="utf-8",
        )
        config = load_config(tmp_path)
        assert "src/" in config.paths_to_mutate
        assert "lib/" in config.paths_to_mutate

    def test_setup_cfg_ignored_if_no_mutmut_section(self, tmp_path: Path) -> None:
        """F5: setup.cfg without [mutmut] section does not raise; defaults apply."""
        setup_cfg = tmp_path / "setup.cfg"
        setup_cfg.write_text("[other]\nkey = value\n", encoding="utf-8")
        config = load_config(tmp_path)
        assert isinstance(config, MutmutConfig)

    def test_pyproject_takes_precedence_over_setup_cfg(self, tmp_path: Path) -> None:
        """F5: pyproject.toml [tool.mutmut] takes precedence over setup.cfg."""
        (tmp_path / "pyproject.toml").write_text(
            '[tool.mutmut]\npaths_to_mutate = ["src/"]\n',
            encoding="utf-8",
        )
        (tmp_path / "setup.cfg").write_text(
            "[mutmut]\npaths_to_mutate = lib/\n",
            encoding="utf-8",
        )
        config = load_config(tmp_path)
        assert config.paths_to_mutate == ["src/"]


class TestApplyDefaultAlsoCopy:
    def test_adds_standard_defaults(self, tmp_path: Path) -> None:
        config = MutmutConfig()
        result = _apply_default_also_copy(config, tmp_path)
        assert "tests/" in result.also_copy
        assert "test/" in result.also_copy
        assert "setup.cfg" in result.also_copy
        assert "pyproject.toml" in result.also_copy
        assert "pytest.ini" in result.also_copy
        assert ".gitignore" in result.also_copy

    def test_preserves_user_entries(self, tmp_path: Path) -> None:
        config = MutmutConfig(also_copy=["my_fixtures/"])
        result = _apply_default_also_copy(config, tmp_path)
        assert result.also_copy[0] == "my_fixtures/"
        assert "tests/" in result.also_copy

    def test_does_not_mutate_original(self, tmp_path: Path) -> None:
        config = MutmutConfig()
        _apply_default_also_copy(config, tmp_path)
        assert config.also_copy == []


class TestGuessPathsToMutate:
    def test_finds_src_dir(self, tmp_path: Path) -> None:
        (tmp_path / "src").mkdir()
        orig = Path.cwd()
        try:
            os.chdir(tmp_path)
            result = guess_paths_to_mutate()
        finally:
            os.chdir(orig)
        assert result == ["src"]

    def test_finds_lib_dir_before_src(self, tmp_path: Path) -> None:
        (tmp_path / "lib").mkdir()
        (tmp_path / "src").mkdir()
        orig = Path.cwd()
        try:
            os.chdir(tmp_path)
            result = guess_paths_to_mutate()
        finally:
            os.chdir(orig)
        # lib takes precedence over src in the heuristic
        assert result == ["lib"]

    def test_finds_project_dir_by_cwd_name(self, tmp_path: Path) -> None:
        project_dir = tmp_path / "myproject"
        project_dir.mkdir()
        inner = project_dir / "myproject"
        inner.mkdir()
        orig = Path.cwd()
        try:
            os.chdir(project_dir)
            result = guess_paths_to_mutate()
        finally:
            os.chdir(orig)
        assert result == ["myproject"]

    def test_raises_when_nothing_found(self, tmp_path: Path) -> None:
        orig = Path.cwd()
        try:
            os.chdir(tmp_path)
            with pytest.raises(FileNotFoundError, match="Could not figure out"):
                guess_paths_to_mutate()
        finally:
            os.chdir(orig)

    def test_finds_py_file_as_fallback(self, tmp_path: Path) -> None:
        # tmp_path will have a directory name like "test_finds_py_file_as_fallback0"
        # We need a .py file whose stem matches the cwd name
        orig = Path.cwd()
        try:
            os.chdir(tmp_path)
            cwd_name = tmp_path.name
            py_file = tmp_path / f"{cwd_name}.py"
            py_file.write_text("# module", encoding="utf-8")
            result = guess_paths_to_mutate()
            assert result == [f"{cwd_name}.py"]
        finally:
            os.chdir(orig)
