"""Configuration management for mutmut-win.

Loads configuration from pyproject.toml [tool.mutmut] section.
Uses Pydantic v2 for validation and type safety.
"""

from __future__ import annotations

import fnmatch
import os
import tomllib
from pathlib import Path

from pydantic import BaseModel, Field, field_validator

from mutmut_win.exceptions import ConfigError


def _default_max_children() -> int:
    """Return the number of CPU cores, minimum 1."""
    return max(1, os.cpu_count() or 1)


class MutmutConfig(BaseModel):
    """Configuration for a mutmut-win mutation testing run.

    Loaded from [tool.mutmut] section of pyproject.toml.
    All fields have sensible defaults.
    """

    paths_to_mutate: list[str] = Field(
        default_factory=lambda: ["src/"],
        description="Paths to source files to mutate",
    )
    tests_dir: list[str] = Field(
        default_factory=lambda: ["tests/"],
        description="Directories containing tests",
    )
    do_not_mutate: list[str] = Field(
        default_factory=list,
        description="Glob patterns for files to exclude from mutation",
    )
    also_copy: list[str] = Field(
        default_factory=list,
        description="Additional files to copy alongside mutated sources",
    )
    max_children: int = Field(
        default_factory=_default_max_children,
        ge=1,
        description="Number of worker processes",
    )
    timeout_multiplier: float = Field(
        default=10.0,
        gt=0.0,
        description="Multiplier for timeout calculation",
    )
    max_stack_depth: int = Field(
        default=-1,
        description="Maximum stack depth for mutations (-1 = unlimited)",
    )
    debug: bool = Field(
        default=False,
        description="Enable debug output",
    )
    pytest_add_cli_args: list[str] = Field(
        default_factory=list,
        description="Additional pytest CLI arguments",
    )
    pytest_add_cli_args_test_selection: list[str] = Field(
        default_factory=list,
        description="Additional pytest CLI arguments for test selection",
    )
    mutate_only_covered_lines: bool = Field(
        default=False,
        description="Only mutate lines covered by tests",
    )
    type_check_command: list[str] = Field(
        default_factory=list,
        description="Type checker command (e.g. ['mypy', 'src/'])",
    )

    @field_validator("paths_to_mutate", "tests_dir", mode="before")
    @classmethod
    def _coerce_string_to_list(cls, v: object) -> object:
        """Accept a single string and wrap it into a list."""
        if isinstance(v, str):
            return [v]
        return v

    @field_validator("type_check_command", "pytest_add_cli_args", mode="before")
    @classmethod
    def _coerce_command_to_list(cls, v: object) -> object:
        """Accept a single string and split it into a list."""
        if isinstance(v, str):
            return v.split()
        return v

    def should_ignore_for_mutation(self, path: str | Path) -> bool:
        """Check if a file path should be excluded from mutation.

        Args:
            path: Path to check against do_not_mutate patterns.

        Returns:
            True if the file should be skipped.
        """
        path_str = str(path)
        if not path_str.endswith(".py"):
            return True
        return any(fnmatch.fnmatch(path_str, pattern) for pattern in self.do_not_mutate)


def load_config(project_dir: Path | None = None) -> MutmutConfig:
    """Load mutmut-win configuration from pyproject.toml.

    Args:
        project_dir: Directory containing pyproject.toml.
                     Defaults to current working directory.

    Returns:
        Validated MutmutConfig instance.

    Raises:
        ConfigError: If pyproject.toml cannot be read or parsed.
    """
    if project_dir is None:
        project_dir = Path.cwd()

    pyproject_path = project_dir / "pyproject.toml"
    if not pyproject_path.exists():
        return MutmutConfig()

    try:
        with pyproject_path.open("rb") as f:
            data = tomllib.load(f)
    except (tomllib.TOMLDecodeError, OSError) as e:
        msg = f"Failed to read pyproject.toml: {e}"
        raise ConfigError(msg) from e

    tool_config = data.get("tool", {}).get("mutmut", {})
    if not isinstance(tool_config, dict):
        return MutmutConfig()

    # Map mutmut config keys with hyphens to underscores
    normalized: dict[str, object] = {}
    for key, value in tool_config.items():
        normalized_key = key.replace("-", "_")
        normalized[normalized_key] = value

    try:
        return MutmutConfig.model_validate(normalized)
    except Exception as e:
        msg = f"Invalid [tool.mutmut] configuration: {e}"
        raise ConfigError(msg) from e
