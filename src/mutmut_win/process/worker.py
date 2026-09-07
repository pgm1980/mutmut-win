"""Worker entry point that runs in spawned child processes.

Each worker loops over a task_queue, runs pytest in a subprocess for each
MutationTask, and sends TaskStarted / TaskCompleted events back through
the event_queue.  A ``None`` sentinel value in the task_queue signals the
worker to exit cleanly.
"""

from __future__ import annotations

import contextlib
import json
import os
import secrets
import shlex
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from mutmut_win.atomic_file import atomic_write_bytes, ensure_atomic_bytes
from mutmut_win.constants import (
    EXIT_CODE_INFINITE_LOOP,
    EXIT_CODE_TIMEOUT,
    SOURCE_ROOT_NAMES,
    configured_staging_relative_path,
)

# Explicit re-export for BWC — single source of truth: constants (#110).
from mutmut_win.constants import MUTANT_ENV_VAR as MUTANT_ENV_VAR
from mutmut_win.exceptions import (
    BadTestExecutionCommandsException,
    ProcessContainmentError,
    PytestBoundaryError,
)
from mutmut_win.models import MutationTask, TaskCompleted, TaskStarted
from mutmut_win.process.output_capture import BoundedOutputCapture

if TYPE_CHECKING:
    import multiprocessing.queues
    from collections.abc import Callable

    from mutmut_win.pytest_boundary import PytestAllowedPathIdentity, PytestBoundary

#: Maximum number of pytest output lines to capture on timeout/suspicious.
_MAX_DIAGNOSTIC_LINES: int = 50

#: Exit codes whose outcome needs no diagnostic log tail: clean survive (0),
#: regular kill (1), no tests (5/33), skipped (34). Everything else —
#: collection errors (2), pytest internal errors (3), suspicious (35),
#: crashes (NTSTATUS) — gets its last output captured (issue #91).
_QUIET_EXIT_CODES: frozenset[int] = frozenset({0, 1, 5, 33, 34})

# Retain the concrete class even when unit tests patch subprocess.Popen.  The
# Windows fallback tracker must never inspect or kill a PID carried by a mock
# or third-party Popen-like object.
_REAL_POPEN_TYPE = subprocess.Popen
_CREATE_SUSPENDED = 0x00000004
_PYTEST_BOUNDARY_OPTIONS = frozenset(
    {
        "--config-file",
        "--confcutdir",
        "--inifilename",
        "--rootdir",
        "-c",
    }
)


def _contained_creationflags(base_flags: int = 0) -> int:
    """Suspend a real Windows child until its Job Object is assigned."""
    if sys.platform == "win32":
        return base_flags | _CREATE_SUSPENDED
    return base_flags


def _resume_suspended_process(proc: subprocess.Popen[bytes]) -> None:
    """Resume the single primary thread created by CREATE_SUSPENDED."""
    import ctypes
    from ctypes import wintypes

    import psutil  # type: ignore[import-untyped,unused-ignore]

    threads = psutil.Process(proc.pid).threads()
    if len(threads) != 1:
        raise OSError(f"suspended subprocess {proc.pid} has {len(threads)} primary threads")

    thread_suspend_resume = 0x0002
    kernel32 = ctypes.WinDLL(  # type: ignore[attr-defined,unused-ignore]
        "kernel32", use_last_error=True
    )
    kernel32.OpenThread.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenThread.restype = wintypes.HANDLE
    kernel32.ResumeThread.argtypes = [wintypes.HANDLE]
    kernel32.ResumeThread.restype = wintypes.DWORD
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL

    thread_handle = kernel32.OpenThread(thread_suspend_resume, False, threads[0].id)
    if not thread_handle:
        raise ctypes.WinError(  # type: ignore[attr-defined,unused-ignore]
            ctypes.get_last_error()  # type: ignore[attr-defined,unused-ignore]
        )
    try:
        previous_count = kernel32.ResumeThread(thread_handle)
        if previous_count == 0xFFFFFFFF:
            raise ctypes.WinError(  # type: ignore[attr-defined,unused-ignore]
                ctypes.get_last_error()  # type: ignore[attr-defined,unused-ignore]
            )
    finally:
        kernel32.CloseHandle(thread_handle)


def _resume_after_containment(proc: subprocess.Popen[bytes], job_handle: int | None) -> None:
    """Resume a Windows child only after reliable containment exists.

    A venv launcher can create and lose an intermediate Python process before
    post-Popen assignment.  Starting it suspended closes that race.  If the
    Job Object is unavailable, execution fails closed rather than knowingly
    permitting descendants to escape the workspace run.
    """
    if sys.platform != "win32" or not isinstance(proc, _REAL_POPEN_TYPE):
        return
    if job_handle is None:
        with contextlib.suppress(Exception):
            proc.kill()
            proc.wait(timeout=2.0)
        raise ProcessContainmentError(
            "Could not establish a Windows Job Object for a subprocess; "
            "refusing to run without reliable descendant cleanup."
        )
    try:
        _resume_suspended_process(proc)
    except BaseException as exc:
        # Closing the kill-on-close Job atomically terminates the still-
        # suspended child.  Callers clear their local handle before their own
        # cleanup path to avoid a double-close/handle-reuse race.
        with contextlib.suppress(Exception):
            from mutmut_win.process.job_object import close_job

            close_job(job_handle)
        raise ProcessContainmentError(
            "Could not resume a Windows subprocess after Job Object assignment; "
            "the contained child was terminated."
        ) from exc


