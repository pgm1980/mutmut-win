"""Module for running external type checkers and parsing their reports."""

import contextlib
import json
import logging
import os
import signal
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Self

import psutil  # type: ignore[import-untyped,unused-ignore]
from pydantic import BaseModel, ConfigDict, TypeAdapter, ValidationError, model_validator

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


def _capture_root_create_time(process: subprocess.Popen[bytes]) -> float | None:
    """Capture the checker root's create_time at safe creation time (M-009/AR-01).

    Called immediately after the launch, while the still-open Popen handle
    reserves the PID from recycling.  The captured value is the ONLY root
    identity the later cleanup trusts: querying psutil at teardown time
    cannot distinguish a dead root from a recycled PID.  Popen test doubles
    carry no kernel identity at all — their synthetic pid must never reach
    psutil — so they capture nothing (None) and the cleanup stays sweep-less
    (fail-closed).  Returns None on any observation failure for the same
    reason: without a verified identity there is no verified membership.
    """
    if not isinstance(process, _REAL_POPEN_TYPE):
        return None
    try:
        create_time: float = psutil.Process(process.pid).create_time()
        return create_time
    # The bare PEP 758 form breaks the pinned Semgrep 1.175 parser (M-004 contract)
    except (psutil.Error, OSError, ValueError):  # fmt: skip
        return None


def _snapshot_process_tree(pid: int, root_create_time: float | None = None) -> list[psutil.Process]:
    """Best-effort identity-verified snapshot of *pid* and its descendants.

    Identity rule (M-009 / AR-01) — one rule for every platform and every
    snapshot path: members are only returned when *root_create_time*, the
    identity captured at safe creation time, is provided.  With it, the
    observable root object is only included if its own create_time still
    matches the captured value (an observable mismatch means the psutil
    object is not this checker — object identity is not provenance), and
    every parent→child edge is accepted only if the child's create_time is
    >= its verified parent's, via :func:`mutmut_win.process.worker._iter_descendants`.
    Without a captured identity (None) the snapshot returns nothing at all:
    there is no unverified PPID walk on Windows or anywhere else, because
    psutil's per-Process identity checks only protect against reuse of a
    child PID — they cannot prove that a PPID edge belongs to this root
    instance (C-001 / SEC-001).
    """
    if root_create_time is None:
        return []
    members: list[psutil.Process] = []
    seen: set[int] = set()
    try:
        root = psutil.Process(pid)
        if root.create_time() == root_create_time:
            members.append(root)
            seen.add(root.pid)
    except (
        psutil.AccessDenied,
        psutil.NoSuchProcess,
    ):
        # Root already exited (normal after process.wait) or unreadable: the
        # verified orphan walk below still covers its surviving descendants.
        pass

    from mutmut_win.process.worker import _iter_descendants

    for child in _iter_descendants(pid, root_create_time):
        if child.pid not in seen:
            members.append(child)
            seen.add(child.pid)
    return members


def _terminate_type_checker_tree(
    process: subprocess.Popen[bytes],
    job_handle: int | None,
    root_create_time: float | None = None,
) -> None:
    """Kill a timed-out checker and its descendants without pipe-dependent waits.

    Windows Job Objects are the primary boundary. POSIX additionally gets a
    dedicated process group via ``start_new_session=True``; the psutil snapshot
    is belt-and-suspenders cleanup for already-contained processes.

    Identity rule (M-009 / AR-01): the caller passes *root_create_time*, the
    identity captured by :func:`_capture_root_create_time` while the launch
    handle still reserved the PID.  This function never queries psutil for
    the root identity at teardown time — a dead or unreadable root would
    leave no identity, and an unverified PPID walk could attribute and kill
    a foreign orphan (C-001 / SEC-001).  Without a captured identity no PPID
    sweep runs at all (fail-closed); the Job Object, the POSIX process group
    and the direct-child kill remain the authoritative cleanup paths.
    """
    cleanup_errors: list[tuple[str, BaseException]] = []

    def attempt(label: str, operation: Any) -> None:
        try:
            operation()
        except BaseException as exc:
            cleanup_errors.append((label, exc))

    processes: list[psutil.Process] = []
    if root_create_time is None:
        logger.debug(
            "type-checker cleanup for PID %s without captured root identity; "
            "PPID sweep skipped (fail-closed)",
            process.pid,
        )
    else:
        try:
            processes = _snapshot_process_tree(process.pid, root_create_time)
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
    # descendants are being terminated.  Every member of the snapshot is
    # identity-verified (captured root create_time + verified PPID edges);
    # psutil Process objects retain PID / creation-time identity, limiting
    # PID-reuse hazards during this short path.
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


