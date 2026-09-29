"""Issue #115 (audit A4-UI-012/014/015): CLI/output consistency.

UI-012 — mutant-name matching was inconsistent across five commands
(run: exact+glob; show/apply/time-estimates: exact only) and documented
nowhere. One shared matcher backs them all; show/apply accept globs but
require a UNIQUE match and list the candidates on ambiguity.

UI-014 — ``show`` diffs were not patch-capable: hunk headers were
function-relative (always ``@@ -1``) and the from/to labels identical.
Hunks now carry the function's real line numbers in the original file
and distinct ``a/``/``b/`` labels.

UI-015 — ``Suspicious:1`` printed without the space every other summary
line has (the label is exactly as wide as the old field width).
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import ClassVar
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from mutmut_win.cli import cli
from mutmut_win.config import load_config
from mutmut_win.exceptions import AmbiguousMutantNameError, StaleStagingError
from mutmut_win.models import MutationResult, SourceFileMutationData
from mutmut_win.mutant_diff import render_function_diff, resolve_mutant
from mutmut_win.test_mapping import match_mutant_names

# ---------------------------------------------------------------------------
# UI-012 — the shared matcher
# ---------------------------------------------------------------------------


class TestMatchMutantNames:
    CANDIDATES: ClassVar[list[str]] = [
        "src.mod.x_foo__mutmut_1",
        "src.mod.x_foo__mutmut_2",
        "src.other.x_bar__mutmut_1",
    ]

    def test_exact_match(self) -> None:
        assert match_mutant_names(["src.mod.x_foo__mutmut_2"], self.CANDIDATES) == [
            "src.mod.x_foo__mutmut_2"
        ]

    def test_glob_match(self) -> None:
        assert match_mutant_names(["src.mod.*"], self.CANDIDATES) == [
            "src.mod.x_foo__mutmut_1",
            "src.mod.x_foo__mutmut_2",
        ]

    def test_no_match_is_empty(self) -> None:
        assert match_mutant_names(["nope"], self.CANDIDATES) == []

    def test_candidate_order_is_stable(self) -> None:
        matched = match_mutant_names(["src.*"], self.CANDIDATES)
        assert matched == self.CANDIDATES

    # M-056 / Q-20: mutant names carry case-sensitive Python identifiers.
    # ``fnmatch.fnmatch`` folds both sides via ``os.path.normcase`` on
    # Windows, so an exact name used to select its case twin too.
    def test_case_twin_exact_name_matches_only_the_identical_candidate(self) -> None:
        candidates = ["pkg.mod.x_Parse__mutmut_1", "pkg.mod.x_parse__mutmut_1"]
        assert match_mutant_names(["pkg.mod.x_parse__mutmut_1"], candidates) == [
            "pkg.mod.x_parse__mutmut_1"
        ]

    def test_case_twin_exact_name_never_matches_the_other_twin(self) -> None:
        assert (
            match_mutant_names(["pkg.mod.x_parse__mutmut_1"], ["pkg.mod.x_Parse__mutmut_1"]) == []
        )

    def test_case_sensitive_glob_selects_only_the_case_twin(self) -> None:
        candidates = ["pkg.mod.x_Parse__mutmut_1", "pkg.mod.x_parse__mutmut_1"]
        assert match_mutant_names(["pkg.mod.x_P*"], candidates) == ["pkg.mod.x_Parse__mutmut_1"]


@given(name=st.from_regex(r"[A-Za-z_][A-Za-z0-9_]{0,15}", fullmatch=True))
@settings(max_examples=25, deadline=None)
def test_matching_is_case_sensitive_for_identifier_twins(name: str) -> None:
    """M-056: identifiers keep their case on every platform (Q-20)."""
    assume(name != name.swapcase())
    exact = f"m.x_{name}__mutmut_1"
    twin = f"m.x_{name.swapcase()}__mutmut_1"
    assert match_mutant_names([exact], [twin]) == []
    assert match_mutant_names([exact], [twin, exact]) == [exact]


# ---------------------------------------------------------------------------
# UI-012 — show/apply resolution: glob + unique match
# ---------------------------------------------------------------------------


_MUTANTS_SOURCE = """\
def x_foo__mutmut_orig() -> int:
    return 1

def x_foo__mutmut_1() -> int:
    return 2

def x_foo__mutmut_2() -> int:
    return 3
