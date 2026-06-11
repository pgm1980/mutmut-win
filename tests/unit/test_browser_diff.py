"""Tests for the browser diff source (Issue #108, audit A4-UI-007).

The TUI diff was a WHOLE-FILE diff: original source vs the trampolined
mutants file — trampoline boilerplate plus ALL mutant variants, identical
for every mutant (a 79-line diff for an 8-line module).  And the DB
fallback searched mutants/ file contents for the QUALIFIED mutant name
(``pkg.mod.x_f__mutmut_1``) while files only ever contain the LOCAL
definition name (``def x_f__mutmut_1``) — it always reported
'mutant not found'.

Single-source fix (the sprint 30-32 line): the browser consumes the same
per-mutant CST diff that powers ``show`` (``mutant_diff``).  The pins below
target the diff SOURCE, not rendered TUI pixels.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

from mutmut_win.browser import _get_diff_for_mutant
from mutmut_win.mutant_diff import render_function_diff

if TYPE_CHECKING:
    import pytest

_MUTANTS_FILE = """\
from typing import Annotated

def x_f__mutmut_orig():
    return 1

def x_f__mutmut_1():
    return 2

x_f__mutmut_mutants = {"x_f__mutmut_1": x_f__mutmut_1}

def f():
    return None
"""


def _stage_mutants_file(tmp_path: Path) -> None:
    src = tmp_path / "mutants" / "src"
    src.mkdir(parents=True)
    (src / "mod.py").write_text(_MUTANTS_FILE, encoding="utf-8")


class TestRenderFunctionDiff:
    def test_renders_the_per_mutant_function_diff(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        _stage_mutants_file(tmp_path)

        diff = render_function_diff(Path("src/mod.py"), "src.mod.x_f__mutmut_1")

        assert "-    return 1" in diff
        assert "+    return 2" in diff
        # The whole-file diff always dragged the trampoline noise along.
        assert "x_f__mutmut_mutants" not in diff


class TestBrowserDiffSingleSource:
    def test_known_path_uses_the_shared_renderer(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Meta-backed case: the browser knows the path — same renderer as
        # `show`, no whole-file diff.
        monkeypatch.chdir(tmp_path)
        with patch(
            "mutmut_win.mutant_diff.render_function_diff", return_value="SENTINEL-DIFF"
        ) as renderer:
            result = _get_diff_for_mutant("src.mod.x_f__mutmut_1", path=Path("src/mod.py"))

        assert result == "SENTINEL-DIFF"
        renderer.assert_called_once_with(Path("src/mod.py"), "src.mod.x_f__mutmut_1")

    def test_db_fallback_finds_the_local_definition_name(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # No meta files, no path: the fallback must search for the LOCAL
        # name form — the qualified name never appears in file contents
        # (the old scan always came back 'not found').
        monkeypatch.chdir(tmp_path)
        _stage_mutants_file(tmp_path)

        diff = _get_diff_for_mutant("src.mod.x_f__mutmut_1", path=None)

        assert "-    return 1" in diff
        assert "+    return 2" in diff

    def test_unknown_mutant_reports_not_found(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        _stage_mutants_file(tmp_path)

        result = _get_diff_for_mutant("src.mod.x_nope__mutmut_9", path=None)

        assert "not found" in result
