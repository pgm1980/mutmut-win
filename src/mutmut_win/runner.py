"""PytestRunner — abstracts pytest execution for mutation testing.

Provides clean-test validation, test collection, timing stats, and
forced-fail verification to ensure the trampoline mechanism works.
"""

from __future__ import annotations

import contextlib
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from mutmut_win.atomic_file import atomic_write_bytes, ensure_atomic_bytes

# Explicit re-export for BWC — single source of truth: constants (#110).
from mutmut_win.constants import MUTANT_ENV_VAR as MUTANT_ENV_VAR
from mutmut_win.constants import SOURCE_ROOT_NAMES, configured_staging_relative_path
from mutmut_win.exceptions import OrchestratorError
from mutmut_win.process.worker import (
    PYTEST_PHASE_GUARD_PLUGIN,
    _write_pytest_argfile,
    apply_pytest_boundary_environment,
    configure_ephemeral_pytest_environment,
    consume_pytest_phase_guard,
    prepare_pytest_collection_guard,
    prepare_pytest_phase_guard,
    redirect_pytest_output_args,
    validated_pytest_args,
    validated_pytest_targets,
)
from mutmut_win.pytest_boundary import PytestBoundary, prepare_pytest_boundary

if TYPE_CHECKING:
    from mutmut_win.config import MutmutConfig

#: Sentinel value that triggers a programmatic fail in the trampoline.
MUTANT_FAIL_SENTINEL = "fail"

#: Sentinel value that triggers stats recording in the trampoline.
MUTANT_STATS_SENTINEL = "stats"

#: Absolute output path consumed by the generated stats plugin.  The parent
#: always points it at a fresh directory outside executable staging.
MUTMUT_STATS_OUTPUT_PATH_ENV = "MUTMUT_STATS_OUTPUT_PATH"

#: The one string the trampoline guarantees in any rendering of its forced
#: fail (the -rfE short summary, conftest tracebacks, collection errors).
#: Used to attribute a forced-fail failure to the trampoline (A2-RN-006)
#: instead of accepting any arbitrary broken test as proof.
FORCED_FAIL_MARKER = "MutmutProgrammaticFailException"
_MAX_COLLECTION_OUTPUT_BYTES = 16 * 1024 * 1024


#: Human explanations for pytest exit classes — a failing gate used to say
#: "Fix tests before mutating" for ALL of them (A2-RN-001), which is plain
#: wrong for usage errors (4) or empty collection (5).
_EXIT_EXPLANATIONS: dict[int, str] = {
    0: "ok",
    1: "tests failed",
    2: "interrupted / collection errors",
    3: "internal pytest error",
    4: "pytest usage error (check pytest_add_cli_args)",
    5: "no tests collected (check tests_dir / test selection)",
    36: "timed out (configure [tool.mutmut].clean_run_timeout)",
}


def decode_pytest_exit(exit_code: int) -> str:
    """Return a short human explanation for a pytest exit code.

    Args:
        exit_code: The raw pytest (or mutmut-win timeout) exit code.

    Returns:
        A non-empty explanation string.
    """
    return _EXIT_EXPLANATIONS.get(exit_code, f"unrecognised exit code {exit_code}")


def _with_isolated_pytest_cache(cmd: list[str], cache_dir: str) -> list[str]:
    """Insert mutmut's cache override before the internal target separator."""

    separator = cmd.index("--") if "--" in cmd else len(cmd)
    return [
        *cmd[:separator],
        "-o",
        f"cache_dir={cache_dir}",
        *cmd[separator:],
    ]


def _with_pytest_target_argfile(cmd: list[str], runtime_dir: Path) -> list[str]:
    """Move the internal target tail into one invocation-owned argument file.

    Every parent phase uses the same ordered target transport as workers,
    avoiding Windows' command-line limit before mutation tasks even begin.
    The enclosing runtime context owns cleanup on success and every failure;
    no argument-file bytes enter the executable staging basis (CX221-070).
    """
    if "--" not in cmd:
        return cmd
    separator = cmd.index("--")
    targets = validated_pytest_targets(cmd[separator + 1 :], field_name="pytest target tail")
    if not targets:
        return cmd
    argument_file = _write_pytest_argfile(targets, runtime_dir)
    return [*cmd[: separator + 1], f"@{argument_file.absolute()}"]


