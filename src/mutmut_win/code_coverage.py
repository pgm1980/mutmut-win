"""Coverage gating for ``mutate_only_covered_lines`` (Issue #95).

The pre-v2.9.0 implementation collected coverage in the PARENT process while
pytest ran in a subprocess (dead since the subprocess rewrite, A3-CM-003):
``lines()`` returned nothing, every mutant was filtered, and the run ended
with an uncaused "No mutants generated."

The reworked flow is a subprocess bridge: the runner executes the suite
under ``coverage run --data-file=<mutants>/.coverage.mutmut`` inside
``mutants/`` (which at that point holds the UNMUTATED copies — line numbers
are identical to the original sources the mutant generator filters against),
and the parent loads the data file.  All path keys are ``os.path.normcase``d:
coverage stores the filesystem case form, and a case-deviating lookup key
returns ``None`` from ``lines()`` (A3-CM-013, spike-verified).

Failure modes are LOUD by design — a broken collection must never silently
degrade into "0 mutants".

Known limits (documented in the README): code exercised only via
test-spawned subprocesses or pytest-xdist workers is not measured; an
all-empty measurement therefore raises instead of filtering everything.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

import coverage

from mutmut_win.exceptions import CoverageCollectionError

if TYPE_CHECKING:
    from collections.abc import Iterable


class _CoverageRunner(Protocol):
    """The slice of ``PytestRunner`` the coverage bridge needs."""

    def run_coverage_collection(self, data_file: Path) -> int:
        """Run the suite under ``coverage run``; return the exit code."""
        ...


def _normalized_key(filename: str) -> str:
    """Return the normcased absolute mutants-path key for *filename*.

    Args:
        filename: Source path relative to the project root (and therefore to
            ``mutants/``), e.g. ``"src/pkg/mod.py"``.

    Returns:
        ``os.path.normcase`` of the absolute path under ``mutants/``.
    """
    return os.path.normcase(str((Path("mutants") / filename).absolute()))


def get_covered_lines_for_file(
    filename: str, covered_lines: dict[str, set[int]] | None
) -> set[int] | None:
    """Look up the covered lines for *filename* in a normcased mapping.

    Args:
        filename: Source path relative to the project root.
        covered_lines: Mapping produced by :func:`gather_coverage`, or
            ``None`` when coverage gating is disabled.

    Returns:
        ``None`` if gating is disabled (or *filename* is ``None``); the
        covered line numbers otherwise — an empty set means the file was
        never executed, so ALL of its mutants are filtered (untested code).
    """
    if covered_lines is None or filename is None:
        return None
    return covered_lines.get(_normalized_key(filename), set())


def gather_coverage(runner: _CoverageRunner, source_files: Iterable[str]) -> dict[str, set[int]]:
    """Collect per-file covered lines via the subprocess coverage bridge.

    Args:
        runner: Runner exposing ``run_coverage_collection(data_file)``.
        source_files: Project-relative paths of the files to be mutated.

    Returns:
        Mapping of normcased absolute mutants-paths to covered line sets.

    Raises:
        CoverageCollectionError: If the collection run fails, produces no
            data file, or measures no coverage in any source file (e.g.
            subprocess- or xdist-based suites, whose execution the bridge
            cannot see). Bare ``Exception`` until issue #114 / A4-QX-023.
    """
    data_file = Path("mutants").absolute() / ".coverage.mutmut"
    if data_file.exists():
        data_file.unlink()  # fresh measurement, no --append semantics

    exit_code = runner.run_coverage_collection(data_file)
    if exit_code != 0:
        raise CoverageCollectionError(
            f"coverage collection run failed with exit code {exit_code} — "
            f"the test suite must pass before mutate_only_covered_lines can "
            f"measure it."
        )
    if not data_file.exists():
        raise CoverageCollectionError(
            "coverage collection produced no data file — coverage did not record anything."
        )

    cov = coverage.Coverage(data_file=str(data_file))
    cov.load()
    coverage_data = cov.get_data()
    measured = {
        os.path.normcase(f): set(coverage_data.lines(f) or [])
        for f in coverage_data.measured_files()
    }

    covered_lines: dict[str, set[int]] = {}
    for filename in source_files:
        covered_lines[_normalized_key(filename)] = measured.get(_normalized_key(filename), set())

    if covered_lines and not any(covered_lines.values()):
        raise CoverageCollectionError(
            "coverage collection measured no coverage in any source file — "
            "suites that run their code in subprocesses or pytest-xdist "
            "workers are not supported with mutate_only_covered_lines "
            "(their execution is invisible to the bridge)."
        )

    return covered_lines
