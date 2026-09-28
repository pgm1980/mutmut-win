"""Coverage gating for ``mutate_only_covered_lines`` (Issue #95).

The pre-v2.9.0 implementation collected coverage in the PARENT process while
pytest ran in a subprocess (dead since the subprocess rewrite, A3-CM-003):
``lines()`` returned nothing, every mutant was filtered, and the run ended
with an uncaused "No mutants generated."

The reworked flow is a subprocess bridge: the runner executes the suite
under ``coverage run --data-file=<fresh external temp dir>/.coverage.mutmut``
inside ``mutants/`` (which at that point holds the UNMUTATED copies — line
numbers are identical to the original sources the mutant generator filters
against), and the parent merges every data file written to the exclusive
output directory — ``parallel = true`` parts, including measurements from
coverage-spawned ``multiprocessing`` children, are combined.  Measured keys
are matched canonically: a relative key (the staged project config may set
``relative_files = true``) is first bound to ``mutants/`` — the coverage
subprocess cwd — then ``os.path.realpath`` folds filesystem aliases (8.3
short names, subst drives) and ``os.path.normcase`` folds case, on both
sides.  Returned keys stay plain ``os.path.normcase``(absolute), so lookups
via :func:`get_covered_lines_for_file` are unchanged (A3-CM-013,
spike-verified: a case-deviating key returns ``None`` from ``lines()``).

Failure modes are LOUD by design — a broken collection must never silently
degrade into "0 mutants".

Known limits (documented in the README): code exercised only via
test-spawned subprocesses or pytest-xdist workers is not measured; an
all-empty measurement therefore raises instead of filtering everything.
Coverage's own child processes (``concurrency = multiprocessing``) ARE
measured — their parallel data parts are merged, which can surface more
covered mutants than a parent-process-only measurement would.
"""

from __future__ import annotations

import os
import tempfile
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


def _canonical_measured_key(raw: str, mutants_dir: Path) -> str:
    """Return the canonical matching key for a raw coverage path key.

    Args:
        raw: Path key exactly as coverage stored it.  With
            ``relative_files = true`` in the project coverage configuration
            this is RELATIVE to the coverage subprocess cwd (``mutants/``),
            e.g. ``"src\\pkg\\mod.py"``; otherwise it is absolute.
        mutants_dir: Absolute staged tree root (the coverage subprocess cwd)
            that relative keys are bound to.

    Returns:
        ``os.path.normcase`` of ``os.path.realpath`` of the bound path, so
        that relative/absolute, case-deviating, and 8.3/subst-aliased forms
        of one file collapse onto a single key.  Used for MATCHING only —
        returned coverage mappings keep :func:`_normalized_key` form.
    """
    key = Path(raw)
    if not key.is_absolute():
        key = mutants_dir / key
    return os.path.normcase(os.path.realpath(key))


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


def _merge_measured_lines(data_candidates: list[Path], mutants_dir: Path) -> dict[str, set[int]]:
    """Merge fresh coverage data files into one canonical-keyed line map.

    ``parallel = true`` in the project coverage configuration (forced as
    well by ``concurrency = multiprocessing``) makes the coverage subprocess
    write ``.coverage.mutmut.<host>.pid<n>.X<random>`` parts instead of one
    suffixless file.  Every candidate is read through the configuration-free
    :class:`coverage.CoverageData` API and united file-wise: per-file
    ``lines()`` unions tolerate a mix of arc and line data across parts,
    which ``CoverageData.update`` would reject with a ``DataError``.

    Args:
        data_candidates: Fresh data files from the exclusive output
            directory — nothing stale or foreign can be among them.
        mutants_dir: Absolute staged tree root that relative measured keys
            are bound to.

    Returns:
        Canonical-keyed (:func:`_canonical_measured_key`) covered-lines map;
        line sets of colliding keys are unioned.

    Raises:
        CoverageCollectionError: If any candidate cannot be read
            (fail-closed; the file name is named in the message).
    """
    measured: dict[str, set[int]] = {}
    for candidate in data_candidates:
        part = coverage.CoverageData(basename=str(candidate))
        try:
            part.read()
            for measured_file in part.measured_files():
                key = _canonical_measured_key(measured_file, mutants_dir)
                measured[key] = measured.get(key, set()) | set(part.lines(measured_file) or [])
        except coverage.CoverageException as exc:
            raise CoverageCollectionError(
                f"coverage data file {candidate.name} is unreadable — "
                f"the measurement cannot be combined."
            ) from exc
    return measured


def gather_coverage(runner: _CoverageRunner, source_files: Iterable[str]) -> dict[str, set[int]]:
    """Collect per-file covered lines via the subprocess coverage bridge.

    Args:
        runner: Runner exposing ``run_coverage_collection(data_file)``.
        source_files: Project-relative paths of the files to be mutated.

    Returns:
        Mapping of normcased absolute mutants-paths to covered line sets.

    Raises:
        CoverageCollectionError: If the collection run fails, leaves no data
            file in the output directory, a data file is unreadable, or no
            coverage was measured in any source file — either because
            nothing was executed at all (e.g. subprocess- or xdist-based
            suites, whose execution the bridge cannot see) or because no
            measured path matches a staged source file.
            Bare ``Exception`` until issue #114 / A4-QX-023.
    """
    # Coverage output is coordination state, never executable staging input.
    # A fresh external directory also prevents stale/parallel data from being
    # merged into the current line authority.
    with tempfile.TemporaryDirectory(
        prefix="mutmut-win-coverage-output-",
        ignore_cleanup_errors=True,
    ) as output_name:
        data_file = (Path(output_name) / ".coverage.mutmut").absolute()
        exit_code = runner.run_coverage_collection(data_file)
        if exit_code != 0:
            raise CoverageCollectionError(
                f"coverage collection run failed with exit code {exit_code} — "
                f"the test suite must pass before mutate_only_covered_lines can "
                f"measure it."
            )
        # parallel=true writes suffixed parts instead of one suffixless
        # file; SQLite sidecars of a crashed run are never data.
        data_candidates = sorted(
            part_file
            for part_file in data_file.parent.iterdir()
            if part_file.name == ".coverage.mutmut"
            or (
                part_file.name.startswith(".coverage.mutmut.")
                and not part_file.name.endswith(("-journal", "-wal", "-shm"))
            )
        )
        if not data_candidates:
            raise CoverageCollectionError(
                "coverage collection produced no data file — coverage did not record anything."
            )

        mutants_dir = Path("mutants").absolute()
        measured = _merge_measured_lines(data_candidates, mutants_dir)

    covered_lines: dict[str, set[int]] = {}
    matched_any_source = False
    for filename in source_files:
        measured_key = _canonical_measured_key(str(mutants_dir / filename), mutants_dir)
        if measured_key in measured:
            matched_any_source = True
        covered_lines[_normalized_key(filename)] = measured.get(measured_key, set())

    if covered_lines and not any(covered_lines.values()):
        if matched_any_source or not any(measured.values()):
            raise CoverageCollectionError(
                "coverage collection measured no coverage in any source file — "
                "suites that run their code in subprocesses or pytest-xdist "
                "workers are not supported with mutate_only_covered_lines "
                "(their execution is invisible to the bridge)."
            )
        raise CoverageCollectionError(
            "coverage collection measured no coverage in any source file — no "
            f"measured path matches a staged source path (expected e.g. "
            f"{next(iter(covered_lines))!r}, measured e.g. {sorted(measured)[0]!r})."
        )

    return covered_lines
