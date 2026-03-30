"""Unit tests for mutmut_win.type_checking."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mutmut_win.type_checking import (
    TypeCheckingError,
    parse_mypy_report,
    parse_pyrefly_report,
    parse_pyright_report,
    parse_ty_report,
    run_type_checker,
)

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
        mock_process = MagicMock()
        mock_process.stdout = "not json"
        mock_process.stderr = ""

        with (
            patch("subprocess.run", return_value=mock_process),
            pytest.raises(Exception, match="did not return JSON"),
        ):
            run_type_checker(["pyright", "--outputjson", "."])

    def test_pyright_route(self) -> None:
        mock_process = MagicMock()
        mock_process.stdout = json.dumps({"generalDiagnostics": []})
        mock_process.stderr = ""

        with patch("subprocess.run", return_value=mock_process):
            errors = run_type_checker(["pyright", "--outputjson", "."])
        assert errors == []

    def test_mypy_route(self) -> None:
        mock_process = MagicMock()
        mock_process.stdout = ""  # empty = empty list
        mock_process.stderr = ""

        with patch("subprocess.run", return_value=mock_process):
            errors = run_type_checker(["mypy", "--output=json", "."])
        assert errors == []

    def test_pyrefly_route(self) -> None:
        mock_process = MagicMock()
        mock_process.stdout = json.dumps({"errors": []})
        mock_process.stderr = ""

        with patch("subprocess.run", return_value=mock_process):
            errors = run_type_checker(["pyrefly", "check", "."])
        assert errors == []

    def test_ty_route(self) -> None:
        mock_process = MagicMock()
        mock_process.stdout = json.dumps([])
        mock_process.stderr = ""

        with patch("subprocess.run", return_value=mock_process):
            errors = run_type_checker(["ty", "check", "."])
        assert errors == []