# Every real pytest phase gets a unique proof token.  The generated plugin
# writes it only after pytest emits a call-phase report, so ``--collect-only``
# and other successful early-exit modes cannot masquerade as test execution.
PYTEST_PHASE_GUARD_PLUGIN: str = "_mutmut_phase_guard"
_PYTEST_PHASE_SENTINEL_PATH_ENV: str = "MUTMUT_PYTEST_PHASE_SENTINEL_PATH"
_PYTEST_PHASE_SENTINEL_PROOF_ENV: str = "MUTMUT_PYTEST_PHASE_SENTINEL_PROOF"
_PYTEST_ALLOWED_DIRS_ENV: str = "MUTMUT_PYTEST_ALLOWED_DIRS"
_PYTEST_ALLOWED_FILES_ENV: str = "MUTMUT_PYTEST_ALLOWED_FILES"
_PYTEST_RUNTIME_DIR_ENV: str = "MUTMUT_PYTEST_RUNTIME_DIR"
_PYTEST_PHASE_GUARD_SOURCE: str = '''\
"""Auto-generated mutmut-win pytest phase-execution guard."""

import json
import os
import stat
from pathlib import Path

import pytest

from mutmut_win.atomic_file import atomic_write_bytes

_PATH_ENV = "MUTMUT_PYTEST_PHASE_SENTINEL_PATH"
_PROOF_ENV = "MUTMUT_PYTEST_PHASE_SENTINEL_PROOF"
_ALLOWED_DIRS_ENV = "MUTMUT_PYTEST_ALLOWED_DIRS"
_ALLOWED_FILES_ENV = "MUTMUT_PYTEST_ALLOWED_FILES"
_RUNTIME_DIR_ENV = "MUTMUT_PYTEST_RUNTIME_DIR"


def _bound_identity(raw, expected_kind):
    """Revalidate one parent-frozen filesystem identity in this child."""
    if not isinstance(raw, dict) or set(raw) != {"path", "st_dev", "st_ino"}:
        raise TypeError("boundary identity must contain path, st_dev and st_ino")
    raw_path = raw["path"]
    expected_dev = raw["st_dev"]
    expected_ino = raw["st_ino"]
    if (
        not isinstance(raw_path, str)
        or type(expected_dev) is not int
        or type(expected_ino) is not int
        or expected_dev < 0
        or expected_ino <= 0
    ):
        raise TypeError("boundary identity fields are invalid")
    path = Path(raw_path)
    if not path.is_absolute():
        raise ValueError("boundary identity path must be absolute")
    leaf = path.lstat()
    resolved = path.resolve(strict=True)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    attributes = getattr(leaf, "st_file_attributes", 0)
    if stat.S_ISLNK(leaf.st_mode) or (reparse_flag and attributes & reparse_flag):
        raise ValueError(f"boundary identity became a link or reparse point: {path}")
    if os.path.normcase(str(path)) != os.path.normcase(str(resolved)):
        raise ValueError(f"boundary identity was redirected: {path}")
    if expected_kind == "directory" and not stat.S_ISDIR(leaf.st_mode):
        raise ValueError(f"boundary directory changed kind: {path}")
    if expected_kind == "file" and not stat.S_ISREG(leaf.st_mode):
        raise ValueError(f"boundary file changed kind: {path}")
    if expected_kind == "file" and leaf.st_nlink != 1:
        raise ValueError(f"boundary file became hard-linked: {path}")
    if (leaf.st_dev, leaf.st_ino) != (expected_dev, expected_ino):
        raise ValueError(f"boundary identity changed: {path}")
    return resolved


def _boundary_paths():
    """Decode and revalidate the parent-authenticated collection allow-list."""
    try:
        raw_dirs = json.loads(os.environ[_ALLOWED_DIRS_ENV])
        raw_files = json.loads(os.environ[_ALLOWED_FILES_ENV])
        if not isinstance(raw_dirs, list) or not raw_dirs or not isinstance(raw_files, list):
            raise TypeError("boundary identities must be non-empty/list records")
        directories = tuple(_bound_identity(value, "directory") for value in raw_dirs)
        files = tuple(_bound_identity(value, "file") for value in raw_files)
    except (KeyError, OSError, RuntimeError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise pytest.UsageError(
            f"mutmut-win pytest location boundary is missing or invalid: {exc}"
        ) from exc
    return directories, files


# ``-p _mutmut_phase_guard`` is loaded before initial conftest discovery.
# Authenticate the exact roots at module import so a replaced external
# conftest cannot execute before a later lifecycle hook notices the swap.
_BOUNDARY_PATHS_AT_IMPORT = _boundary_paths()


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config):
    """Reject stateful selection and externalise optional plugin storage."""
    stateful = [
        option
        for attribute, option in (
            ("lf", "--lf/--last-failed"),
            ("failedfirst", "--ff/--failed-first"),
            ("newfirst", "--nf/--new-first"),
            ("stepwise", "--sw/--stepwise"),
            ("stepwise_skip", "--sw-skip/--stepwise-skip"),
            ("cacheshow", "--cache-show"),
        )
        if bool(getattr(config.option, attribute, False))
    ]
    if stateful:
        raise pytest.UsageError(
            "mutmut-win forbids cache-driven pytest selection or ordering: "
            + ", ".join(stateful)
        )
    runtime_dir = Path(os.environ[_RUNTIME_DIR_ENV])
    if not runtime_dir.is_absolute() or not runtime_dir.is_dir():
        raise pytest.UsageError("mutmut-win pytest runtime directory is missing or invalid")

    # User-supplied pytest reporting/temp options are evaluated with the
    # executable staging tree as cwd.  Relative destinations would otherwise
    # create test-visible files after the frozen snapshot and make an ordinary
    # JUnit/coverage configuration fail as unexplained staging drift.  Keep
    # their semantics, but confine every known output to this invocation's
    # fresh external runtime directory.
    for attribute, leaf in (
        ("basetemp", "pytest-tmp"),
        ("xmlpath", "junit.xml"),
        ("log_file", "pytest.log"),
        ("htmlpath", "pytest.html"),
        ("json_report_file", "pytest-report.json"),
        ("report_log", "pytest-report.jsonl"),
        ("allure_report_dir", "allure-results"),
    ):
        if getattr(config.option, attribute, None):
            setattr(config.option, attribute, str(runtime_dir / leaf))

    cov_reports = getattr(config.option, "cov_report", None)
    if cov_reports:
        external_reports = {
            "annotate": runtime_dir / "coverage-annotate",
            "html": runtime_dir / "coverage-html",
            "json": runtime_dir / "coverage.json",
            "lcov": runtime_dir / "coverage.lcov",
            "markdown": runtime_dir / "coverage.md",
            "markdown-append": runtime_dir / "coverage-append.md",
            "xml": runtime_dir / "coverage.xml",
        }
        rewritten = []
        for report in cov_reports:
            report_name = str(report).split(":", 1)[0]
            destination = external_reports.get(report_name)
            rewritten.append(
                f"{report_name}:{destination}" if destination is not None else str(report)
            )
        config.option.cov_report = rewritten

    # pytest-benchmark constructs its storage even when no benchmark is
    # saved.  Its default ``./.benchmarks`` would mutate executable staging.
    # Assign only when that optional plugin registered the option; ordinary
    # pytest installations therefore see no unknown command-line option.
    if hasattr(config.option, "benchmark_storage"):
        # pytest-benchmark 5.x strips ``file://`` manually; a standards-based
        # ``file:///C:/...`` URI becomes ``/C:/...`` and is then treated as a
        # relative Windows path under executable staging.  Its supported raw
        # absolute-path form round-trips correctly through ``load_storage``.
        config.option.benchmark_storage = str(runtime_dir / "benchmarks")


def _inside(path, directories):
    for directory in directories:
        try:
            path.relative_to(directory)
        except ValueError:
            continue
        return True
    return False


@pytest.hookimpl(wrapper=True, tryfirst=True)
def pytest_load_initial_conftests(early_config):
    """Externalise early plugin outputs and install the conftest boundary."""
    # pytest-cov creates its controller in this same hook and snapshots
    # ``known_args_namespace`` before pytest_configure.  A try-first wrapper
    # runs before every non-wrapper implementation regardless of registration
    # order, covering both explicit argv and ``addopts`` from frozen config.
    runtime_value = os.environ.get(_RUNTIME_DIR_ENV)
    cov_reports = getattr(early_config.known_args_namespace, "cov_report", None)
    if runtime_value and cov_reports:
        runtime_dir = Path(runtime_value)
        external_reports = {
            "annotate": runtime_dir / "coverage-annotate",
            "html": runtime_dir / "coverage-html",
            "json": runtime_dir / "coverage.json",
            "lcov": runtime_dir / "coverage.lcov",
            "markdown": runtime_dir / "coverage.md",
            "markdown-append": runtime_dir / "coverage-append.md",
            "xml": runtime_dir / "coverage.xml",
        }
        rewritten = []
        for report in cov_reports:
            report_name = str(report).split(":", 1)[0]
            destination = external_reports.get(report_name)
            rewritten.append(
                f"{report_name}:{destination}" if destination is not None else str(report)
            )
        early_config.known_args_namespace.cov_report = rewritten

    pluginmanager = early_config.pluginmanager
    if getattr(pluginmanager, "_mutmut_boundary_loader_installed", False):
        yield
        return
    original_loader = pluginmanager._loadconftestmodules

    def boundary_loader(
        path,
        importmode,
        rootpath,
        *,
        consider_namespace_packages,
    ):
        directories, files = _boundary_paths()
        try:
            canonical = Path(path).resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise pytest.UsageError(
                f"mutmut-win could not validate conftest search anchor: {exc}"
            ) from exc

        containing_roots = [
            directory for directory in directories if _inside(canonical, (directory,))
        ]
        if containing_roots:
            # Pick the outermost explicitly authorized root. Temporarily using
            # it as confcutdir makes pytest's 8/9 upward walk include that root
            # and descendants, but never its ancestors or an unrelated tree.
            allowed_root = min(containing_roots, key=lambda value: len(value.parts))
            previous_confcutdir = pluginmanager._confcutdir
            pluginmanager._confcutdir = allowed_root
            try:
                return original_loader(
                    path,
                    importmode,
                    rootpath,
                    consider_namespace_packages=consider_namespace_packages,
                )
            finally:
                pluginmanager._confcutdir = previous_confcutdir

        if canonical in files or any(
            canonical in target.parents for target in (*directories, *files)
        ):
            # Exact files and routing collectors above an allowed external
            # target authorize no conftest code. Cache an empty chain before
            # pytest can walk those parent directories.
            directory = pluginmanager._get_directory(Path(path))
            pluginmanager._dirpath2confmods[directory] = []
            return None

        raise pytest.UsageError(
            "pytest attempted conftest discovery outside the frozen mutmut-win "
            f"execution basis: {canonical}"
        )

    pluginmanager._loadconftestmodules = boundary_loader
    pluginmanager._mutmut_boundary_loader_installed = True
    yield


@pytest.hookimpl(trylast=True)
def pytest_sessionstart(session):
    """Close the parent-to-child replacement window before collection."""
    _boundary_paths()


@pytest.hookimpl(trylast=True)
def pytest_collection_finish(session):
    """Reject tests/conftests outside staging or explicit basis-bound roots."""
    directories, files = _boundary_paths()
    violations = []
    for item in session.items:
        try:
            item_path = Path(item.path).resolve(strict=True)
        except (AttributeError, OSError, RuntimeError) as exc:
            raise pytest.UsageError(
                f"mutmut-win could not validate collected test location: {exc}"
            ) from exc
        if not _inside(item_path, directories) and item_path not in files:
            violations.append(f"test item {item.nodeid!r} at {item_path}")

    conftest_plugins = getattr(session.config.pluginmanager, "_conftest_plugins", ())
    for plugin in conftest_plugins:
        raw_path = getattr(plugin, "__file__", None)
        if not isinstance(raw_path, str):
            raise pytest.UsageError("mutmut-win could not identify a loaded conftest plugin")
        try:
            conftest_path = Path(raw_path).resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise pytest.UsageError(
                f"mutmut-win could not validate loaded conftest location: {exc}"
            ) from exc
        if not _inside(conftest_path, directories):
            violations.append(f"conftest at {conftest_path}")

    if violations:
        detail = "; ".join(violations[:10])
        if len(violations) > 10:
            detail += f"; and {len(violations) - 10} more"
        raise pytest.UsageError(
            "pytest collected or loaded files outside the frozen mutmut-win "
            f"execution basis: {detail}"
        )


def pytest_runtest_logreport(report):
    """Publish proof only after pytest executed a non-skipped test call."""
    if report.when != "call" or report.skipped:
        return
    marker_path = os.environ.get(_PATH_ENV)
    proof = os.environ.get(_PROOF_ENV)
    if marker_path and proof:
        atomic_write_bytes(Path(marker_path), proof.encode("utf-8"))
'''

