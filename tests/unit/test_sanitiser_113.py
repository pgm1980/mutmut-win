"""Issue #113 (audit A3-FD-008): pyproject sanitiser vs. uv subtables.

The staged ``mutants/pyproject.toml`` must not point at local/relative
uv sources — mutants/ is one level deeper, so those paths break with
"Distribution not found". The sanitiser stripped ``[tool.uv.sources]``
but missed the SUBTABLE syntax ``[tool.uv.sources.<pkg>]``, which kept
the error alive for projects using that form.

M-035 adds the TOML-lexical regressions: the removal must be anchored to
real header lines and verified against ``tomllib`` so table patterns that
live inside valid TOML strings (or trailing comments) survive untouched.
"""

from __future__ import annotations

import copy
import json
import tempfile
import tomllib
from typing import TYPE_CHECKING

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from mutmut_win.file_setup import _sanitise_mutants_pyproject

if TYPE_CHECKING:
    from pathlib import Path
    from typing import Any


@pytest.fixture(autouse=True)
def _isolated_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "mutants").mkdir()


def _sanitise(content: str, tmp_path: Path) -> str:
    pyproject = tmp_path / "mutants" / "pyproject.toml"
    pyproject.write_text(content, encoding="utf-8")
    _sanitise_mutants_pyproject()
    return pyproject.read_text(encoding="utf-8")


def _runtime_warnings(recwarn: pytest.WarningsRecorder) -> list[pytest.WarningsRecorder.Item]:
    return [entry for entry in recwarn.list if issubclass(entry.category, RuntimeWarning)]


def _oracle_without_uv_sources(document: dict[str, Any]) -> dict[str, Any]:
    """Test-local oracle: the document minus tool.uv.sources (M-035).

    Deliberately independent of the production helper so the property
    cannot prove the implementation with itself.
    """
    cleaned = copy.deepcopy(document)
    tool = cleaned.get("tool")
    if not isinstance(tool, dict):
        return cleaned
    uv = tool.get("uv")
    if isinstance(uv, dict):
        uv.pop("sources", None)
        if not uv:
            del tool["uv"]
    if not tool:
        cleaned.pop("tool", None)
    return cleaned


PROJECT_HEADER = '[project]\nname = "demo"\nversion = "1.0"\n'


class TestPlainSourcesSection:
    def test_plain_sources_section_removed(self, tmp_path: Path) -> None:
        """Regression pin — the pre-#113 behavior that already worked."""
        content = PROJECT_HEADER + '[tool.uv.sources]\nmy-pkg = { path = "../../my-pkg" }\n'
        cleaned = _sanitise(content, tmp_path)
        assert "[tool.uv.sources]" not in cleaned
        assert "my-pkg" not in cleaned
        assert '[project]\nname = "demo"' in cleaned

    def test_file_without_sources_untouched(self, tmp_path: Path) -> None:
        content = PROJECT_HEADER + "[tool.ruff]\nline-length = 100\n"
        assert _sanitise(content, tmp_path) == content

    def test_missing_pyproject_is_a_noop(self) -> None:
        _sanitise_mutants_pyproject()  # must not raise


class TestSubtableSources:
    def test_subtable_removed(self, tmp_path: Path) -> None:
        """FD-008: ``[tool.uv.sources.<pkg>]`` is its own section header —
        the old regex stopped right in front of it."""
        content = PROJECT_HEADER + '[tool.uv.sources.my-pkg]\npath = "../../my-pkg"\n'
        cleaned = _sanitise(content, tmp_path)
        assert "tool.uv.sources" not in cleaned
        assert "../../my-pkg" not in cleaned
        assert '[project]\nname = "demo"' in cleaned

    def test_quoted_subtable_removed(self, tmp_path: Path) -> None:
        content = PROJECT_HEADER + '[tool.uv.sources."my.pkg"]\npath = "../x"\n'
        cleaned = _sanitise(content, tmp_path)
        assert "tool.uv.sources" not in cleaned

    def test_multiple_subtables_removed_and_neighbours_survive(self, tmp_path: Path) -> None:
        content = (
            PROJECT_HEADER
            + '[tool.uv.sources.pkg-a]\npath = "../a"\n'
            + '[tool.uv.sources.pkg-b]\ngit = "https://example.com/b.git"\n'
            + "[tool.ruff]\nline-length = 100\n"
        )
        cleaned = _sanitise(content, tmp_path)
        assert "tool.uv.sources" not in cleaned
        assert "[tool.ruff]\nline-length = 100" in cleaned

    def test_mixed_parent_and_subtable_removed(self, tmp_path: Path) -> None:
        content = (
            PROJECT_HEADER
            + '[tool.uv.sources]\npkg-a = { path = "../a" }\n'
            + '[tool.uv.sources.pkg-b]\npath = "../b"\n'
        )
        cleaned = _sanitise(content, tmp_path)
        assert "tool.uv.sources" not in cleaned

    def test_subtable_at_eof_without_trailing_newline(self, tmp_path: Path) -> None:
        content = PROJECT_HEADER + '[tool.uv.sources.my-pkg]\npath = "../x"'
        cleaned = _sanitise(content, tmp_path)
        assert "tool.uv.sources" not in cleaned
        assert "../x" not in cleaned


