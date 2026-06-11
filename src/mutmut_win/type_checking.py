"""Module for running external type checkers and parsing their reports."""

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mutmut_win.exceptions import TypeCheckCommandError

#: Wall-clock budget for one type-checker invocation. A hung checker used to
#: hang the whole mutation run (A3-CM-010); 300 s comfortably covers cold
#: pyright/mypy runs on large codebases while still failing visibly.
TYPE_CHECK_TIMEOUT_SECONDS: int = 300

#: Checker names recognised anywhere in the command, by token basename —
#: `mypy.exe`, `.venv\Scripts\mypy.exe`, `uv run mypy` and `python -m mypy`
#: all resolve to "mypy" (A3-CM-008: exact list membership sent the
#: Windows-normal forms into the pyright JSON parser, aborting the run).
_KNOWN_CHECKERS: frozenset[str] = frozenset({"mypy", "pyright", "pyrefly", "ty"})


@dataclass
class TypeCheckingError:
    """Represents a single type checking error from an external type checker."""

    file_path: Path
    line_number: int
    """line number (first line is 1)"""
    error_description: str


def _detect_checker(type_check_command: list[str]) -> str | None:
    """Return the recognised checker name in *type_check_command*, if any.

    Matches on the casefolded basename stem of each token, so wrapper forms
    (``uv run mypy``, ``python -m mypy``) and Windows paths
    (``.venv\\Scripts\\mypy.exe``) are all recognised.
    """
    for token in type_check_command:
        stem = Path(token).stem.casefold()
        if stem in _KNOWN_CHECKERS:
            return stem
    return None


def run_type_checker(type_check_command: list[str]) -> list[TypeCheckingError]:
    """Run an external type checker and return a list of errors.

    Args:
        type_check_command: The command to run (e.g. ['mypy', '--output=json', 'src/']).

    Returns:
        A list of TypeCheckingError instances parsed from the command output.

    Raises:
        TypeCheckCommandError: If the checker times out, exits with a
            non-finding status (anything but 0/1 — e.g. mypy 2 = fatal,
            pyright 3/4 = config or usage error), or does not return valid
            JSON output (issue #114 / A4-QX-023 — these were bare
            ``Exception`` raises).
    """
    try:
        # S603: type_check_command is a trusted list supplied by the mutmut
        # framework, not user input
        completed_process = subprocess.run(  # noqa: S603
            type_check_command,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=TYPE_CHECK_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise TypeCheckCommandError(
            f"type check command timed out after {TYPE_CHECK_TIMEOUT_SECONDS}s: "
            f"{type_check_command}"
        ) from exc

    # 0 = clean, 1 = findings (every supported checker). Anything else is a
    # checker FAILURE — e.g. mypy exit 2 leaves stdout empty, which the old
    # code happily parsed into "zero errors": a silent no-op filter.
    if completed_process.returncode not in (0, 1):
        raise TypeCheckCommandError(
            f"type check command failed with exit code "
            f"{completed_process.returncode}. stderr: {completed_process.stderr}"
        )

    checker = _detect_checker(type_check_command)

    try:
        report: Any = (
            [json.loads(line) for line in completed_process.stdout.splitlines()]
            if checker == "mypy"
            else json.loads(completed_process.stdout)
        )
    except json.JSONDecodeError as exc:
        raise TypeCheckCommandError(
            f"type check command did not return JSON. "
            f"Got: {completed_process.stdout} (stderr: {completed_process.stderr})"
        ) from exc

    if checker == "pyrefly":
        return parse_pyrefly_report(report)
    if checker == "mypy":
        return parse_mypy_report(report)
    if checker == "ty":
        return parse_ty_report(report)
    # Unknown checkers fall through to the pyright parser (historic default).
    return parse_pyright_report(report)


def parse_pyright_report(result: dict[str, Any]) -> list[TypeCheckingError]:
    """Parse a pyright JSON report into a list of TypeCheckingError instances.

    Only ``severity == "error"`` diagnostics count (A3-CM-011): pyright emits
    ``error | warning | information``, and warnings must not kill mutants.
    """
    if "generalDiagnostics" not in result:
        raise TypeCheckCommandError(
            f'Invalid pyright report. Could not find key "generalDiagnostics". '
            f"Found: {set(result.keys())}"
        )

    return [
        TypeCheckingError(
            file_path=Path(diagnostic["file"]),
            line_number=diagnostic["range"]["start"]["line"] + 1,
            error_description=diagnostic["message"],
        )
        for diagnostic in result["generalDiagnostics"]
        if diagnostic.get("severity") == "error"
    ]


def parse_pyrefly_report(result: dict[str, Any]) -> list[TypeCheckingError]:
    """Parse a pyrefly JSON report into a list of TypeCheckingError instances."""
    if "errors" not in result:
        raise TypeCheckCommandError(
            f'Invalid pyrefly report. Could not find key "errors". Found: {set(result.keys())}'
        )

    return [
        TypeCheckingError(
            file_path=Path(error["path"]).absolute(),
            line_number=error["line"],
            error_description=error["concise_description"],
        )
        for error in result["errors"]
    ]


def parse_mypy_report(result: list[dict[str, Any]]) -> list[TypeCheckingError]:
    """Parse a mypy JSON report into a list of TypeCheckingError instances."""
    return [
        TypeCheckingError(
            file_path=Path(diagnostic["file"]).absolute(),
            line_number=diagnostic["line"],
            error_description=diagnostic["message"],
        )
        for diagnostic in result
        if diagnostic["severity"] == "error"
    ]


def parse_ty_report(result: list[dict[str, Any]]) -> list[TypeCheckingError]:
    """Parse a 'ty' type checker report into a list of TypeCheckingError instances."""
    # assuming the gitlab code quality report format, these severities seem okay
    # https://docs.gitlab.com/ci/testing/code_quality/#code-quality-report-format
    return [
        TypeCheckingError(
            file_path=Path(diagnostic["location"]["path"]).absolute(),
            line_number=diagnostic["location"]["positions"]["begin"]["line"],
            error_description=diagnostic["description"],
        )
        for diagnostic in result
        if diagnostic["severity"] in ("major", "critical", "blocker")
    ]