# pytest accepts several informational/control options that exit successfully
# without executing test bodies.  Allowing one through the shared config would
# neutralise every mutation-testing phase while still looking green.  Selection
# options such as ``-k``, ``-m`` and test paths deliberately stay unrestricted.
_PYTEST_PHASE_NEUTRALIZERS: frozenset[str] = frozenset(
    {
        "--collect-only",
        "--co",
        "--fixtures",
        "--fixtures-per-test",
        "--funcargs",
        "--help",
        "--markers",
        "--setup-only",
        "--setup-plan",
        "--version",
        "-V",
        "-h",
    }
)

# Built-in cache-driven selection/order flags can make one mutant's outcome
# change which tests a later mutant executes.  Every pytest process also
# disables the cacheprovider plugin, closing the same ingress through staged
# pytest configuration rather than only through mutmut's explicit argv.
_PYTEST_STATEFUL_OPTIONS: frozenset[str] = frozenset(
    {
        "--cache-show",
        "--failed-first",
        "--ff",
        "--last-failed",
        "--last-failed-no-failures",
        "--lf",
        "--new-first",
        "--nf",
        "--stepwise",
        "--stepwise-skip",
        "--sw",
        "--sw-skip",
    }
)

_PYTEST_EXTERNAL_OUTPUT_OPTIONS: dict[str, str] = {
    "--alluredir": "allure-results",
    "--basetemp": "pytest-tmp",
    "--benchmark-storage": "benchmarks",
    "--html": "pytest.html",
    "--json-report-file": "pytest-report.json",
    "--junit-xml": "junit.xml",
    "--junitxml": "junit.xml",
    "--log-file": "pytest.log",
    "--report-log": "pytest-report.jsonl",
}
_PYTEST_FILE_COVERAGE_REPORTS: dict[str, str] = {
    "annotate": "coverage-annotate",
    "html": "coverage-html",
    "json": "coverage.json",
    "lcov": "coverage.lcov",
    "markdown": "coverage.md",
    "markdown-append": "coverage-append.md",
    "xml": "coverage.xml",
}


def redirect_pytest_output_args(cmd: list[str], runtime_dir: Path) -> list[str]:
    """Route known pytest report/temp outputs outside executable staging.

    This happens in the parent argv before pytest startup.  In particular,
    pytest-cov snapshots ``--cov-report`` during
    ``pytest_load_initial_conftests``; changing ``config.option`` later in the
    phase guard cannot prevent its default ``htmlcov/`` write.
    """

    external_root = runtime_dir.absolute()
    separator = cmd.index("--") if "--" in cmd else len(cmd)
    rewritten = list(cmd)

    def external_value(option: str, value: str) -> str:
        if option == "--cov-report":
            report_name = value.split(":", 1)[0]
            leaf = _PYTEST_FILE_COVERAGE_REPORTS.get(report_name)
            return f"{report_name}:{external_root / leaf}" if leaf is not None else value
        leaf = _PYTEST_EXTERNAL_OUTPUT_OPTIONS[option]
        destination = external_root / leaf
        return str(destination)

    index = 0
    while index < separator:
        token = rewritten[index]
        for option in (*_PYTEST_EXTERNAL_OUTPUT_OPTIONS, "--cov-report"):
            if token == option:
                if index + 1 < separator:
                    rewritten[index + 1] = external_value(option, rewritten[index + 1])
                    index += 1
                break
            prefix = f"{option}="
            if token.startswith(prefix):
                rewritten[index] = prefix + external_value(option, token[len(prefix) :])
                break
        index += 1
    # ``log_file`` is also a native pytest INI key, so it may be active even
    # when no output option appears in argv/addopts.  A final command-line INI
    # override is the only pre-start authority that covers both sources.
    rewritten[separator:separator] = [
        "-o",
        f"log_file={external_root / 'pytest.log'}",
    ]
    return rewritten


def validated_pytest_args(
    general_args: object,
    selection_args: object,
    *,
    stats_phase: bool = False,
    environment_addopts: str = "",
) -> list[str]:
    """Merge and validate user-configured pytest arguments.

    The function lives in the process layer so both the parent-side runner
    and spawned workers enforce exactly the same contract without introducing
    an upward import from ``process`` to ``runner``.

    Args:
        general_args: Serialized ``pytest_add_cli_args`` value.
        selection_args: Serialized ``pytest_add_cli_args_test_selection`` value.
        stats_phase: Reject pytest-xdist execution.  The generated stats plugin
            owns one process-local hit set and therefore cannot publish a
            trustworthy merged mapping from multiple xdist workers.

    Returns:
        A new list containing the two argument groups in configuration order.

    Raises:
        BadTestExecutionCommandsException: If the values are malformed, a
            phase-neutralising option is present, or xdist is requested for
            the stats phase.
    """

    try:
        args: list[str] = shlex.split(environment_addopts) if environment_addopts else []
    except ValueError as exc:
        raise BadTestExecutionCommandsException(
            [],
            detail=f"PYTEST_ADDOPTS could not be parsed: {exc}",
        ) from exc
    for field_name, raw_args in (
        ("pytest_add_cli_args", general_args),
        ("pytest_add_cli_args_test_selection", selection_args),
    ):
        if not isinstance(raw_args, list) or not all(isinstance(arg, str) for arg in raw_args):
            raise BadTestExecutionCommandsException(
                args,
                detail=f"{field_name} must be a list of strings.",
            )
        args.extend(raw_args)

    for arg in args:
        if arg == "--":
            raise BadTestExecutionCommandsException(
                args,
                detail=(
                    "-- is not allowed in mutmut-win pytest arguments: it can hide "
                    "the mandatory config/root boundary from pytest."
                ),
            )
        if arg.startswith("@"):
            raise BadTestExecutionCommandsException(
                args,
                detail=(
                    "user pytest @argfiles are not allowed: their unbound contents can "
                    "override the mandatory config/root boundary."
                ),
            )

        option_name = arg.partition("=")[0]
        if option_name in _PYTEST_BOUNDARY_OPTIONS or (
            arg.startswith("-c") and not arg.startswith("--")
        ):
            raise BadTestExecutionCommandsException(
                args,
                detail=(
                    f"{option_name} is owned by mutmut-win and cannot override the "
                    "staged pytest config/root boundary."
                ),
            )
        if option_name in _PYTEST_PHASE_NEUTRALIZERS:
            raise BadTestExecutionCommandsException(
                args,
                detail=(
                    f"{option_name} is not allowed in mutmut-win pytest arguments: "
                    "it can exit successfully without executing test bodies."
                ),
            )
        if option_name in _PYTEST_STATEFUL_OPTIONS:
            raise BadTestExecutionCommandsException(
                args,
                detail=(
                    f"{option_name} is not allowed in mutmut-win pytest arguments: "
                    "cache-driven selection or ordering can make one mutant alter the "
                    "test population of a later mutant."
                ),
            )

        if stats_phase and (
            option_name
            in {
                "--boxed",
                "--dist",
                "--looponfail",
                "--numprocesses",
                "--rsyncdir",
                "--tx",
                "-d",
                "-n",
            }
            or (arg.startswith("-n") and not arg.startswith("--") and len(arg) > 2)
        ):
            raise BadTestExecutionCommandsException(
                args,
                detail=(
                    "pytest-xdist is not supported during mutmut-win stats collection: "
                    "parallel workers cannot publish one authoritative hit map."
                ),
            )

    return args