"""


@pytest.fixture
def staged_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "mod.py").write_text("def foo() -> int:\n    return 1\n", encoding="utf-8")
    (tmp_path / "mutants" / "src").mkdir(parents=True)
    (tmp_path / "mutants" / "src" / "mod.py").write_text(_MUTANTS_SOURCE, encoding="utf-8")
    data = SourceFileMutationData(path="src/mod.py")
    # Q-21: canonical names as get_mutant_name() builds them for src/mod.py
    # (the leading ``src.`` root is stripped) — the logic is never bent to
    # non-canonical fixture spellings.
    data.exit_code_by_key = {
        "mod.x_foo__mutmut_1": 0,
        "mod.x_foo__mutmut_2": 1,
    }
    data.save()
    return tmp_path


def _config() -> MagicMock:
    cfg = MagicMock()
    cfg.paths_to_mutate = ["src/"]
    cfg.should_ignore_for_mutation.return_value = False
    return cfg


@pytest.mark.usefixtures("staged_project")
class TestResolveMutant:
    def test_exact_name_resolves(self) -> None:
        from pathlib import Path as _Path

        name, data = resolve_mutant("mod.x_foo__mutmut_1", _config())
        assert name == "mod.x_foo__mutmut_1"
        assert _Path(data.path) == _Path("src/mod.py")

    def test_unique_glob_resolves(self) -> None:
        name, _data = resolve_mutant("*__mutmut_2", _config())
        assert name == "mod.x_foo__mutmut_2"

    def test_ambiguous_glob_lists_candidates(self) -> None:
        with pytest.raises(AmbiguousMutantNameError) as excinfo:
            resolve_mutant("mod.*", _config())
        msg = str(excinfo.value)
        assert "mod.x_foo__mutmut_1" in msg
        assert "mod.x_foo__mutmut_2" in msg

    def test_no_match_keeps_file_not_found(self) -> None:
        with pytest.raises(FileNotFoundError):
            resolve_mutant("nope.*", _config())

    def test_exact_name_resolves_despite_case_twin_in_the_same_file(self) -> None:
        # M-056: with the case-insensitive matcher, the exact lowercase
        # name matched BOTH keys of one file and resolve_mutant failed
        # with AmbiguousMutantNameError for a uniquely named mutant.
        data = SourceFileMutationData(path="src/mod.py")
        data.exit_code_by_key = {
            "mod.x_Parse__mutmut_1": 0,
            "mod.x_parse__mutmut_1": 1,
        }
        data.save()

        name, _m = resolve_mutant("mod.x_parse__mutmut_1", _config())

        assert name == "mod.x_parse__mutmut_1"

    def test_case_deviant_input_fails_closed_instead_of_matching_the_twin(self) -> None:
        # M-056: apply must never silently pick the case twin — a name
        # that is not recorded exactly is "not found", nothing else.
        data = SourceFileMutationData(path="src/mod.py")
        data.exit_code_by_key = {"mod.x_Parse__mutmut_1": 0}
        data.save()

        with pytest.raises(FileNotFoundError):
            resolve_mutant("mod.x_parse__mutmut_1", _config())


def _write_pyproject(paths: list[str]) -> None:
    """Write a pyproject.toml whose config survives the validation path."""
    import json

    entries = ", ".join(json.dumps(entry) for entry in paths)
    Path("pyproject.toml").write_text(
        f"[tool.mutmut]\npaths_to_mutate = [{entries}]\n", encoding="utf-8"
    )


@pytest.mark.usefixtures("staged_project")
class TestResolveMutantDuplicateRoots:
    """M-113: duplicate/overlapping roots must not make a name ambiguous."""

    @pytest.mark.parametrize(
        "paths",
        [["src/", "src/"], ["src", "src/"], ["src", "SRC"]],
        ids=["identical", "trailing-slash", "case-alias"],
    )
    def test_duplicate_roots_resolve_an_exact_name(self, paths: list[str]) -> None:
        # The config goes through the regular validation path (pyproject +
        # load_config) so the duplicate entries are provably preserved.
        _write_pyproject(paths)
        config = load_config()
        assert config.paths_to_mutate == paths

        name, data = resolve_mutant("mod.x_foo__mutmut_1", config)

        assert name == "mod.x_foo__mutmut_1"
        assert Path(data.path) == Path("src/mod.py")

    def test_overlapping_roots_cover_the_nested_file(self, tmp_path: Path) -> None:
        (tmp_path / "src" / "sub").mkdir(parents=True)
        (tmp_path / "src" / "sub" / "m.py").write_text(
            "def bar() -> int:\n    return 1\n", encoding="utf-8"
        )
        (tmp_path / "mutants" / "src" / "sub").mkdir(parents=True)
        data = SourceFileMutationData(path="src/sub/m.py")
        data.exit_code_by_key = {"sub.m.x_bar__mutmut_1": 0}
        data.save()
        _write_pyproject(["src", "src/sub"])
        config = load_config()

        name, owner = resolve_mutant("sub.m.x_bar__mutmut_1", config)

        assert name == "sub.m.x_bar__mutmut_1"
        assert Path(owner.path) == Path("src/sub/m.py")

    def test_genuine_cross_file_collision_stays_ambiguous(self, tmp_path: Path) -> None:
        # Only DIFFERENT files owning the same key are ambiguous — that is
        # the fail-closed contract show/apply keep after the deduplication.
        (tmp_path / "src" / "other.py").write_text(
            "def foo() -> int:\n    return 1\n", encoding="utf-8"
        )
        other = SourceFileMutationData(path="src/other.py")
        other.exit_code_by_key = {"mod.x_foo__mutmut_1": 0}
        other.save()

        with pytest.raises(AmbiguousMutantNameError):
            resolve_mutant("mod.x_foo__mutmut_1", _config())

    def test_ignored_duplicate_does_not_consume_the_seen_slot(self) -> None:
        # Mirrors the generation order (orchestrator seen_sources): the
        # ignore check runs BEFORE deduplication, so an ignored alias never
        # shadows the same file walked again through another root.
        config = MagicMock()
        config.paths_to_mutate = ["src", "src"]
        config.should_ignore_for_mutation.side_effect = [True, False]

        name, data = resolve_mutant("mod.x_foo__mutmut_1", config)

        assert name == "mod.x_foo__mutmut_1"
        assert Path(data.path) == Path("src/mod.py")


@given(root_lists=st.lists(st.sampled_from(["src", "src/", "SRC"]), min_size=1, max_size=4))
@settings(max_examples=25, deadline=None)
def test_any_root_alias_combination_resolves_like_a_single_root(root_lists: list[str]) -> None:
    """M-113: resolution depends on file identity, not on root spelling."""
    import contextlib
    import tempfile

    with tempfile.TemporaryDirectory() as tmp, contextlib.chdir(tmp):
        root = Path(tmp)
        (root / "src").mkdir()
        (root / "src" / "mod.py").write_text("def foo() -> int:\n    return 1\n", encoding="utf-8")
        (root / "mutants" / "src").mkdir(parents=True)
        data = SourceFileMutationData(path="src/mod.py")
        data.exit_code_by_key = {"mod.x_foo__mutmut_1": 0}
        data.save()
        _write_pyproject(root_lists)

        name, owner = resolve_mutant("mod.x_foo__mutmut_1", load_config())

        assert name == "mod.x_foo__mutmut_1"
        assert Path(owner.path) == Path("src/mod.py")


class TestTimeEstimatesGlob:
    def test_time_estimates_accepts_glob(self) -> None:
        stats = MagicMock()
        stats.tests_by_mangled_function_name = {}
        stats.duration_by_test = {}
        rows = [
            MutationResult(mutant_name="src.mod.x_foo__mutmut_1", status="survived"),
            MutationResult(mutant_name="src.other.x_bar__mutmut_1", status="survived"),
        ]
        with (
            patch("mutmut_win.cli.load_stats", return_value=stats),
            patch("mutmut_win.cli._load_results_or_exit", return_value=rows),
        ):
            result = CliRunner().invoke(cli, ["time-estimates", "src.mod.*"])
        assert result.exit_code == 0
        assert "src.mod.x_foo__mutmut_1" in result.output
        assert "src.other.x_bar__mutmut_1" not in result.output

    def test_time_estimates_matching_is_case_sensitive(self) -> None:
        # M-056 / Q-20: the shared matcher also drives the time-estimates
        # filter — an exact name must not list its case twin.
        stats = MagicMock()
        stats.tests_by_mangled_function_name = {}
        stats.duration_by_test = {}
        rows = [
            MutationResult(mutant_name="mod.x_Parse__mutmut_1", status="survived"),
            MutationResult(mutant_name="mod.x_parse__mutmut_1", status="killed"),
        ]
        with (
            patch("mutmut_win.cli.load_stats", return_value=stats),
            patch("mutmut_win.cli._load_results_or_exit", return_value=rows),
        ):
            result = CliRunner().invoke(cli, ["time-estimates", "mod.x_parse__mutmut_1"])
        assert result.exit_code == 0
        assert "mod.x_parse__mutmut_1" in result.output
        assert "mod.x_Parse__mutmut_1" not in result.output


# ---------------------------------------------------------------------------
# UI-014 — patch-capable diffs
# ---------------------------------------------------------------------------


class TestPatchCapableDiff:
    def test_hunk_carries_real_line_numbers(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / "src").mkdir()
        # The function starts at line 5 of the original file.
        (tmp_path / "src" / "mod.py").write_text(
            "X = 1\n\n\ndef helper() -> int:\n    return 0\n", encoding="utf-8"
        )
        original = "X = 1\n\n\ndef foo() -> int:\n    return 1\n"  # foo starts at line 4
        source_path = tmp_path / "src" / "mod.py"
        source_path.write_text(original, encoding="utf-8")
        (tmp_path / "mutants" / "src").mkdir(parents=True)
        staged_path = tmp_path / "mutants" / "src" / "mod.py"
        staged_path.write_text(_MUTANTS_SOURCE, encoding="utf-8")
        metadata = SourceFileMutationData(path="src/mod.py")
        metadata.exit_code_by_key = {"mod.x_foo__mutmut_1": 0}
        metadata.source_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
        metadata.generated_hash = hashlib.sha256(staged_path.read_bytes()).hexdigest()
        metadata.save()

        diff = render_function_diff("src/mod.py", "mod.x_foo__mutmut_1")
        assert "--- a/src/mod.py" in diff
        assert "+++ b/src/mod.py" in diff
        assert "@@ -4" in diff  # real position, not function-relative -1
        assert "+4" in diff

    def test_changed_source_fails_closed_instead_of_using_relative_fallback(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        source_path = tmp_path / "src" / "mod.py"
        source_path.parent.mkdir()
        source_path.write_text("def foo() -> int:\n    return 1\n", encoding="utf-8")
        (tmp_path / "mutants" / "src").mkdir(parents=True)
        staged_path = tmp_path / "mutants" / "src" / "mod.py"
        staged_path.write_text(_MUTANTS_SOURCE, encoding="utf-8")
        metadata = SourceFileMutationData(path="src/mod.py")
        metadata.exit_code_by_key = {"mod.x_foo__mutmut_1": 0}
        metadata.source_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
        metadata.generated_hash = hashlib.sha256(staged_path.read_bytes()).hexdigest()
        metadata.save()
        source_path.write_text("def foo() -> int:\n    return 100\n", encoding="utf-8")

        with pytest.raises(StaleStagingError, match="before showing or applying"):
            render_function_diff("src/mod.py", "mod.x_foo__mutmut_1")


# ---------------------------------------------------------------------------
# UI-015 — summary alignment
# ---------------------------------------------------------------------------


class TestSummaryAlignment:
    def test_suspicious_line_has_a_space(self) -> None:
        rows = [
            MutationResult(mutant_name="m1", status="suspicious"),
            MutationResult(mutant_name="m2", status="killed"),
        ]
        with patch(
            "mutmut_win.cli._load_result_snapshot_or_exit",
            return_value=(None, rows),
        ):
            result = CliRunner().invoke(cli, ["results"])
        assert result.exit_code == 0
        assert "Suspicious:1" not in result.output
        assert "Suspicious: 1" in result.output

    def test_all_summary_lines_align(self) -> None:
        """Every label column ends at the same offset — one field width."""
        rows = [
            MutationResult(mutant_name="m1", status="suspicious"),
            MutationResult(mutant_name="m2", status="killed"),
            MutationResult(mutant_name="m3", status="survived"),
        ]
        with patch(
            "mutmut_win.cli._load_result_snapshot_or_exit",
            return_value=(None, rows),
        ):
            result = CliRunner().invoke(cli, ["results"])
        value_columns = set()
        for line in result.output.splitlines():
            label, _, rest = line.partition(":")
            if not rest or not rest.strip() or " " in label:
                continue
            value_columns.add(len(line) - len(rest.lstrip()))
        assert len(value_columns) == 1, result.output
