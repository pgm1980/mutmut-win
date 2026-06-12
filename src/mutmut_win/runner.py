"""PytestRunner — abstracts pytest execution for mutation testing.

Provides clean-test validation, test collection, timing stats, and
forced-fail verification to ensure the trampoline mechanism works.
"""

from __future__ import annotations

import contextlib
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

# Explicit re-export for BWC — single source of truth: constants (#110).
from mutmut_win.constants import MUTANT_ENV_VAR as MUTANT_ENV_VAR
from mutmut_win.constants import SOURCE_ROOT_NAMES

if TYPE_CHECKING:
    from mutmut_win.config import MutmutConfig

#: Sentinel value that triggers a programmatic fail in the trampoline.
MUTANT_FAIL_SENTINEL = "fail"

#: Sentinel value that triggers stats recording in the trampoline.
MUTANT_STATS_SENTINEL = "stats"

#: The one string the trampoline guarantees in any rendering of its forced
#: fail (the -rfE short summary, conftest tracebacks, collection errors).
#: Used to attribute a forced-fail failure to the trampoline (A2-RN-006)
#: instead of accepting any arbitrary broken test as proof.
FORCED_FAIL_MARKER = "MutmutProgrammaticFailException"


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
        cmd = self._base_pytest_cmd()
        cmd.extend(self._config.pytest_add_cli_args)
        if self._config.tests_dir:
            cmd.extend(self._config.tests_dir)
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
        """Run one pytest phase with tail capture (issue #99 / A2-RN-001).

        Captures stdout+stderr into a temp file (the worker's deadlock-safe
        pattern — PIPE deadlocks on Windows when grandchildren inherit
        handles) and keeps the tail in :attr:`last_diagnostic_output` when
        the phase fails, so gate errors can finally show WHY.

        Args:
            phase_name: Human-readable phase name for the timeout warning.
            cmd: Full command list.
            env: Environment for the subprocess.
            timeout: Wall-clock budget; defaults to ``clean_run_timeout``.
            timeout_hint: Config key named in the timeout warning.

        Returns:
            The exit code (36 on timeout, mirroring the worker convention).
        """
        import os
        import tempfile

        from mutmut_win.process.worker import _MAX_DIAGNOSTIC_LINES, _read_last_lines

        budget = timeout if timeout is not None else self._config.clean_run_timeout
        self._last_diagnostic_output = None
        log_fd, log_path_str = tempfile.mkstemp(suffix=".log", prefix="mutmut_phase_", text=True)
        log_path = Path(log_path_str)
        try:
            try:
                result = subprocess.run(  # noqa: S603  # command is fully controlled — no user input
                    cmd,
                    stdout=log_fd,
                    stderr=subprocess.STDOUT,
                    cwd="mutants",
                    env=env,
                    timeout=budget,
                )
                exit_code = result.returncode
            except subprocess.TimeoutExpired:
                print(
                    f"Warning: {phase_name} timed out after {budget}s "
                    f"(configure [tool.mutmut].{timeout_hint})"
                )
                exit_code = 36  # timeout exit code
        finally:
            os.close(log_fd)
        if exit_code != 0:
            self._last_diagnostic_output = _read_last_lines(log_path, _MAX_DIAGNOSTIC_LINES)
        with contextlib.suppress(OSError):
            log_path.unlink()
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
        cmd = [*self._base_pytest_cmd(), "--collect-only", "-q", "--no-header"]
        cmd.extend(self._config.pytest_add_cli_args)
        cmd.extend(self._config.pytest_add_cli_args_test_selection)
        if self._config.tests_dir:
            cmd.extend(self._config.tests_dir)

        staging_exists = Path("mutants").is_dir()
        env: dict[str, str] | None = None
        if staging_exists:
            env = self._mutants_env()
            env[MUTANT_ENV_VAR] = ""
            env["PYTHONIOENCODING"] = "utf-8"

        result = subprocess.run(  # noqa: S603  # command is fully controlled — no user input
            cmd,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            cwd="mutants" if staging_exists else None,
            env=env,
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

    def run_stats(self) -> int:
        """Run pytest as a subprocess with MUTANT_UNDER_TEST=stats.

        Injects a pytest plugin (``_mutmut_stats_plugin.py``) into
        ``mutants/`` that captures per-test trampoline hits and durations.
        The plugin writes the mapping to ``mutants/mutmut-stats.json``
        at session end; the parent reads that file after the subprocess
        exits — the plugin JSON is the single source of truth (issue #99 /
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

        # Inject the stats-collection pytest plugin into mutants/.
        mutants_abs = Path("mutants").absolute()
        self._write_stats_plugin(mutants_abs)

        # Run all tests with the stats plugin active.
        cmd = [*self._base_pytest_cmd(), "-p", "_mutmut_stats_plugin", "--tb=no", "-q"]
        cmd.extend(self._config.pytest_add_cli_args)
        if self._config.tests_dir:
            cmd.extend(self._config.tests_dir)

        exit_code = self._run_phase("stats collection", cmd, env)
        if exit_code != 0:
            print(
                f"Warning: stats collection failed — "
                f"{decode_pytest_exit(exit_code)} (exit {exit_code})"
            )
            return exit_code

        # Read the JSON file written by the plugin in the subprocess.
        stats = load_stats(mutants_abs)
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
        ]
        cmd.extend(self._config.pytest_add_cli_args)
        if self._config.tests_dir:
            cmd.extend(self._config.tests_dir)
        env = self._mutants_env()
        env[MUTANT_ENV_VAR] = ""
        try:
            result = subprocess.run(  # noqa: S603  # command is fully controlled — no user input
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                cwd="mutants",
                env=env,
                timeout=self._config.clean_run_timeout,
            )
        except subprocess.TimeoutExpired:
            print(
                f"Warning: coverage collection timed out after "
                f"{self._config.clean_run_timeout}s "
                "(configure [tool.mutmut].clean_run_timeout)"
            )
            return 36  # timeout exit code
        return result.returncode

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
        cmd = [*self._base_pytest_cmd(), "--tb=line", "-q", "-x", "-rfE"]
        cmd.extend(self._config.pytest_add_cli_args)
        if self._config.tests_dir:
            cmd.extend(self._config.tests_dir)
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
        self._write_sitecustomize_pth_blocker(target)

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
        mutants_abs = Path("mutants").absolute()
        # Same paths as setup_source_paths: src, source, . — PLUS the
        # configured extra_paths (Bug #69). Only the worker had them before
        # (issue #99 / A2-RN-002): affected projects failed the clean gate
        # with an ImportError nobody could see.
        extra_paths = []
        for subdir in [*SOURCE_ROOT_NAMES, ".", *self._config.extra_paths]:
            candidate = mutants_abs / subdir
            if candidate.exists():
                extra_paths.append(str(candidate))
        if extra_paths:
            existing = env.get("PYTHONPATH", "")
            env["PYTHONPATH"] = os.pathsep.join(extra_paths + ([existing] if existing else []))

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
        trampoline functions each test exercises, and writes the complete
        mapping to ``mutmut-stats.json`` at session end.

        This bridges the subprocess isolation gap: trampoline hits
        accumulate in ``_state._stats`` inside the subprocess, the plugin
        snapshots them per-test, and persists the result to a JSON file
        that the parent process reads after the subprocess exits.
        """
        plugin_path = mutants_abs / "_mutmut_stats_plugin.py"
        plugin_path.write_text(
            '''\
# Auto-generated by mutmut-win — pytest plugin for per-test trampoline hit collection
import json
from collections import defaultdict
from pathlib import Path

import pytest

_tests_by_func: dict[str, set[str]] = defaultdict(set)
_duration_by_test: dict[str, float] = {}


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_protocol(item, nextitem):  # noqa: ARG001
    """Wrap each test: clear hits before, snapshot after."""
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
    """Write the collected mapping to mutmut-stats.json."""
    payload = {
        "tests_by_mangled_function_name": {
            k: sorted(v) for k, v in _tests_by_func.items()
        },
        "duration_by_test": _duration_by_test,
        "stats_time": sum(_duration_by_test.values()),
    }
    stats_path = Path("mutmut-stats.json")
    with stats_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=4)
''',
            encoding="utf-8",
        )

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
        sitecustomize.write_text(
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
            f"sys.path[:] = [p for p in sys.path if _norm(p) not in _shadow]\n",
            encoding="utf-8",
        )
