"""Unit tests for mutmut_win.type_checking."""

import json
import os
import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from mutmut_win.exceptions import ProcessContainmentError, TypeCheckCommandError
from mutmut_win.type_checking import (
    TypeCheckingError,
    _redirect_checker_caches,
    _run_type_check_process,
    parse_mypy_report,
    parse_pyrefly_report,
    parse_pyright_report,
    parse_ty_report,
    run_type_checker,
)


class TestRedirectCheckerCaches:
    """M-063: checker caches must land in the ephemeral runtime directory."""

    def test_overrides_inherited_relative_value(self, tmp_path: Path) -> None:
        environment = {"MYPY_CACHE_DIR": ".mypy_cache"}

        _redirect_checker_caches(environment, tmp_path)

        result = Path(environment["MYPY_CACHE_DIR"])
        assert result.is_absolute()
        assert result == tmp_path / "mypy-cache"

    def test_sets_value_in_empty_environment(self, tmp_path: Path) -> None:
        environment: dict[str, str] = {}

        _redirect_checker_caches(environment, tmp_path)

        assert Path(environment["MYPY_CACHE_DIR"]) == tmp_path / "mypy-cache"


def _completed(stdout: str = "", returncode: int = 0, stderr: str = "") -> MagicMock:
    mock_process = MagicMock()
    mock_process.stdout = stdout
    mock_process.stderr = stderr
    mock_process.returncode = returncode
    return mock_process


_MYPY_JSON_LINE = json.dumps(
    {
        "file": "src\\foo.py",
        "line": 3,
        "column": 0,
        "message": "Incompatible types",
        "hint": None,
        "code": "assignment",
        "severity": "error",
    }
)

_MYPY_NOTE_LINE = json.dumps(
    {
        "file": "src\\foo.py",
        "line": 4,
        "column": 0,
        "message": "note text",
        "hint": None,
        "code": None,
        "severity": "note",
    }
)


def _parses_as_json(text: str) -> bool:
    try:
        json.loads(text)
    except json.JSONDecodeError:
        return False
    return True


#: The fail-closed property alphabet must not contain characters that
#: ``str.splitlines`` treats as line boundaries (\x0b \x0c \x1c-\x1e \x85 are
#: Cc, \u2028 is Zl, \u2029 is Zp) — otherwise one generated "line" secretly
#: becomes several and the property is not about single non-JSON lines.
_NON_JSON_LINE_ALPHABET = st.characters(exclude_categories=("Cc", "Zl", "Zp"))

# --- TypeCheckingError dataclass ----------------------------------------------


class TestTypeCheckingError:
    def test_fields_are_accessible(self) -> None:
        err = TypeCheckingError(
            file_path=Path("src/foo.py"),
            line_number=42,
            error_description="some error",
        )
        assert err.file_path == Path("src/foo.py")
        assert err.line_number == 42
        assert err.error_description == "some error"


# --- parse_pyright_report -----------------------------------------------------


class TestParsePyrightReport:
    def test_parses_errors(self) -> None:
        report = {
            "generalDiagnostics": [
                {
                    "file": "src/foo.py",
                    "severity": "error",
                    "range": {"start": {"line": 9}},
                    "message": "Type error",
                }
            ]
        }
        errors = parse_pyright_report(report)
        assert len(errors) == 1
        assert errors[0].line_number == 10  # 0-indexed + 1
        assert errors[0].error_description == "Type error"
        assert errors[0].file_path == Path("src/foo.py")

    def test_missing_key_raises(self) -> None:
        with pytest.raises(Exception, match="generalDiagnostics"):
            parse_pyright_report({"other": []})

    def test_empty_diagnostics(self) -> None:
        errors = parse_pyright_report({"generalDiagnostics": []})
        assert errors == []


# --- parse_pyrefly_report -----------------------------------------------------


class TestParsePyreflyReport:
    def test_parses_errors(self) -> None:
        report = {
            "errors": [
                {
                    "path": "src/bar.py",
                    "line": 5,
                    "concise_description": "pyrefly error",
                }
            ]
        }
        errors = parse_pyrefly_report(report)
        assert len(errors) == 1
        assert errors[0].line_number == 5
        assert errors[0].error_description == "pyrefly error"

    def test_missing_key_raises(self) -> None:
        with pytest.raises(Exception, match="errors"):
            parse_pyrefly_report({"other": []})

    def test_empty_errors(self) -> None:
        errors = parse_pyrefly_report({"errors": []})
        assert errors == []


