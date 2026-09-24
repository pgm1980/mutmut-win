"""Staging follow-up-run benchmark for the retain policy (AP-02 / issue #144).

Measures ``copy_src_dir`` in the scenario the retain policy changes most:
a follow-up run without ``--force`` where every target already carries
trampolined generator output plus an owned ``.meta`` sidecar from a previous
run (``mutate_only_covered_lines=True`` restores all of them; a CLI subset
run restores the deselected half).

Run with::

    uv run pytest benchmarks/test_staging_benchmark.py --benchmark-only

Values are recorded in issue #144 and the sprint backlog (P-18: measure on
the unchanged code first, then after the fix).
"""

from __future__ import annotations

import contextlib
import hashlib
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from mutmut_win.config import MutmutConfig
from mutmut_win.file_setup import copy_src_dir
from mutmut_win.models import SourceFileMutationData

if TYPE_CHECKING:
    from collections.abc import Iterator

    from pytest_benchmark.fixture import BenchmarkFixture

#: Number of source modules in the synthetic project.
_MODULE_COUNT = 25

_SOURCE = "def add(a, b):\n    return a + b\n"
_GENERATED = (
    "# trampolined generator output (benchmark fixture)\n"
    + _SOURCE
    + "\ndef _mutmut_trampoline():\n    return add\n"
)


def _hash_bytes(payload: bytes) -> str:
    """Return the hex sha256 of *payload* (metadata fixture helper)."""
    return hashlib.sha256(payload).hexdigest()


def _build_project(root: Path) -> None:
    """Create the synthetic project with pre-generated staging state."""
    package = root / "src" / "benchpkg"
    package.mkdir(parents=True)
    mutants_package = root / "mutants" / "src" / "benchpkg"
    mutants_package.mkdir(parents=True)
    for index in range(_MODULE_COUNT):
        name = f"mod{index:02d}.py"
        source = package / name
        source.write_text(_SOURCE, encoding="utf-8")
        staged = mutants_package / name
        staged.write_text(_GENERATED, encoding="utf-8")
        metadata = SourceFileMutationData(
            path=f"src/benchpkg/{name}",
            source_hash=_hash_bytes(_SOURCE.encode("utf-8")),
            generation_fingerprint="a" * 64,
            generated_hash=_hash_bytes(_GENERATED.encode("utf-8")),
        )
        metadata.save_generation_metadata()


@pytest.fixture
def staging_project() -> Iterator[Path]:
    """Yield a fresh synthetic project root with cwd switched into it."""
    with tempfile.TemporaryDirectory(prefix="mutmut-staging-bench-") as name:
        root = Path(name).resolve()
        _build_project(root)
        with contextlib.chdir(root):
            yield root


def test_followup_run_coverage_mode_copy_src_dir(
    benchmark: BenchmarkFixture, staging_project: Path
) -> None:
    """copy_src_dir with mutate_only_covered_lines=True over pre-generated staging."""
    assert staging_project.is_dir()
    config = MutmutConfig(
        paths_to_mutate=["src"],
        max_children=1,
        mutate_only_covered_lines=True,
    )

    def run() -> None:
        copy_src_dir(config)

    benchmark.pedantic(run, rounds=5, iterations=1)


def test_followup_run_subset_selection_copy_src_dir(
    benchmark: BenchmarkFixture, staging_project: Path
) -> None:
    """copy_src_dir with half of the modules deselected via do_not_mutate."""
    assert staging_project.is_dir()
    config = MutmutConfig(
        paths_to_mutate=["src"],
        max_children=1,
        do_not_mutate=[f"src/benchpkg/mod{index:02d}.py" for index in range(0, _MODULE_COUNT, 2)],
    )

    def run() -> None:
        copy_src_dir(config)

    benchmark.pedantic(run, rounds=5, iterations=1)


def test_followup_run_plain_retain_copy_src_dir(
    benchmark: BenchmarkFixture, staging_project: Path
) -> None:
    """copy_src_dir keeping every target retained (the historical fast shape)."""
    assert staging_project.is_dir()
    config = MutmutConfig(paths_to_mutate=["src"], max_children=1)

    def run() -> None:
        copy_src_dir(config)

    benchmark.pedantic(run, rounds=5, iterations=1)
