"""Module for running external type checkers and parsing their reports."""

import contextlib
import json
import logging
import os
import signal
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psutil  # type: ignore[import-untyped,unused-ignore]

from mutmut_win.constants import INTERNAL_CHILD_ENVIRONMENT_VARS
from mutmut_win.exceptions import ProcessContainmentError, TypeCheckCommandError
from mutmut_win.process.output_capture import BoundedOutputCapture

logger = logging.getLogger(__name__)
_REAL_POPEN_TYPE = subprocess.Popen

#: Wall-clock budget for one type-checker invocation. A hung checker used to
#: hang the whole mutation run (A3-CM-010); 300 s comfortably covers cold
#: pyright/mypy runs on large codebases while still failing visibly.
TYPE_CHECK_TIMEOUT_SECONDS: int = 300

#: A timeout first kills the complete process tree, then waits only this long
#: for the direct child to become reapable.  Output is file-backed rather than
#: pipe-backed, so a missed/privileged descendant cannot extend this wait by
#: retaining an inherited capture handle.
_PROCESS_KILL_GRACE_SECONDS: float = 2.0
_MAX_CHECKER_OUTPUT_BYTES: int = 16 * 1024 * 1024


def _type_checker_environment() -> dict[str, str]:
    """Return inherited inputs with mutmut's internal child controls removed.

    This is defense-in-depth for the external checker; the execution-basis
    digest independently binds the complete inherited environment because
    Python startup can observe values before this boundary. Environment keys
    are case-insensitive on Windows and case-sensitive on POSIX, matching each
    platform's subprocess semantics.
    """

    if os.name == "nt":
        return {
            name: value
            for name, value in os.environ.items()
            if name.upper() not in INTERNAL_CHILD_ENVIRONMENT_VARS
        }
    return {
        name: value
        for name, value in os.environ.items()
        if name not in INTERNAL_CHILD_ENVIRONMENT_VARS
    }


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


def _create_type_checker_job() -> int | None:
    """Create a Windows kill-on-close Job Object before suspended launch."""
    if sys.platform != "win32":
        return None

    from mutmut_win.process.job_object import create_kill_on_close_job

    try:
        return create_kill_on_close_job()
    except OSError as exc:
        logger.warning(
            "Could not create a Job Object for the type checker; "
            "the suspended checker will be refused: %s",
            exc,
        )
        return None


def _close_type_checker_job(job_handle: int) -> None:
    """Close a Windows Job Object handle (and therefore kill its members)."""
    from mutmut_win.process.job_object import close_job

    close_job(job_handle)


def _assign_type_checker_to_job(job_handle: int, pid: int) -> bool:
    """Assign *pid* to *job_handle* before resume; return False on denial."""
    from mutmut_win.process.job_object import assign_process_to_job

    try:
        assign_process_to_job(job_handle, pid)
    except OSError as exc:
        logger.warning(
            "Could not assign type checker PID %d to its Job Object; "
            "the suspended checker will be refused: %s",
            pid,
            exc,
        )
        return False
    return True


def _snapshot_process_tree(pid: int) -> list[psutil.Process]:
    """Best-effort snapshot of *pid* and descendants, even after root exit."""
    members: list[psutil.Process] = []
    seen: set[int] = set()
    try:
        root = psutil.Process(pid)
        members.append(root)
        seen.add(root.pid)
        for child in root.children(recursive=True):
            if child.pid not in seen:
                members.append(child)
                seen.add(child.pid)
    except (psutil.AccessDenied, psutil.NoSuchProcess):
        pass

    # On Windows, an orphan keeps the exited parent's PID as its PPID.  A
    # Process(pid).children() lookup therefore loses exactly the descendants
    # we need to reap after a successful root exit.  Build a PPID graph from a
    # system snapshot so the dead-root fallback remains effective.
    children_by_ppid: dict[int, list[psutil.Process]] = {}
    for process in psutil.process_iter(["pid", "ppid"]):
        with contextlib.suppress(psutil.AccessDenied, psutil.NoSuchProcess):
            children_by_ppid.setdefault(process.info["ppid"], []).append(process)
    pending = [pid]
    while pending:
        parent_pid = pending.pop()
        for child in children_by_ppid.get(parent_pid, []):
            if child.pid in seen:
                continue
            members.append(child)
            seen.add(child.pid)
            pending.append(child.pid)
    return members


def _terminate_type_checker_tree(process: subprocess.Popen[bytes], job_handle: int | None) -> None:
    """Kill a timed-out checker and its descendants without pipe-dependent waits.

    Windows Job Objects are the primary boundary. POSIX additionally gets a
    dedicated process group via ``start_new_session=True``; the psutil snapshot
    is belt-and-suspenders cleanup for already-contained processes.
    """
    cleanup_errors: list[tuple[str, BaseException]] = []

    def attempt(label: str, operation: Any) -> None:
        try:
            operation()
        except BaseException as exc:
            cleanup_errors.append((label, exc))

    try:
        processes = _snapshot_process_tree(process.pid)
    except BaseException as exc:
        # A failed diagnostic snapshot must never prevent the authoritative
        # Job/process-group and direct-child kill stages.
        processes = []
        cleanup_errors.append(("snapshot process tree", exc))

    if job_handle is not None:
        attempt("close type-checker Job Object", lambda: _close_type_checker_job(job_handle))
    elif sys.platform != "win32":

        def kill_process_group() -> None:
            with contextlib.suppress(ProcessLookupError, PermissionError):
                os.killpg(process.pid, signal.SIGKILL)

        attempt("kill type-checker process group", kill_process_group)

    # Kill the root first so it cannot create more children while the captured
    # descendants are being terminated.  psutil Process objects retain PID /
    # creation-time identity, limiting PID-reuse hazards during this short path.
    for member in processes:
        attempt(f"kill captured PID {member.pid}", member.kill)
    if processes:
        attempt(
            "wait for captured process tree",
            lambda: psutil.wait_procs(processes, timeout=_PROCESS_KILL_GRACE_SECONDS),
        )

    # Last-resort direct-child kill/reap.  This wait is bounded and cannot be
    # extended by a descendant holding stdout/stderr because they are files.
    attempt("kill direct type-checker child", process.kill)
    try:
        process.wait(timeout=_PROCESS_KILL_GRACE_SECONDS)
    except subprocess.TimeoutExpired:
        logger.error("Timed-out type checker PID %d could not be reaped", process.pid)
    except BaseException as exc:
        cleanup_errors.append(("reap direct type-checker child", exc))

    for label, cleanup_exc in cleanup_errors:
        logger.error("type-checker cleanup failed (%s): %s", label, cleanup_exc)