# --- parse_mypy_report --------------------------------------------------------


class TestParseMypyReport:
    def test_parses_error_severity(self) -> None:
        report = [
            {
                "file": "src/baz.py",
                "line": 15,
                "message": "mypy error",
                "severity": "error",
            }
        ]
        errors = parse_mypy_report(report)
        assert len(errors) == 1
        assert errors[0].line_number == 15
        assert errors[0].error_description == "mypy error"

    def test_skips_non_errors(self) -> None:
        report = [
            {
                "file": "src/baz.py",
                "line": 1,
                "message": "note",
                "severity": "note",
            }
        ]
        errors = parse_mypy_report(report)
        assert errors == []

    def test_empty_report(self) -> None:
        errors = parse_mypy_report([])
        assert errors == []


# --- parse_ty_report ----------------------------------------------------------


class TestParseTyReport:
    def test_parses_major_severity(self) -> None:
        report = [
            {
                "severity": "major",
                "location": {
                    "path": "src/x.py",
                    "positions": {"begin": {"line": 7}},
                },
                "description": "ty error",
            }
        ]
        errors = parse_ty_report(report)
        assert len(errors) == 1
        assert errors[0].line_number == 7
        assert errors[0].error_description == "ty error"
        # Dogfooding survivor x_parse_ty_report__mutmut_3 (file_path=None):
        # no test ever asserted the path field.
        assert errors[0].file_path == Path("src/x.py").absolute()

    def test_skips_minor_severity(self) -> None:
        report = [
            {
                "severity": "minor",
                "location": {
                    "path": "src/x.py",
                    "positions": {"begin": {"line": 1}},
                },
                "description": "minor issue",
            }
        ]
        errors = parse_ty_report(report)
        assert errors == []

    def test_parses_critical_and_blocker(self) -> None:
        report = [
            {
                "severity": "critical",
                "location": {"path": "a.py", "positions": {"begin": {"line": 1}}},
                "description": "critical",
            },
            {
                "severity": "blocker",
                "location": {"path": "b.py", "positions": {"begin": {"line": 2}}},
                "description": "blocker",
            },
        ]
        errors = parse_ty_report(report)
        assert len(errors) == 2

    def test_empty_report(self) -> None:
        errors = parse_ty_report([])
        assert errors == []


# --- run_type_checker ---------------------------------------------------------


class TestRunTypeChecker:
    def test_invalid_json_raises_exception(self) -> None:
        with (
            patch(
                "mutmut_win.type_checking._run_type_check_process",
                return_value=_completed("not json"),
            ),
            pytest.raises(Exception, match="did not return JSON"),
        ):
            run_type_checker(["pyright", "--outputjson", "."])

    def test_pyright_route(self) -> None:
        completed = _completed(json.dumps({"generalDiagnostics": []}))
        with patch("mutmut_win.type_checking._run_type_check_process", return_value=completed):
            errors = run_type_checker(["pyright", "--outputjson", "."])
        assert errors == []

    def test_mypy_route(self) -> None:
        # Realistic finding-free mypy stdout: exactly one blank line (the
        # hidden success summary — mypy 1.19.1 main.py + util.format_success).
        with patch(
            "mutmut_win.type_checking._run_type_check_process", return_value=_completed("\n")
        ):
            errors = run_type_checker(["mypy", "--output=json", "."])
        assert errors == []

    def test_pyrefly_route(self) -> None:
        with patch(
            "mutmut_win.type_checking._run_type_check_process",
            return_value=_completed(json.dumps({"errors": []})),
        ):
            errors = run_type_checker(["pyrefly", "check", "."])
        assert errors == []

    def test_ty_route(self) -> None:
        with patch(
            "mutmut_win.type_checking._run_type_check_process",
            return_value=_completed(json.dumps([])),
        ):
            errors = run_type_checker(["ty", "check", "."])
        assert errors == []


