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
        env = self._mutants_env()
        env[MUTANT_ENV_VAR] = ""
        result = subprocess.run(  # noqa: S603  # command is fully controlled — no user input
            cmd,
            capture_output=True,
            encoding="utf-8",
            cwd="mutants",
            env=env,
        )
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
        """Run pytest in-process with StatsCollector plugin to track trampoline hits.

        Sets ``MUTANT_UNDER_TEST=stats`` so the trampoline records which
        mangled function names are called by each test.  After this method
        completes, ``_state.tests_by_mangled_function_name`` and
        ``_state.duration_by_test`` are populated.
        """
        import os

        import pytest

        from mutmut_win import _state
        from mutmut_win.file_setup import strip_prefix

        _state._reset_globals()
        os.environ[MUTANT_ENV_VAR] = MUTANT_STATS_SENTINEL
        os.environ["PY_IGNORE_IMPORTMISMATCH"] = "1"

        class StatsCollector:
            """Pytest plugin that maps trampoline hits to test node IDs."""

            def pytest_runtest_teardown(  # type: ignore[no-untyped-def]
                self,
                item,
                nextitem,  # noqa: ARG002  # nextitem required by hook signature
            ) -> None:
                """Record trampoline hits accumulated during this test."""
                for function in _state._stats:
                    _state.tests_by_mangled_function_name[function].add(
                        strip_prefix(item._nodeid, prefix="mutants/")
                    )
                _state._stats.clear()

            def pytest_runtest_makereport(  # type: ignore[no-untyped-def]
                self, item, call
            ) -> None:
                """Accumulate per-test duration across setup/call/teardown phases."""
                _state.duration_by_test[item.nodeid] = (
                    _state.duration_by_test.get(item.nodeid, 0.0) + call.duration
                )

        stats_collector = StatsCollector()
        pytest_args = ["-x", "-q", "--rootdir=.", "--tb=native"]
        pytest_args += self._config.pytest_add_cli_args
        pytest_args += self._config.tests_dir

        if self._config.debug:
            pytest_args = ["-vv", *pytest_args]

        old_cwd = Path.cwd()
        os.chdir("mutants")
        try:
            exit_code = int(pytest.main(pytest_args, plugins=[stats_collector]))
        finally:
            os.chdir(old_cwd)

        os.environ[MUTANT_ENV_VAR] = ""

        if exit_code != 0:
            print(f"Warning: stats collection returned exit code {exit_code}")

        # Verify we got some test-to-mutant mappings.
        num_mapped = sum(len(t) for t in _state.tests_by_mangled_function_name.values())
        if num_mapped == 0:
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
        env = self._mutants_env()
        env[MUTANT_ENV_VAR] = MUTANT_FAIL_SENTINEL
        result = subprocess.run(  # noqa: S603  # command is fully controlled — no user input
            cmd,
            capture_output=True,
            encoding="utf-8",
            cwd="mutants",
            env=env,
        )
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
        ``mutants/src``, ``mutants/source``, or ``mutants/.``.  This is the
        subprocess equivalent of ``setup_source_paths()`` which manipulates
        ``sys.path`` in-process.

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
        return env