def validated_pytest_targets(raw_targets: object, *, field_name: str) -> list[str]:
    """Validate argv values that are allowed to be pytest test targets only."""

    if not isinstance(raw_targets, list) or not all(
        isinstance(target, str) for target in raw_targets
    ):
        raise BadTestExecutionCommandsException(
            [],
            detail=f"{field_name} must be a list of strings.",
        )
    targets = list(raw_targets)
    for target in targets:
        if not target or target.isspace():
            raise BadTestExecutionCommandsException(
                targets,
                detail=f"{field_name} entries must not be empty.",
            )
        if target.startswith(("-", "@")) or target == "--":
            raise BadTestExecutionCommandsException(
                targets,
                detail=(
                    f"{field_name} accepts test paths/node IDs only; pytest options, "
                    "the -- separator, and user @argfiles are not allowed."
                ),
            )
        # argparse expands pytest argument files with str.splitlines(), which
        # also recognizes these ASCII and Unicode line boundaries beyond CR/LF.
        if any(character in target for character in "\0\r\n\v\f\x1c\x1d\x1e\x85\u2028\u2029"):
            raise BadTestExecutionCommandsException(
                targets,
                detail=(
                    f"{field_name} entries must not contain NUL or line breaks; "
                    "they could inject arguments into the internal pytest argfile."
                ),
            )
    return targets


def apply_pytest_boundary_environment(boundary: PytestBoundary, env: dict[str, str]) -> None:
    """Publish frozen test-location identities to the child guard plugin."""

    try:
        identities = boundary.canonical_allowed_test_identities()
    except PytestBoundaryError:
        raise
    except (AttributeError, OSError, RuntimeError, TypeError, ValueError) as exc:
        raise PytestBoundaryError("Could not validate pytest test-location boundary.") from exc

    directories = [identity for identity in identities if identity.kind == "directory"]
    files = [identity for identity in identities if identity.kind == "file"]

    def payload(identity: PytestAllowedPathIdentity) -> dict[str, object]:
        return {
            "path": str(identity.canonical_path),
            "st_dev": identity.st_dev,
            "st_ino": identity.st_ino,
        }

    env[_PYTEST_ALLOWED_DIRS_ENV] = json.dumps(
        [payload(identity) for identity in directories],
        separators=(",", ":"),
    )
    env[_PYTEST_ALLOWED_FILES_ENV] = json.dumps(
        [payload(identity) for identity in files],
        separators=(",", ":"),
    )


def _publish_pytest_guard(plugin_path: Path) -> None:
    """Publish the immutable guard, or fail as an execution-boundary error."""
    try:
        ensure_atomic_bytes(plugin_path, _PYTEST_PHASE_GUARD_SOURCE.encode("utf-8"))
    except OSError as exc:
        raise PytestBoundaryError(
            f"Could not publish the pytest execution guard at {plugin_path}: "
            f"{type(exc).__name__}: {exc}"
        ) from exc


def prepare_pytest_collection_guard(mutants_dir: Path = Path("mutants")) -> None:
    """Install the location guard for collection-only phases."""

    plugin_path = mutants_dir / f"{PYTEST_PHASE_GUARD_PLUGIN}.py"
    _publish_pytest_guard(plugin_path)


def configure_ephemeral_pytest_environment(env: dict[str, str], runtime_dir: Path) -> Path:
    """Redirect Python/pytest/Hypothesis state to one fresh process directory.

    ``PYTHONDONTWRITEBYTECODE`` alone does not stop CPython from consuming an
    existing ``UNCHECKED_HASH`` pyc.  A unique ``PYTHONPYCACHEPREFIX`` changes
    the normal import lookup as well as the write target.  The directory must
    never be shared across phases: explicit ``py_compile`` can still populate
    it despite the no-write flag.

    Returns:
        The isolated pytest cache directory to use in ``-o cache_dir=...``.
    """

    runtime_dir = runtime_dir.absolute()
    cache_dir = runtime_dir / "pytest-cache"
    pycache_dir = runtime_dir / "python-cache"
    hypothesis_dir = runtime_dir / "hypothesis"
    for directory in (cache_dir, pycache_dir, hypothesis_dir):
        directory.mkdir(parents=True, exist_ok=False)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPYCACHEPREFIX"] = str(pycache_dir)
    env["HYPOTHESIS_STORAGE_DIRECTORY"] = str(hypothesis_dir)
    env["COVERAGE_FILE"] = str(runtime_dir / ".coverage")
    env[_PYTEST_RUNTIME_DIR_ENV] = str(runtime_dir)
    return cache_dir


def prepare_pytest_phase_guard(
    env: dict[str, str],
    mutants_dir: Path = Path("mutants"),
    *,
    runtime_dir: Path | None = None,
) -> tuple[Path, str]:
    """Install the guard plugin and add one unique proof target to *env*.

    Byte-identical concurrent publishers share an idempotent atomic
    publication. A different or unverifiable competing leaf is a fatal pytest
    execution-boundary failure, never a mutant verdict.

    Args:
        env: Child-process environment to augment.
        mutants_dir: Staging directory from which pytest loads the plugin.
        runtime_dir: Fresh parent-owned directory for the execution proof.
            Production callers always provide one outside executable staging;
            the legacy default is retained for direct helper callers.

    Returns:
        ``(marker_path, expected_token)`` for post-process verification.
    """
    plugin_path = mutants_dir / f"{PYTEST_PHASE_GUARD_PLUGIN}.py"
    _publish_pytest_guard(plugin_path)

    # Do not create and reopen a workspace marker through tempfile: an
    # existing redirected staging parent would already have received that
    # write. The generated plugin publishes this unpredictable leaf with the
    # same safe atomic writer only after a real pytest call-phase report exists.
    marker_root = mutants_dir if runtime_dir is None else runtime_dir
    marker_path = (
        marker_root / f".mutmut_pytest_executed_{secrets.token_hex(16)}.sentinel"
    ).absolute()
    token = secrets.token_hex(32)
    env[_PYTEST_PHASE_SENTINEL_PATH_ENV] = str(marker_path)
    env[_PYTEST_PHASE_SENTINEL_PROOF_ENV] = token
    return marker_path, token


def consume_pytest_phase_guard(marker_path: Path, expected_token: str) -> bool:
    """Return whether a matching execution proof exists, then remove it."""
    try:
        return marker_path.read_text(encoding="utf-8") == expected_token
    except OSError:
        return False
    finally:
        with contextlib.suppress(OSError):
            marker_path.unlink()


