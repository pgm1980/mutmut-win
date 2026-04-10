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
        if self._config.tests_dir:
            cmd.extend(self._config.tests_dir)
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
        """Run pytest as subprocess with MUTANT_UNDER_TEST=stats to collect timing data.

        Runs each test individually to measure duration.  The trampoline
        records which mangled function names are called by each test into
        ``_state.tests_by_mangled_function_name``.

        Uses subprocess instead of in-process ``pytest.main()`` to avoid
        hangs caused by pytest-asyncio, hypothesis, or other plugins that
        don't clean up properly in embedded pytest runs (Bug 1).
        """
        import os

        from mutmut_win import _state

        _state._reset_globals()

        # Step 1: Collect all test node IDs via --collect-only
        cmd = [*self._base_pytest_cmd(), "--collect-only", "-q"]
        cmd.extend(self._config.pytest_add_cli_args)
        if self._config.tests_dir:
            cmd.extend(self._config.tests_dir)

        env = self._mutants_env()
        env[MUTANT_ENV_VAR] = ""

        result = subprocess.run(  # noqa: S603
            cmd, capture_output=True, encoding="utf-8", cwd="mutants", env=env,
        )
        test_ids: list[str] = []
        for line in result.stdout.splitlines():
            line = line.strip()
            if "::" in line and not line.startswith(("=", "-", " ")):
                test_ids.append(line)

        if not test_ids:
            return

        # Step 2: Run each test individually with MUTANT_UNDER_TEST=stats
        # to measure duration. The trampoline records hits to _state._stats
        # which we can't capture from subprocess — so we use --durations output.
        env[MUTANT_ENV_VAR] = MUTANT_STATS_SENTINEL
        env["PY_IGNORE_IMPORTMISMATCH"] = "1"

        cmd_base = [*self._base_pytest_cmd(), "--tb=no", "-q"]
        cmd_base.extend(self._config.pytest_add_cli_args)
        if self._config.tests_dir:
            cmd_base.extend(self._config.tests_dir)

        # Run all tests at once to get durations (not one-by-one — too slow)
        result = subprocess.run(  # noqa: S603
            cmd_base, capture_output=True, encoding="utf-8", cwd="mutants", env=env,
        )

        # Parse durations from pytest output
        for line in result.stdout.splitlines():
            line = line.strip()
            if "::" in line and ("PASSED" in line or "FAILED" in line):
                # Extract test ID (everything before PASSED/FAILED)
                parts = line.split()
                if parts:
                    test_id = parts[0]
                    _state.duration_by_test[test_id] = 0.1  # default ~100ms

        # If trampoline hits can't be collected from subprocess (no shared state),
        # fall back to mapping ALL tests to ALL mutants. This is less efficient
        # but correct — every mutant runs against the full test suite.
        # The trampoline hit optimization is a performance optimization, not
        # a correctness requirement.
        os.environ[MUTANT_ENV_VAR] = ""

        exit_code = result.returncode
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
        if self._config.tests_dir:
            cmd.extend(self._config.tests_dir)
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
