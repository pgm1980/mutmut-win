"""Config source contract tests (AP-18: M-027, M-079, M-080).

The load boundary of both configuration sources is a contract:
``load_config`` either returns a ``MutmutConfig`` or raises
``ConfigError`` — never a raw ``OSError``, ``UnicodeDecodeError`` or
``AttributeError``, and never silent defaults for a file that exists
but cannot be read.

* M-027 (Q-37): an existing-but-unreadable setup.cfg used to fall back
  to ``MutmutConfig()`` defaults because ``ConfigParser.read``
  swallows every ``OSError`` and ``Path.exists`` treats ``OSError`` as
  absence. Only ``FileNotFoundError`` is proven absence now.
* M-079: undecodable (non-UTF-8) configuration escaped the
  ``ConfigError`` translation at both read boundaries.
* M-080 (in test_hardening_132.py): the setup.cfg typo warning
  inherited keys from ``[DEFAULT]``.

This file doubles as the sole ``--tests-dir`` for the targeted
``config.py`` mutation gate (Q-41).
"""

from __future__ import annotations

import configparser
import string
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from click.testing import CliRunner
from hypothesis import given
from hypothesis import strategies as st

from mutmut_win.cli import cli
from mutmut_win.config import MutmutConfig, load_config
from mutmut_win.exceptions import ConfigError, InvalidConfigValueError

if TYPE_CHECKING:
    from collections.abc import Callable


class TestSetupCfgReadBoundary:
    """M-027 / Q-37: unreadable-but-existing setup.cfg is a ConfigError."""

    def test_directory_named_setup_cfg_is_a_config_error(self, tmp_path: Path) -> None:
        # A directory named setup.cfg exists, yet cannot be read as a
        # file. Before the fix: parser.read() swallowed the OSError and
        # silently returned MutmutConfig() defaults.
        (tmp_path / "setup.cfg").mkdir()

        with pytest.raises(ConfigError, match=r"Failed to read setup\.cfg"):
            load_config(tmp_path)

    def test_directory_setup_cfg_is_an_error_on_the_pyproject_fallback_path(
        self, tmp_path: Path
    ) -> None:
        # Same mechanism via the second fallback (pyproject.toml exists
        # but has no [tool.mutmut]).
        (tmp_path / "pyproject.toml").write_text("[tool.other]\nfoo = 1\n", encoding="utf-8")
        (tmp_path / "setup.cfg").mkdir()

        with pytest.raises(ConfigError, match=r"Failed to read setup\.cfg"):
            load_config(tmp_path)

    def test_byte_range_locked_setup_cfg_is_a_config_error(
        self, tmp_path: Path, locked_file: Callable[[str], Path]
    ) -> None:
        # Real Windows state (Q-02): open() succeeds, read() fails with
        # PermissionError — this kills any fix that only guards open().
        locked_file("setup.cfg")

        with pytest.raises(ConfigError, match=r"Failed to read setup\.cfg"):
            load_config(tmp_path)

    def test_missing_setup_cfg_still_yields_defaults(self, tmp_path: Path) -> None:
        # Counter-check: absence remains absence — defaults, no error.
        config = load_config(tmp_path)

        assert isinstance(config, MutmutConfig)

    @pytest.mark.parametrize(
        "exc_cls",
        [PermissionError, IsADirectoryError, TimeoutError, OSError],
    )
    def test_open_oserror_is_never_silent_defaults(self, exc_cls: type[OSError]) -> None:
        # Path-exact monkeypatch: only opens of setup.cfg fail; any
        # other open (e.g. pyproject.toml) must stay real.
        with tempfile.TemporaryDirectory() as td, pytest.MonkeyPatch.context() as mp:
            project = Path(td)
            (project / "setup.cfg").write_text(
                "[mutmut]\npaths_to_mutate = src/\n", encoding="utf-8"
            )
            real_open = Path.open

            def failing_open(self: Path, *args: object, **kwargs: object) -> object:
                if self.name == "setup.cfg":
                    raise exc_cls(13, "sharing violation")
                return real_open(self, *args, **kwargs)  # type: ignore[arg-type]

            mp.setattr(Path, "open", failing_open)

            with pytest.raises(ConfigError, match=r"Failed to read setup\.cfg"):
                load_config(project)

    def test_file_not_found_from_open_still_yields_defaults(self) -> None:
        # FileNotFoundError is the ONLY OSError that means absence.
        with tempfile.TemporaryDirectory() as td, pytest.MonkeyPatch.context() as mp:
            project = Path(td)
            real_open = Path.open

            def missing_open(self: Path, *args: object, **kwargs: object) -> object:
                if self.name == "setup.cfg":
                    raise FileNotFoundError(2, "no such file")
                return real_open(self, *args, **kwargs)  # type: ignore[arg-type]

            mp.setattr(Path, "open", missing_open)

            config = load_config(project)

            assert isinstance(config, MutmutConfig)

    @given(
        sections=st.lists(
            st.tuples(
                st.from_regex(r"[a-z]{1,8}", fullmatch=True),
                st.lists(
                    st.tuples(
                        st.from_regex(r"[a-z_]{1,12}", fullmatch=True),
                        st.text(
                            alphabet=string.ascii_letters + string.digits + " ._-/",
                            max_size=20,
                        ),
                    ),
                    max_size=4,
                ),
            ),
            max_size=4,
        ),
        newline=st.sampled_from(["\n", "\r\n"]),
    )
    def test_read_string_route_matches_configparser_read_route(
        self,
        sections: list[tuple[str, list[tuple[str, str]]]],
        newline: str,
    ) -> None:
        # Equivalence property backing the M-027 refactor: reading the
        # file once as UTF-8 text and parsing with read_string yields
        # exactly what ConfigParser.read produced (which also opens in
        # text mode), including CRLF translation. Duplicate generated
        # section headers must fail identically on both routes.
        lines: list[str] = []
        for name, entries in sections:
            lines.append(f"[{name}]")
            for key, value in entries:
                lines.append(f"{key} = {value}")
        text = newline.join(lines) + newline if lines else ""

        def outcome(parser: configparser.ConfigParser, route: Callable[[], None]) -> object:
            try:
                route()
            except configparser.Error as exc:
                return type(exc)
            return sorted((section, sorted(parser.items(section))) for section in parser.sections())

        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "setup.cfg"
            path.write_text(text, encoding="utf-8", newline="")

            via_read = configparser.ConfigParser(interpolation=None)
            read_outcome = outcome(via_read, lambda: via_read.read(path, encoding="utf-8"))

            via_string = configparser.ConfigParser(interpolation=None)
            with path.open(encoding="utf-8") as fh:
                once_read_text = fh.read()
            string_outcome = outcome(
                via_string, lambda: via_string.read_string(once_read_text, source=str(path))
            )

            assert string_outcome == read_outcome