def _write_pytest_argfile(tests: list[str], output_dir: Path = Path("mutants")) -> Path:
    """Publish one private pytest argument file in a caller-owned directory."""
    tests = validated_pytest_targets(tests, field_name="pytest argument file targets")
    argfile = output_dir / f"mutmut_tests_{secrets.token_hex(16)}.txt"
    payload = "".join(f"{test}\n" for test in tests).encode("utf-8")
    atomic_write_bytes(argfile, payload)
    return argfile


def _suppress_windows_error_dialogs() -> None:
    """Keep WerFault from holding crashing pytest children (issue #123).

    External QA WIN-001 (code-evidenced): on interactive Windows hosts with
    WER UI enabled, a hard-crashing mutant (access violation, stack
    overflow) can stall on the Windows Error Reporting dialog past the
    task's wall-clock budget — the job object then reaps the tree and the
    mutant is misclassified ``timeout`` instead of ``segfault``.
    ``SetErrorMode`` is inherited by child processes, so crashes return
    immediately as NTSTATUS exit codes. POSIX: no-op.
    """
    if sys.platform != "win32":
        return
    import ctypes

    sem_failcriticalerrors = 0x0001
    sem_nogpfaulterrorbox = 0x0002
    with contextlib.suppress(Exception):  # never let dialog hygiene kill a worker
        kernel32 = ctypes.windll.kernel32
        current = kernel32.GetErrorMode()
        kernel32.SetErrorMode(current | sem_failcriticalerrors | sem_nogpfaulterrorbox)


def worker_main(
    task_queue: multiprocessing.queues.Queue[dict[str, object] | None],
    event_queue: multiprocessing.queues.Queue[dict[str, object]],
    config_data: dict[str, object],
    containment_queue: Any = None,
) -> None:
    """Main loop executed in each spawned worker process.

    Pulls ``MutationTask`` objects from *task_queue*, runs pytest in a
    subprocess for the mutant under test, and sends domain events back via
    *event_queue*.  Exits when it receives the ``None`` sentinel.

    Args:
        task_queue: Queue from which ``MutationTask`` dicts (or ``None``) are
            consumed.  Items are serialised dicts to guarantee pickle safety.
        event_queue: Queue into which ``TaskStarted`` and ``TaskCompleted``
            events are placed.
        config_data: Serialised ``MutmutConfig`` as a plain ``dict``.  Using a
            dict instead of the Pydantic model avoids any potential pickle
            incompatibility across process boundaries.
    """
    pid = os.getpid()
    # Once per worker process — children inherit the error mode (issue #123
    # / external QA WIN-001).
    _suppress_windows_error_dialogs()
    pytest_extra_args = validated_pytest_args(
        config_data.get("pytest_add_cli_args", []),
        config_data.get("pytest_add_cli_args_test_selection", []),
        environment_addopts=os.environ.get("PYTEST_ADDOPTS", ""),
    )
    pytest_targets = validated_pytest_targets(
        config_data.get("tests_dir", []),
        field_name="tests_dir",
    )
    from mutmut_win.pytest_boundary import PytestBoundary

    raw_boundary = config_data.get("_pytest_boundary")
    if raw_boundary is None:
        raise PytestBoundaryError(
            "Worker start refused: the parent supplied no frozen pytest boundary."
        )
    pytest_boundary = PytestBoundary.from_dict(raw_boundary)
    pytest_boundary.arguments()

    while True:
        raw_item = task_queue.get()
        if raw_item is None:
            # Sentinel: no more tasks — exit cleanly.
            break
        # Best-effort extract mutant_name from the raw dict so we can still
        # report something useful if validation itself blows up.
        fallback_name = "unknown"
        if isinstance(raw_item, dict):
            raw_name = raw_item.get("mutant_name")
            if isinstance(raw_name, str) and raw_name:
                fallback_name = raw_name

        try:
            _process_task(
                raw_item,
                event_queue,
                pid,
                pytest_extra_args,
                config_data,
                pytest_boundary,
                pytest_targets,
                containment_queue,
            )
        except Exception as exc:  # Bug #12 recovery: keep the worker alive
            # Any uncaught exception (Pydantic ValidationError, RuntimeError from
            # the subprocess layer, libcst hiccup, transient FS error, …) would
            # otherwise kill the worker mid-task. The orchestrator would then
            # hang in get_events() waiting for a TaskCompleted that will never
            # arrive. Emit a synthetic completion so progress can be made, and
            # continue the loop.
            # stderr: workers inherit OS fd 1 — the parent's --output json
            # redirect can never catch child prints (issue #127 / 360°-A6).
            print(
                f"WORKER RECOVERY (#12): uncaught {type(exc).__name__} on {fallback_name}: {exc}",
                file=sys.stderr,
                flush=True,
            )
            fatal = isinstance(exc, (ProcessContainmentError, PytestBoundaryError))
            event_queue.put(
                TaskCompleted(
                    mutant_name=fallback_name,
                    worker_pid=pid,
                    exit_code=35,  # suspicious
                    duration=0.0,
                    last_output=f"Worker recovery (Bug #12): {type(exc).__name__}: {exc}",
                    fatal=fatal,
                ).model_dump()
            )
            if fatal:
                # Continuing would turn a host-wide containment/boundary
                # failure into one suspicious row per mutant. The executor
                # treats this terminal event as a run-aborting failure.
                break