def _run_collection_process(
    cmd: list[str],
    *,
    cwd: str | None,
    env: dict[str, str] | None,
    timeout: float,
) -> subprocess.CompletedProcess[str]:
    """Run collection with bounded output and complete tree cleanup."""
    from mutmut_win.process.output_capture import BoundedOutputCapture
    from mutmut_win.process.worker import (
        _contained_creationflags,
        _kill_proc_tree,
        _popen_contained,
    )

    with (
        BoundedOutputCapture(max_tail_bytes=_MAX_COLLECTION_OUTPUT_BYTES) as stdout_capture,
        BoundedOutputCapture(max_tail_bytes=_MAX_COLLECTION_OUTPUT_BYTES) as stderr_capture,
    ):
        proc: subprocess.Popen[bytes] | None = None
        job_handle: int | None = None
        tree_cleanup_done = False
        try:
            proc, job_handle = _popen_contained(
                cmd,
                stdout=stdout_capture.writer_fd,
                stderr=stderr_capture.writer_fd,
                cwd=cwd,
                env=env,
                start_new_session=sys.platform != "win32",
                creationflags=_contained_creationflags(),
            )
            stdout_capture.close_writer()
            stderr_capture.close_writer()
            try:
                return_code = proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                _kill_proc_tree(proc, job_handle)
                job_handle = None
                tree_cleanup_done = True
                return_code = 36
            except BaseException:
                _kill_proc_tree(proc, job_handle)
                job_handle = None
                tree_cleanup_done = True
                raise
            finally:
                if job_handle is not None:
                    with contextlib.suppress(Exception):
                        from mutmut_win.process.job_object import close_job

                        close_job(job_handle)
                elif not tree_cleanup_done:
                    _kill_proc_tree(proc)
        finally:
            stdout_capture.close_writer()
            stderr_capture.close_writer()

        stdout_capture.close()
        stderr_capture.close()
        if stdout_capture.truncated or stderr_capture.truncated:
            raise OrchestratorError("pytest collection output exceeded the 16 MiB safety limit")
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=return_code,
            stdout=stdout_capture.text(),
            stderr=stderr_capture.text(),
        )


