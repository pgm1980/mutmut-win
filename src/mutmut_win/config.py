"""Configuration management for mutmut-win.

Loads configuration from pyproject.toml [tool.mutmut] section.
Uses Pydantic v2 for validation and type safety.
"""

from __future__ import annotations

import fnmatch
import os
import tomllib
from configparser import ConfigParser, NoOptionError, NoSectionError
from pathlib import Path

from pydantic import BaseModel, Field, field_validator

from mutmut_win.exceptions import ConfigError


def _default_max_children() -> int:
    """Return the number of CPU cores, minimum 1."""
    return max(1, os.cpu_count() or 1)


def _split_cli_string(value: str) -> list[str]:
    """Tokenize a CLI argument string shell-style, Windows-safe.

    Quotes (single or double) group tokens and are stripped; backslash is
    NOT an escape character, so Windows paths survive untouched. This is
    what a naive ``str.split()`` got wrong for ``'-m "not slow"'``
    (issue #112 / A2-RN-013).

    Args:
        value: The raw argument string from config or CLI.

    Returns:
        The token list (empty for an empty/blank string).

    Raises:
        ValueError: On unbalanced quotes — surfaced by pydantic as a
            validation error naming the offending string.
    """
    import shlex

    lex = shlex.shlex(value, posix=True)
    lex.whitespace_split = True
    lex.escape = ""  # keep Windows backslashes literal
    try:
        return list(lex)
    except ValueError as exc:
        msg = f"unbalanced quotes in CLI argument string {value!r}: {exc}"
        raise ValueError(msg) from exc


def guess_paths_to_mutate() -> list[str]:
    """Guess source paths to mutate based on common project layouts.

    Mirrors the heuristic from mutmut 3.5.0: checks for ``lib/``, ``src/``,
    a directory named after the current working directory (with common
    transformations applied), and finally a top-level ``.py`` file with the
    same stem.

    Returns:
        A list containing the single best-guess path.

    Raises:
        FileNotFoundError: If no suitable source directory or file can be found.
    """
    this_dir = Path.cwd().name
    candidates = [
        "lib",
        "src",
        this_dir,
        this_dir.replace("-", "_"),
        this_dir.replace(" ", "_"),
        this_dir.replace("-", ""),
        this_dir.replace(" ", ""),
    ]
    for candidate in candidates:
        if Path(candidate).is_dir():
            return [candidate]

    py_file = this_dir + ".py"
    if Path(py_file).is_file():
        return [py_file]

    msg = (
        "Could not figure out where the code to mutate is. "
        "Please specify it by adding paths_to_mutate in pyproject.toml "
        "under [tool.mutmut]."
    )
    raise FileNotFoundError(msg)


def _guess_paths_safe() -> list[str]:
    """Return guessed source paths, falling back to ``['src/']`` on failure."""
    try:
        return guess_paths_to_mutate()
    except FileNotFoundError:
        return ["src/"]