def _redirect_checker_caches(environment: dict[str, str], runtime_dir: Path) -> None:
    """Point checker cache directories at the ephemeral per-run directory.

    mypy resolves its default ``.mypy_cache`` relative to the process cwd,
    which is ``mutants/`` during type-check filtering; writing it there
    invalidates the strict staging evidence.  The variable deliberately
    overrides any inherited value (the ephemeral environment overrides
    ``HYPOTHESIS_STORAGE_DIRECTORY`` the same way).  A ``--cache-dir``
    argument in the checker argv still wins over the variable and is caught
    by the orchestrator's post-check fail-safe instead.
    """

    environment["MYPY_CACHE_DIR"] = str(runtime_dir / "mypy-cache")


def _run_type_check_process(
    type_check_command: list[str], *, timeout: float
) -> subprocess.CompletedProcess[str]:
    """Run a checker with bounded process-tree cleanup and bounded output.

    The Windows Job Object handle is created as the first statement of the
    protected launch region, after every fallible setup step, so no setup
    failure can leak the kill-on-close handle (M-128).

    Launch contract (M-144 / AR-05): on Windows with the import-time
    ``subprocess.Popen`` intact, the checker is created atomically inside
    its Job Object (``AtomicJobPopen``).  The non-atomic compatibility
    branch serves only Popen test doubles; a ``subprocess.Popen`` replaced
    after import is fail-closed refused — a replacing subclass before any
    launch, a real instance returned by a function wrapper immediately
    after the launch and before the PID-based assign/resume path — via
    ``ProcessContainmentError``, with writer and Job handle cleaned up by
    the existing except path.
    """
    from mutmut_win.process.worker import (
        _contained_creationflags,
        _refuse_real_process_from_replaced_popen,
        _refuse_replaced_popen_subclass,
        _resume_after_containment,
        configure_ephemeral_pytest_environment,
    )

    with (
        tempfile.TemporaryDirectory(
            prefix="mutmut-win-typecheck-runtime-",
            ignore_cleanup_errors=True,
        ) as runtime_name,
        BoundedOutputCapture(max_tail_bytes=_MAX_CHECKER_OUTPUT_BYTES) as stdout_capture,
        BoundedOutputCapture(max_tail_bytes=_MAX_CHECKER_OUTPUT_BYTES) as stderr_capture,
    ):
        # M-128: every fallible setup step (environment sanitize, ephemeral
        # pytest directories with exist_ok=False mkdirs, cache redirect,
        # creationflags) runs BEFORE any Job Object handle exists, so a
        # setup failure can no longer leak a kill-on-close handle.
        checker_environment = _type_checker_environment()
        configure_ephemeral_pytest_environment(checker_environment, Path(runtime_name))
        _redirect_checker_caches(checker_environment, Path(runtime_name))
        popen_kwargs: dict[str, Any] = {
            "env": checker_environment,
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
        job_handle: int | None = None
        try:
            # First statement inside the protected region (M-128): the Job
            # Object must exist before the suspended launch (atomic-launch
            # contract), and every later failure is covered by the cleanup
            # below.
            job_handle = _create_type_checker_job()
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
                # M-144 (AR-05): this compatibility branch exists only for
                # Popen test doubles.  A Popen replaced after import is
                # refused BEFORE any launch (a subclass could start a real,
                # uncontained process) and a real instance returned by a
                # function wrapper is refused right after the launch and
                # before the PID-based assign/resume path; the except path
                # below closes writer and Job handle exactly once.
                _refuse_replaced_popen_subclass(_REAL_POPEN_TYPE)
                process = subprocess.Popen(type_check_command, **popen_kwargs)  # noqa: S603
                _refuse_real_process_from_replaced_popen(process, _REAL_POPEN_TYPE)
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

        # M-009 / AR-01: capture the root identity right after the safe
        # launch, while the open Popen handle still reserves the PID from
        # recycling, and carry it into every cleanup call.  Test doubles
        # capture nothing (None); without a captured identity the cleanup
        # refuses to sweep PPID edges at all (fail-closed).
        root_create_time = _capture_root_create_time(process)

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
                _terminate_type_checker_tree(process, job_handle, root_create_time=root_create_time)
                tree_cleanup_done = True
                raise
        finally:
            if not tree_cleanup_done:
                # A successful checker can leave background children behind.
                # Job Objects cover Windows; the POSIX process group and the
                # identity-verified dead-root PPID sweep cover the rest.
                _terminate_type_checker_tree(process, job_handle, root_create_time=root_create_time)

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


def _decode_checker_report(checker: str | None, stdout: str, stderr: str) -> Any:
    """Decode checker stdout into one decoded JSON report value (M-059).

    mypy speaks JSONL: every non-blank stdout line is one JSON diagnostic
    object.  A finding-free ``mypy --output=json`` run still writes exactly
    one blank line (the success summary collapses to a bare newline in mypy
    1.19.1), and blank lines may also appear between diagnostics, so
    whitespace-only lines are skipped.  Fail-closed is preserved: any other
    non-JSON line (text-mode mypy output, a ``Success: no issues found in 1
    source file`` summary, garbage) aborts with TypeCheckCommandError instead
    of silently filtering to zero findings.  All other checkers emit one JSON
    document, decoded as a whole.

    Raises:
        TypeCheckCommandError: If stdout is not the checker's expected JSON
            shape at the syntax level (see the mypy blank-line rule above).
    """
    try:
        if checker == "mypy":
            return [json.loads(line) for line in stdout.splitlines() if line.strip()]
        return json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise TypeCheckCommandError(
            f"type check command did not return JSON. Got: {stdout} (stderr: {stderr})"
        ) from exc


class _PyrightDiagnostic(BaseModel):
    """Shape contract for one pyright ``generalDiagnostics`` entry (M-127).

    Only the keys the parser actually reads are checked, and only for
    entries the severity filter keeps: validation must never be stricter
    than the historical accesses — a warning without ``range`` stays
    acceptable and ignored.  Values stay untyped (``Any``): a non-string
    ``severity`` means "not an error" today and must not start failing.
    """

    model_config = ConfigDict(extra="ignore")

    severity: Any = None
    file: Any = None
    message: Any = None
    range: Any = None

    @model_validator(mode="after")
    def _error_entries_must_carry_the_accessed_keys(self) -> Self:
        if self.severity != "error":
            return self
        for field in ("file", "message", "range"):
            if field not in self.model_fields_set:
                raise ValueError(f"error diagnostic is missing '{field}'")
        if not isinstance(self.range, dict):
            raise ValueError("'range' must be a JSON object")
        start = self.range.get("start")
        if not isinstance(start, dict) or "line" not in start:
            raise ValueError("'range.start' must be a JSON object with a 'line' key")
        return self


class _PyrightReport(BaseModel):
    """Top-level pyright report contract; unknown keys are ignored."""

    model_config = ConfigDict(extra="ignore")

    # The key is pyright's documented camelCase wire name; an alias would
    # change the validation error location away from the wire format.
    generalDiagnostics: list[_PyrightDiagnostic]  # noqa: N815


class _PyreflyError(BaseModel):
    """Shape contract for one pyrefly ``errors`` entry (M-127).

    pyrefly reports carry no severity — every entry is read, so every
    entry must carry the three accessed keys.
    """

    model_config = ConfigDict(extra="ignore")

    path: Any
    line: Any
    concise_description: Any


class _PyreflyReport(BaseModel):
    """Top-level pyrefly report contract; unknown keys are ignored."""

    model_config = ConfigDict(extra="ignore")

    errors: list[_PyreflyError]


class _MypyDiagnostic(BaseModel):
    """Shape contract for one mypy JSONL diagnostic (M-127).

    ``severity`` is read for EVERY entry, so the key is required (a missing
    key was a raw KeyError before); ``file``/``line``/``message`` are only
    read for ``severity == "error"``.  Values stay untyped (``Any``).
    """

    model_config = ConfigDict(extra="ignore")

    severity: Any
    file: Any = None
    line: Any = None
    message: Any = None

    @model_validator(mode="after")
    def _error_entries_must_carry_the_accessed_keys(self) -> Self:
        if self.severity == "error":
            for field in ("file", "line", "message"):
                if field not in self.model_fields_set:
                    raise ValueError(f"error diagnostic is missing '{field}'")
        return self


class _TyDiagnostic(BaseModel):
    """Shape contract for one 'ty' code-quality report entry (M-127).

    ``severity`` is read for EVERY entry, so the key is required;
    ``location``/``description`` and the nested begin position are only
    checked for the severities the filter keeps.  Values stay untyped.
    """

    model_config = ConfigDict(extra="ignore")

    severity: Any
    location: Any = None
    description: Any = None

    @model_validator(mode="after")
    def _finding_entries_must_carry_the_accessed_keys(self) -> Self:
        if self.severity not in ("major", "critical", "blocker"):
            return self
        for field in ("location", "description"):
            if field not in self.model_fields_set:
                raise ValueError(f"{self.severity} diagnostic is missing '{field}'")
        if not isinstance(self.location, dict):
            raise ValueError("'location' must be a JSON object")
        for key in ("path", "positions"):
            if key not in self.location:
                raise ValueError(f"'location' is missing '{key}'")
        positions = self.location["positions"]
        if not isinstance(positions, dict) or "begin" not in positions:
            raise ValueError("'location.positions' must be an object with a 'begin' key")
        begin = positions["begin"]
        if not isinstance(begin, dict) or "line" not in begin:
            raise ValueError("'location.positions.begin' must be an object with a 'line' key")
        return self


_PYRIGHT_REPORT_SCHEMA: TypeAdapter[_PyrightReport] = TypeAdapter(_PyrightReport)
_PYREFLY_REPORT_SCHEMA: TypeAdapter[_PyreflyReport] = TypeAdapter(_PyreflyReport)
_MYPY_REPORT_SCHEMA: TypeAdapter[list[_MypyDiagnostic]] = TypeAdapter(list[_MypyDiagnostic])
_TY_REPORT_SCHEMA: TypeAdapter[list[_TyDiagnostic]] = TypeAdapter(list[_TyDiagnostic])

#: Per-checker schema; unknown checkers keep the historic pyright fallback.
_REPORT_SCHEMAS: dict[str, TypeAdapter[Any]] = {
    "pyright": _PYRIGHT_REPORT_SCHEMA,
    "pyrefly": _PYREFLY_REPORT_SCHEMA,
    "mypy": _MYPY_REPORT_SCHEMA,
    "ty": _TY_REPORT_SCHEMA,
}

#: Maximum stdout characters embedded in a schema-failure message; the full
#: report may be up to 16 MiB (the BoundedOutputCapture limit).
_REPORT_EXCERPT_CHARS: int = 512


def _checker_label(checker: str | None) -> str:
    """Return the checker name for messages; unknown checkers ride pyright."""
    return checker or "unknown checker (pyright parser fallback)"


def _stdout_excerpt(stdout: str) -> str:
    """Return a bounded stdout excerpt for schema-failure messages."""
    if len(stdout) <= _REPORT_EXCERPT_CHARS:
        return stdout
    return stdout[:_REPORT_EXCERPT_CHARS] + "…[truncated]"


def _parse_report(checker: str | None, report: Any, stdout: str) -> list[TypeCheckingError]:
    """Validate the decoded report's structure, then parse it (M-127).

    Syntactically valid JSON with a foreign structure used to escape the
    documented error taxonomy as raw KeyError/TypeError/AttributeError
    (cli.py only catches MutmutWinError, so those surfaced as tracebacks).
    Every schema deviation becomes TypeCheckCommandError with the checker
    name and a bounded stdout excerpt; the original ValidationError stays
    chained as ``__cause__``.

    Raises:
        TypeCheckCommandError: If the report does not match the checker's
            expected structure (container forms and the keys the parser
            reads for severity-passing entries).
    """
    schema = _REPORT_SCHEMAS.get(checker or "", _PYRIGHT_REPORT_SCHEMA)
    try:
        schema.validate_python(report)
    except ValidationError as exc:
        first = exc.errors()[0]
        location = ".".join(str(part) for part in first["loc"]) or "<root>"
        raise TypeCheckCommandError(
            f"{_checker_label(checker)} returned a structurally unexpected report "
            f"at {location}: {first['msg']}. "
            f"stdout excerpt: {_stdout_excerpt(stdout)}"
        ) from exc
    if checker == "pyrefly":
        return parse_pyrefly_report(report)
    if checker == "mypy":
        return parse_mypy_report(report)
    if checker == "ty":
        return parse_ty_report(report)
    # Unknown checkers fall through to the pyright parser (historic default).
    return parse_pyright_report(report)


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
            ``Exception`` raises). mypy JSONL decoding ignores whitespace-only
            lines: a finding-free mypy run writes a single blank line. A
            syntactically valid but structurally unexpected report (M-127)
            is also rejected here — never as a raw KeyError/TypeError.
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

    report: Any = _decode_checker_report(
        checker, completed_process.stdout, completed_process.stderr
    )

    return _parse_report(checker, report, completed_process.stdout)