class TestMypyJsonlBlankLineTolerance:
    """M-059: a finding-free ``mypy --output=json`` run writes exactly one
    blank line — the old per-line ``json.loads`` aborted every such run with
    ``TypeCheckCommandError`` and thereby killed the whole mutation run."""

    def test_finding_free_run_newline_stdout_yields_no_errors(self) -> None:
        with patch(
            "mutmut_win.type_checking._run_type_check_process",
            return_value=_completed("\n"),
        ):
            errors = run_type_checker(["mypy", "--output=json", "."])
        assert errors == []

    def test_blank_lines_between_json_lines_are_ignored(self) -> None:
        stdout = _MYPY_JSON_LINE + "\n\n" + _MYPY_JSON_LINE + "\r\n"
        with patch(
            "mutmut_win.type_checking._run_type_check_process",
            return_value=_completed(stdout, returncode=1),
        ):
            errors = run_type_checker(["mypy", "--output=json", "."])
        assert len(errors) == 2

    def test_whitespace_only_stdout_yields_no_errors(self) -> None:
        with patch(
            "mutmut_win.type_checking._run_type_check_process",
            return_value=_completed(" \r\n\t\n"),
        ):
            errors = run_type_checker(["mypy", "--output=json", "."])
        assert errors == []

    def test_notes_only_run_with_exit_one_yields_no_errors(self) -> None:
        # Pure-note runs exit 1 without a summary line (mypy main.py:154-155)
        # — no error diagnostics, so nothing may be reported.
        with patch(
            "mutmut_win.type_checking._run_type_check_process",
            return_value=_completed(_MYPY_NOTE_LINE + "\n", returncode=1),
        ):
            errors = run_type_checker(["mypy", "--output=json", "."])
        assert errors == []

    @pytest.mark.parametrize(
        "stdout",
        [
            "Success: no issues found in 1 source file\n",
            "a.py:1: error: cannot find x\n",
        ],
    )
    def test_text_mode_mypy_lines_still_fail_closed(self, stdout: str) -> None:
        # A misconfigured text-mode mypy must abort, not silently filter to
        # zero findings (the silent no-op filter issue #114 removed).
        with (
            patch(
                "mutmut_win.type_checking._run_type_check_process",
                return_value=_completed(stdout, returncode=0),
            ),
            pytest.raises(TypeCheckCommandError, match="did not return JSON"),
        ):
            run_type_checker(["mypy", "--output=json", "."])

    def test_pyright_newline_stdout_still_fails_closed(self) -> None:
        # The tolerance is mypy-JSONL-specific: pyright stdout is ONE JSON
        # document, and a bare newline stays invalid there.
        with (
            patch(
                "mutmut_win.type_checking._run_type_check_process",
                return_value=_completed("\n"),
            ),
            pytest.raises(TypeCheckCommandError, match="did not return JSON"),
        ):
            run_type_checker(["pyright", "--outputjson", "."])

    @given(
        json_lines=st.lists(st.sampled_from([_MYPY_JSON_LINE, _MYPY_NOTE_LINE]), max_size=8),
        blank_lines=st.lists(st.sampled_from(["", " ", "\t", "\r"]), max_size=8),
    )
    def test_interleaved_blank_lines_never_change_the_findings(
        self, json_lines: list[str], blank_lines: list[str]
    ) -> None:
        lines = [
            line
            for json_line, blank_line in zip(json_lines, blank_lines, strict=False)
            for line in (json_line, blank_line)
        ]
        lines.extend(json_lines[len(blank_lines) :])
        lines.extend(blank_lines[len(json_lines) :])

        with patch(
            "mutmut_win.type_checking._run_type_check_process",
            return_value=_completed("\n".join(lines), returncode=1),
        ):
            errors = run_type_checker(["mypy", "--output=json", "."])

        assert len(errors) == json_lines.count(_MYPY_JSON_LINE)

    @given(
        garbage_line=st.text(alphabet=_NON_JSON_LINE_ALPHABET, min_size=1, max_size=30).filter(
            lambda text: bool(text.strip()) and not _parses_as_json(text)
        )
    )
    def test_any_non_json_line_still_fails_closed(self, garbage_line: str) -> None:
        stdout = _MYPY_JSON_LINE + "\n" + garbage_line + "\n"
        with (
            patch(
                "mutmut_win.type_checking._run_type_check_process",
                return_value=_completed(stdout, returncode=1),
            ),
            pytest.raises(TypeCheckCommandError, match="did not return JSON"),
        ):
            run_type_checker(["mypy", "--output=json", "."])