def _process_task(
    raw_item: dict[str, object],
    event_queue: multiprocessing.queues.Queue[dict[str, object]],
    pid: int,
    pytest_extra_args: list[str],
    config_data: dict[str, object],
    pytest_boundary: PytestBoundary,
    pytest_targets: list[str],
    containment_queue: Any = None,
) -> None:
    """Process a single mutation task.

    Extracted from the main loop so ``worker_main`` can catch any exception
    that bubbles up from here and synthesise a recovery event (Bug #12).
    """
    task = MutationTask.model_validate(raw_item)
    # Per-task budget computed by the orchestrator (estimated runtime of the
    # assigned tests times timeout_multiplier, floor 5 s).  Before issue #81 /
    # A2-JT-003 the worker ignored it and used max(60, timeout_multiplier) —
    # the MULTIPLIER acted as flat absolute seconds for every task.
    timeout_seconds = task.timeout_seconds
    # The deadline starts before any per-task filesystem/process setup.  The
    # executor separately bounds a worker that wedges before TaskStarted; once
    # setup succeeds, only the remaining task budget is passed to wait().
    start = time.monotonic()
    deadline = start + timeout_seconds
    runtime_context = tempfile.TemporaryDirectory(
        prefix="mutmut-win-worker-runtime-",
        ignore_cleanup_errors=True,
    )
    runtime_dir = Path(runtime_context.name)

    # Build the pytest command.
    cmd: list[str] = _pytest_base_cmd()
    cmd.extend(pytest_extra_args)
    # Revalidate immediately before every task. A config/root/target identity
    # that drifted after worker startup aborts the entire run.
    cmd.extend(pytest_boundary.arguments())

    # Always use pytest's @file syntax for test arguments.
    # This avoids the Windows CreateProcess 32767-char command line limit
    # (WinError 206) regardless of how many tests are assigned — no magic
    # thresholds, no dual code paths, predictable behavior at any scale.
    # pytest reads arguments from the file, one per line.
    # Requires pytest >= 8.2 (issue #125 / 360°-A2): enforced by the
    # dependency floor AND the orchestrator's run-start guard against
    # constants.MINIMUM_PYTEST_VERSION — never silently degraded here.
    tests_argfile: Path | None = None
    selected_targets: list[str] = []
    if task.tests and task.test_selection_is_authoritative:
        selected_targets = validated_pytest_targets(
            task.tests,
            field_name="MutationTask.tests",
        )
    elif pytest_targets:
        # A non-authoritative mapping is only a scheduling hint. Preserve the
        # complete configured target vector, in its original order, while
        # keeping it out of Windows' 32,767-character command-line limit.
        selected_targets = pytest_targets
    if selected_targets:
        tests_argfile = _write_pytest_argfile(selected_targets, runtime_dir)
        cmd.append("--")
        cmd.append(f"@{tests_argfile.absolute()}")

    # Activate the specific mutant via the trampoline env var.
    # Set PYTHONPATH so subprocess can import from mutants/src etc.
    env = os.environ.copy()
    # The value has already been parsed and validated into ``cmd``. Removing
    # it prevents pytest from prepending it a second time ahead of the internal
    # config/root boundary (including a hostile ``--`` separator).
    env.pop("PYTEST_ADDOPTS", None)
    # Keep mutation subprocesses inside the same explicit staging universe as
    # clean/stats phases.  Live inherited PYTHONPATH entries are not evidence-
    # bound staging inputs; users must mirror them through extra_paths.
    env.pop("PYTHONPATH", None)
    apply_pytest_boundary_environment(pytest_boundary, env)
    pythonpath_dirs: list[str] = []
    for subdir in [*SOURCE_ROOT_NAMES, "."]:
        candidate = Path("mutants") / subdir
        if candidate.exists():
            pythonpath_dirs.append(str(candidate.absolute()))
    # Bug #69: extra_paths from config map to mutants/<extra_path> and must be
    # on PYTHONPATH so sibling-package imports resolve inside the mutants venv.
    raw_extra_paths = config_data.get("extra_paths", [])
    if isinstance(raw_extra_paths, list):
        for extra in raw_extra_paths:
            extra_as_path = configured_staging_relative_path(
                str(extra),
                project_root=Path.cwd(),
            )
            if extra_as_path is None:
                continue
            extra_path = Path("mutants") / extra_as_path
            if extra_path.exists():
                pythonpath_dirs.append(str(extra_path.absolute()))
    if pythonpath_dirs:
        env["PYTHONPATH"] = os.pathsep.join(pythonpath_dirs)
    env[MUTANT_ENV_VAR] = task.mutant_name
    # Unbuffered stdout/stderr for the whole subprocess tree: with block
    # buffering the capture byte counter froze while the suite made progress,
    # blinding the IL classifier's output signal (issue #88 / A2-JT-002).
    env["PYTHONUNBUFFERED"] = "1"
    # Same env truth as every runner phase (issue #111 / A2-RN-012): the
    # copied test modules in mutants/ keep their original basenames, and
    # pytest's import-mismatch check would reject them via stale __pycache__.
    env["PY_IGNORE_IMPORTMISMATCH"] = "1"
    cache_dir = configure_ephemeral_pytest_environment(env, runtime_dir)
    cmd = redirect_pytest_output_args(cmd, runtime_dir)
    phase_marker_path, phase_marker_token = prepare_pytest_phase_guard(
        env,
        runtime_dir=runtime_dir,
    )
    separator = cmd.index("--") if "--" in cmd else len(cmd)
    # Mutation testing needs only the first failing test. Keep pytest's native
    # order: reordering diagnostic mapping hits would change the semantics of
    # order-dependent suites and could create false survivors or false kills.
    # When no failure occurs, the entire configured suite still runs.
    cmd[separator:separator] = ["--maxfail=1", "-o", f"cache_dir={cache_dir}"]

    # A continuously drained pipe avoids PIPE-buffer deadlock while retaining
    # only a bounded tail. The monotonic byte counter remains an honest output
    # progress signal without allowing a print loop to exhaust the disk.
    capture = BoundedOutputCapture()
    last_output: str | None = None
    forensics_dict: dict[str, object] | None = None
    exit_code: int = 35  # default to suspicious so the finally clause is safe

    # ---- IL-detection setup (Issue #71, Sprint 26) ---------------------
    il_enabled = bool(config_data.get("infinite_loop_detection", True))
    il_thresholds = _build_il_thresholds(config_data)
    # IL-001: clamp the sampling window to THIS task's budget before the monitor
    # starts and before the classifier reads thresholds.window_seconds — the
    # default 10s window otherwise spans a fast suite's whole timeout and keeps
    # CPU-priming samples in the snapshot, mis-scoring real loops as 'timeout'.
    il_thresholds = _scale_il_window(il_thresholds, timeout_seconds)
    monitor: Any = None  # ProcessMonitor or None — Any avoids loop_monitor import
    # The window-vs-timeout configuration hint (A2-JT-018) is emitted by the
    # orchestrator, once per RUN — a per-worker guard meant N-fold spam on
    # N worker processes (issue #110 / DOG-002).

    proc: subprocess.Popen[bytes] | None = None
    task_job_handle: int | None = None
    tree_cleanup_done = False
    try:
        # Popen + wait(timeout) so we can attach the monitor against a live PID
        # and run our classifier on timeout. (subprocess.run cannot expose the
        # PID until after the call returns.)
        posix_register: Callable[[int], None] | None = None
        if sys.platform != "win32" and containment_queue is not None:

            def publish_process_group(process_group: int) -> None:
                containment_queue.put(
                    {
                        "mutant_name": task.mutant_name,
                        "worker_pid": pid,
                        "process_group": process_group,
                    }
                )

            posix_register = publish_process_group

        proc, task_job_handle = _popen_contained(
            cmd,
            posix_start_stopped=containment_queue is not None,
            posix_register=posix_register,
            env=env,
            stdout=capture.writer_fd,
            stderr=subprocess.STDOUT,
            cwd="mutants",
            # No console window for the pytest child (issue #123 / WIN-001);
            # 0 on POSIX where the attribute does not exist.
            creationflags=_contained_creationflags(getattr(subprocess, "CREATE_NO_WINDOW", 0)),
            start_new_session=sys.platform != "win32",
        )
        capture.close_writer()
        # Windows membership is an atomic CreateProcess attribute.  POSIX
        # registration and pre-exec gate release completed inside
        # _popen_contained before it returned.
        monitor = _maybe_start_loop_monitor(
            il_enabled,
            proc.pid,
            None,
            window_seconds=il_thresholds.window_seconds,
            output_counter=lambda: capture.total_bytes,
        )
        # A task is in flight only after its pytest process and containment
        # boundary exist.  Before this point the pool startup watchdog remains
        # armed, so mkstemp/Popen/job-setup hangs cannot disable it forever.
        event_queue.put(TaskStarted(mutant_name=task.mutant_name, worker_pid=pid).model_dump())
        try:
            remaining_seconds = max(0.001, deadline - time.monotonic())
            exit_code = proc.wait(timeout=remaining_seconds)
        except subprocess.TimeoutExpired:
            # Kill the still-running subprocess tree before sampling so the
            # classifier sees the final state of the rolling window.
            _kill_proc_tree(proc, task_job_handle)
            task_job_handle = None  # consumed (closed) by the kill
            tree_cleanup_done = True
            # Snapshot BEFORE the log read (A2-JT-014): the snapshot is a pure
            # deque copy, while the tail read can take long enough to matter.
            samples = monitor.take_samples_snapshot() if monitor is not None else []
            capture.close()
            last_output = capture.last_lines(_MAX_DIAGNOSTIC_LINES)
            if monitor is not None:
                classification = _classify_with_monitor(
                    samples,
                    il_thresholds,
                    last_output,
                    status_signal_available=sys.platform != "win32",
                    sampler_errors=monitor.sampler_errors,
                )
                if classification.verdict == "killed_by_infinite_loop":
                    exit_code = EXIT_CODE_INFINITE_LOOP
                    forensics_dict = classification.forensics.model_dump()
                    forensics_dict["confidence"] = classification.confidence
                else:
                    exit_code = EXIT_CODE_TIMEOUT
                    # Persist forensics even on plain timeout so the user can see
                    # why the classifier said "not IL".
                    forensics_dict = classification.forensics.model_dump()
                    forensics_dict["confidence"] = classification.confidence
            else:
                exit_code = EXIT_CODE_TIMEOUT  # no detection available
    except OSError as exc:
        print(f"WORKER ERROR for {task.mutant_name}: {exc}", file=sys.stderr, flush=True)
        exit_code = 35  # suspicious
    finally:
        phase_executed = consume_pytest_phase_guard(phase_marker_path, phase_marker_token)
        if exit_code == 0 and not phase_executed:
            exit_code = 35
            last_output = (
                "pytest exited 0 without executing a test call; the worker phase was "
                "neutralized by pytest arguments/configuration or every selected test was skipped"
            )
        if task_job_handle is not None:
            # Normal completion: closing the kill-on-close job reaps any
            # background processes the tests left behind (issue #82).
            with contextlib.suppress(Exception):
                from mutmut_win.process.job_object import close_job

                close_job(task_job_handle)
            tree_cleanup_done = True
        elif proc is not None and not tree_cleanup_done:
            # POSIX has no Job Object. Successful tests may still leave
            # background descendants, so normal completion needs the same
            # explicit process-group/PPID cleanup as timeout paths. A mocked
            # Windows Popen can also reach this branch in unit tests.
            _kill_proc_tree(proc)
            tree_cleanup_done = True
        if monitor is not None:
            with contextlib.suppress(Exception):
                monitor.shutdown()
        capture.close_writer()
        capture.close()
        # Read diagnostics for every anomalous exit (if not already read by
        # the timeout path). Issue #91: exit 2 is a collection-error kill and
        # NTSTATUS codes are crashes — their forensics ARE the pytest output;
        # only the quiet outcomes (survived/killed/no-tests/skipped) carry no
        # diagnostic value.
        if exit_code not in _QUIET_EXIT_CODES and last_output is None:
            last_output = capture.last_lines(_MAX_DIAGNOSTIC_LINES)
        if tests_argfile is not None and tests_argfile.exists():
            with contextlib.suppress(OSError):
                tests_argfile.unlink()
        runtime_context.cleanup()

    duration = time.monotonic() - start

    event_queue.put(
        TaskCompleted(
            mutant_name=task.mutant_name,
            worker_pid=pid,
            exit_code=exit_code,
            duration=duration,
            last_output=last_output,
            forensics=forensics_dict,
        ).model_dump()
    )


