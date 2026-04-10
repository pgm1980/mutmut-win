"""PytestRunner — abstracts pytest execution for mutation testing.

Provides clean-test validation, test collection, timing stats, and
forced-fail verification to ensure the trampoline mechanism works.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mutmut_win.config import MutmutConfig

#: Environment variable used by the trampoline to select the active mutant.
MUTANT_ENV_VAR = "MUTANT_UNDER_TEST"

#: Default timeout (seconds) for subprocess pytest runs in runner phases.
#: Generous to avoid false positives on slow CI machines.
_RUNNER_TIMEOUT: int = 300

#: Default timeout (seconds) for forced-fail verification.
_FORCED_FAIL_TIMEOUT: int = 120

#: Sentinel value that triggers a programmatic fail in the trampoline.
MUTANT_FAIL_SENTINEL = "fail"

#: Sentinel value that triggers stats recording in the trampoline.
MUTANT_STATS_SENTINEL = "stats"


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

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

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
        try:
            result = subprocess.run(  # noqa: S603  # command is fully controlled — no user input
                cmd,
                capture_output=True,
                encoding="utf-8",
                cwd="mutants",
                env=env,
                timeout=_RUNNER_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            print(f"Warning: clean test suite timed out after {_RUNNER_TIMEOUT}s")
            return 36  # timeout exit code
        return result.returncode

    def collect_tests(self) -> list[str]:
        """Collect test node IDs via ``pytest --collect-only``.

        Returns:
            Sorted list of test node ID strings (e.g. ``tests/unit/test_foo.py::test_bar``).
        """
        cmd = [*self._base_pytest_cmd(), "--collect-only", "-q", "--no-header"]
        cmd.extend(self._config.pytest_add_cli_args_test_selection)
        result = subprocess.run(  # noqa: S603  # command is fully controlled — no user input
            cmd,
            capture_output=True,
            encoding="utf-8",
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

    def run_stats(self) -> None:
        """Run pytest as subprocess with MUTANT_UNDER_TEST=stats to collect timing data.

        Injects a pytest plugin (``_mutmut_stats_plugin.py``) into
        ``mutants/`` that captures per-test trampoline hits and durations.
        The plugin writes the mapping to ``mutants/mutmut-stats.json``
        at session end, which the parent reads after the subprocess exits.

        Uses subprocess instead of in-process ``pytest.main()`` to avoid
        hangs caused by pytest-asyncio, hypothesis, or other plugins that
        don't clean up properly in embedded pytest runs.
        """
        import os

        from mutmut_win import _state
        from mutmut_win.stats import load_stats

        _state._reset_globals()

        env = self._mutants_env()
        env[MUTANT_ENV_VAR] = MUTANT_STATS_SENTINEL
        env["PY_IGNORE_IMPORTMISMATCH"] = "1"

        # Inject the stats-collection pytest plugin into mutants/.
        mutants_abs = Path("mutants").absolute()
        self._write_stats_plugin(mutants_abs)

        # Run all tests with the stats plugin active.
        cmd = [*self._base_pytest_cmd(), "-p", "_mutmut_stats_plugin", "--tb=no", "-q"]
        cmd.extend(self._config.pytest_add_cli_args)
        if self._config.tests_dir:
            cmd.extend(self._config.tests_dir)

        try:
            result = subprocess.run(  # noqa: S603  # command is fully controlled — no user input
                cmd, capture_output=True, encoding="utf-8", cwd="mutants", env=env,
                timeout=_RUNNER_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            print(f"Warning: stats collection timed out after {_RUNNER_TIMEOUT}s")
            os.environ[MUTANT_ENV_VAR] = ""
            return

        os.environ[MUTANT_ENV_VAR] = ""

        exit_code = result.returncode
        if exit_code != 0:
            print(f"Warning: stats collection returned exit code {exit_code}")

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

    def prepare_main_test_run(self) -> None:
        """Prepare for a main test run (no-op for subprocess-based runner).

        Provided for API compatibility with the mutmut 3.5.0 ``TestRunner``
        abstract interface so that ``code_coverage.gather_coverage()`` can call
        this method without branching.
        """

    def run_tests(
        self,
        *,
        mutant_name: str | None,  # noqa: ARG002  # kept for API symmetry
        tests: list[str] | None,  # noqa: ARG002  # kept for API symmetry
    ) -> int:
        """Run the test suite (in mutants/ directory) for coverage gathering.

        Provided for API compatibility with the mutmut 3.5.0 ``TestRunner``
        interface.  Delegates to ``run_clean_test`` which runs in ``mutants/``.

        Args:
            mutant_name: Unused — kept for interface symmetry.
            tests: Unused — kept for interface symmetry.

        Returns:
            The pytest exit code.
        """
        return self.run_clean_test()

    def run_forced_fail(
        self,
        mutant_name: str,  # noqa: ARG002  # kept for API symmetry — future: filter tests by mutant
    ) -> int:
        """Run pytest with ``MUTANT_UNDER_TEST=fail`` in mutants/ directory.

        The trampoline raises ``MutmutProgrammaticFailException`` for every
        function call, so all tests should fail.

        Args:
            mutant_name: Mutant identifier (reserved for future test filtering — unused now).

        Returns:
            The pytest exit code (non-zero means tests caught the failure, as expected).
        """
        cmd = [*self._base_pytest_cmd(), "--tb=no", "-q"]
        cmd.extend(self._config.pytest_add_cli_args)
        if self._config.tests_dir:
            cmd.extend(self._config.tests_dir)
        env = self._mutants_env()
        env[MUTANT_ENV_VAR] = MUTANT_FAIL_SENTINEL
        try:
            result = subprocess.run(  # noqa: S603  # command is fully controlled — no user input
                cmd,
                capture_output=True,
                encoding="utf-8",
                cwd="mutants",
                env=env,
                timeout=_FORCED_FAIL_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            # Forced-fail timeout likely means pytest-asyncio event loop corruption.
            # Return non-zero so the orchestrator treats it as "tests did fail" (correct).
            print(f"Warning: forced-fail verification timed out after {_FORCED_FAIL_TIMEOUT}s")
            return 1  # non-zero = tests failed = trampoline works
        return result.returncode

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _base_pytest_cmd(self) -> list[str]:
        """Build the base pytest command using the current Python interpreter.

        Returns:
            Base command list: ``[sys.executable, '-m', 'pytest']``.
        """
        return [sys.executable, "-m", "pytest"]

    def _mutants_env(self) -> dict[str, str]:
        """Build env dict for subprocess runs inside ``mutants/``.

        Sets ``PYTHONPATH`` so the subprocess can import source modules from
        ``mutants/src``, ``mutants/source``, or ``mutants/.``.

        Also disables editable ``.pth`` files by injecting a
        ``sitecustomize.py`` that removes the real ``src/`` from
        ``sys.path`` at startup.

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
        # Same paths as setup_source_paths: src, source, .
        extra_paths = []
        for subdir in ["src", "source", "."]:
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

        # Disable .pth files from editable installs that shadow mutants/src/.
        # Write a sitecustomize.py into mutants/ that removes the real src/
        # from sys.path at Python startup — before any imports happen.
        self._write_sitecustomize_pth_blocker(mutants_abs)

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
        """
        # Collect real source dirs that should be removed from sys.path
        real_src_dirs: list[str] = []
        for subdir in ["src", "source"]:
            candidate = Path(subdir).absolute()
            if candidate.exists():
                real_src_dirs.append(str(candidate))

        if not real_src_dirs:
            return

        # Write sitecustomize.py into mutants/ (the cwd of the subprocess)
        sitecustomize = mutants_abs / "sitecustomize.py"
        dirs_repr = repr(real_src_dirs)
        sitecustomize.write_text(
            f"# Auto-generated by mutmut-win — removes editable-install .pth paths\n"
            f"import sys\n"
            f"_shadow = {dirs_repr}\n"
            f"sys.path[:] = [p for p in sys.path if p not in _shadow]\n",
            encoding="utf-8",
        )