class PytestRunner:
    """Abstracts pytest execution for the mutation testing pipeline.

    Wraps subprocess calls to pytest, providing:
    - Clean baseline test run
    - Test collection
    - Per-test timing statistics
    - Forced-fail verification

    Args:
        config: Validated ``MutmutConfig`` instance.
    """

    def __init__(self, config: MutmutConfig) -> None:
        self._config = config
        self._project_root = Path.cwd().resolve()
        self._pytest_boundary: PytestBoundary | None = None
        self._last_diagnostic_output: str | None = None
        self._forced_fail_attributed: bool | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def last_diagnostic_output(self) -> str | None:
        """Tail of the pytest output from the last FAILED phase run.

        ``None`` after a successful phase. The diagnostic channel for the
        orchestrator's gate error messages (issue #99 / A2-RN-001 — the
        phases used to pipe to DEVNULL, leaving zero output on failure).
        """
        return self._last_diagnostic_output

    @property
    def pytest_boundary_data(self) -> dict[str, object]:
        """Return the validated boundary payload transported to spawn workers."""

        self.prepare_pytest_boundary()
        boundary = self._pytest_boundary
        if boundary is None:  # pragma: no cover - prepare either returns or raises
            raise OrchestratorError("pytest boundary was not prepared")
        boundary.arguments()
        return boundary.to_dict()

    def prepare_pytest_boundary(self, mutants_dir: Path | None = None) -> None:
        """Freeze one staged config/root boundary before the first pytest phase."""

        staging = Path("mutants") if mutants_dir is None else mutants_dir
        existing = self._pytest_boundary
        if existing is not None:
            try:
                requested_root = staging.resolve(strict=True)
                frozen_root = Path(existing.staging_root).resolve(strict=True)
            except (OSError, RuntimeError) as exc:
                raise OrchestratorError("Could not validate the frozen pytest boundary.") from exc
            if requested_root != frozen_root:
                raise OrchestratorError(
                    "pytest boundary is already frozen for a different staging root"
                )
            # Never refresh the digest or selected config. A changed/missing
            # file is run-input drift and must fail, not become re-authorized.
            existing.arguments()
            return
        self._pytest_boundary = prepare_pytest_boundary(
            project_root=self._project_root,
            staging_root=staging,
            tests_dir=self._pytest_targets(),
        )

    @property
    def last_forced_fail_attributed(self) -> bool | None:
        """Whether the last forced-fail failure stems from the trampoline.

        ``True`` when :data:`FORCED_FAIL_MARKER` appeared in the captured
        output of a failing forced-fail run, ``False`` when the run failed
        for some other reason (or did not fail at all), ``None`` when no
        verdict exists (timeout — issue #111 / A2-RN-006).
        """
        return self._forced_fail_attributed

    def run_clean_test(self) -> int:
        """Run pytest without any mutations active (in mutants/ directory).

        The test suite runs against the trampolined code in ``mutants/`` with
        ``MUTANT_UNDER_TEST=''``, so all trampoline calls forward to the
        original functions.  This validates the test suite passes before
        mutation testing begins.

        Returns:
            The pytest exit code (0 means all tests passed).
        """
        cmd = self._guarded_pytest_cmd()
        cmd.extend(self._configured_pytest_args())
        cmd.extend(self._pytest_target_args())
        env = self._mutants_env()
        env[MUTANT_ENV_VAR] = ""
        return self._run_phase("clean test suite", cmd, env)

    def _run_phase(
        self,
        phase_name: str,
        cmd: list[str],
        env: dict[str, str],
        timeout: int | None = None,
        timeout_hint: str = "clean_run_timeout",
    ) -> int:
        """Run one pytest phase with a fresh process-local cache directory."""

        with tempfile.TemporaryDirectory(
            prefix="mutmut-win-pytest-runtime-",
            ignore_cleanup_errors=True,
        ) as runtime_name:
            runtime_dir = Path(runtime_name)
            isolated_env = env.copy()
            cache_dir = configure_ephemeral_pytest_environment(isolated_env, runtime_dir)
            isolated_cmd = redirect_pytest_output_args(cmd, runtime_dir)
            isolated_cmd = _with_isolated_pytest_cache(isolated_cmd, str(cache_dir))
            isolated_cmd = _with_pytest_target_argfile(isolated_cmd, runtime_dir)
            return self._run_phase_process(
                phase_name,
                isolated_cmd,
                isolated_env,
                timeout=timeout,
                timeout_hint=timeout_hint,
                runtime_dir=runtime_dir,
            )

    def _run_phase_process(
        self,
        phase_name: str,
        cmd: list[str],
        env: dict[str, str],
        timeout: int | None = None,
        timeout_hint: str = "clean_run_timeout",
        runtime_dir: Path | None = None,
    ) -> int:
        """Run one pytest phase with tail capture and full-tree reaping.

        Drains stdout+stderr concurrently into a bounded in-memory tail. This
        avoids both an unread ``PIPE`` deadlock and the unbounded disk growth
        of a runaway temporary log, while retaining diagnostics in
        :attr:`last_diagnostic_output` when the phase fails.

        Issue #132 / 360°-B5: ``subprocess.run(timeout=...)`` killed only
        the direct child on expiry — pytest's own grandchildren (xdist
        workers, subprocess-spawning tests) survived and kept the staging
        locked. The phases now mirror the worker's pattern: a kill-on-close
        Job Object around the child plus the psutil tree sweep on timeout.

        Args:
            phase_name: Human-readable phase name for the timeout warning.
            cmd: Full command list.
            env: Environment for the subprocess.
            timeout: Wall-clock budget; defaults to ``clean_run_timeout``.
            timeout_hint: Config key named in the timeout warning.

        Returns:
            The exit code (36 on timeout, mirroring the worker convention).
        """
        from mutmut_win.process.output_capture import BoundedOutputCapture
        from mutmut_win.process.worker import (
            _MAX_DIAGNOSTIC_LINES,
            _contained_creationflags,
            _kill_proc_tree,
            _popen_contained,
        )

        budget = timeout if timeout is not None else self._config.clean_run_timeout
        self._last_diagnostic_output = None
        phase_marker_path, phase_marker_token = prepare_pytest_phase_guard(
            env,
            runtime_dir=runtime_dir,
        )
        capture = BoundedOutputCapture()
        proc: subprocess.Popen[bytes] | None = None
        job_handle: int | None = None
        tree_cleanup_done = False
        try:
            try:
                proc, job_handle = _popen_contained(
                    cmd,
                    stdout=capture.writer_fd,
                    stderr=subprocess.STDOUT,
                    cwd="mutants",
                    env=env,
                    start_new_session=sys.platform != "win32",
                    creationflags=_contained_creationflags(),
                )
                capture.close_writer()
                try:
                    exit_code = proc.wait(timeout=budget)
                except subprocess.TimeoutExpired:
                    print(
                        f"Warning: {phase_name} timed out after {budget}s "
                        f"(configure [tool.mutmut].{timeout_hint})"
                    )
                    _kill_proc_tree(proc, job_handle)
                    job_handle = None  # the sweep closed it
                    tree_cleanup_done = True
                    exit_code = 36  # timeout exit code
                except BaseException:
                    # POSIX process-group cleanup and the psutil sweep reap the
                    # root/tree on Ctrl-C or another non-timeout exception.
                    # Windows reached this point only after Job containment.
                    _kill_proc_tree(proc, job_handle)
                    job_handle = None
                    tree_cleanup_done = True
                    raise
                finally:
                    if job_handle is not None:
                        # Normal completion: closing the kill-on-close job reaps
                        # background processes the phase left behind (issue #82).
                        with contextlib.suppress(Exception):
                            from mutmut_win.process.job_object import close_job

                            close_job(job_handle)
                    elif not tree_cleanup_done:
                        _kill_proc_tree(proc)
            finally:
                capture.close_writer()
        except BaseException:
            # KeyboardInterrupt/SystemExit and unexpected BaseExceptions must
            # not leak per-phase proof or diagnostic artifacts. Do not treat a
            # proof as success here: the phase did not return a verdict.
            consume_pytest_phase_guard(phase_marker_path, phase_marker_token)
            capture.close()
            raise
        capture.close()
        phase_executed = consume_pytest_phase_guard(phase_marker_path, phase_marker_token)
        if exit_code == 0 and not phase_executed:
            diagnostic = capture.last_lines(_MAX_DIAGNOSTIC_LINES)
            message = (
                f"{phase_name} exited 0 without executing a pytest test call; "
                "the phase was neutralized by pytest arguments/configuration "
                "or every selected test was skipped"
            )
            self._last_diagnostic_output = (
                f"{message}\n{diagnostic}" if diagnostic is not None else message
            )
            raise OrchestratorError(message)
        if exit_code != 0:
            self._last_diagnostic_output = capture.last_lines(_MAX_DIAGNOSTIC_LINES)
        return exit_code

    def collect_tests(self) -> list[str]:
        """Collect test node IDs via ``pytest --collect-only``.

        Scope parity with the stats phase (issue #130 / 360°-B2): the
        collection runs inside ``mutants/`` with the staging env and BOTH
        cli-arg lists plus ``tests_dir`` — a marker filter visible only to
        the stats run used to make every collection see "new" tests and
        re-collect the full stats run forever. Falls back to the project
        root when no staging exists (ad-hoc callers, unit tests). The pipe
        decodes utf-8 with replacement: a cp1252 console with non-ASCII
        test IDs crashed the strict reader.

        Returns:
            Sorted list of test node ID strings (e.g. ``tests/unit/test_foo.py::test_bar``).
        """
        staging_exists = Path("mutants").is_dir()
        pytest_cmd = self._guarded_pytest_cmd() if staging_exists else self._base_pytest_cmd()
        cmd = [*pytest_cmd, "--collect-only", "-q", "--no-header"]
        cmd.extend(self._configured_pytest_args())
        cmd.extend(self._pytest_target_args())

        env: dict[str, str] | None = None
        if staging_exists:
            env = self._mutants_env()
            env[MUTANT_ENV_VAR] = ""
            env["PYTHONIOENCODING"] = "utf-8"
            prepare_pytest_collection_guard()

        with tempfile.TemporaryDirectory(
            prefix="mutmut-win-pytest-runtime-",
            ignore_cleanup_errors=True,
        ) as runtime_name:
            runtime_dir = Path(runtime_name)
            if env is not None:
                env = env.copy()
                cache_dir = configure_ephemeral_pytest_environment(env, runtime_dir)
            else:
                cache_dir = runtime_dir / "pytest-cache"
                cache_dir.mkdir()
            isolated_cmd = redirect_pytest_output_args(cmd, runtime_dir)
            isolated_cmd = _with_isolated_pytest_cache(isolated_cmd, str(cache_dir))
            isolated_cmd = _with_pytest_target_argfile(isolated_cmd, runtime_dir)
            result = _run_collection_process(
                isolated_cmd,
                cwd="mutants" if staging_exists else None,
                env=env,
                timeout=self._config.clean_run_timeout,
            )
        if result.returncode != 0:
            diagnostic = "\n".join(
                part.strip() for part in (result.stdout, result.stderr) if part and part.strip()
            )
            if len(diagnostic) > 4000:
                diagnostic = diagnostic[-4000:]
            detail = f"\n{diagnostic}" if diagnostic else ""
            raise OrchestratorError(
                "pytest test collection failed — "
                f"{decode_pytest_exit(result.returncode)} (exit {result.returncode})."
                f"{detail}"
            )
        tests: list[str] = []
        for line in result.stdout.splitlines():
            line = line.strip()
            # pytest --collect-only -q outputs lines like:
            #   tests/unit/test_foo.py::test_bar
            # Skip summary lines, warnings and blank lines
            if "::" in line and not line.startswith("=") and not line.startswith("WARNING"):
                tests.append(line)
        return sorted(tests)

    def run_stats(self, output_file: Path | None = None) -> int:
        """Run pytest as a subprocess with MUTANT_UNDER_TEST=stats.

        Injects a pytest plugin (``_mutmut_stats_plugin.py``) into
        ``mutants/`` that captures per-test trampoline hits and durations.
        The plugin writes the mapping to a fresh parent-owned temporary file
        outside ``mutants/``; the parent reads that file after the subprocess
        exits and optionally publishes it to *output_file*.  The plugin JSON
        is the single source of truth (issue #99 /
        A2-RN-009: pre-rewrite "in-process" docs survived here for a while).

        Returns:
            The subprocess exit code (36 on timeout). Callers must treat a
            non-zero exit as a failed collection — the JSON may be partial
            and ``_state`` stays empty (issue #99 / A2-RN-003).
        """
        from mutmut_win import _state
        from mutmut_win.stats import load_stats

        _state._reset_globals()

        env = self._mutants_env()
        env[MUTANT_ENV_VAR] = MUTANT_STATS_SENTINEL

        # Validate before writing even the generated plugin. Stats collection
        # is deliberately single-process: independent xdist workers cannot
        # merge the process-local trampoline hit set authoritatively.
        stats_args = self._configured_pytest_args(stats_phase=True)

        # The deterministic plugin is part of the frozen staging basis.  This
        # idempotent ensure is also safe for direct/ad-hoc callers that did not
        # invoke write_pth_blocker first.
        mutants_abs = Path("mutants").absolute()
        self._write_stats_plugin(mutants_abs)

        # Run all tests with the stats plugin active.
        cmd = [*self._guarded_pytest_cmd(), "-p", "_mutmut_stats_plugin", "--tb=no", "-q"]
        cmd.extend(stats_args)
        cmd.extend(self._pytest_target_args())

        with tempfile.TemporaryDirectory(
            prefix="mutmut-win-stats-output-",
            ignore_cleanup_errors=True,
        ) as output_name:
            transient_dir = Path(output_name)
            transient_file = (transient_dir / "mutmut-stats.json").absolute()
            env[MUTMUT_STATS_OUTPUT_PATH_ENV] = str(transient_file)
            exit_code = self._run_phase("stats collection", cmd, env)
            if exit_code != 0:
                print(
                    f"Warning: stats collection failed — "
                    f"{decode_pytest_exit(exit_code)} (exit {exit_code})"
                )
                return exit_code

            # Read the JSON file written by the plugin in the subprocess.
            stats = load_stats(transient_dir)
            if stats is not None and output_file is not None:
                atomic_write_bytes(output_file, transient_file.read_bytes())
        if stats is not None:
            _state.tests_by_mangled_function_name.update(stats.tests_by_mangled_function_name)
            _state.duration_by_test.update(stats.duration_by_test)
            num_mapped = sum(len(t) for t in _state.tests_by_mangled_function_name.values())
            num_tests = len(_state.duration_by_test)
            print(f"Collected {num_mapped} test-to-mutant mappings across {num_tests} tests.")
        else:
            print(
                "Warning: no test-to-mutant mappings found. Tests may not cover any mutated code."
            )
        return exit_code

    def run_coverage_collection(self, data_file: Path) -> int:
        """Run the clean suite under ``coverage run`` inside ``mutants/``.

        The subprocess coverage bridge for ``mutate_only_covered_lines``
        (issue #95): pytest executes under ``coverage run`` with an explicit
        data file, and the parent process loads that file afterwards.  Runs
        against the unmutated copies with ``MUTANT_UNDER_TEST=''``.

        Args:
            data_file: Absolute path the coverage data is written to.

        Returns:
            The exit code (0 = suite passed; 36 on timeout, mirroring
            ``run_clean_test``).
        """
        cmd = [
            sys.executable,
            "-m",
            "coverage",
            "run",
            f"--data-file={data_file}",
            "--source=.",
            "-m",
            "pytest",
            "-p",
            PYTEST_PHASE_GUARD_PLUGIN,
        ]
        cmd.extend(self._configured_pytest_args())
        cmd.extend(self._pytest_target_args())
        env = self._mutants_env()
        env[MUTANT_ENV_VAR] = ""
        return self._run_phase("coverage collection", cmd, env)

    def run_forced_fail(
        self,
        mutant_name: str,  # noqa: ARG002  # kept for API symmetry — future: filter tests by mutant
    ) -> int:
        """Run pytest with ``MUTANT_UNDER_TEST=fail`` in mutants/ directory.

        The trampoline raises ``MutmutProgrammaticFailException`` for every
        function call, so the run must fail — and the failure must come from
        exactly that exception. ``-x`` stops at the first failure (one
        failure is all the proof there is), ``-rfE`` puts the exception name
        into the output even with ``--tb=no`` (issue #111 / A2-RN-006; the
        pre-#111 code ran the FULL suite and converted a timeout into
        "trampoline works").

        Args:
            mutant_name: Mutant identifier (reserved for future test filtering — unused now).

        Returns:
            The pytest exit code, untranslated (36 = timeout). The
            attribution verdict is published via
            :attr:`last_forced_fail_attributed`; the orchestrator owns the
            gate decision.
        """
        # --tb=line (not --tb=no): the one-line traceback carries the
        # exception name and is never width-truncated; the -rfE summary
        # alone is cut to terminal width and could lose the marker behind
        # a long node id. COLUMNS widens that summary as belt and braces.
        cmd = [*self._guarded_pytest_cmd(), "--tb=line", "-q", "-x", "-rfE"]
        cmd.extend(self._configured_pytest_args())
        cmd.extend(self._pytest_target_args())
        env = self._mutants_env()
        env[MUTANT_ENV_VAR] = MUTANT_FAIL_SENTINEL
        env["COLUMNS"] = "200"
        exit_code = self._run_phase(
            "forced-fail verification",
            cmd,
            env,
            timeout=self._config.forced_fail_timeout,
            timeout_hint="forced_fail_timeout",
        )
        if exit_code == 36:
            # A hung suite proves nothing about the trampoline — no verdict.
            self._forced_fail_attributed = None
            return exit_code
        self._forced_fail_attributed = exit_code != 0 and FORCED_FAIL_MARKER in (
            self._last_diagnostic_output or ""
        )
        return exit_code

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _base_pytest_cmd(self) -> list[str]:
        """Build the base pytest command using the current Python interpreter.

        Returns:
            Base command list: ``[sys.executable, '-m', 'pytest']``.
        """
        return [sys.executable, "-m", "pytest"]

    def _guarded_pytest_cmd(self) -> list[str]:
        """Build a pytest command that publishes proof of real test calls."""
        return [*self._base_pytest_cmd(), "-p", PYTEST_PHASE_GUARD_PLUGIN]

    def _configured_pytest_args(self, *, stats_phase: bool = False) -> list[str]:
        """Return both configured pytest-argument groups after validation.

        Test-selection arguments affect every phase, including workers: a
        marker or expression that defines the suite must not disappear after
        collection and silently change baseline, coverage, stats, or verdicts.

        Args:
            stats_phase: Apply the additional single-process stats contract.

        Returns:
            General arguments followed by test-selection arguments.
        """
        user_args = validated_pytest_args(
            self._config.pytest_add_cli_args,
            self._config.pytest_add_cli_args_test_selection,
            stats_phase=stats_phase,
            environment_addopts=os.environ.get("PYTEST_ADDOPTS", ""),
        )
        return [*user_args, *self._pytest_boundary_args()]

    def _pytest_boundary_args(self) -> list[str]:
        """Return the frozen boundary; keep only non-authoritative ad-hoc fallback open."""

        if self._pytest_boundary is None:
            if not Path("mutants").is_dir():
                return []
            self.prepare_pytest_boundary()
        boundary = self._pytest_boundary
        if boundary is None:  # pragma: no cover - prepare either returns or raises
            raise OrchestratorError("pytest boundary was not prepared")
        return boundary.arguments()

    def _pytest_targets(self) -> list[str]:
        """Return validated path/node-id targets from the dedicated config field."""

        return validated_pytest_targets(self._config.tests_dir, field_name="tests_dir")

    def _pytest_target_args(self) -> list[str]:
        """Place test targets behind an internal end-of-options boundary."""

        targets = self._pytest_targets()
        return ["--", *targets] if targets else []

    def write_pth_blocker(self, mutants_dir: Path | None = None) -> None:
        """Write the ``sitecustomize.py`` .pth blocker into the staging dir.

        The explicit setup step (issue #116 / A2-RN-010): ``_mutants_env``
        used to write this file as a side effect of building an env dict —
        unit tests touching the getter left real artifacts in the repo.
        The orchestrator runs this once per run, before the first phase;
        the file then covers every phase and worker (same staging dir).

        Args:
            mutants_dir: Staging directory to write into; defaults to
                ``mutants/`` under the current working directory.
        """
        target = Path("mutants").absolute() if mutants_dir is None else mutants_dir
        self.prepare_pytest_boundary(target)
        self._write_sitecustomize_pth_blocker(target)
        self._write_stats_plugin(target)
        prepare_pytest_collection_guard(target)

    def _mutants_env(self) -> dict[str, str]:
        """Build env dict for subprocess runs inside ``mutants/``.

        Pure (issue #116 / A2-RN-010): builds and returns the dict, writes
        nothing — the ``sitecustomize.py`` .pth blocker is written by the
        explicit :meth:`write_pth_blocker` setup step.

        Sets ``PYTHONPATH`` so the subprocess can import source modules from
        ``mutants/src``, ``mutants/source``, or ``mutants/.``.

        Prevents ``uv`` from auto-creating a ``.venv`` inside ``mutants/``
        by setting ``UV_PROJECT_ENVIRONMENT`` to the parent venv.  Without
        this, ``uv`` detects the copied ``pyproject.toml`` in ``mutants/``
        and creates an empty ``.venv`` that shadows the parent interpreter.

        Returns:
            Copy of ``os.environ`` with ``PYTHONPATH`` adjusted.
        """
        import os

        env = os.environ.copy()
        # PYTEST_ADDOPTS is parsed into the validated argv exactly once. Letting
        # pytest prepend it again could place ``--`` or a config override ahead
        # of the internal staged boundary.
        env.pop("PYTEST_ADDOPTS", None)
        # Tests execute only against the frozen staging universe.  An inherited
        # PYTHONPATH could otherwise reintroduce live, unmirrored source bytes;
        # projects needing such imports must declare them through extra_paths.
        env.pop("PYTHONPATH", None)
        self.prepare_pytest_boundary()
        boundary = self._pytest_boundary
        if boundary is None:  # pragma: no cover - prepare either returns or raises
            raise OrchestratorError("pytest boundary was not prepared")
        apply_pytest_boundary_environment(boundary, env)
        mutants_abs = Path("mutants").absolute()
        # The isolated pytest child receives src, source, . and configured
        # extra_paths.  Never add these staging roots to the orchestration
        # parent: Windows spawn workers inherit its import path (CX221-059).
        # Before issue #99 / A2-RN-002 only the worker had extra_paths, so
        # affected projects failed the clean gate with a hidden ImportError.
        extra_paths = []
        configured = []
        for entry in self._config.extra_paths:
            entry_as_path = configured_staging_relative_path(
                entry,
                project_root=self._project_root,
            )
            if entry_as_path is not None:
                configured.append(entry_as_path)
        for subdir in [*map(Path, SOURCE_ROOT_NAMES), Path(), *configured]:
            candidate = mutants_abs / subdir
            if candidate.exists():
                extra_paths.append(str(candidate))
        if extra_paths:
            env["PYTHONPATH"] = os.pathsep.join(extra_paths)

        # Prevent uv from auto-creating a .venv in mutants/.
        # uv detects the copied pyproject.toml and would create an empty
        # venv that shadows the parent interpreter.  UV_PROJECT_ENVIRONMENT
        # tells uv to use the parent venv instead of creating a new one.
        parent_venv = Path(sys.executable).resolve().parent.parent
        env["UV_PROJECT_ENVIRONMENT"] = str(parent_venv)

        # mutants/ holds copies of the test modules under their original
        # basenames — pytest's import-mismatch check would reject them when
        # stale __pycache__ entries point at the originals. Set for EVERY
        # phase (clean / stats / coverage / forced-fail); the stats run used
        # to be the only one (issue #111 / A2-RN-012).
        env["PY_IGNORE_IMPORTMISMATCH"] = "1"

        return env

    @staticmethod
    def _write_stats_plugin(mutants_abs: Path) -> None:
        """Write the stats-collection pytest plugin into *mutants_abs*.

        The generated ``_mutmut_stats_plugin.py`` is loaded by pytest via
        ``-p _mutmut_stats_plugin`` during the stats subprocess.  It uses
        ``hookwrapper`` on ``pytest_runtest_protocol`` to track which
        trampoline functions each test exercises. Hits produced while test
        modules are imported during collection are conservatively assigned to
        every collected test instead of being erased before the first item.
        The complete mapping is atomically written to the absolute path in
        ``MUTMUT_STATS_OUTPUT_PATH`` only after a successful, single-process
        session.  That target is a fresh parent-owned directory outside
        executable staging.

        This bridges the subprocess isolation gap: trampoline hits
        accumulate in ``_state._stats`` inside the subprocess, the plugin
        snapshots them per-test, and persists the result to a JSON file
        that the parent process reads after the subprocess exits.
        """
        plugin_path = mutants_abs / "_mutmut_stats_plugin.py"
        plugin_source = '''\
# Auto-generated by mutmut-win — pytest plugin for per-test trampoline hit collection
import json
import os
from collections import defaultdict
from pathlib import Path

import pytest

from mutmut_win.atomic_file import atomic_write_bytes

_tests_by_func: dict[str, set[str]] = defaultdict(set)
_duration_by_test: dict[str, float] = {}
_collection_hits: set[str] = set()
_collected_test_ids: set[str] = set()


def pytest_configure(config):
    """Reject active xdist: process-local hit maps cannot be merged safely."""
    num_processes = getattr(config.option, "numprocesses", None)
    tx_specs = getattr(config.option, "tx", None)
    dist_mode = getattr(config.option, "dist", "no")
    loop_on_fail = getattr(config.option, "looponfail", False)
    boxed = getattr(config.option, "boxed", False)
    if (
        hasattr(config, "workerinput")
        or num_processes
        or tx_specs
        or dist_mode != "no"
        or loop_on_fail
        or boxed
    ):
        raise pytest.UsageError(
            "mutmut-win stats collection does not support pytest-xdist; "
            "remove -n/--numprocesses for an authoritative mapping"
        )


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_collection_finish(session):
    """Preserve import/collection hits and remember the authoritative suite."""
    # Enter first and resume last so collection-finish hooks from the target
    # project cannot add a hit after our snapshot.
    yield
    from mutmut_win._state import _stats
    _collection_hits.update(_stats)
    _stats.clear()
    _collected_test_ids.update(item.nodeid for item in session.items)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_protocol(item, nextitem):  # noqa: ARG001
    """Wrap each test: clear per-test hits before, snapshot after."""
    from mutmut_win._state import _stats
    _stats.clear()
    yield
    for func_name in list(_stats):
        _tests_by_func[func_name].add(item.nodeid)


def pytest_runtest_makereport(item, call):
    """Capture per-test duration from the call phase."""
    if call.when == "call":
        _duration_by_test[item.nodeid] = call.duration


def pytest_sessionfinish(session, exitstatus):  # noqa: ARG001
    """Atomically publish a complete mapping after a successful session."""
    if exitstatus != 0:
        return
    for func_name in _collection_hits:
        _tests_by_func[func_name].update(_collected_test_ids)
    payload = {
        "tests_by_mangled_function_name": {
            k: sorted(v) for k, v in _tests_by_func.items()
        },
        "duration_by_test": _duration_by_test,
        "stats_time": sum(_duration_by_test.values()),
    }
    payload_bytes = json.dumps(payload, indent=4).encode("utf-8")
    raw_output = os.environ.get("MUTMUT_STATS_OUTPUT_PATH")
    if not raw_output:
        raise RuntimeError("MUTMUT_STATS_OUTPUT_PATH is required")
    output_path = Path(raw_output)
    if not output_path.is_absolute():
        raise RuntimeError("MUTMUT_STATS_OUTPUT_PATH must be absolute")
    atomic_write_bytes(output_path, payload_bytes)
'''
        ensure_atomic_bytes(plugin_path, plugin_source.encode("utf-8"))

    def _write_sitecustomize_pth_blocker(self, mutants_abs: Path) -> None:
        """Write a sitecustomize.py that removes the real src/ from sys.path.

        Editable installs (``uv pip install -e .``) create ``.pth`` files that
        inject the project's real ``src/`` into ``sys.path`` at startup —
        **before** ``PYTHONPATH``.  This shadows the mutated code.

        The sitecustomize.py runs at Python startup and removes any ``sys.path``
        entry that points to the real source directories (not mutants/).
        Both sides of the comparison are ``normcase(realpath(...))``-
        normalized (issue #116 / A2-RN-011 — exact-string matching let case
        or symlink variants of the real ``src/`` shadow the staged tree).
        """
        import os

        # Collect real source dirs that should be removed from sys.path,
        # pre-normalized to match the generated code's normalization.
        real_src_dirs: list[str] = []
        for subdir in SOURCE_ROOT_NAMES:
            candidate = Path(subdir).absolute()
            if candidate.exists():
                real_src_dirs.append(os.path.normcase(os.path.realpath(candidate)))

        if not real_src_dirs:
            return

        # Write sitecustomize.py into mutants/ (the cwd of the subprocess)
        sitecustomize = mutants_abs / "sitecustomize.py"
        dirs_repr = repr(set(real_src_dirs))
        blocker_source = (
            f"# Auto-generated by mutmut-win — removes editable-install .pth paths\n"
            f"import os\n"
            f"import sys\n"
            f"_shadow = {dirs_repr}\n"
            f"\n"
            f"\n"
            f"def _norm(p):\n"
            f"    try:\n"
            f"        return os.path.normcase(os.path.realpath(p))\n"
            f"    except OSError:\n"
            f"        return os.path.normcase(p)\n"
            f"\n"
            f"\n"
            f"sys.path[:] = [p for p in sys.path if _norm(p) not in _shadow]\n"
        )
        atomic_write_bytes(sitecustomize, blocker_source.encode("utf-8"))
