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
from mutmut_win.file_setup import _iter_automatic_staging_inputs, copy_src_dir
from mutmut_win.models import SourceFileMutationData

if TYPE_CHECKING:
    from collections.abc import Iterator

    from pytest_benchmark.fixture import BenchmarkFixture

#: Number of source modules in the synthetic project.
_MODULE_COUNT = 25

#: Number of modules in the ignored mutation-root tree (AP-10 / M-032).
_FORCED_TREE_FILES = 50

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


def _build_forced_root_project(root: Path) -> None:
    """Add a git-ignored tree that ``paths_to_mutate`` force-includes.

    AP-10 / M-032: the mutation search walks ``generated/`` with
    ``descend_forced`` semantics; the automatic staging mirror must walk it
    through the same forced roots (additional walk cost to be benchmarked),
    and M-030 adds one ``lstat`` per staged directory and file.
    """
    _build_project(root)
    (root / ".gitignore").write_text("generated/\n", encoding="utf-8")
    generated = root / "generated"
    generated.mkdir()
    for index in range(_FORCED_TREE_FILES):
        (generated / f"gen{index:02d}.py").write_text(_SOURCE, encoding="utf-8")


@pytest.fixture
def forced_root_project() -> Iterator[Path]:
    """Yield a synthetic project whose mutation root is git-ignored."""
    with tempfile.TemporaryDirectory(prefix="mutmut-staging-forced-bench-") as name:
        root = Path(name).resolve()
        _build_forced_root_project(root)
        with contextlib.chdir(root):
            yield root


def test_iter_automatic_staging_inputs_plain(
    benchmark: BenchmarkFixture, staging_project: Path
) -> None:
    """Namespace preflight planning over the plain synthetic project."""
    assert staging_project.is_dir()

    def run() -> None:
        list(_iter_automatic_staging_inputs(frozenset()))

    benchmark.pedantic(run, rounds=5, iterations=1)


def test_iter_automatic_staging_inputs_with_forced_roots(
    benchmark: BenchmarkFixture, forced_root_project: Path
) -> None:
    """Namespace preflight planning including the forced mutation root (M-032)."""
    from mutmut_win.file_setup import _forced_mutation_roots
    from mutmut_win.gitignore_boundary import GitignoreBoundary

    assert forced_root_project.is_dir()
    project_root = forced_root_project.resolve()
    config = MutmutConfig(paths_to_mutate=["src", "generated"], max_children=1)
    forced_roots = _forced_mutation_roots(
        config, GitignoreBoundary.load(project_root), project_root
    )
    assert forced_roots

    def run() -> None:
        list(_iter_automatic_staging_inputs(frozenset(), forced_roots=forced_roots))

    benchmark.pedantic(run, rounds=5, iterations=1)


def test_followup_run_forced_root_copy_src_dir(
    benchmark: BenchmarkFixture, forced_root_project: Path
) -> None:
    """copy_src_dir follow-up run with a git-ignored mutation root (M-032)."""
    assert forced_root_project.is_dir()
    config = MutmutConfig(
        paths_to_mutate=["src", "generated"],
        max_children=1,
    )

    def run() -> None:
        copy_src_dir(config)

    benchmark.pedantic(run, rounds=5, iterations=1)


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


def test_streaming_copy_many_small_and_one_large_file(
    benchmark: BenchmarkFixture, tmp_path: Path
) -> None:
    """AP-33 / M-070 streaming scenario: many small files plus one large file.

    Baseline on the full-read path (2026-10-03, this machine): 300 small
    copies 0.695 s, one 24 MiB copy 0.029 s. The streaming rewrite trades
    ~16% on small files (extra per-file opens) for O(chunk) peak memory
    (tracemalloc proof in tests/unit/test_atomic_streaming_copy.py).
    """
    from mutmut_win.file_setup import _copy_with_retry

    source_dir = tmp_path / "src"
    target_dir = tmp_path / "dst"
    source_dir.mkdir()
    target_dir.mkdir()
    small_files = []
    for index in range(300):
        source = source_dir / f"mod_{index:04d}.py"
        source.write_bytes(b"x = 1\n" * 50)
        small_files.append((source, target_dir / source.name))
    large_source = source_dir / "large.bin"
    large_source.write_bytes(b"\0" * (24 * 1024 * 1024))
    large_target = target_dir / "large.bin"
    for source, target in small_files[:20]:  # warm-up
        _copy_with_retry(source, target)

    def run() -> None:
        for source, target in small_files:
            _copy_with_retry(source, target)
        _copy_with_retry(large_source, large_target)

    benchmark.pedantic(run, rounds=3, iterations=1)
