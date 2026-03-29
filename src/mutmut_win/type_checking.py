"""Module for running external type checkers and parsing their reports."""

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import cast


@dataclass
class TypeCheckingError:
    """Represents a single type checking error from an external type checker."""

    file_path: Path
    line_number: int
    """line number (first line is 1)"""
    error_description: str


def run_type_checker(type_check_command: list[str]) -> list[TypeCheckingError]:
    """Run an external type checker and return a list of errors.

    Args:
        type_check_command: The command to run (e.g. ['mypy', '--output=json', 'src/']).

    Returns:
        A list of TypeCheckingError instances parsed from the command output.

    Raises:
        Exception: If the type checker does not return valid JSON output.
    """
    # S603: type_check_command is a trusted list supplied by the mutmut framework, not user input
    completed_process = subprocess.run(  # noqa: S603
        type_check_command, capture_output=True, encoding="utf-8"
    )

    try:
        if "mypy" in type_check_command:
            report = [json.loads(line) for line in completed_process.stdout.splitlines()]
        else:
            report = json.loads(completed_process.stdout)
    except json.JSONDecodeError as exc:
        raise Exception(
            f"type check command did not return JSON. "
            f"Got: {completed_process.stdout} (stderr: {completed_process.stderr})"
        ) from exc

    if "pyrefly" in type_check_command:
        return parse_pyrefly_report(cast("dict", report))
    if "mypy" in type_check_command:
        return parse_mypy_report(report)
    if "ty" in type_check_command:
        return parse_ty_report(report)
    return parse_pyright_report(cast("dict", report))


def parse_pyright_report(result: dict) -> list[TypeCheckingError]:
    """Parse a pyright JSON report into a list of TypeCheckingError instances."""
    if "generalDiagnostics" not in result:
        raise Exception(
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
    ]


def parse_pyrefly_report(result: dict) -> list[TypeCheckingError]:
    """Parse a pyrefly JSON report into a list of TypeCheckingError instances."""
    if "errors" not in result:
        raise Exception(
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


def parse_mypy_report(result: list[dict]) -> list[TypeCheckingError]:
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


def parse_ty_report(result: list[dict]) -> list[TypeCheckingError]:
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
