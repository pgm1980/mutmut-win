"""Unit tests for mutmut_win.type_checking."""

import json
import os
import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from mutmut_win.exceptions import TypeCheckCommandError
from mutmut_win.type_checking import (
    TypeCheckingError,
    _run_type_check_process,
    parse_mypy_report,
    parse_pyrefly_report,
    parse_pyright_report,
    parse_ty_report,
    run_type_checker,
)


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
        with patch(
            "mutmut_win.type_checking._run_type_check_process", return_value=_completed("")
        ):  # empty = empty list
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