class TestEmptyToolUvCleanup:
    def test_tool_uv_left_empty_is_removed(self, tmp_path: Path) -> None:
        content = PROJECT_HEADER + '[tool.uv]\n[tool.uv.sources.my-pkg]\npath = "../x"\n'
        cleaned = _sanitise(content, tmp_path)
        assert "[tool.uv]" not in cleaned

    def test_tool_uv_with_other_keys_survives(self, tmp_path: Path) -> None:
        content = (
            PROJECT_HEADER
            + '[tool.uv]\ndev-dependencies = ["pytest"]\n'
            + '[tool.uv.sources.my-pkg]\npath = "../x"\n'
        )
        cleaned = _sanitise(content, tmp_path)
        assert '[tool.uv]\ndev-dependencies = ["pytest"]' in cleaned
        assert "tool.uv.sources" not in cleaned


class TestTomlLexicalState:
    """M-035: table patterns inside valid TOML strings/comments survive."""

    def test_table_pattern_inside_multiline_string_keeps_valid_toml(
        self,
        tmp_path: Path,
    ) -> None:
        content = (
            PROJECT_HEADER
            + 'description = """\n[tool.uv.sources]\nmore\n"""\n'
            + "[tool.ruff]\nline-length = 100\n"
        )
        with pytest.warns(RuntimeWarning):
            result = _sanitise(content, tmp_path)

        tomllib.loads(result)  # must remain parseable
        assert result == content

    def test_table_pattern_in_trailing_comment_does_not_drop_keys(self, tmp_path: Path) -> None:
        content = (
            "[tool.pytest.ini_options] # like [tool.uv.sources]\n"
            'addopts = "-q"\n[tool.ruff]\nx = 1\n'
        )
        assert _sanitise(content, tmp_path) == content

    def test_table_pattern_mid_line_in_multiline_string_is_untouched(self, tmp_path: Path) -> None:
        content = (
            PROJECT_HEADER
            + 'description = """\nsee [tool.uv.sources] here\n"""\n'
            + "[tool.ruff]\nx = 1\n"
        )
        assert _sanitise(content, tmp_path) == content

    def test_crlf_file_with_real_sources_table_is_sanitised(self, tmp_path: Path) -> None:
        pyproject = tmp_path / "mutants" / "pyproject.toml"
        raw = (
            PROJECT_HEADER
            + '[tool.uv.sources]\r\nmy-pkg = { path = "../../my-pkg" }\r\n'
            + "[tool.ruff]\r\nline-length = 100\r\n"
        ).encode("utf-8")
        pyproject.write_bytes(raw)

        _sanitise_mutants_pyproject()

        cleaned = pyproject.read_bytes()
        assert b"[tool.uv.sources]" not in cleaned
        assert b"my-pkg" not in cleaned
        assert b"[tool.ruff]" in cleaned
        assert b"line-length = 100" in cleaned

    def test_nan_value_does_not_block_sources_removal(
        self,
        tmp_path: Path,
        recwarn: pytest.WarningsRecorder,
    ) -> None:
        content = PROJECT_HEADER + '[tool.x]\nv = nan\n[tool.uv.sources]\npkg = { path = "../a" }\n'
        cleaned = _sanitise(content, tmp_path)

        assert "tool.uv.sources" not in cleaned
        assert "../a" not in cleaned
        assert _runtime_warnings(recwarn) == []

    def test_real_sources_plus_header_like_line_in_multiline_string(
        self,
        tmp_path: Path,
        recwarn: pytest.WarningsRecorder,
    ) -> None:
        """Per-candidate semantics: the genuine table goes, the string stays."""
        content = (
            PROJECT_HEADER
            + 'story = """\n[tool.uv.sources]\nkept inline\n"""\n'
            + '[tool.uv.sources]\npkg = { path = "../a" }\n[tool.ruff]\nx = 1\n'
        )
        cleaned = _sanitise(content, tmp_path)

        parsed = tomllib.loads(cleaned)
        assert parsed["project"]["name"] == "demo"
        assert "[tool.uv.sources]\nkept inline" in cleaned
        assert "../a" not in cleaned
        assert _runtime_warnings(recwarn) == []

    def test_header_with_trailing_comment_is_removed(self, tmp_path: Path) -> None:
        content = PROJECT_HEADER + '[tool.uv.sources] # local deps\nmy-pkg = { path = "../p" }\n'
        cleaned = _sanitise(content, tmp_path)

        assert "tool.uv.sources" not in cleaned
        assert "../p" not in cleaned

    def test_invalid_original_is_left_untouched_without_warning(
        self,
        tmp_path: Path,
        recwarn: pytest.WarningsRecorder,
    ) -> None:
        content = PROJECT_HEADER + "this is = not valid toml\n"
        assert _sanitise(content, tmp_path) == content
        assert _runtime_warnings(recwarn) == []