class MutmutConfig(BaseModel):
    """Configuration for a mutmut-win mutation testing run.

    Loaded from [tool.mutmut] section of pyproject.toml.
    All fields have sensible defaults.
    """

    paths_to_mutate: list[str] = Field(
        default_factory=lambda: _guess_paths_safe(),
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
    extra_paths: list[str] = Field(
        default_factory=list,
        description=(
            "Sibling directories to copy into mutants/ AND add to the worker's "
            "PYTHONPATH. Use when tests import from packages outside the wheel "
            "(e.g. a sibling ``benchmarks/`` directory). See issue #69."
        ),
    )
    max_children: int = Field(
        default_factory=_default_max_children,
        ge=1,
        description="Number of worker processes",
    )
    timeout_multiplier: float = Field(
        default=30.0,
        gt=0.0,
        description="Multiplier for timeout calculation (mutmut default: 30x)",
    )
    clean_run_timeout: int = Field(
        default=300,
        gt=0,
        description=(
            "Timeout (seconds) for the clean baseline and stats pytest runs "
            "inside mutants/. The trampolined suite runs slower than the "
            "native one — raise this for suites that need more than five "
            "minutes. See issue #74."
        ),
    )
    forced_fail_timeout: int = Field(
        default=120,
        gt=0,
        description=(
            "Timeout (seconds) for the forced-fail trampoline verification run. See issue #74."
        ),
    )
    max_stack_depth: int = Field(
        default=-1,
        # ge=-1: values below the sentinel walked the frame stack with a
        # truthy-negative counter (issue #110 / A4-QX-018). 0 is rejected
        # separately below — it would discard EVERY stats hit.
        ge=-1,
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

    # ---- True infinite-loop detection (Bug #5 / Issue #71, Sprint 26) -----
    infinite_loop_detection: bool = Field(
        default=True,
        description=(
            "Enable triple-check classifier that reclassifies wall-clock "
            "timeouts as killed_by_infinite_loop when CPU is pegged AND no "
            "output growth AND process status=running. Requires psutil. "
            "See Issue #71."
        ),
    )
    infinite_loop_cpu_threshold: float = Field(
        default=70.0,
        ge=0.0,
        le=10_000.0,
        description="Mean CPU%% in window required to classify as infinite loop.",
    )
    infinite_loop_output_threshold: int = Field(
        default=1024,
        # gt=0: a 0 threshold silently disabled IL detection (growth<0 never
        # holds, A2-JT-010). Use infinite_loop_detection=false to opt out.
        gt=0,
        description=(
            "Maximum output growth (bytes) in window allowed for an IL "
            "verdict. Above this, the test is making observable progress."
        ),
    )
    infinite_loop_running_ratio: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description=(
            "Minimum fraction of samples where process status == 'running' "
            "required for an IL verdict. Filters out sleeping (network-wait) "
            "tests."
        ),
    )
    infinite_loop_window_seconds: float = Field(
        default=10.0,
        gt=0.0,
        description="Rolling sample window (seconds) used by the classifier.",
    )

    @field_validator("paths_to_mutate", "tests_dir", mode="before")
    @classmethod
    def _coerce_string_to_list(cls, v: object) -> object:
        """Accept a single string and wrap it into a list."""
        if isinstance(v, str):
            return [v]
        return v

    @field_validator("max_stack_depth", mode="after")
    @classmethod
    def _reject_zero_stack_depth(cls, v: int) -> int:
        """Reject ``max_stack_depth=0`` loudly (issue #110 / A4-QX-018).

        0 exhausts the frame-walk budget before the first frame, so EVERY
        stats hit is silently discarded — every mutant then runs the full
        suite. Nobody means that; -1 is the documented "unlimited" sentinel.
        """
        if v == 0:
            msg = (
                "max_stack_depth=0 would discard every stats hit "
                "(every mutant would run the full suite) — use -1 for "
                "unlimited or a positive depth."
            )
            raise ValueError(msg)
        return v

    @field_validator("paths_to_mutate", mode="after")
    @classmethod
    def _reject_absolute_paths(cls, v: list[str]) -> list[str]:
        """Reject absolute ``paths_to_mutate`` entries (issue #75 / A3-CM-001).

        ``Path("mutants") / <absolute path>`` discards the left operand, so an
        absolute entry would make the mutation engine write the trampoline
        code INTO the original source file.  Entries under the current working
        directory are silently relativized; anything else is an error.
        """
        safe: list[str] = []
        for entry in v:
            path = Path(entry)
            if path.is_absolute():
                try:
                    path = path.relative_to(Path.cwd())
                except ValueError as exc:
                    msg = (
                        f"paths_to_mutate entry {entry!r} is an absolute path "
                        "outside the project root — use paths relative to the "
                        "project root (absolute paths would let the mutants/ "
                        "staging overwrite the original sources)"
                    )
                    raise ValueError(msg) from exc
                safe.append(str(path))
            else:
                safe.append(entry)
        return safe

    @field_validator(
        "type_check_command",
        "pytest_add_cli_args",
        "pytest_add_cli_args_test_selection",
        mode="before",
    )
    @classmethod
    def _coerce_command_to_list(cls, v: object) -> object:
        """Accept a single string and tokenize it shell-style.

        Quote-aware — ``'-m "not slow"'`` stays one marker expression —
        and Windows-safe: backslash is NOT an escape character, so path
        arguments survive untouched (issue #112 / A2-RN-013; the naive
        ``str.split()`` handed pytest broken tokens, and the
        test-selection field accepted no string at all).
        """
        if isinstance(v, str):
            return _split_cli_string(v)
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


def _apply_default_also_copy(config: MutmutConfig, project_dir: Path) -> MutmutConfig:
    """Append default also_copy entries to *config* (mirrors mutmut 3.5.0).

    The defaults are appended AFTER any user-provided entries so that
    user configuration takes precedence for duplicate paths.

    Args:
        config: Existing ``MutmutConfig`` to extend.
        project_dir: Project root directory used to glob ``test*.py`` files.

    Returns:
        New ``MutmutConfig`` with default also_copy entries appended.
    """
    default_also_copy: list[str] = [
        "tests/",
        "test/",
        "setup.cfg",
        "pyproject.toml",
        "pytest.ini",
        ".gitignore",
    ] + [str(p.relative_to(project_dir)) for p in project_dir.glob("test*.py")]
    return config.model_copy(update={"also_copy": config.also_copy + default_also_copy})


def _load_setup_cfg(project_dir: Path) -> MutmutConfig | None:
    """Attempt to load mutmut configuration from setup.cfg [mutmut] section.

    Mirrors the ConfigParser fallback from mutmut 3.5.0 ``config_reader()``.

    Args:
        project_dir: Project root directory containing setup.cfg.

    Returns:
        ``MutmutConfig`` loaded from setup.cfg, or ``None`` if the file does
        not exist or has no ``[mutmut]`` section.
    """
    setup_cfg_path = project_dir / "setup.cfg"
    if not setup_cfg_path.exists():
        return None

    parser = ConfigParser()
    parser.read(str(setup_cfg_path), encoding="utf-8")

    def _get(key: str, default: object) -> object:
        try:
            result = parser.get("mutmut", key)
        except (NoOptionError, NoSectionError):
            return default
        if isinstance(default, list):
            # Multi-line values: split on newlines; single-line: split on commas
            if "\n" in result:
                return [x for x in result.split("\n") if x]
            return [x.strip() for x in result.split(",") if x.strip()]
        return result

    if not parser.has_section("mutmut"):
        return None

    normalized: dict[str, object] = {
        "paths_to_mutate": _get("paths_to_mutate", []),
        "tests_dir": _get("tests_dir", ["tests/"]),
        "do_not_mutate": _get("do_not_mutate", []),
        "also_copy": _get("also_copy", []),
        "max_children": _get("max_children", _default_max_children()),
        "timeout_multiplier": _get("timeout_multiplier", 30.0),
        "clean_run_timeout": _get("clean_run_timeout", 300),
        "forced_fail_timeout": _get("forced_fail_timeout", 120),
        "max_stack_depth": _get("max_stack_depth", -1),
        "debug": _get("debug", False),
        "mutate_only_covered_lines": _get("mutate_only_covered_lines", False),
        "pytest_add_cli_args": _get("pytest_add_cli_args", []),
        "pytest_add_cli_args_test_selection": _get("pytest_add_cli_args_test_selection", []),
        "type_check_command": _get("type_check_command", []),
    }
    # Remove empty-list defaults that were not configured so model defaults apply
    normalized = {k: v for k, v in normalized.items() if v != [] or k in ("do_not_mutate",)}
    return MutmutConfig.model_validate(normalized)


def load_config(project_dir: Path | None = None) -> MutmutConfig:
    """Load mutmut-win configuration from pyproject.toml or setup.cfg.

    Tries ``[tool.mutmut]`` in ``pyproject.toml`` first, then falls back to
    the ``[mutmut]`` section in ``setup.cfg`` (mirrors mutmut 3.5.0).

    Args:
        project_dir: Directory containing pyproject.toml / setup.cfg.
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
        # Fall back to setup.cfg if available
        setup_cfg_config = _load_setup_cfg(project_dir)
        if setup_cfg_config is not None:
            return _apply_default_also_copy(setup_cfg_config, project_dir)
        return _apply_default_also_copy(MutmutConfig(), project_dir)

    try:
        with pyproject_path.open("rb") as f:
            data = tomllib.load(f)
    except (tomllib.TOMLDecodeError, OSError) as e:
        msg = f"Failed to read pyproject.toml: {e}"
        raise ConfigError(msg) from e

    tool_config = data.get("tool", {}).get("mutmut", {})
    if not isinstance(tool_config, dict) or not tool_config:
        # No [tool.mutmut] section — try setup.cfg before returning defaults
        setup_cfg_config = _load_setup_cfg(project_dir)
        if setup_cfg_config is not None:
            return _apply_default_also_copy(setup_cfg_config, project_dir)
        return _apply_default_also_copy(MutmutConfig(), project_dir)

    # Map mutmut config keys with hyphens to underscores
    normalized: dict[str, object] = {}
    for key, value in tool_config.items():
        normalized_key = key.replace("-", "_")
        if normalized_key in normalized:
            print(
                f"Warning: [tool.mutmut] declares '{normalized_key}' twice "
                f"(hyphen/underscore twins) — the last one wins."
            )
        normalized[normalized_key] = value

    # Issue #102 / A3-CM-005: extra='ignore' swallowed typos silently —
    # 'paths_to_mutat' fell back to the default guess and mutated the wrong
    # tree unnoticed. Warn (non-breaking) with a close-match suggestion.
    import difflib

    known_keys = set(MutmutConfig.model_fields)
    for unknown in sorted(set(normalized) - known_keys):
        matches = difflib.get_close_matches(unknown, sorted(known_keys), n=1)
        hint = f" — did you mean '{matches[0]}'?" if matches else ""
        print(f"Warning: unknown [tool.mutmut] key '{unknown}'{hint}")

    try:
        config = MutmutConfig.model_validate(normalized)
    except Exception as e:
        msg = f"Invalid [tool.mutmut] configuration: {e}"
        raise ConfigError(msg) from e

    return _apply_default_also_copy(config, project_dir)
