"""Tests for the type-check baseline subtraction + JSON-flag hint (issue #131).

360°-B4: a PRE-EXISTING type error inside a function body replicates into
every mutant copy of that function — the checker reports it in every
``x_f__mutmut_N`` range and ALL its mutants were falsely 'caught by type
check' (score inflation). The errors inside the ``__mutmut_orig`` copy ARE
the baseline: a mutant only counts as caught when it carries at least one
error that is NOT (line-offset, text)-identical to an orig-copy error.

360°-A5: the README documented ``type_check_command = ["mypy", "src/"]`` —
guaranteed to abort because the parser requires JSON output. The
orchestrator now warns with the concrete flag BEFORE running the checker.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

from mutmut_win.models import MutationTask
from mutmut_win.orchestrator import _filter_with_type_checker
from mutmut_win.type_checking import TypeCheckingError

if TYPE_CHECKING:
    import pytest

_STAGED = """\
def f():
    return _mutmut_trampoline()


def x_f__mutmut_orig():
    value = "pre-existing"
    return value


def x_f__mutmut_1():
    value = "pre-existing"
    return value


def x_f__mutmut_2():
    value = "pre-existing"
    return value
"""


def _line_of(source: str, needle: str) -> int:
    """1-based line number of the first line containing *needle*."""
    for index, line in enumerate(source.splitlines(), start=1):
        if needle in line:
            return index
    msg = f"needle {needle!r} not found"
    raise AssertionError(msg)


def _staging(tmp_path: Path) -> Path:
    staged = tmp_path / "mutants" / "src" / "mod.py"
    staged.parent.mkdir(parents=True)
    staged.write_text(_STAGED, encoding="utf-8")
    return staged


class TestBaselineSubtraction:
    def test_replicated_baseline_error_does_not_catch_the_mutant(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.chdir(tmp_path)
        _staging(tmp_path)
        # The same error text at the SAME offset inside orig and mutant 1
        # (offset 1 = the 'value =' line of each copy) — replicated baseline.
        orig_line = _line_of(_STAGED, "def x_f__mutmut_orig") + 1
        mutant1_line = _line_of(_STAGED, "def x_f__mutmut_1") + 1
        # Mutant 2 carries a NEW error (different text) at the same offset.
        mutant2_line = _line_of(_STAGED, "def x_f__mutmut_2") + 1
        errors = [
            TypeCheckingError(Path("src/mod.py"), orig_line, "incompatible str"),
            TypeCheckingError(Path("src/mod.py"), mutant1_line, "incompatible str"),
            TypeCheckingError(Path("src/mod.py"), mutant2_line, "mutation broke it"),
        ]
        tasks = [
            MutationTask(mutant_name="mod.x_f__mutmut_1"),
            MutationTask(mutant_name="mod.x_f__mutmut_2"),
        ]
        with patch("mutmut_win.type_checking.run_type_checker", return_value=errors):
            remaining, caught = _filter_with_type_checker(tasks, {}, ["mypy", "--output=json", "."])

        assert caught == {"mod.x_f__mutmut_2"}  # only the NEW error catches
        assert [t.mutant_name for t in remaining] == ["mod.x_f__mutmut_1"]
        err = capsys.readouterr().err
        assert "pre-existing" in err  # the subtraction is announced, not silent

    def test_without_baseline_errors_behavior_is_unchanged(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        _staging(tmp_path)
        mutant1_line = _line_of(_STAGED, "def x_f__mutmut_1") + 1
        errors = [TypeCheckingError(Path("src/mod.py"), mutant1_line, "mutation broke it")]
        tasks = [
            MutationTask(mutant_name="mod.x_f__mutmut_1"),
            MutationTask(mutant_name="mod.x_f__mutmut_2"),
        ]
        with patch("mutmut_win.type_checking.run_type_checker", return_value=errors):
            remaining, caught = _filter_with_type_checker(tasks, {}, ["mypy", "--output=json", "."])
        assert caught == {"mod.x_f__mutmut_1"}
        assert [t.mutant_name for t in remaining] == ["mod.x_f__mutmut_2"]


class TestFilterHardening:
    """Mutation-hardening pins for the rewritten filter (wave-4 gate)."""

    def test_no_staging_returns_tasks_and_empty_set(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)  # no mutants/ at all
        tasks = [MutationTask(mutant_name="mod.x_f__mutmut_1")]
        remaining, caught = _filter_with_type_checker(tasks, {}, ["mypy", "--output=json", "."])
        assert remaining == tasks
        assert caught == set()

    def test_clean_checker_runs_inside_mutants_with_the_exact_command(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        _staging(tmp_path)
        seen: dict[str, object] = {}

        def fake_checker(command: list[str]) -> list[TypeCheckingError]:
            seen["cwd"] = Path.cwd().name
            seen["command"] = command
            return []

        tasks = [MutationTask(mutant_name="mod.x_f__mutmut_1")]
        with patch("mutmut_win.type_checking.run_type_checker", side_effect=fake_checker):
            remaining, caught = _filter_with_type_checker(tasks, {}, ["mypy", "--output=json", "."])
        assert seen["cwd"] == "mutants"  # parity with mutmut 3.5.0: checker sees staging
        assert seen["command"] == ["mypy", "--output=json", "."]
        assert remaining == tasks
        assert caught == set()

    def test_error_outside_any_function_is_skipped_without_crash(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Line 1 is the trampoline def — owned by NO mutant range.
        monkeypatch.chdir(tmp_path)
        _staging(tmp_path)
        mutant2_line = _line_of(_STAGED, "def x_f__mutmut_2") + 1
        errors = [
            TypeCheckingError(Path("src/mod.py"), 1, "module-level breakage"),
            TypeCheckingError(Path("src/mod.py"), mutant2_line, "mutation broke it"),
        ]
        tasks = [
            MutationTask(mutant_name="mod.x_f__mutmut_1"),
            MutationTask(mutant_name="mod.x_f__mutmut_2"),
        ]
        with patch("mutmut_win.type_checking.run_type_checker", return_value=errors):
            _, caught = _filter_with_type_checker(tasks, {}, ["mypy", "--output=json", "."])
        assert caught == {"mod.x_f__mutmut_2"}

    def test_foreign_path_error_does_not_stop_normalization(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # An error OUTSIDE mutants/ is dropped; the errors after it must
        # still be processed (a 'break' here would eat real catches).
        monkeypatch.chdir(tmp_path)
        _staging(tmp_path)
        mutant2_line = _line_of(_STAGED, "def x_f__mutmut_2") + 1
        errors = [
            TypeCheckingError(Path("C:/elsewhere/other.py"), 3, "foreign"),
            TypeCheckingError(Path("src/mod.py"), mutant2_line, "mutation broke it"),
        ]
        tasks = [MutationTask(mutant_name="mod.x_f__mutmut_2")]
        with patch("mutmut_win.type_checking.run_type_checker", return_value=errors):
            _, caught = _filter_with_type_checker(tasks, {}, ["mypy", "--output=json", "."])
        assert caught == {"mod.x_f__mutmut_2"}

    def test_orig_only_error_is_silent_and_catches_nothing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # An error confined to the orig copy is no replication and no kill —
        # nothing is announced.
        monkeypatch.chdir(tmp_path)
        _staging(tmp_path)
        orig_line = _line_of(_STAGED, "def x_f__mutmut_orig") + 1
        errors = [TypeCheckingError(Path("src/mod.py"), orig_line, "pre-existing")]
        tasks = [MutationTask(mutant_name="mod.x_f__mutmut_1")]
        with patch("mutmut_win.type_checking.run_type_checker", return_value=errors):
            _, caught = _filter_with_type_checker(tasks, {}, ["mypy", "--output=json", "."])
        assert caught == set()
        assert capsys.readouterr().err == ""

    def test_replicated_count_message_is_word_exact(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.chdir(tmp_path)
        _staging(tmp_path)
        orig_line = _line_of(_STAGED, "def x_f__mutmut_orig")
        mutant1_line = _line_of(_STAGED, "def x_f__mutmut_1")
        errors = [
            TypeCheckingError(Path("src/mod.py"), orig_line + 1, "err one"),
            TypeCheckingError(Path("src/mod.py"), orig_line + 2, "err two"),
            TypeCheckingError(Path("src/mod.py"), mutant1_line + 1, "err one"),
            TypeCheckingError(Path("src/mod.py"), mutant1_line + 2, "err two"),
        ]
        tasks = [MutationTask(mutant_name="mod.x_f__mutmut_1")]
        with patch("mutmut_win.type_checking.run_type_checker", return_value=errors):
            _, caught = _filter_with_type_checker(tasks, {}, ["mypy", "--output=json", "."])
        assert caught == set()
        assert capsys.readouterr().err == (
            "Type-check filter: ignored 2 pre-existing error(s) replicated "
            "from the original code — not counted as kills (issue #131).\n"
        )

    def test_def_line_error_is_inside_the_mutant_range(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # mypy reports signature errors ON the def line — both range ends
        # are inclusive.
        monkeypatch.chdir(tmp_path)
        _staging(tmp_path)
        errors = [
            TypeCheckingError(
                Path("src/mod.py"), _line_of(_STAGED, "def x_f__mutmut_1"), "bad signature"
            )
        ]
        tasks = [MutationTask(mutant_name="mod.x_f__mutmut_1")]
        with patch("mutmut_win.type_checking.run_type_checker", return_value=errors):
            _, caught = _filter_with_type_checker(tasks, {}, ["mypy", "--output=json", "."])
        assert caught == {"mod.x_f__mutmut_1"}

    def test_last_line_error_is_inside_the_mutant_range(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        _staging(tmp_path)
        last_line = _line_of(_STAGED, "def x_f__mutmut_1") + 2  # 'return value'
        errors = [TypeCheckingError(Path("src/mod.py"), last_line, "bad return")]
        tasks = [MutationTask(mutant_name="mod.x_f__mutmut_1")]
        with patch("mutmut_win.type_checking.run_type_checker", return_value=errors):
            _, caught = _filter_with_type_checker(tasks, {}, ["mypy", "--output=json", "."])
        assert caught == {"mod.x_f__mutmut_1"}

    def test_replicated_def_line_error_is_subtracted(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Baseline ranges are inclusive on BOTH ends too — a def-line error
        # in orig must subtract its replica on the mutant's def line.
        monkeypatch.chdir(tmp_path)
        _staging(tmp_path)
        errors = [
            TypeCheckingError(
                Path("src/mod.py"), _line_of(_STAGED, "def x_f__mutmut_orig"), "bad signature"
            ),
            TypeCheckingError(
                Path("src/mod.py"), _line_of(_STAGED, "def x_f__mutmut_1"), "bad signature"
            ),
        ]
        tasks = [MutationTask(mutant_name="mod.x_f__mutmut_1")]
        with patch("mutmut_win.type_checking.run_type_checker", return_value=errors):
            _, caught = _filter_with_type_checker(tasks, {}, ["mypy", "--output=json", "."])
        assert caught == set()

    def test_replicated_last_line_error_is_subtracted(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        _staging(tmp_path)
        errors = [
            TypeCheckingError(
                Path("src/mod.py"), _line_of(_STAGED, "def x_f__mutmut_orig") + 2, "bad return"
            ),
            TypeCheckingError(
                Path("src/mod.py"), _line_of(_STAGED, "def x_f__mutmut_1") + 2, "bad return"
            ),
        ]
        tasks = [MutationTask(mutant_name="mod.x_f__mutmut_1")]
        with patch("mutmut_win.type_checking.run_type_checker", return_value=errors):
            _, caught = _filter_with_type_checker(tasks, {}, ["mypy", "--output=json", "."])
        assert caught == set()

    def test_caught_mutants_are_booked_into_source_data(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from mutmut_win.constants import EXIT_CODE_TYPE_CHECK
        from mutmut_win.models import SourceFileMutationData

        monkeypatch.chdir(tmp_path)
        _staging(tmp_path)
        sfd = SourceFileMutationData(path="src/mod.py")
        sfd.exit_code_by_key = {"mod.x_f__mutmut_1": None, "mod.x_f__mutmut_2": None}
        mutant2_line = _line_of(_STAGED, "def x_f__mutmut_2") + 1
        errors = [TypeCheckingError(Path("src/mod.py"), mutant2_line, "mutation broke it")]
        tasks = [
            MutationTask(mutant_name="mod.x_f__mutmut_1"),
            MutationTask(mutant_name="mod.x_f__mutmut_2"),
        ]
        with patch("mutmut_win.type_checking.run_type_checker", return_value=errors):
            _filter_with_type_checker(tasks, {"src/mod.py": sfd}, ["mypy", "--output=json", "."])
        assert sfd.exit_code_by_key["mod.x_f__mutmut_2"] == EXIT_CODE_TYPE_CHECK
        assert sfd.exit_code_by_key["mod.x_f__mutmut_1"] is None

    def test_non_ascii_staged_source_is_decoded_as_utf8(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # U+01C1 encodes to 0xC7 0x81 in utf-8; 0x81 is UNDEFINED in
        # cp1252, so a locale-default read crashes on Windows. The staged
        # files are written as utf-8 — the filter must read them as such.
        monkeypatch.chdir(tmp_path)
        staged = _staging(tmp_path)
        staged.write_text(_STAGED + "\n# marker: ǁ\n", encoding="utf-8")
        mutant2_line = _line_of(_STAGED, "def x_f__mutmut_2") + 1
        errors = [TypeCheckingError(Path("src/mod.py"), mutant2_line, "mutation broke it")]
        tasks = [MutationTask(mutant_name="mod.x_f__mutmut_2")]
        with patch("mutmut_win.type_checking.run_type_checker", return_value=errors):
            _, caught = _filter_with_type_checker(tasks, {}, ["mypy", "--output=json", "."])
        assert caught == {"mod.x_f__mutmut_2"}

    def test_pep263_staged_source_uses_its_declared_encoding(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        staged = tmp_path / "mutants" / "src" / "mod.py"
        staged.parent.mkdir(parents=True)
        source = "# coding: cp1252\n# marker: café\n" + _STAGED
        staged.write_bytes(source.encode("cp1252"))
        mutant2_line = _line_of(source, "def x_f__mutmut_2") + 1
        errors = [TypeCheckingError(Path("src/mod.py"), mutant2_line, "mutation broke it")]
        tasks = [MutationTask(mutant_name="mod.x_f__mutmut_2")]

        with patch("mutmut_win.type_checking.run_type_checker", return_value=errors):
            _, caught = _filter_with_type_checker(tasks, {}, ["mypy", "--output=json", "."])

        assert caught == {"mod.x_f__mutmut_2"}

    def test_unreadable_file_does_not_stop_the_filter(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # group_by_path keeps insertion order: the ghost file comes first;
        # its OSError must not abort the remaining per-file work.
        monkeypatch.chdir(tmp_path)
        _staging(tmp_path)
        mutant2_line = _line_of(_STAGED, "def x_f__mutmut_2") + 1
        errors = [
            TypeCheckingError(Path("src/ghost.py"), 2, "unreadable"),
            TypeCheckingError(Path("src/mod.py"), mutant2_line, "mutation broke it"),
        ]
        tasks = [MutationTask(mutant_name="mod.x_f__mutmut_2")]
        with patch("mutmut_win.type_checking.run_type_checker", return_value=errors):
            _, caught = _filter_with_type_checker(tasks, {}, ["mypy", "--output=json", "."])
        assert caught == {"mod.x_f__mutmut_2"}


class TestJsonFlagHint:
    def test_mypy_without_output_flag_warns_with_the_fix(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # 360°-A5: the documented-config failure mode gets a concrete hint
        # BEFORE the parser aborts with 'did not return JSON'.
        monkeypatch.chdir(tmp_path)
        _staging(tmp_path)
        with patch("mutmut_win.type_checking.run_type_checker", return_value=[]):
            _filter_with_type_checker([], {}, ["mypy", "src/"])
        assert capsys.readouterr().err == (
            "Warning: type_check_command uses mypy without its JSON output "
            "flag — the report parser will abort. Add --output=json "
            "(requires mypy >= 1.11), e.g. type_check_command = "
            '["mypy", "--output=json", "src/"].\n'
        )

    def test_pyright_without_outputjson_warns(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.chdir(tmp_path)
        _staging(tmp_path)
        with patch("mutmut_win.type_checking.run_type_checker", return_value=[]):
            _filter_with_type_checker([], {}, ["pyright", "."])
        assert capsys.readouterr().err == (
            "Warning: type_check_command uses pyright without its JSON "
            "output flag — the report parser will abort. Add --outputjson, "
            'e.g. type_check_command = ["pyright", "--outputjson", "."].\n'
        )

    def test_pyright_with_outputjson_stays_silent(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.chdir(tmp_path)
        _staging(tmp_path)
        with patch("mutmut_win.type_checking.run_type_checker", return_value=[]):
            _filter_with_type_checker([], {}, ["pyright", "--outputjson", "."])
        assert capsys.readouterr().err == ""

    def test_correct_command_stays_silent(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.chdir(tmp_path)
        _staging(tmp_path)
        with patch("mutmut_win.type_checking.run_type_checker", return_value=[]):
            _filter_with_type_checker([], {}, ["mypy", "--output=json", "src/"])
        assert capsys.readouterr().err == ""