class TestStructuralReportValidation:
    """M-127: syntactically valid JSON with a foreign structure used to
    escape the documented error taxonomy as raw KeyError / TypeError /
    AttributeError (cli.py only catches MutmutWinError)."""

    @pytest.mark.parametrize(
        ("command", "stdout"),
        [
            (["pyright", "--outputjson", "."], "[]"),
            (["pyright", "--outputjson", "."], "null"),
            (["pyright", "--outputjson", "."], "5"),
            (["pyright", "--outputjson", "."], json.dumps({"generalDiagnostics": [5]})),
            (
                ["pyright", "--outputjson", "."],
                json.dumps({"generalDiagnostics": [{"severity": "error"}]}),
            ),
            (["pyrefly", "check", "."], "[]"),
            (["pyrefly", "check", "."], json.dumps({"errors": [5]})),
            (["pyrefly", "check", "."], json.dumps({"errors": [{"path": "a.py"}]})),
            (["mypy", "--output=json", "."], "[1]"),
            (["mypy", "--output=json", "."], json.dumps({"file": "a.py"})),
            (["ty", "check", "."], json.dumps({"a": 1})),
            (["ty", "check", "."], json.dumps([5])),
            (["ty", "check", "."], json.dumps([{"severity": "major"}])),
            (["mychecker", "."], "[]"),
        ],
    )
    def test_structurally_invalid_reports_raise_domain_error(
        self, command: list[str], stdout: str
    ) -> None:
        with (
            patch(
                "mutmut_win.type_checking._run_type_check_process",
                return_value=_completed(stdout),
            ),
            pytest.raises(TypeCheckCommandError, match="structurally unexpected"),
        ):
            run_type_checker(command)

    def test_pyright_warning_without_range_is_ignored_not_rejected(self) -> None:
        # Validation must not be stricter than the historical accesses:
        # filtered-out severities never have their fields read.
        stdout = json.dumps({"generalDiagnostics": [{"severity": "warning", "message": "w"}]})
        with patch(
            "mutmut_win.type_checking._run_type_check_process",
            return_value=_completed(stdout),
        ):
            errors = run_type_checker(["pyright", "--outputjson", "."])
        assert errors == []

    def test_mypy_note_without_line_is_ignored_not_rejected(self) -> None:
        stdout = json.dumps({"file": "a.py", "message": "n", "severity": "note"}) + "\n"
        with patch(
            "mutmut_win.type_checking._run_type_check_process",
            return_value=_completed(stdout, returncode=1),
        ):
            errors = run_type_checker(["mypy", "--output=json", "."])
        assert errors == []

    def test_ty_minor_without_location_is_ignored_not_rejected(self) -> None:
        stdout = json.dumps([{"severity": "minor"}])
        with patch(
            "mutmut_win.type_checking._run_type_check_process",
            return_value=_completed(stdout),
        ):
            errors = run_type_checker(["ty", "check", "."])
        assert errors == []

    def test_error_message_names_checker_and_chains_the_cause(self) -> None:
        with (
            patch(
                "mutmut_win.type_checking._run_type_check_process",
                return_value=_completed("5"),
            ),
            pytest.raises(TypeCheckCommandError, match="pyright") as exc_info,
        ):
            run_type_checker(["pyright", "--outputjson", "."])
        message = str(exc_info.value)
        assert "structurally unexpected" in message
        assert "5" in message  # the bounded stdout excerpt is part of the message
        assert isinstance(exc_info.value.__cause__, ValidationError)

    def test_error_message_names_the_pyright_fallback_for_unknown_checkers(self) -> None:
        with (
            patch(
                "mutmut_win.type_checking._run_type_check_process",
                return_value=_completed("5"),
            ),
            pytest.raises(TypeCheckCommandError, match="unknown checker"),
        ):
            run_type_checker(["mychecker", "."])

    def test_error_message_excerpt_is_bounded(self) -> None:
        # stdout may be up to 16 MiB — the schema-failure message must not
        # embed it whole (unlike the decode-failure message, unchanged).
        stdout = json.dumps("x" * 5000)
        with (
            patch(
                "mutmut_win.type_checking._run_type_check_process",
                return_value=_completed(stdout),
            ),
            pytest.raises(TypeCheckCommandError) as exc_info,
        ):
            run_type_checker(["pyright", "--outputjson", "."])
        message = str(exc_info.value)
        assert len(message) < 1200
        assert message.count("x") < 1000


