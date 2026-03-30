"""Tests for mutmut_win.config."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from mutmut_win.config import MutmutConfig, guess_paths_to_mutate, load_config
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
        assert config.timeout_multiplier == 10.0
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
