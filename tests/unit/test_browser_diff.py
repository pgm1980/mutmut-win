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

import contextlib
import hashlib
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from mutmut_win.browser import _get_diff_for_mutant, _load_source_file_data
from mutmut_win.config import MutmutConfig
from mutmut_win.exceptions import AmbiguousMutantNameError, StaleStagingError
from mutmut_win.file_setup import get_mutant_name
from mutmut_win.models import SourceFileMutationData
from mutmut_win.mutant_diff import locate_staged_source_for_mutant, render_function_diff

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
    # Q-21: canonical name — get_mutant_name(Path("src/mod.py"), ...) builds
    # "mod.x_f__mutmut_1" (the leading "src." root is stripped), so the
    # fixtures must not carry a spelling the generator never produces.
    (src / "mod.py.meta").write_text(
        json.dumps(
            {
                "exit_code_by_key": {"mod.x_f__mutmut_1": 0},
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

        diff = render_function_diff(Path("src/mod.py"), "mod.x_f__mutmut_1")

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
            result = _get_diff_for_mutant("mod.x_f__mutmut_1", path=Path("src/mod.py"))

        assert result == "SENTINEL-DIFF"
        renderer.assert_called_once_with(Path("src/mod.py"), "mod.x_f__mutmut_1")

    def test_db_fallback_without_meta_refuses_unverified_diff(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # A DB-only name can locate staged code, but without the generation
        # source hash it cannot authorize a patchable diff.
        monkeypatch.chdir(tmp_path)
        _stage_mutants_file(tmp_path)
        (tmp_path / "mutants" / "src" / "mod.py.meta").unlink()

        with pytest.raises(StaleStagingError, match="before showing or applying"):
            _get_diff_for_mutant("mod.x_f__mutmut_1", path=None)

    def test_db_fallback_with_corrupt_sidecar_never_deletes_it(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # M-026: a corrupt sidecar is NOT healed away by the read-only
        # fallback — the browser shares the no-delete reading contract of
        # the overview (whatever fails, fails without touching metadata).
        monkeypatch.chdir(tmp_path)
        _stage_mutants_file(tmp_path)
        corrupt = tmp_path / "mutants" / "src" / "mod.py.meta"
        payload = b"\xffnot json\x00"
        corrupt.write_bytes(payload)

        with pytest.raises(StaleStagingError, match="before showing or applying"):
            _get_diff_for_mutant("mod.x_f__mutmut_1", path=None)

        assert corrupt.read_bytes() == payload

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
            _get_diff_for_mutant("mod.x_f__mutmut_1", path=Path("src/mod.py"))

    def test_unknown_mutant_reports_not_found(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        _stage_mutants_file(tmp_path)

        result = _get_diff_for_mutant("mod.x_nope__mutmut_9", path=None)

        assert "not found" in result

    @staticmethod
    def _force_mutants_rglob_order(monkeypatch: pytest.MonkeyPatch, first: Path) -> None:
        """Deterministic rglob order for the mutants root only (delegates
        everywhere else — a global Path.rglob patch would hit every caller)."""
        original_rglob = Path.rglob

        def ordered_rglob(self: Path, pattern: str) -> object:
            result = original_rglob(self, pattern)
            if pattern == "*.py" and self == Path("mutants"):
                files = [entry for entry in result if entry.is_file()]
                files.sort(key=lambda entry: (entry != first, str(entry)))
                return iter(files)
            return result

        monkeypatch.setattr(Path, "rglob", ordered_rglob)

    def test_db_fallback_renders_the_true_owner_not_the_first_content_hit(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # M-115: identical staged content in two modules — the fallback must
        # identify the owner by module identity, not by the first file whose
        # text happens to contain "def x_f__mutmut_1".
        monkeypatch.chdir(tmp_path)
        for module in ("a", "b"):
            source = tmp_path / "src" / f"{module}.py"
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_text("def f():\n    return 1\n", encoding="utf-8")
            staged = tmp_path / "mutants" / "src" / f"{module}.py"
            staged.parent.mkdir(parents=True, exist_ok=True)
            staged.write_text(_MUTANTS_FILE, encoding="utf-8")
        meta_owner = SourceFileMutationData(path="src/a.py")
        meta_owner.exit_code_by_key = {"a.x_f__mutmut_1": 0}
        meta_owner.source_hash = hashlib.sha256(
            (tmp_path / "src" / "a.py").read_bytes()
        ).hexdigest()
        meta_owner.generated_hash = hashlib.sha256(
            (tmp_path / "mutants" / "src" / "a.py").read_bytes()
        ).hexdigest()
        meta_owner.save()
        # The foreign module comes first in the scan: on the old content
        # fallback this rendered a's diff for b's mutant.
        self._force_mutants_rglob_order(monkeypatch, tmp_path / "mutants" / "src" / "a.py")

        with pytest.raises(StaleStagingError) as excinfo:
            _get_diff_for_mutant("b.x_f__mutmut_1", path=None)

        assert "b.py" in str(excinfo.value)

    def test_db_fallback_result_is_independent_of_scan_order(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        for module in ("a", "b"):
            source = tmp_path / "src" / f"{module}.py"
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_text("def f():\n    return 1\n", encoding="utf-8")
            staged = tmp_path / "mutants" / "src" / f"{module}.py"
            staged.parent.mkdir(parents=True, exist_ok=True)
            staged.write_text(_MUTANTS_FILE, encoding="utf-8")

        for first in (tmp_path / "mutants" / "src" / "a.py", tmp_path / "mutants" / "src" / "b.py"):
            self._force_mutants_rglob_order(monkeypatch, first)
            with pytest.raises(StaleStagingError) as excinfo:
                _get_diff_for_mutant("b.x_f__mutmut_1", path=None)
            assert "b.py" in str(excinfo.value)

    def test_render_function_diff_refuses_foreign_mutant_of_another_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # M-115: a known path alone is no provenance — rendering b's mutant
        # from a's file (valid meta, passing hashes) must fail closed.
        monkeypatch.chdir(tmp_path)
        for module in ("a", "b"):
            source = tmp_path / "src" / f"{module}.py"
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_text("def f():\n    return 1\n", encoding="utf-8")
            staged = tmp_path / "mutants" / "src" / f"{module}.py"
            staged.parent.mkdir(parents=True, exist_ok=True)
            staged.write_text(_MUTANTS_FILE, encoding="utf-8")
        meta_owner = SourceFileMutationData(path="src/a.py")
        meta_owner.exit_code_by_key = {"a.x_f__mutmut_1": 0}
        meta_owner.source_hash = hashlib.sha256(
            (tmp_path / "src" / "a.py").read_bytes()
        ).hexdigest()
        meta_owner.generated_hash = hashlib.sha256(
            (tmp_path / "mutants" / "src" / "a.py").read_bytes()
        ).hexdigest()
        meta_owner.save()

        with pytest.raises(FileNotFoundError, match="not recorded"):
            render_function_diff(Path("src/a.py"), "b.x_f__mutmut_1")

    def test_ordinal_prefix_does_not_render_the_longer_ordinal(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # M-115: "def x_add__mutmut_3" is a substring of "def
        # x_add__mutmut_30" — a content scan treated the longer ordinal as
        # the requested mutant's owner.
        monkeypatch.chdir(tmp_path)
        source = tmp_path / "src" / "a.py"
        source.parent.mkdir(parents=True)
        source.write_text("def add():\n    return 1\n", encoding="utf-8")
        staged = tmp_path / "mutants" / "src" / "a.py"
        staged.parent.mkdir(parents=True)
        staged.write_text(
            "def x_add__mutmut_orig():\n    return 1\n\ndef x_add__mutmut_30():\n    return 2\n",
            encoding="utf-8",
        )
        metadata = SourceFileMutationData(path="src/a.py")
        metadata.exit_code_by_key = {"a.x_add__mutmut_30": 0}
        metadata.source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
        metadata.generated_hash = hashlib.sha256(staged.read_bytes()).hexdigest()
        metadata.save()

        result = _get_diff_for_mutant("a.x_add__mutmut_3", path=None)

        assert "not found" in result

    def test_identity_collision_across_staging_roots_is_ambiguous(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # mutants/a.py and mutants/src/a.py both map to the module identity
        # "a" — an owner is not uniquely determinable, which is never the
        # license to render the first hit.
        monkeypatch.chdir(tmp_path)
        for staged in (tmp_path / "mutants" / "a.py", tmp_path / "mutants" / "src" / "a.py"):
            staged.parent.mkdir(parents=True, exist_ok=True)
            staged.write_text(_MUTANTS_FILE, encoding="utf-8")

        with pytest.raises(AmbiguousMutantNameError):
            _get_diff_for_mutant("a.x_f__mutmut_1", path=None)


class TestLocateStagedSource:
    """M-115: identity-based owner location for the DB-only fallback."""

    def test_roundtrips_the_canonical_forward_mapping(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        staged = tmp_path / "mutants" / "src" / "pkg" / "mod.py"
        staged.parent.mkdir(parents=True)
        staged.write_text(_MUTANTS_FILE, encoding="utf-8")

        located = locate_staged_source_for_mutant("pkg.mod.x_f__mutmut_1")

        assert located == Path("src/pkg/mod.py")

    def test_no_staged_tree_fails_closed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / "mutants").mkdir()

        with pytest.raises(FileNotFoundError):
            locate_staged_source_for_mutant("mod.x_f__mutmut_1")

    def test_module_identity_is_case_sensitive(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Q-20: components below the stripped source root must match the
        # generation-time spelling exactly — deviating casing is "not
        # found" (fail-closed), never a different module's diff.
        monkeypatch.chdir(tmp_path)
        staged = tmp_path / "mutants" / "src" / "Pkg" / "mod.py"
        staged.parent.mkdir(parents=True)
        staged.write_text(_MUTANTS_FILE, encoding="utf-8")

        with pytest.raises(FileNotFoundError):
            locate_staged_source_for_mutant("pkg.mod.x_f__mutmut_1")

    def test_identity_collision_is_ambiguous(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        for staged in (tmp_path / "mutants" / "a.py", tmp_path / "mutants" / "src" / "a.py"):
            staged.parent.mkdir(parents=True, exist_ok=True)
            staged.write_text(_MUTANTS_FILE, encoding="utf-8")

        with pytest.raises(AmbiguousMutantNameError):
            locate_staged_source_for_mutant("a.x_f__mutmut_1")


@given(
    components=st.lists(
        st.from_regex(r"[a-z][a-z0-9_]{0,6}", fullmatch=True),
        min_size=1,
        max_size=4,
        unique=True,
    )
)
@settings(max_examples=25, deadline=None)
def test_locate_roundtrips_every_canonical_module_path(components: list[str]) -> None:
    """M-115: locate inverts get_mutant_name for any generated module path."""
    with (
        tempfile.TemporaryDirectory() as tmp,
        contextlib.chdir(tmp),
    ):
        source_rel = Path("src").joinpath(*components).with_suffix(".py")
        staged = Path("mutants") / source_rel
        staged.parent.mkdir(parents=True)
        staged.write_text(_MUTANTS_FILE, encoding="utf-8")

        mutant_name = get_mutant_name(source_rel, "x_f__mutmut_1")

        assert locate_staged_source_for_mutant(mutant_name) == source_rel


class TestFallbackToleratesNonUtf8Staging:
    """M-116: staged files keep their source encoding (e.g. cp1252) — the
    fallback must never abort with a UnicodeDecodeError scanning them.

    The fix came with M-115's identity-based location (no file contents
    are read anymore); these pins guard against a reintroduction of a
    strict UTF-8 scan."""

    @staticmethod
    def _stage_cp1252_neighbor(tmp_path: Path) -> Path:
        latin = tmp_path / "mutants" / "src" / "latin.py"
        payload = "# coding: cp1252\nlabel = 'caf\xe9'\n".encode("cp1252")
        latin.write_bytes(payload)
        # Fixture guard: these bytes are genuinely not valid UTF-8.
        try:
            payload.decode("utf-8")
        except UnicodeDecodeError:
            return latin
        raise AssertionError("fixture must be non-UTF-8")

    def test_unknown_mutant_with_cp1252_staging_reports_not_found(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        _stage_mutants_file(tmp_path)
        self._stage_cp1252_neighbor(tmp_path)

        result = _get_diff_for_mutant("mod.x_nope__mutmut_9", path=None)

        assert "not found" in result

    def test_target_mutant_is_found_despite_non_utf8_neighbor_first(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        _stage_mutants_file(tmp_path)
        latin = self._stage_cp1252_neighbor(tmp_path)
        # Force the config walk to fail so the DB-only fallback runs, and
        # make the non-UTF-8 file the first entry of the mutants scan.
        TestBrowserDiffSingleSource._force_mutants_rglob_order(monkeypatch, latin)
        empty_config = MutmutConfig(paths_to_mutate=[])

        with patch("mutmut_win.config.load_config", return_value=empty_config):
            diff = _get_diff_for_mutant("mod.x_f__mutmut_1", path=None)

        assert "-    return 1" in diff
        assert "+    return 2" in diff