#: Recursive arbitrary JSON values: the never-a-foreign-exception property
#: must hold for ANY syntactically valid report, not just hand-picked ones.
_ANY_JSON_VALUE = st.recursive(
    st.none()
    | st.booleans()
    | st.integers()
    | st.floats(allow_nan=False, allow_infinity=False)
    | st.text(max_size=5),
    lambda children: (
        st.lists(children, max_size=3) | st.dictionaries(st.text(max_size=5), children, max_size=3)
    ),
    max_leaves=10,
)

_PROPERTY_COMMANDS = [
    ["pyright", "--outputjson", "."],
    ["pyrefly", "check", "."],
    ["mypy", "--output=json", "."],
    ["ty", "check", "."],
    ["mychecker", "."],
]


class TestNoForeignExceptionProperty:
    """Q-68: decode + validate + parse must yield list[TypeCheckingError] or
    TypeCheckCommandError for any stdout — never a foreign exception."""

    @given(value=_ANY_JSON_VALUE, command=st.sampled_from(_PROPERTY_COMMANDS))
    def test_any_json_report_either_parses_or_raises_the_domain_error(
        self, value: Any, command: list[str]
    ) -> None:
        # json.dumps is always single-line (newlines are escaped), so the
        # mypy JSONL branch decodes exactly one diagnostic line.
        stdout = json.dumps(value)
        with patch(
            "mutmut_win.type_checking._run_type_check_process",
            return_value=_completed(stdout),
        ):
            try:
                errors = run_type_checker(command)
            except TypeCheckCommandError:
                return
        assert isinstance(errors, list)
        assert all(isinstance(error, TypeCheckingError) for error in errors)


class TestCheckerDetection:
    """Issue #92 / A3-CM-008: detection was exact list membership — the
    Windows-normal command forms fell into the pyright branch, json.loads
    choked on mypy's JSON lines, and the whole run ABORTED."""

    @pytest.mark.parametrize(
        "command",
        [
            ["mypy.exe", "--output=json", "."],
            [".venv\\Scripts\\mypy.exe", "--output=json", "."],
            ["uv", "run", "mypy", "--output=json", "."],
            ["python", "-m", "mypy", "--output=json", "."],
            ["C:\\tools\\MyPy.EXE", "--output=json", "."],  # case-insensitive
        ],
    )
    def test_windows_command_forms_take_the_mypy_route(self, command: list[str]) -> None:
        with patch(
            "mutmut_win.type_checking._run_type_check_process",
            return_value=_completed(_MYPY_JSON_LINE, returncode=1),
        ):
            errors = run_type_checker(command)
        assert len(errors) == 1
        assert errors[0].line_number == 3

    def test_pyright_exe_takes_the_pyright_route(self) -> None:
        report = json.dumps(
            {
                "generalDiagnostics": [
                    {
                        "file": "src/foo.py",
                        "severity": "error",
                        "message": "boom",
                        "range": {"start": {"line": 2}},
                    }
                ]
            }
        )
        with patch(
            "mutmut_win.type_checking._run_type_check_process",
            return_value=_completed(report, returncode=1),
        ):
            errors = run_type_checker(["pyright.exe", "--outputjson", "."])
        assert len(errors) == 1


