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
import ctypes
import string
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from click.testing import CliRunner
from hypothesis import given, settings
from hypothesis import strategies as st

from mutmut_win.cli import cli
from mutmut_win.config import MutmutConfig, load_config
from mutmut_win.exceptions import ConfigError, InvalidConfigValueError


class TestMutationPathAliasAuthority:
    """Windows short aliases must not become runtime mutant prefixes."""

    @pytest.mark.parametrize("select_file", [False, True])
    def test_real_ntfs_short_alias_is_rejected_before_generation(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, select_file: bool
    ) -> None:
        monkeypatch.chdir(tmp_path)
        package = tmp_path / "src" / "longsourcepackage"
        package.mkdir(parents=True)
        source = package / "longsourcemodule.py"
        source.write_text("def value():\n    return 1\n", encoding="utf-8")
        selected = source if select_file else package
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        short_path = kernel32.GetShortPathNameW
        short_path.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32]
        short_path.restype = ctypes.c_uint32
        buffer = ctypes.create_unicode_buffer(32768)
        length = short_path(str(selected), buffer, len(buffer))
        assert 0 < length < len(buffer), ctypes.get_last_error()
        alias = Path(buffer.value)
        # A missing short-name host capability is not passing alias evidence.
        if alias.name.casefold() == selected.name.casefold():
            pytest.skip("NTFS did not allocate a distinct 8.3 name for this fixture")
        assert alias.samefile(selected)
        relative = selected.relative_to(tmp_path).with_name(alias.name).as_posix()
        (tmp_path / "pyproject.toml").write_text(
            f'[tool.mutmut]\npaths_to_mutate=["{relative}"]\n', encoding="utf-8"
        )
        with pytest.raises(InvalidConfigValueError, match="filesystem alias"):
            load_config()
        result = CliRunner().invoke(cli, ["run", "--dry-run", "--output", "json"])
        assert result.exit_code == 2
        assert "filesystem alias" in result.output
        assert not (tmp_path / "mutants").exists()

    @pytest.mark.parametrize("selected", ["src/package", "SRC/PACKAGE", "src/real~1"])
    def test_existing_case_spelling_and_real_tilde_names_remain_valid(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, selected: str
    ) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / "src/package").mkdir(parents=True)
        (tmp_path / "src/real~1").mkdir()
        config = MutmutConfig(paths_to_mutate=[selected])
        assert config.paths_to_mutate == [selected]

    @given(st.text(alphabet=string.ascii_lowercase, min_size=1, max_size=8))
    def test_existing_directory_case_variants_preserve_configuration(self, name: str) -> None:
        with tempfile.TemporaryDirectory(prefix="mutmut-alias-property-") as directory:
            project = Path(directory)
            (project / name).mkdir()
            config = MutmutConfig.model_validate(
                {"paths_to_mutate": [name.upper()]}, context={"project_root": project}
            )
            assert config.paths_to_mutate == [name.upper()]

if TYPE_CHECKING:
    from collections.abc import Callable