def parse_pyright_report(result: dict[str, Any]) -> list[TypeCheckingError]:
    """Parse a pyright JSON report into a list of TypeCheckingError instances.

    Only ``severity == "error"`` diagnostics count (A3-CM-011): pyright emits
    ``error | warning | information``, and warnings must not kill mutants.

    Raises:
        TypeCheckCommandError: If the result is not a JSON object, lacks
            ``generalDiagnostics``, or an entry is not a JSON object.
    """
    if not isinstance(result, dict):
        raise TypeCheckCommandError(
            f"Invalid pyright report: expected a JSON object, got {type(result).__name__}."
        )
    if "generalDiagnostics" not in result:
        raise TypeCheckCommandError(
            f'Invalid pyright report. Could not find key "generalDiagnostics". '
            f"Found: {set(result.keys())}"
        )
    for diagnostic in result["generalDiagnostics"]:
        if not isinstance(diagnostic, dict):
            raise TypeCheckCommandError(
                "Invalid pyright report: expected JSON objects in "
                f'"generalDiagnostics", got {type(diagnostic).__name__}.'
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
    """Parse a pyrefly JSON report into a list of TypeCheckingError instances.

    Raises:
        TypeCheckCommandError: If the result is not a JSON object, lacks
            ``errors``, or an entry is not a JSON object.
    """
    if not isinstance(result, dict):
        raise TypeCheckCommandError(
            f"Invalid pyrefly report: expected a JSON object, got {type(result).__name__}."
        )
    if "errors" not in result:
        raise TypeCheckCommandError(
            f'Invalid pyrefly report. Could not find key "errors". Found: {set(result.keys())}'
        )
    for error in result["errors"]:
        if not isinstance(error, dict):
            raise TypeCheckCommandError(
                f'Invalid pyrefly report: expected JSON objects in "errors", '
                f"got {type(error).__name__}."
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
    """Parse a mypy JSON report into a list of TypeCheckingError instances.

    Raises:
        TypeCheckCommandError: If the result is not a JSON array of JSON
            objects.
    """
    if not isinstance(result, list):
        raise TypeCheckCommandError(
            f"Invalid mypy report: expected a JSON array of diagnostics, "
            f"got {type(result).__name__}."
        )
    for diagnostic in result:
        if not isinstance(diagnostic, dict):
            raise TypeCheckCommandError(
                f"Invalid mypy report: expected JSON objects as diagnostics, "
                f"got {type(diagnostic).__name__}."
            )

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
    """Parse a 'ty' type checker report into a list of TypeCheckingError instances.

    Raises:
        TypeCheckCommandError: If the result is not a JSON array of JSON
            objects.
    """
    if not isinstance(result, list):
        raise TypeCheckCommandError(
            f"Invalid ty report: expected a JSON array of diagnostics, got {type(result).__name__}."
        )
    for diagnostic in result:
        if not isinstance(diagnostic, dict):
            raise TypeCheckCommandError(
                f"Invalid ty report: expected JSON objects as diagnostics, "
                f"got {type(diagnostic).__name__}."
            )

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