class TestConfigDecodingBoundary:
    """M-079: non-UTF-8 configuration becomes a ConfigError, not a crash."""

    def test_utf16_pyproject_is_a_config_error(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_bytes(
            '[tool.mutmut]\npaths_to_mutate = ["src/"]\n'.encode("utf-16")
        )

        with pytest.raises(ConfigError, match=r"Failed to read pyproject\.toml"):
            load_config(tmp_path)

    def test_utf16_setup_cfg_is_a_config_error(self, tmp_path: Path) -> None:
        (tmp_path / "setup.cfg").write_bytes("[mutmut]\npaths_to_mutate = src/\n".encode("utf-16"))

        with pytest.raises(ConfigError, match=r"Failed to read setup\.cfg"):
            load_config(tmp_path)

    def test_utf16_setup_cfg_is_an_error_on_the_pyproject_fallback_path(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "pyproject.toml").write_text("[tool.other]\nfoo = 1\n", encoding="utf-8")
        (tmp_path / "setup.cfg").write_bytes("[mutmut]\npaths_to_mutate = src/\n".encode("utf-16"))

        with pytest.raises(ConfigError, match=r"Failed to read setup\.cfg"):
            load_config(tmp_path)

    def test_utf8_bom_setup_cfg_still_reports_the_parse_error(self, tmp_path: Path) -> None:
        # Counter-check (no utf-8-sig): a BOM stays a section-header
        # error — unchanged behaviour, just via the new read boundary.
        (tmp_path / "setup.cfg").write_bytes(b"\xef\xbb\xbf[mutmut]\npaths_to_mutate = src/\n")

        with pytest.raises(ConfigError, match=r"Failed to read setup\.cfg"):
            load_config(tmp_path)


class TestSetupCfgReadBoundaryCli:
    """M-027: the CLI turns an unreadable setup.cfg into exit 2."""

    @pytest.mark.parametrize("command", ["show", "apply"])
    def test_unreadable_setup_cfg_exits_2_without_traceback(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, command: str
    ) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / "mutants").mkdir()
        (tmp_path / "setup.cfg").mkdir()

        result = CliRunner().invoke(cli, [command, "src.mod.x_f__mutmut_1"])

        assert result.exit_code == 2
        assert "setup.cfg" in result.output + str(result.stderr)
        assert result.exception is None or isinstance(result.exception, SystemExit)


def _toml_scalar_literal(value: int | bool | list[int]) -> str:
    """Serialize a hypothesis-generated value as a TOML literal.

    ``str(True)`` would produce ``True``, which is INVALID TOML (the
    resulting TOMLDecodeError would make the tests vacuously green).
    """
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        return "[" + ", ".join(str(item) for item in value) + "]"
    return str(value)


# TOML integers are 64-bit signed; tomllib rejects anything wider with a
# TOMLDecodeError before the structure check can run.
_TOML_INT64 = st.integers(min_value=-(2**63), max_value=2**63 - 1)


