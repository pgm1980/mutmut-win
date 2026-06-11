"""Issue #113 (audit A3-FD-008): pyproject sanitiser vs. uv subtables.

The staged ``mutants/pyproject.toml`` must not point at local/relative
uv sources — mutants/ is one level deeper, so those paths break with
"Distribution not found". The sanitiser stripped ``[tool.uv.sources]``
but missed the SUBTABLE syntax ``[tool.uv.sources.<pkg>]``, which kept
the error alive for projects using that form.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from mutmut_win.file_setup import _sanitise_mutants_pyproject

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture(autouse=True)
def _isolated_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "mutants").mkdir()


def _sanitise(content: str, tmp_path: Path) -> str:
    pyproject = tmp_path / "mutants" / "pyproject.toml"
    pyproject.write_text(content, encoding="utf-8")
    _sanitise_mutants_pyproject()
    return pyproject.read_text(encoding="utf-8")


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