class TestSubprocessRobustness:
    """Issue #92 / A3-CM-010: no timeout, unchecked returncode, strict encoding."""

    def test_checker_crash_raises_instead_of_zero_findings(self) -> None:
        # mypy exit 2 = fatal (e.g. unreadable file): stdout is EMPTY, the
        # message is on stderr. The old code parsed the empty stdout into
        # zero errors — a silent no-op filter.
        completed = _completed("", returncode=2, stderr="mypy: can't read file 'x'")
        with (
            patch("mutmut_win.type_checking._run_type_check_process", return_value=completed),
            pytest.raises(Exception, match="can't read file"),
        ):
            run_type_checker(["mypy", "--output=json", "x"])

    def test_findings_exit_code_is_not_an_error(self) -> None:
        # Exit 1 just means "errors found" for every supported checker.
        with patch(
            "mutmut_win.type_checking._run_type_check_process",
            return_value=_completed(_MYPY_JSON_LINE, returncode=1),
        ):
            errors = run_type_checker(["mypy", "--output=json", "."])
        assert len(errors) == 1

    def test_process_helper_gets_timeout(self) -> None:
        captured: dict[str, Any] = {}

        def fake_run(cmd: list[str], **kwargs: Any) -> MagicMock:  # noqa: ARG001
            captured.update(kwargs)
            return _completed("")

        with patch("mutmut_win.type_checking._run_type_check_process", side_effect=fake_run):
            run_type_checker(["mypy", "--output=json", "."])
        assert captured.get("timeout") is not None

    def test_timeout_expiry_raises_a_clear_message(self) -> None:
        with (
            patch(
                "mutmut_win.type_checking._run_type_check_process",
                side_effect=subprocess.TimeoutExpired(cmd="mypy", timeout=300),
            ),
            pytest.raises(Exception, match="timed out"),
        ):
            run_type_checker(["mypy", "--output=json", "."])