_LITERAL_STRING_LINE = st.sampled_from(
    [
        "[tool.uv.sources]",
        "[tool.uv]",
        "# [tool.uv.sources]",
        "plain text",
    ]
)

_TOOL_X_EXTRA_VALUE = st.sampled_from(["", "f = nan\n", "f = inf\n", "f = -0.5\n"])

_TOML_SAFE_TEXT = st.text(
    alphabet=st.characters(min_codepoint=1, max_codepoint=0xD7FF, exclude_characters="\x7f"),
    max_size=8,
)


@st.composite
def _pyproject_documents(draw: st.DrawFn) -> str:
    parts = [PROJECT_HEADER]
    string_lines = draw(st.lists(_LITERAL_STRING_LINE, max_size=3))
    parts.append("note = '''\n" + "\n".join(string_lines) + "\n'''\n")
    if draw(st.booleans()):
        parts.append("[tool.uv]\n")
    if draw(st.booleans()):
        if draw(st.booleans()):
            parts.append('[tool.uv.sources]\nmy-pkg = { path = "../my-pkg" }\n')
        else:
            parts.append('[tool.uv.sources.my-pkg]\npath = "../my-pkg"\n')
    parts.append(f"[tool.x]\nk = {json.dumps(draw(_TOML_SAFE_TEXT))}\n")
    parts.append(draw(_TOOL_X_EXTRA_VALUE))
    parts.append("[tool.ruff]\nline-length = 100\n")
    return "".join(parts)


@settings(deadline=None)  # per-example temp-dir chdir I/O exceeds the 200 ms default
@given(document=_pyproject_documents())
def test_sanitiser_preserves_toml_semantics(document: str) -> None:
    """M-035 property: sanitising never changes TOML semantics.

    The staged result must parse, must equal the original document minus
    ``tool.uv.sources`` (nan-immune via ``parse_float=str``), and must not
    retain a ``sources`` sub-table.  Table patterns inside the literal
    multi-line string must not corrupt the document.
    """
    from pathlib import Path

    with (
        tempfile.TemporaryDirectory() as temporary,
        pytest.MonkeyPatch.context() as patcher,
    ):
        patcher.chdir(temporary)
        (Path(temporary) / "mutants").mkdir()
        pyproject = Path(temporary) / "mutants" / "pyproject.toml"
        pyproject.write_text(document, encoding="utf-8")
        _sanitise_mutants_pyproject()
        result = pyproject.read_text(encoding="utf-8")

    parsed_original = tomllib.loads(document, parse_float=str)
    parsed_result = tomllib.loads(result, parse_float=str)
    assert _oracle_without_uv_sources(parsed_result) == _oracle_without_uv_sources(parsed_original)
    tool = parsed_result.get("tool")
    uv = tool.get("uv") if isinstance(tool, dict) else None
    assert not (isinstance(uv, dict) and "sources" in uv)