#: Tail block size for diagnostic log reads — generously covers
#: ``_MAX_DIAGNOSTIC_LINES`` even with very long lines.
_TAIL_READ_BYTES: int = 64 * 1024


def _read_last_lines(path: Path, n: int) -> str | None:
    """Tail-read the last *n* lines from *path*, returning None on failure.

    Reads only the final block of the file (issue #81 / A2-EW-014):
    ``read_text`` loaded output-runaway mutant logs fully into memory,
    risking MemoryError right inside the diagnostic path.
    """
    try:
        with path.open("rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            block = min(size, _TAIL_READ_BYTES)
            f.seek(size - block)
            data = f.read(block)
    except OSError:
        return None
    lines = data.decode("utf-8", errors="replace").splitlines()
    return "\n".join(lines[-n:]) if lines else None


# ---------------------------------------------------------------------------
# IL-detection helpers (Issue #71, Sprint 26)
# ---------------------------------------------------------------------------


def _maybe_start_loop_monitor(
    enabled: bool,
    pid: int,
    log_path: Path | None = None,
    window_seconds: float = 10.0,
    *,
    output_counter: Any = None,
) -> Any:
    """Try to spawn an IL-detection monitor; return ``None`` on opt-out / failure.

    Failures here MUST NEVER take down the worker — IL detection is best-effort
    enhancement. psutil missing, permission denied on the PID, or any other
    error degrades gracefully to "no detection, plain timeout".

    *window_seconds* carries the configured ``infinite_loop_window_seconds``
    through to the sampler — previously the monitor was hard-wired to its
    10 s default while the forensics claimed the configured value
    (issue #81 / A2-EW-009).
    """
    if not enabled:
        return None
    try:
        from mutmut_win.process.loop_monitor import ProcessMonitor, has_psutil

        if not has_psutil():
            return None
        monitor = ProcessMonitor(
            pid=pid,
            log_path=log_path,
            window_seconds=window_seconds,
            output_counter=output_counter,
        )
        monitor.start()
    except Exception as exc:  # graceful degradation: never poison the run
        print(f"WORKER MONITOR start failed: {exc}", file=sys.stderr, flush=True)
        return None
    return monitor


def _build_il_thresholds(config_data: dict[str, object]) -> Any:
    """Build an :class:`IlThresholds` from the worker's config dict.

    Lazy-imported so that workers can avoid the loop_monitor module entirely
    when IL detection is disabled (one less code path loaded under the GIL).
    """
    from mutmut_win.process.loop_monitor import IlThresholds

    def _coerce_float(key: str, default: float) -> float:
        v = config_data.get(key, default)
        try:
            return float(v) if isinstance(v, (int, float)) else default
        except (
            TypeError,
            ValueError,
        ):
            return default

    def _coerce_int(key: str, default: int) -> int:
        v = config_data.get(key, default)
        try:
            return int(v) if isinstance(v, (int, float)) else default
        except (
            TypeError,
            ValueError,
        ):
            return default

    return IlThresholds(
        cpu_threshold=_coerce_float("infinite_loop_cpu_threshold", 70.0),
        output_threshold=_coerce_int("infinite_loop_output_threshold", 1024),
        running_ratio=_coerce_float("infinite_loop_running_ratio", 0.8),
        window_seconds=_coerce_float("infinite_loop_window_seconds", 10.0),
    )


def _scale_il_window(thresholds: Any, timeout_seconds: float) -> Any:
    """Return *thresholds* with its IL window clamped to this task's budget.

    IL-001: a window wider than the task's wall-clock budget (the shipped 10 s
    default on a fast suite with a small timeout) keeps CPU-priming samples in
    the classifier snapshot and dilutes the mean, so a genuine infinite loop is
    scored ``timeout`` instead of ``killed_by_infinite_loop``. A no-op on slow
    suites whose timeout is large. See
    :func:`mutmut_win.process.loop_monitor.effective_window_seconds`.
    """
    from mutmut_win.process.loop_monitor import effective_window_seconds

    scaled = effective_window_seconds(thresholds.window_seconds, timeout_seconds)
    return thresholds.model_copy(update={"window_seconds": scaled})


def _classify_with_monitor(
    samples: Any,
    thresholds: Any,
    last_output: str | None,
    *,
    status_signal_available: bool = True,
    sampler_errors: int = 0,
) -> Any:
    """Lazy-import classifier indirection — keeps loop_monitor optional in tests."""
    from mutmut_win.process.loop_monitor import classify_samples

    return classify_samples(  # type: ignore[arg-type,unused-ignore]
        samples,
        thresholds,
        last_output_tail=last_output,
        status_signal_available=status_signal_available,
        sampler_errors=sampler_errors,
    )


def _pytest_base_cmd() -> list[str]:
    """Pytest invocation pinned to the running interpreter (issue #82 / A4-QX-008).

    Bare ``"pytest"`` resolved via PATH could hit a different interpreter
    than the venv the clean gate validated (a non-activated venv produced
    exit-35 floods despite a green clean run); ``sys.executable -m pytest``
    matches what the runner phases use.
    """
    return [
        sys.executable,
        "-m",
        "pytest",
        "-p",
        PYTEST_PHASE_GUARD_PLUGIN,
        "--tb=no",
        "-q",
    ]


def _create_task_job(pid: int | None = None) -> int | None:
    """Create a per-task Windows Job (issue #82 / A2-EW-008).

    Production creates the child atomically in this Job.  The optional *pid*
    retains the old assign-before-resume path only for Popen test doubles;
    real processes never cross that non-atomic boundary.
    """
    if sys.platform != "win32":
        return None
    try:
        from mutmut_win.process.job_object import (
            assign_process_to_job,
            close_job,
            create_kill_on_close_job,
        )

        handle = create_kill_on_close_job()
    except (
        OSError,
        RuntimeError,
    ):
        return None
    if pid is not None:
        try:
            assign_process_to_job(handle, pid)
        except (
            OSError,
            RuntimeError,
        ):
            with contextlib.suppress(Exception):
                close_job(handle)
            return None
    return handle


def _popen_contained(
    cmd: list[str],
    *,
    posix_start_stopped: bool = False,
    posix_register: Callable[[int], None] | None = None,
    **kwargs: Any,
) -> tuple[subprocess.Popen[bytes], int | None]:
    """Start one subprocess with a parent-owned containment boundary.

    Windows passes the Job through ``PROC_THREAD_ATTRIBUTE_JOB_LIST`` so
    membership and process creation are one kernel operation. Unit tests that
    replace ``subprocess.Popen`` retain the old suspended handshake; no real
    production child uses that compatibility branch.
    """
    if sys.platform != "win32":
        launch_cmd = cmd
        gate_read: int | None = None
        gate_write: int | None = None
        if posix_start_stopped:
            if os.name != "posix":
                raise ProcessContainmentError("POSIX stopped launch requested off POSIX")
            if posix_register is None:
                raise ProcessContainmentError(
                    "POSIX gated launch requires synchronous process-group registration"
                )
            if kwargs.get("start_new_session") is not True:
                raise ProcessContainmentError(
                    "POSIX gated launch requires a dedicated process session"
                )
            # The shell cannot exec user code until it reads one release byte.
            # Only the worker owns the write end.  If the worker hard-exits at
            # any point before or during synchronous registration, EOF makes
            # the gate terminate itself instead of leaving an unregistered,
            # stopped orphan behind.
            gate_read, gate_write = os.pipe()
            inherited_fds = tuple(int(fd) for fd in kwargs.pop("pass_fds", ()))
            kwargs["pass_fds"] = (*inherited_fds, gate_read)
            launch_cmd = [
                "/bin/sh",
                "-c",
                (
                    '_mutmut_gate_fd="$1"; shift; '
                    'if IFS= read -r _mutmut_gate <&"$_mutmut_gate_fd"; '
                    'then exec "$@"; else exit 70; fi'
                ),
                "mutmut-posix-gate",
                str(gate_read),
                *cmd,
            ]
        proc: subprocess.Popen[bytes] | None = None
        try:
            proc = subprocess.Popen(launch_cmd, **kwargs)  # noqa: S603
            _close_posix_gate_fd(gate_read)
            gate_read = None
            if posix_start_stopped:
                if posix_register is None:  # defensive: checked before launch
                    raise ProcessContainmentError("POSIX launch registration callback vanished")
                posix_register(proc.pid)
                if gate_write is None:
                    raise ProcessContainmentError("POSIX launch gate lost its release handle")
                os.write(gate_write, b"\n")
            return proc, None
        except BaseException as exc:
            if proc is not None:
                _abort_posix_gated_process(proc)
            if posix_start_stopped and not isinstance(exc, ProcessContainmentError):
                raise ProcessContainmentError(
                    "Could not register and release the POSIX task process group."
                ) from exc
            raise
        finally:
            _close_posix_gate_fd(gate_read)
            _close_posix_gate_fd(gate_write)

    if subprocess.Popen is not _REAL_POPEN_TYPE:
        proc = subprocess.Popen(cmd, **kwargs)  # noqa: S603
        job_handle = _create_task_job(proc.pid)
        try:
            _resume_after_containment(proc, job_handle)
        except BaseException:
            job_handle = None
            raise
        return proc, job_handle

    job_handle = _create_task_job()
    if job_handle is None:
        raise ProcessContainmentError(
            "Could not establish a Windows Job Object for a subprocess; "
            "refusing to run without reliable descendant cleanup."
        )
    kwargs["creationflags"] = int(kwargs.get("creationflags", 0)) & ~_CREATE_SUSPENDED
    try:
        from mutmut_win.process.atomic_spawn import AtomicJobPopen

        proc = AtomicJobPopen(cmd, job_handle=job_handle, **kwargs)
    except BaseException as exc:
        with contextlib.suppress(Exception):
            from mutmut_win.process.job_object import close_job

            close_job(job_handle)
        if isinstance(exc, ProcessContainmentError):
            raise
        raise ProcessContainmentError(
            "Could not create a subprocess atomically inside its Windows Job Object."
        ) from exc
    return proc, job_handle


def _close_posix_gate_fd(fd: int | None) -> None:
    if fd is not None:
        with contextlib.suppress(OSError):
            os.close(fd)


def _abort_posix_gated_process(proc: subprocess.Popen[bytes]) -> None:
    """Kill a failed gate session and bound direct-child reap time."""
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.killpg(  # type: ignore[attr-defined,unused-ignore]
            proc.pid,
            signal.SIGKILL,  # type: ignore[attr-defined,unused-ignore]
        )
    with contextlib.suppress(OSError):
        proc.kill()
    with contextlib.suppress(OSError, subprocess.TimeoutExpired):
        proc.wait(timeout=2.0)


def _iter_descendants(root_pid: int) -> list[Any]:
    """Collect live descendant processes of *root_pid* by walking ppids.

    Unlike ``psutil.Process(root_pid).children(recursive=True)`` this also
    works when the root itself ALREADY EXITED (issue #82 / A2-EW-008):
    Windows does not re-parent orphans, so their recorded ppid keeps
    pointing at the dead pid.  Minor caveat: if the dead pid is recycled
    very quickly, an unrelated process tree could match — the window is
    milliseconds wide and the previous behaviour (orphans surviving until
    job-object close) was strictly worse.
    """
    import psutil  # type: ignore[import-untyped,unused-ignore]

    children_by_ppid: dict[int, list[Any]] = {}
    for proc in psutil.process_iter(["pid", "ppid"]):
        with contextlib.suppress(psutil.NoSuchProcess, psutil.AccessDenied):
            children_by_ppid.setdefault(proc.info["ppid"], []).append(proc)

    descendants: list[Any] = []
    pending = [root_pid]
    seen: set[int] = set()
    while pending:
        current = pending.pop()
        for child in children_by_ppid.get(current, []):
            if child.pid in seen:
                continue
            seen.add(child.pid)
            descendants.append(child)
            pending.append(child.pid)
    return descendants


def _kill_proc_tree(proc: subprocess.Popen[bytes], job_handle: int | None = None) -> None:
    """Terminate the subprocess AND its descendant tree.

    Primary mechanism (win32): closing the per-task kill-on-close
    *job_handle* makes the kernel reap the whole tree atomically — including
    across already-dead intermediate processes, which no live-pid scan can
    bridge (issue #82 / A2-EW-008).  The psutil ppid sweep below remains as
    belt-and-suspenders for non-win32 platforms and job failures; it runs
    even when the direct child already exited (the old code returned early
    and orphaned the grandchildren until the END of the whole run).  Two
    sweeps narrow the TOCTOU window for processes spawned mid-kill.
    """
    # Unit tests and third-party integrations can supply Popen-like objects.
    # Their synthetic ``pid`` values are not process identities and must never
    # reach Job Object assignment, killpg, or the psutil descendant sweep: a
    # coincidental live PID would target an unrelated process.  Real production
    # launchers inherit from the concrete Popen type captured at import time.
    if not isinstance(proc, _REAL_POPEN_TYPE):
        with contextlib.suppress(Exception):
            proc.kill()
        with contextlib.suppress(Exception):
            proc.wait(timeout=2.0)
        return

    if job_handle is not None:
        with contextlib.suppress(Exception):
            from mutmut_win.process.job_object import close_job

            close_job(job_handle)
    elif sys.platform != "win32":
        # Every POSIX caller starts the child in a dedicated session.  The
        # root may already have exited normally, but its process group remains
        # addressable while background descendants survive.
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(proc.pid, signal.SIGKILL)

    use_psutil = False
    try:
        from mutmut_win.process.loop_monitor import has_psutil

        use_psutil = has_psutil()
    except ImportError:
        pass

    if use_psutil:
        import psutil  # type: ignore[import-untyped,unused-ignore]

        for _sweep in range(2):
            for child in _iter_descendants(proc.pid):
                with contextlib.suppress(psutil.NoSuchProcess, psutil.AccessDenied):
                    child.kill()
            if proc.poll() is None:
                with contextlib.suppress(Exception):
                    proc.kill()

    with contextlib.suppress(Exception):
        proc.kill()
    with contextlib.suppress(Exception):
        proc.wait(timeout=2.0)