def _run_type_check_process(
    type_check_command: list[str], *, timeout: float
) -> subprocess.CompletedProcess[str]:
    """Run a checker with bounded process-tree cleanup and bounded output."""
    from mutmut_win.process.worker import _contained_creationflags, _resume_after_containment

    with (
        BoundedOutputCapture(max_tail_bytes=_MAX_CHECKER_OUTPUT_BYTES) as stdout_capture,
        BoundedOutputCapture(max_tail_bytes=_MAX_CHECKER_OUTPUT_BYTES) as stderr_capture,
    ):
        job_handle = _create_type_checker_job()
        popen_kwargs: dict[str, Any] = {
            "env": _type_checker_environment(),
            "stdout": stdout_capture.writer_fd,
            "stderr": stderr_capture.writer_fd,
        }
        if sys.platform != "win32":
            popen_kwargs["start_new_session"] = True
        else:
            popen_kwargs["creationflags"] = _contained_creationflags(
                getattr(subprocess, "CREATE_NO_WINDOW", 0)
            )

        atomic_windows_launch = sys.platform == "win32" and subprocess.Popen is _REAL_POPEN_TYPE
        if atomic_windows_launch:
            popen_kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)

        process: subprocess.Popen[bytes]
        try:
            # S603: type_check_command is a trusted list supplied by the mutmut
            # framework, not untrusted shell input.  PIPE is deliberately not
            # used: descendants retaining inherited pipe handles made the old
            # subprocess.run(timeout=...) path block after its timeout.
            if atomic_windows_launch:
                if job_handle is None:
                    raise ProcessContainmentError(
                        "Could not establish a Windows Job Object for the type checker."
                    )
                from mutmut_win.process.atomic_spawn import AtomicJobPopen

                process = AtomicJobPopen(
                    type_check_command,
                    job_handle=job_handle,
                    **popen_kwargs,
                )
            else:
                process = subprocess.Popen(type_check_command, **popen_kwargs)  # noqa: S603
            stdout_capture.close_writer()
            stderr_capture.close_writer()
        except BaseException as exc:
            stdout_capture.close_writer()
            stderr_capture.close_writer()
            if job_handle is not None:
                try:
                    _close_type_checker_job(job_handle)
                except BaseException as cleanup_exc:
                    exc.add_note(
                        "type-checker launch cleanup failed while closing the Job Object: "
                        f"{type(cleanup_exc).__qualname__}: {cleanup_exc}"
                    )
            if atomic_windows_launch and not isinstance(exc, ProcessContainmentError):
                raise ProcessContainmentError(
                    "Could not create the type checker atomically inside its Windows Job Object."
                ) from exc
            raise

        if not atomic_windows_launch:
            if job_handle is not None and not _assign_type_checker_to_job(job_handle, process.pid):
                _close_type_checker_job(job_handle)
                job_handle = None
            try:
                _resume_after_containment(process, job_handle)
            except BaseException:
                job_handle = None
                raise

        tree_cleanup_done = False
        try:
            try:
                returncode = process.wait(timeout=timeout)
            except BaseException:
                # Timeout is the normal producer, but Ctrl-C/SystemExit and
                # unexpected wait failures must obey the same no-orphan rule.
                _terminate_type_checker_tree(process, job_handle)
                tree_cleanup_done = True
                raise
        finally:
            if not tree_cleanup_done:
                # A successful checker can leave background children behind.
                # Job Objects cover Windows; the POSIX process group and
                # dead-root PPID sweep cover the non-Windows path.
                _terminate_type_checker_tree(process, job_handle)

        stdout_capture.close()
        stderr_capture.close()
        if stdout_capture.truncated or stderr_capture.truncated:
            raise TypeCheckCommandError(
                "type check command output exceeded the 16 MiB safety limit"
            )
        return subprocess.CompletedProcess(
            args=type_check_command,
            returncode=returncode,
            stdout=stdout_capture.text(),
            stderr=stderr_capture.text(),
        )


def run_type_checker(type_check_command: list[str]) -> list[TypeCheckingError]:
    """Run an external type checker and return a list of errors.

    Args:
        type_check_command: The command to run (e.g. ['mypy', '--output=json', 'src/']).

    Returns:
        A list of TypeCheckingError instances parsed from the command output.

    Raises:
        ProcessContainmentError: If the checker process cannot be placed in
            the mandatory Windows Job Object containment boundary.
        TypeCheckCommandError: If the checker times out, exits with a
            non-finding status (anything but 0/1 — e.g. mypy 2 = fatal,
            pyright 3/4 = config or usage error), or does not return valid
            JSON output (issue #114 / A4-QX-023 — these were bare
            ``Exception`` raises).
    """
    try:
        completed_process = _run_type_check_process(
            type_check_command,
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