class TestBoundedProcessRunner:
    """The checker timeout must cover the tree, not just the direct process."""

    def test_output_is_bounded_pipe_capture_instead_of_inherited_pipes(self) -> None:
        process = MagicMock()
        process.pid = 123
        process.wait.return_value = 0

        with (
            patch("mutmut_win.type_checking._create_type_checker_job", return_value=None),
            patch("mutmut_win.type_checking.subprocess.Popen", return_value=process) as popen,
            patch("mutmut_win.type_checking._terminate_type_checker_tree") as terminate_tree,
        ):
            result = _run_type_check_process(["mypy"], timeout=7)

        kwargs = popen.call_args.kwargs
        assert kwargs["stdout"] is not subprocess.PIPE
        assert kwargs["stderr"] is not subprocess.PIPE
        assert isinstance(kwargs["stdout"], int)
        assert isinstance(kwargs["stderr"], int)
        assert result.stdout == ""
        assert result.stderr == ""
        process.wait.assert_called_once_with(timeout=7)
        terminate_tree.assert_called_once_with(process, None)

    def test_internal_child_controls_are_sanitized_from_type_checker_environment(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from mutmut_win.constants import INTERNAL_CHILD_ENVIRONMENT_VARS

        process = MagicMock()
        process.pid = 123
        process.wait.return_value = 0
        for name in INTERNAL_CHILD_ENVIRONMENT_VARS:
            monkeypatch.setenv(name, f"outer-{name}")
        if os.name != "nt":
            monkeypatch.setenv("mutant_under_test", "case-sensitive-user-input")

        with (
            patch("mutmut_win.type_checking._create_type_checker_job", return_value=None),
            patch("mutmut_win.type_checking.subprocess.Popen", return_value=process) as popen,
            patch("mutmut_win.type_checking._terminate_type_checker_tree"),
        ):
            _run_type_check_process(["mypy"], timeout=7)

        child_environment = popen.call_args.kwargs["env"]
        if os.name == "nt":
            child_names = {name.upper() for name in child_environment}
            assert child_names.isdisjoint(INTERNAL_CHILD_ENVIRONMENT_VARS)
        else:
            assert set(child_environment).isdisjoint(INTERNAL_CHILD_ENVIRONMENT_VARS)
            assert child_environment["mutant_under_test"] == "case-sensitive-user-input"

    def test_file_output_is_decoded_tolerantly(self) -> None:
        process = MagicMock()
        process.pid = 124
        process.wait.return_value = 0

        def fake_popen(command: list[str], **kwargs: Any) -> MagicMock:  # noqa: ARG001
            os.write(kwargs["stdout"], b"bad: \xff")
            os.write(kwargs["stderr"], b"err: \xfe")
            return process

        with (
            patch("mutmut_win.type_checking._create_type_checker_job", return_value=None),
            patch("mutmut_win.type_checking.subprocess.Popen", side_effect=fake_popen),
        ):
            result = _run_type_check_process(["mypy"], timeout=7)

        assert result.stdout == "bad: \ufffd"
        assert result.stderr == "err: \ufffd"

    def test_output_limit_fails_closed_without_unbounded_capture(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        process = MagicMock()
        process.pid = 124
        process.wait.return_value = 0

        def fake_popen(command: list[str], **kwargs: Any) -> MagicMock:  # noqa: ARG001
            os.write(kwargs["stdout"], b"12345")
            return process

        monkeypatch.setattr("mutmut_win.type_checking._MAX_CHECKER_OUTPUT_BYTES", 4)
        with (
            patch("mutmut_win.type_checking._create_type_checker_job", return_value=None),
            patch("mutmut_win.type_checking.subprocess.Popen", side_effect=fake_popen),
            pytest.raises(TypeCheckCommandError, match="output exceeded"),
        ):
            _run_type_check_process(["mypy"], timeout=7)

    def test_timeout_invokes_tree_termination_before_reraising(self) -> None:
        process = MagicMock()
        process.pid = 125
        timeout = subprocess.TimeoutExpired(cmd="mypy", timeout=7)
        process.wait.side_effect = timeout

        with (
            patch("mutmut_win.type_checking._create_type_checker_job", return_value=77),
            patch("mutmut_win.type_checking._assign_type_checker_to_job", return_value=True),
            patch("mutmut_win.type_checking._close_type_checker_job") as close_job,
            patch("mutmut_win.type_checking._terminate_type_checker_tree") as terminate,
            patch("mutmut_win.type_checking.subprocess.Popen", return_value=process),
            pytest.raises(subprocess.TimeoutExpired),
        ):
            _run_type_check_process(["mypy"], timeout=7)

        terminate.assert_called_once_with(process, 77)
        close_job.assert_not_called()  # termination owns the one-and-only close

    def test_windows_job_is_assigned_and_closed_after_success(self) -> None:
        process = MagicMock()
        process.pid = 126
        process.wait.return_value = 0

        with (
            patch("mutmut_win.type_checking.sys.platform", "win32"),
            patch("mutmut_win.type_checking._create_type_checker_job", return_value=88),
            patch(
                "mutmut_win.type_checking._assign_type_checker_to_job", return_value=True
            ) as assign,
            patch("mutmut_win.type_checking._close_type_checker_job") as close_job,
            patch("mutmut_win.type_checking.subprocess.Popen", return_value=process),
        ):
            _run_type_check_process(["mypy"], timeout=7)

        assign.assert_called_once_with(88, 126)
        close_job.assert_called_once_with(88)

    def test_interrupt_also_reaps_the_process_tree(self) -> None:
        process = MagicMock()
        process.pid = 127
        process.wait.side_effect = KeyboardInterrupt

        with (
            patch("mutmut_win.type_checking._create_type_checker_job", return_value=None),
            patch("mutmut_win.type_checking._terminate_type_checker_tree") as terminate,
            patch("mutmut_win.type_checking.subprocess.Popen", return_value=process),
            pytest.raises(KeyboardInterrupt),
        ):
            _run_type_check_process(["mypy"], timeout=7)

        terminate.assert_called_once_with(process, None)

    def test_job_close_failure_does_not_skip_fallback_kill_or_mask_timeout(self) -> None:
        process = MagicMock()
        process.pid = 128
        timeout = subprocess.TimeoutExpired(cmd="mypy", timeout=7)
        process.wait.side_effect = [timeout, 0]
        captured_member = MagicMock()
        captured_member.pid = 129

        with (
            patch("mutmut_win.type_checking._create_type_checker_job", return_value=91),
            patch("mutmut_win.type_checking._assign_type_checker_to_job", return_value=True),
            patch("mutmut_win.type_checking.subprocess.Popen", return_value=process),
            patch(
                "mutmut_win.type_checking._snapshot_process_tree",
                return_value=[captured_member],
            ),
            patch(
                "mutmut_win.type_checking._close_type_checker_job",
                side_effect=OSError("close failed"),
            ),
            patch("mutmut_win.type_checking.psutil.wait_procs", return_value=([], [])),
            pytest.raises(subprocess.TimeoutExpired) as exc_info,
        ):
            _run_type_check_process(["mypy"], timeout=7)

        assert exc_info.value is timeout
        captured_member.kill.assert_called_once_with()
        process.kill.assert_called_once_with()
        assert process.wait.call_args_list[-1].kwargs["timeout"] > 0


class TestSetupFailureNeverLeaksJobHandle:
    """M-128: the unguarded window between Job Object creation and the
    protected launch could raise (ephemeral mkdir, environment sanitize,
    creationflags) and leak the kill-on-close handle until process exit."""

    def _instrumented_handles(self, monkeypatch: pytest.MonkeyPatch) -> tuple[list[int], list[int]]:
        created: list[int] = []
        closed: list[int] = []
        monkeypatch.setattr(
            "mutmut_win.type_checking._create_type_checker_job",
            lambda: created.append(4242) or 4242,
        )
        monkeypatch.setattr("mutmut_win.type_checking._close_type_checker_job", closed.append)
        return created, closed

    def test_ephemeral_environment_failure_never_leaks_the_job_handle(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        created, closed = self._instrumented_handles(monkeypatch)

        def boom(environment: dict[str, str], runtime_dir: Path) -> None:  # noqa: ARG001
            raise OSError("mkdir failed")

        # Resolved at call time through the local worker import.
        monkeypatch.setattr(
            "mutmut_win.process.worker.configure_ephemeral_pytest_environment", boom
        )

        with pytest.raises(OSError, match="mkdir failed"):
            _run_type_check_process(["mypy", "--output=json", "."], timeout=1)

        assert set(created) <= set(closed)

    def test_environment_setup_failure_never_leaks_the_job_handle(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        created, closed = self._instrumented_handles(monkeypatch)

        def boom() -> dict[str, str]:
            raise RuntimeError("environment exploded")

        monkeypatch.setattr("mutmut_win.type_checking._type_checker_environment", boom)

        with pytest.raises(RuntimeError, match="environment exploded"):
            _run_type_check_process(["mypy", "--output=json", "."], timeout=1)

        assert set(created) <= set(closed)

    def test_creationflags_setup_failure_never_leaks_the_job_handle(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        created, closed = self._instrumented_handles(monkeypatch)

        def boom(base: int) -> int:  # noqa: ARG001
            raise RuntimeError("creationflags exploded")

        monkeypatch.setattr("mutmut_win.process.worker._contained_creationflags", boom)

        with pytest.raises(RuntimeError, match="creationflags exploded"):
            _run_type_check_process(["mypy", "--output=json", "."], timeout=1)

        assert set(created) <= set(closed)

    def test_atomic_launch_failure_closes_the_handle_exactly_once(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        created, closed = self._instrumented_handles(monkeypatch)
        failing_launch = MagicMock(side_effect=OSError("launch failed"))
        monkeypatch.setattr("mutmut_win.process.atomic_spawn.AtomicJobPopen", failing_launch)

        with pytest.raises(ProcessContainmentError, match="atomically"):
            _run_type_check_process(["mypy", "--output=json", "."], timeout=1)

        assert created == [4242]
        assert closed == [4242]

    def test_non_atomic_launch_failure_closes_the_handle_exactly_once(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        created, closed = self._instrumented_handles(monkeypatch)
        failing_launch = MagicMock(side_effect=OSError("launch failed"))

        with (
            patch("mutmut_win.type_checking.sys.platform", "linux"),
            patch("mutmut_win.type_checking.subprocess.Popen", failing_launch),
            pytest.raises(OSError, match="launch failed"),
        ):
            _run_type_check_process(["mypy", "--output=json", "."], timeout=1)

        assert created == [4242]
        assert closed == [4242]


class TestPyrightSeverityFilter:
    """Issue #92 / A3-CM-011: warnings and information counted as type errors."""

    def test_only_error_severity_counts(self) -> None:
        report = {
            "generalDiagnostics": [
                {
                    "file": "src/a.py",
                    "severity": "error",
                    "message": "real error",
                    "range": {"start": {"line": 1}},
                },
                {
                    "file": "src/a.py",
                    "severity": "warning",
                    "message": "just a warning",
                    "range": {"start": {"line": 2}},
                },
                {
                    "file": "src/a.py",
                    "severity": "information",
                    "message": "fyi",
                    "range": {"start": {"line": 3}},
                },
            ]
        }
        errors = parse_pyright_report(report)
        assert len(errors) == 1
        assert errors[0].error_description == "real error"