class TestPyprojectToolStructure:
    """M-078: a non-table `tool` value is an AttributeError today."""

    @pytest.mark.parametrize(
        "toml_value",
        ["1", '"x"', "[1, 2]", "true", "[]"],
    )
    def test_non_table_tool_is_a_config_error(self, tmp_path: Path, toml_value: str) -> None:
        (tmp_path / "pyproject.toml").write_text(f"tool = {toml_value}\n", encoding="utf-8")

        with pytest.raises(ConfigError, match=r"\[tool\] must be a table"):
            load_config(tmp_path)

    @given(st.one_of(_TOML_INT64, st.booleans(), st.lists(st.integers(0, 99), max_size=3)))
    def test_any_non_table_tool_literal_is_a_config_error(
        self, value: int | bool | list[int]
    ) -> None:
        with tempfile.TemporaryDirectory() as td:
            project = Path(td)
            (project / "pyproject.toml").write_text(
                f"tool = {_toml_scalar_literal(value)}\n", encoding="utf-8"
            )
            with pytest.raises(ConfigError, match=r"\[tool\] must be a table"):
                load_config(project)

    def test_inline_empty_tool_table_still_falls_back(self, tmp_path: Path) -> None:
        # 'tool = {}' is a table — the fallback stays reachable.
        (tmp_path / "pyproject.toml").write_text("tool = {}\n", encoding="utf-8")

        config = load_config(tmp_path)

        assert isinstance(config, MutmutConfig)

    def test_missing_tool_still_falls_back(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text("[other]\nfoo = 1\n", encoding="utf-8")

        config = load_config(tmp_path)

        assert isinstance(config, MutmutConfig)


class TestPyprojectMutmutStructure:
    """M-028: a present-but-non-table `tool.mutmut` is silently ignored today."""

    @pytest.mark.parametrize(
        "toml_value",
        ["1", '"src"', "[1, 2]", "[]"],
    )
    def test_non_table_mutmut_is_invalid_config_value(
        self, tmp_path: Path, toml_value: str
    ) -> None:
        (tmp_path / "pyproject.toml").write_text(
            f"[tool]\nmutmut = {toml_value}\n", encoding="utf-8"
        )

        with pytest.raises(InvalidConfigValueError, match="expected a table"):
            load_config(tmp_path)

    @given(st.one_of(_TOML_INT64, st.booleans(), st.lists(st.integers(0, 99), max_size=3)))
    def test_any_non_table_mutmut_literal_is_invalid_config_value(
        self, value: int | bool | list[int]
    ) -> None:
        with tempfile.TemporaryDirectory() as td:
            project = Path(td)
            (project / "pyproject.toml").write_text(
                f"[tool]\nmutmut = {_toml_scalar_literal(value)}\n", encoding="utf-8"
            )
            with pytest.raises(InvalidConfigValueError, match="expected a table"):
                load_config(project)

    def test_array_of_tables_with_setup_cfg_present_proves_no_fallback(
        self, tmp_path: Path
    ) -> None:
        # [[tool.mutmut]] parses to a LIST; the old code silently fell
        # through to setup.cfg — this setup.cfg must never be reached.
        (tmp_path / "pyproject.toml").write_text(
            '[[tool.mutmut]]\npaths_to_mutate = ["lib/"]\n', encoding="utf-8"
        )
        (tmp_path / "setup.cfg").write_text("[mutmut]\npaths_to_mutate = src/\n", encoding="utf-8")

        with pytest.raises(InvalidConfigValueError, match="expected a table"):
            load_config(tmp_path)

    def test_empty_mutmut_table_still_falls_back_to_setup_cfg(self, tmp_path: Path) -> None:
        # Only the EMPTY TABLE equals a missing section (Gegenprobe to
        # 'mutmut = []' above, which is a present non-table value).
        (tmp_path / "pyproject.toml").write_text("[tool.mutmut]\n", encoding="utf-8")
        (tmp_path / "setup.cfg").write_text("[mutmut]\npaths_to_mutate = src/\n", encoding="utf-8")

        config = load_config(tmp_path)

        assert config.paths_to_mutate == ["src/"]


class TestPyprojectStructureCli:
    """M-078/M-028: wrong TOML types exit 2 through the config contract."""

    @pytest.mark.parametrize(
        ("pyproject_text", "expected_fragment"),
        [
            ("tool = 1\n", "must be a table"),
            ("[tool]\nmutmut = 1\n", "expected a table"),
        ],
    )
    def test_structure_errors_exit_2_without_traceback(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        pyproject_text: str,
        expected_fragment: str,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / "mutants").mkdir()
        (tmp_path / "pyproject.toml").write_text(pyproject_text, encoding="utf-8")

        result = CliRunner().invoke(cli, ["show", "src.mod.x_f__mutmut_1"])

        assert result.exit_code == 2
        assert expected_fragment in result.output + str(result.stderr)
        assert result.exception is None or isinstance(result.exception, SystemExit)
