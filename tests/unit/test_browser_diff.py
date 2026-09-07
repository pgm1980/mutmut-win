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

import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from mutmut_win.browser import _get_diff_for_mutant, _load_source_file_data
from mutmut_win.exceptions import StaleStagingError
from mutmut_win.models import SourceFileMutationData
from mutmut_win.mutant_diff import render_function_diff

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
    staged = src / "mod.py"
    staged.write_text(_MUTANTS_FILE, encoding="utf-8")
    source = tmp_path / "src" / "mod.py"
    source.parent.mkdir(parents=True)
    source.write_text("def f():\n    return 1\n", encoding="utf-8")
    (src / "mod.py.meta").write_text(
        json.dumps(
            {
                "exit_code_by_key": {"src.mod.x_f__mutmut_1": 0},
                "source_hash": hashlib.sha256(source.read_bytes()).hexdigest(),
                "generated_hash": hashlib.sha256(staged.read_bytes()).hexdigest(),
            }
        ),
        encoding="utf-8",
    )


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
    def test_metadata_discovery_ignores_fixture_without_deleting_it(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        fixture = tmp_path / "mutants" / "tests" / "runtime.meta"
        fixture.parent.mkdir(parents=True)
        payload = b"\xffproject fixture\x00"
        fixture.write_bytes(payload)

        assert _load_source_file_data() == {}
        assert fixture.read_bytes() == payload

    def test_metadata_discovery_loads_only_schema_owned_sidecar(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        generated = tmp_path / "mutants" / "src" / "mod.py"
        generated.parent.mkdir(parents=True)
        generated.write_text("VALUE = 1\n", encoding="utf-8")
        metadata = SourceFileMutationData(
            path="src/mod.py",
            exit_code_by_key={"mod.x_f__mutmut_1": 1},
            source_hash="a" * 64,
            generation_fingerprint="b" * 64,
            generated_hash=hashlib.sha256(generated.read_bytes()).hexdigest(),
        )
        metadata.save()

        loaded = _load_source_file_data()

        source_path = str(Path("src/mod.py"))
        assert set(loaded) == {source_path}
        assert loaded[source_path][0].exit_code_by_key == {"mod.x_f__mutmut_1": 1}

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

    def test_db_fallback_without_meta_refuses_unverified_diff(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # A DB-only name can locate staged code, but without the generation
        # source hash it cannot authorize a patchable diff.
        monkeypatch.chdir(tmp_path)
        _stage_mutants_file(tmp_path)
        (tmp_path / "mutants" / "src" / "mod.py.meta").unlink()

        with pytest.raises(StaleStagingError, match="before showing or applying"):
            _get_diff_for_mutant("src.mod.x_f__mutmut_1", path=None)

    def test_known_path_refuses_stale_source(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        _stage_mutants_file(tmp_path)
        (tmp_path / "src" / "mod.py").write_text(
            "def f():\n    return 100\n",
            encoding="utf-8",
        )

        with pytest.raises(StaleStagingError, match="before showing or applying"):
            _get_diff_for_mutant("src.mod.x_f__mutmut_1", path=Path("src/mod.py"))

    def test_unknown_mutant_reports_not_found(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        _stage_mutants_file(tmp_path)

        result = _get_diff_for_mutant("src.mod.x_nope__mutmut_9", path=None)

        assert "not found" in result