class TestSetupCfgReadBoundary:
    """M-027 / Q-37: unreadable-but-existing setup.cfg is a ConfigError."""

    def test_directory_named_setup_cfg_is_a_config_error(self, tmp_path: Path) -> None:
        # A directory named setup.cfg exists, yet cannot be read as a
        # file. Before the fix: parser.read() swallowed the OSError and
        # silently returned MutmutConfig() defaults.
        (tmp_path / "setup.cfg").mkdir()

        with pytest.raises(ConfigError, match=r"^Failed to read setup\.cfg"):
            load_config(tmp_path)

    def test_directory_setup_cfg_is_an_error_on_the_pyproject_fallback_path(
        self, tmp_path: Path
    ) -> None:
        # Same mechanism via the second fallback (pyproject.toml exists
        # but has no [tool.mutmut]).
        (tmp_path / "pyproject.toml").write_text("[tool.other]\nfoo = 1\n", encoding="utf-8")
        (tmp_path / "setup.cfg").mkdir()

        with pytest.raises(ConfigError, match=r"^Failed to read setup\.cfg"):
            load_config(tmp_path)

    def test_byte_range_locked_setup_cfg_is_a_config_error(
        self, tmp_path: Path, locked_file: Callable[[str], Path]
    ) -> None:
        # Real Windows state (Q-02): open() succeeds, read() fails with
        # PermissionError — this kills any fix that only guards open().
        locked_file("setup.cfg")

        with pytest.raises(ConfigError, match=r"^Failed to read setup\.cfg"):
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

            with pytest.raises(ConfigError, match=r"^Failed to read setup\.cfg"):
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
    @settings(deadline=None)
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

        with pytest.raises(
            ConfigError, match=r"^Failed to read pyproject\.toml: file is not valid UTF-8"
        ):
            load_config(tmp_path)

    def test_utf16_setup_cfg_is_a_config_error(self, tmp_path: Path) -> None:
        (tmp_path / "setup.cfg").write_bytes("[mutmut]\npaths_to_mutate = src/\n".encode("utf-16"))

        with pytest.raises(
            ConfigError, match=r"^Failed to read setup\.cfg: file is not valid UTF-8"
        ):
            load_config(tmp_path)

    def test_utf16_setup_cfg_is_an_error_on_the_pyproject_fallback_path(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "pyproject.toml").write_text("[tool.other]\nfoo = 1\n", encoding="utf-8")
        (tmp_path / "setup.cfg").write_bytes("[mutmut]\npaths_to_mutate = src/\n".encode("utf-16"))

        with pytest.raises(ConfigError, match=r"^Failed to read setup\.cfg"):
            load_config(tmp_path)

    def test_utf8_bom_setup_cfg_still_reports_the_parse_error(self, tmp_path: Path) -> None:
        # Counter-check (no utf-8-sig): a BOM stays a section-header
        # error — unchanged behaviour, just via the new read boundary.
        (tmp_path / "setup.cfg").write_bytes(b"\xef\xbb\xbf[mutmut]\npaths_to_mutate = src/\n")

        with pytest.raises(ConfigError, match=r"^Failed to read setup\.cfg"):
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

        with pytest.raises(
            ConfigError, match=r"^Invalid pyproject\.toml: \[tool\] must be a table"
        ):
            load_config(tmp_path)

    def test_non_table_tool_message_names_the_type(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text("tool = 1\n", encoding="utf-8")

        with pytest.raises(ConfigError, match=r"\[tool\] must be a table, got int$"):
            load_config(tmp_path)

    @given(st.one_of(_TOML_INT64, st.booleans(), st.lists(st.integers(0, 99), max_size=3)))
    @settings(deadline=None)
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

    def test_non_table_mutmut_message_is_word_exact(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text("[tool]\nmutmut = 1\n", encoding="utf-8")

        with pytest.raises(
            InvalidConfigValueError,
            match=(
                r"expected a table, got int \(an array of tables such as "
                r"\[\[tool\.mutmut\]\] is not supported\)$"
            ),
        ):
            load_config(tmp_path)

    @given(st.one_of(_TOML_INT64, st.booleans(), st.lists(st.integers(0, 99), max_size=3)))
    @settings(deadline=None)
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


class TestSetupCfgValidationBoundary:
    """M-077 / Q-39: setup.cfg value errors cross the shared boundary.

    Before the fix the unguarded ``MutmutConfig.model_validate`` let a
    raw pydantic ``ValidationError`` traceback escape (exit 1) instead
    of the exit-2 config contract.
    """

    def test_setup_cfg_value_error_is_invalid_config_value(self, tmp_path: Path) -> None:
        (tmp_path / "setup.cfg").write_text(
            "[mutmut]\npaths_to_mutate = src/\nmax_children = 0\n", encoding="utf-8"
        )

        with pytest.raises(InvalidConfigValueError, match=r"setup\.cfg"):
            load_config(tmp_path)

    def test_setup_cfg_value_error_on_pyproject_fallback_path(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text("[tool.other]\nfoo = 1\n", encoding="utf-8")
        (tmp_path / "setup.cfg").write_text("[mutmut]\nmax_children = 0\n", encoding="utf-8")

        with pytest.raises(InvalidConfigValueError, match=r"setup\.cfg"):
            load_config(tmp_path)

    def test_setup_cfg_message_names_the_source(self, tmp_path: Path) -> None:
        (tmp_path / "setup.cfg").write_text(
            "[mutmut]\npaths_to_mutate = src/\nmax_children = 0\n", encoding="utf-8"
        )

        with pytest.raises(
            InvalidConfigValueError, match=r"^Invalid setup\.cfg \[mutmut\] configuration: "
        ):
            load_config(tmp_path)

    def test_toml_validation_message_is_byte_identical(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            "[tool.mutmut]\nmax_children = 0\n", encoding="utf-8"
        )

        with pytest.raises(
            InvalidConfigValueError, match=r"^Invalid \[tool\.mutmut\] configuration: "
        ):
            load_config(tmp_path)

    def test_validation_context_pins_the_project_root_not_cwd(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The validator context carries project_dir into the model — an
        # absolute paths_to_mutate entry inside the project relativizes
        # against the PROJECT even when the process cwd is elsewhere.
        # (Kills 'context={}' in _validate_config_mapping: without the
        # context the entry resolves against the foreign cwd and fails.)
        (tmp_path / "src").mkdir()
        (tmp_path / "pyproject.toml").write_text(
            f'[tool.mutmut]\npaths_to_mutate = ["{(tmp_path / "src").as_posix()}"]\n',
            encoding="utf-8",
        )
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        monkeypatch.chdir(elsewhere)

        config = load_config(tmp_path)

        assert config.paths_to_mutate == ["src"]

    @given(
        st.sampled_from(
            [
                ("max_children", "0"),
                ("timeout_multiplier", "-1"),
                ("clean_run_timeout", "0"),
                ("max_stack_depth", "0"),
                ("debug", "vielleicht"),
                ("mutation_profile", "bogus"),
                ("do_not_mutate_patterns", "["),
            ]
        )
    )
    @settings(deadline=None)
    def test_every_invalid_setup_cfg_value_is_invalid_config_value(
        self, key_value: tuple[str, str]
    ) -> None:
        # Never a bare pydantic ValidationError — for ANY invalid value,
        # on any hypothesis example (temp dir in the body, no
        # function-scoped fixtures).
        key, value = key_value
        with tempfile.TemporaryDirectory() as td:
            project = Path(td)
            (project / "setup.cfg").write_text(
                f"[mutmut]\npaths_to_mutate = src/\n{key} = {value}\n", encoding="utf-8"
            )
            with pytest.raises(InvalidConfigValueError, match=r"setup\.cfg"):
                load_config(project)


class TestSetupCfgRegexListSplit:
    """M-029: single-line setup.cfg regex lists must not split at quantifier commas.

    ``do_not_mutate_patterns = ^f[0-9]{1,3}$`` used to become the two
    fragments ``'^f[0-9]{1'`` and ``'3}$'`` — both compile, so
    ``_validate_regex_patterns`` stayed green while neither fragment
    matched any function name: the exclusion silently stopped working.
    Only commas inside VALID quantifiers (``{m,n}``, ``{m,}``, ``{,n}``)
    are protected; every other comma keeps splitting exactly as before
    (narrow fix per the design review — a bracket-depth state machine and
    an ambiguity ValueError were explicitly rejected: they would newly
    reject accepted, compilable lists).
    """

    def _load_patterns(self, tmp_path: Path, value: str) -> list[str]:
        (tmp_path / "setup.cfg").write_text(
            f"[mutmut]\npaths_to_mutate = src/\ndo_not_mutate_patterns = {value}\n",
            encoding="utf-8",
        )
        return load_config(tmp_path).do_not_mutate_patterns

    def test_quantifier_comma_does_not_split_the_pattern(self, tmp_path: Path) -> None:
        # Before the fix: ['^f[0-9]{1', '3}$', '_internal'] — two silent
        # no-op fragments instead of the exclusion pattern.
        assert self._load_patterns(tmp_path, "^f[0-9]{1,3}$, _internal") == [
            "^f[0-9]{1,3}$",
            "_internal",
        ]

    def test_simple_comma_list_still_splits(self, tmp_path: Path) -> None:
        # Contract (test_hardening_132 TestSetupCfgParity): plain comma
        # lists keep working byte-for-byte.
        assert self._load_patterns(tmp_path, "test_.*, _internal") == ["test_.*", "_internal"]

    def test_multiline_value_with_comma_in_a_line_stays_unsplit(self, tmp_path: Path) -> None:
        # The multi-line branch (split on newlines) is untouched by the fix.
        (tmp_path / "setup.cfg").write_text(
            "[mutmut]\n"
            "paths_to_mutate = src/\n"
            "do_not_mutate_patterns = ^f[0-9]{1,3}$\n"
            "  _internal\n",
            encoding="utf-8",
        )
        assert load_config(tmp_path).do_not_mutate_patterns == ["^f[0-9]{1,3}$", "_internal"]

    def test_open_half_quantifier_keeps_the_legacy_split(self) -> None:
        from mutmut_win.config import _split_setup_cfg_regex_list

        # '{, b' is NOT a valid quantifier (space, no closing brace) — the
        # legacy comma split applies, and no new rejection is introduced.
        assert _split_setup_cfg_regex_list("a{, b") == ["a{", "b"]

    def test_spaced_quantifier_is_literal_and_still_splits(self) -> None:
        from mutmut_win.config import _split_setup_cfg_regex_list

        # 'a{1, 3}' is a LITERAL in Python re (the space breaks the
        # quantifier), so its comma stays a list separator — unchanged.
        assert _split_setup_cfg_regex_list("^f[0-9]{1, 3}$") == ["^f[0-9]{1", "3}$"]

    def test_all_three_quantifier_forms_are_protected(self) -> None:
        from mutmut_win.config import _split_setup_cfg_regex_list

        assert _split_setup_cfg_regex_list("^f[0-9]{1,3}$") == ["^f[0-9]{1,3}$"]
        assert _split_setup_cfg_regex_list("x{2,}") == ["x{2,}"]
        assert _split_setup_cfg_regex_list("x{,3}") == ["x{,3}"]
        assert _split_setup_cfg_regex_list("x{,3},y") == ["x{,3}", "y"]
        assert _split_setup_cfg_regex_list("a{2,}, b{1,2}") == ["a{2,}", "b{1,2}"]

    @given(
        st.lists(
            st.tuples(
                st.from_regex(r"[a-z_]{1,4}", fullmatch=True),
                st.sampled_from(["", "{2,5}", "{3,}", "{,4}", "{0,9}"]),
            ),
            min_size=1,
            max_size=4,
        )
    )
    def test_patterns_with_quantifier_commas_roundtrip(self, parts: list[tuple[str, str]]) -> None:
        # Property 1 (narrow variant): patterns whose commas all sit in
        # valid quantifiers survive a ', '-join/split round-trip.
        from mutmut_win.config import _split_setup_cfg_regex_list

        patterns = [literal + quant for literal, quant in parts]
        assert _split_setup_cfg_regex_list(", ".join(patterns)) == patterns

    @given(st.text(alphabet="abc[](),._*^$0123456789- ", max_size=40))
    def test_brace_free_strings_behave_exactly_like_the_legacy_split(self, value: str) -> None:
        # Property 2 (compatibility): without '{' there is no quantifier,
        # so the result must equal the old comprehension byte-for-byte.
        from mutmut_win.config import _split_setup_cfg_regex_list

        assert _split_setup_cfg_regex_list(value) == [
            x.strip() for x in value.split(",") if x.strip()
        ]


class TestSetupCfgPatternsReachGeneration:
    """M-029 Folge-Nachweis on generation level: with the pattern loaded
    from setup.cfg, ``f1``/``f123`` produce no mutants while ``f1234``
    still does. Before the fix the fragments matched nothing, so f1/f123
    were mutated despite the exclusion.
    """

    def test_quantifier_pattern_excludes_only_matching_names(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from mutmut_win.constants import Profile
        from mutmut_win.orchestrator import _create_mutants_worker

        monkeypatch.chdir(tmp_path)
        (tmp_path / "setup.cfg").write_text(
            "[mutmut]\npaths_to_mutate = src/\ndo_not_mutate_patterns = ^f[0-9]{1,3}$\n",
            encoding="utf-8",
        )
        patterns = tuple(load_config(tmp_path).do_not_mutate_patterns)
        assert patterns == ("^f[0-9]{1,3}$",)

        src = tmp_path / "m.py"
        src.write_text(
            "def f1():\n"
            "    return 1 + 2\n"
            "\n"
            "\n"
            "def f123():\n"
            "    return 3 + 4\n"
            "\n"
            "\n"
            "def f1234():\n"
            "    return 5 + 6\n",
            encoding="utf-8",
        )
        args: tuple[str, Path, Path, None, bool, Profile, tuple[str, ...]] = (
            "m.py",
            src,
            tmp_path / "mutants" / "m.py",
            None,
            False,
            Profile.ADVANCED,
            patterns,
        )
        _rel, names, err, _warns, _fast, _degraded = _create_mutants_worker(args)
        assert err is None
        # Mutant names look like 'x_f1__mutmut_1'; the '__mutmut_' suffix
        # makes the startswith probe unambiguous ('x_f1__' does not match
        # 'x_f123__...').
        assert not any(name.startswith("x_f1__") for name in names)
        assert not any(name.startswith("x_f123__") for name in names)
        assert any(name.startswith("x_f1234__") for name in names)


class TestConfigErrorChannelCli:
    """Q-40: exit 2 on the config error channel for every subcommand."""

    @pytest.mark.parametrize(
        "argv",
        [
            ["show", "src.mod.x_f__mutmut_1"],
            ["apply", "src.mod.x_f__mutmut_1"],
            ["run", "--dry-run", "--output", "json"],
        ],
    )
    def test_invalid_setup_cfg_value_exits_2(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, argv: list[str]
    ) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / "mutants").mkdir()
        (tmp_path / "setup.cfg").write_text(
            "[mutmut]\npaths_to_mutate = src/\nmax_children = 0\n", encoding="utf-8"
        )

        result = CliRunner().invoke(cli, argv)

        assert result.exit_code == 2
        assert "setup.cfg" in result.output + str(result.stderr)
        assert result.exception is None or isinstance(result.exception, SystemExit)

    def test_run_dry_run_json_emits_a_json_error_object(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import json

        monkeypatch.chdir(tmp_path)
        (tmp_path / "mutants").mkdir()
        (tmp_path / "setup.cfg").write_text(
            "[mutmut]\npaths_to_mutate = src/\nmax_children = 0\n", encoding="utf-8"
        )

        result = CliRunner().invoke(cli, ["run", "--dry-run", "--output", "json"])

        assert result.exit_code == 2
        payload = json.loads(result.stdout)
        assert payload["exit_code"] == 2
        assert "setup.cfg" in payload["error"]


class TestSetupCfgTypoWarningBoundary:
    """M-080 diagnostics, carried in the gate's sole test file (Q-41).

    The full behavioural suite lives in test_hardening_132.py
    (TestSetupCfgParity); these three pin the diagnostic-parser wiring
    so the targeted config.py mutation gate kills its mutants.
    """

    def test_unknown_mutmut_key_still_warns(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        (tmp_path / "setup.cfg").write_text(
            "[mutmut]\npaths_to_mutate = src/\nzz_typo = 1\n", encoding="utf-8"
        )

        load_config(tmp_path)

        assert "zz_typo" in capsys.readouterr().err

    def test_default_only_key_does_not_warn(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # Kills removing the sentinel default_section: without it the
        # effective view returns and the false warning reappears.
        (tmp_path / "setup.cfg").write_text(
            "[DEFAULT]\nauthor_note = x\n[mutmut]\npaths_to_mutate = src/\n",
            encoding="utf-8",
        )

        load_config(tmp_path)

        assert capsys.readouterr().err == ""

    def test_double_default_headers_do_not_fail(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # Kills strict=True in the diagnostic parser: it would reject
        # the repeated [DEFAULT] headers the strict parser accepts.
        (tmp_path / "setup.cfg").write_text(
            "[DEFAULT]\na = 1\n[DEFAULT]\nb = 2\n[mutmut]\npaths_to_mutate = src/\n",
            encoding="utf-8",
        )

        config = load_config(tmp_path)

        assert config.paths_to_mutate == ["src/"]
        assert capsys.readouterr().err == ""


class TestLoadConfigTotalContract:
    """Q-40: for arbitrary configuration bytes load_config is total.

    Either a ``MutmutConfig`` or a ``ConfigError`` — never any other
    exception (raw ``OSError``, ``UnicodeDecodeError``,
    ``AttributeError``, pydantic ``ValidationError``, ...). Robustness
    net across M-027/M-077/M-078/M-079/M-028; the targeted structure
    tests above stay authoritative for the messages. Temp dir in the
    body — no function-scoped fixtures under ``@given``.
    """

    @given(st.binary(min_size=1, max_size=200))
    @settings(deadline=None)
    def test_arbitrary_pyproject_bytes_never_crash_past_the_contract(self, blob: bytes) -> None:
        with tempfile.TemporaryDirectory() as td:
            project = Path(td)
            (project / "pyproject.toml").write_bytes(blob)
            try:
                config = load_config(project)
            except ConfigError:
                pass
            else:
                assert isinstance(config, MutmutConfig)

    @given(st.binary(min_size=1, max_size=200))
    @settings(deadline=None)
    def test_arbitrary_setup_cfg_bytes_never_crash_past_the_contract(self, blob: bytes) -> None:
        with tempfile.TemporaryDirectory() as td:
            project = Path(td)
            (project / "setup.cfg").write_bytes(blob)
            try:
                config = load_config(project)
            except ConfigError:
                pass
            else:
                assert isinstance(config, MutmutConfig)
