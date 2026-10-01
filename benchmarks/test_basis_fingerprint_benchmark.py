"""Execution-basis fingerprint cost benchmark (AR-12 / M-101 / PERF-004).

A ``mutmut-win run`` that reaches the terminal status ``completed`` builds
the execution basis FIVE times with identical semantics over the same
files (orchestrator.py: prelude double pass, step-3 stats fingerprint,
final double pass):

======= ========================== ==========================================
pass    call                       where
======= ========================== ==========================================
1 / 5   ``build_run_basis_evidence``    prelude snapshot A (watched)
2 / 5   ``build_run_basis_evidence``    prelude snapshot B (stability pair)
3 / 5   ``build_stats_context_fingerprint``  step 3, timing-stats context
4 / 5   ``build_run_basis_evidence``    end comparison snapshot A
5 / 5   ``build_run_basis_evidence``    end comparison snapshot B
======= ========================== ==========================================

This benchmark records the CURRENT state (delivered stage 1: watchdog
containment only).  Stage 1 wraps the passes in the stall watchdog — that
is containment, NOT an acceleration, and nothing here claims a speedup
from it.  Stage 2 (lazy end comparison, 5 -> 4 passes) and any digest
memoisation remain deferred by decision B (P-08 / M-064 / M-101); the
numbers produced here are the "before" evidence that this decision
requires.  No percentage saving is asserted: the receipt only reports
measured wall/CPU time per pass.

Dataset (synthetic, offline, byte-reproducible)
-----------------------------------------------

The measured input set is fully synthetic so the run needs no network,
no git oracle and no real site-packages, and can be repeated on any
machine with CPython 3.14:

* **project** (walked as the run workspace, cwd): ``pyproject.toml``,
  ``src/benchpkg/__init__.py`` (160 B), 25 modules ``mod00..24.py``
  (1024 B each), ``tests/test_bench.py`` (512 B).
* **site-packages** (the only real sys.path entry besides ``""`` during
  measurement): 131 distributions named ``benchdist001..benchdist131``
  (count rebuilt after the review reference environment), version scheme
  ``1.<i%7>.<i%13>``.  Each carries ``__init__.py`` (160 B), ``core.py``
  (4096 B), ``helpers.py`` (2560 B), ``_native.pyd`` (32768 B binary
  payload) plus a ``.dist-info`` with METADATA / WHEEL / RECORD (proper
  sha256 inventory, so ``importlib.metadata.distributions()`` binds every
  file); every 9th distribution adds ``resources/data<i>.json`` (3072 B).
* all payload bytes are derived deterministically from sha256 counters —
  byte-identical on every run of this module (file mtimes are hashed per
  observation, so digests are stable within one run, not across machines).
* per pass the engine reads the project files twice (context stream plus
  project-core stream, because ``""`` — the flat-layout project root — is
  on sys.path) and every site-packages file once (distribution inventory;
  the later sys.path content walk re-stats but re-reads nothing), plus
  the interpreter executable, ``os.environ`` and distribution identity
  strings (constant-size non-file inputs, reported separately).

``sys.path`` is pinned to ``["", <synthetic site-packages>]`` around each
measured call so neither the host stdlib nor any real environment leaks
into the measurement.

Cold vs warm
------------

True OS-cold page caches cannot be produced portably on Windows; the
fixture writes the dataset immediately before measurement, so the coldest
observable state is the FIRST execution in a fresh process (cold
importlib/FastPath and boundary caches; page cache pre-warmed by the
fixture writes).  That first execution is instrumented and printed per
pass; the pytest-benchmark rounds that follow are the warm measurements.
Per-round durations are preserved via ``--benchmark-json``.

Run with::

    uv run pytest benchmarks/test_basis_fingerprint_benchmark.py \\
        --benchmark-only -s

Before/after comparisons (e.g. for the deferred stage-2 decision) must
run this file unmodified on the same machine, runtime and dataset shape;
the ``[ar12] dataset:`` line in the output proves the file/byte totals
being compared.
"""

from __future__ import annotations

import base64
import contextlib
import hashlib
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from mutmut_win.config import MutmutConfig
from mutmut_win.db import DEFAULT_DB_PATH
from mutmut_win.stats import build_run_basis_evidence, build_stats_context_fingerprint

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from pytest_benchmark.fixture import BenchmarkFixture

#: Distributions in the synthetic site-packages (review reference count).
_DISTRIBUTION_COUNT = 131

#: Modules in the synthetic project package.
_PROJECT_MODULE_COUNT = 25

#: Deterministic payload sizes (bytes) per file class.
_INIT_SIZE = 160
_MODULE_SIZE = 1024
_CORE_SIZE = 4096
_HELPER_SIZE = 2560
_NATIVE_SIZE = 32768
_RESOURCE_SIZE = 3072
_TEST_SIZE = 512

#: Every Nth distribution additionally carries a resource file.
_RESOURCE_EVERY = 9


def _synthetic_text(seed: int, size: int) -> str:
    """Return ``size`` ASCII bytes derived deterministically from *seed*."""
    lines: list[str] = []
    written = 0
    counter = seed
    while written < size:
        line = f"# ar12 synthetic payload {counter:08d} {'x' * (counter % 31 + 1)}\n"
        lines.append(line)
        written += len(line)
        counter += 7
    return "".join(lines)[:size]


def _synthetic_binary(seed: int, size: int) -> bytes:
    """Return ``size`` deterministic bytes derived from a sha256 counter."""
    payload = bytearray()
    counter = seed
    while len(payload) < size:
        payload += hashlib.sha256(counter.to_bytes(8, "big")).digest()
        counter += 1
    return bytes(payload[:size])


def _record_hash(payload: bytes) -> str:
    """Return the PEP 376 RECORD hash column for *payload*."""
    encoded = base64.urlsafe_b64encode(hashlib.sha256(payload).digest())
    return f"sha256={encoded.rstrip(b'=').decode('ascii')}"


@dataclass(frozen=True)
class _DatasetInventory:
    """Exact file/byte totals of the synthetic dataset (verify by re-walk)."""

    distribution_count: int
    project_files: int
    project_bytes: int
    site_files: int
    site_bytes: int

    @property
    def hashed_files(self) -> int:
        """Files read per pass (dataset + interpreter executable)."""
        return self.project_files + self.site_files + 1

    @property
    def dataset_bytes(self) -> int:
        """Dataset bytes reported per pass (every file counted once).

        The second project read (core stream) and the interpreter
        executable are additional reads not included in this total.
        """
        return self.project_bytes + self.site_bytes


def _write_file(path: Path, payload: bytes) -> tuple[int, int]:
    """Write *payload* (creating parents) and return (files, bytes)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return 1, len(payload)


def _distribution_version(index: int) -> str:
    """Deterministic version scheme: ``1.<i%7>.<i%13>``."""
    return f"1.{index % 7}.{index % 13}"


def _build_project(project_root: Path) -> tuple[int, int]:
    """Create the synthetic run workspace; return (files, bytes)."""
    files = 0
    total_bytes = 0
    for relative, payload in (
        (
            "pyproject.toml",
            b"[project]\nname = 'benchproj'\nversion = '1.0'\nrequires-python = '==3.14.7'\n",
        ),
        ("src/benchpkg/__init__.py", _synthetic_text(1, _INIT_SIZE).encode()),
        ("tests/test_bench.py", _synthetic_text(3, _TEST_SIZE).encode()),
    ):
        written_files, written_bytes = _write_file(project_root / relative, payload)
        files += written_files
        total_bytes += written_bytes
    for index in range(_PROJECT_MODULE_COUNT):
        module = _synthetic_text(100 + index, _MODULE_SIZE).encode()
        written_files, written_bytes = _write_file(
            project_root / "src" / "benchpkg" / f"mod{index:02d}.py", module
        )
        files += written_files
        total_bytes += written_bytes
    return files, total_bytes


def _build_site(site_root: Path) -> tuple[int, int]:
    """Create the synthetic site-packages; return (files, bytes)."""
    files = 0
    total_bytes = 0
    for index in range(1, _DISTRIBUTION_COUNT + 1):
        name = f"benchdist{index:03d}"
        version = _distribution_version(index)
        payload: dict[str, bytes] = {
            f"{name}/__init__.py": _synthetic_text(index * 10, _INIT_SIZE).encode(),
            f"{name}/core.py": _synthetic_text(index * 20, _CORE_SIZE).encode(),
            f"{name}/helpers.py": _synthetic_text(index * 30, _HELPER_SIZE).encode(),
            f"{name}/_native.pyd": _synthetic_binary(index * 40, _NATIVE_SIZE),
        }
        if index % _RESOURCE_EVERY == 0:
            payload[f"{name}/resources/data{index:03d}.json"] = _synthetic_text(
                index * 50, _RESOURCE_SIZE
            ).encode()
        dist_info = f"{name}-{version}.dist-info"
        payload[f"{dist_info}/METADATA"] = (
            f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n".encode()
        )
        payload[f"{dist_info}/WHEEL"] = (
            b"Wheel-Version: 1.0\nGenerator: ar12-benchmark\n"
            b"Root-Is-Purelib: true\nTag: py3-none-any\n"
        )
        record_lines = [
            f"{relative},{_record_hash(data)},{len(data)}"
            for relative, data in sorted(payload.items())
        ]
        record_lines.append(f"{dist_info}/RECORD,,")
        payload[f"{dist_info}/RECORD"] = ("\n".join(record_lines) + "\n").encode()
        for relative, data in payload.items():
            written_files, written_bytes = _write_file(site_root / relative, data)
            files += written_files
            total_bytes += written_bytes
    return files, total_bytes


def _tree_stats(root: Path) -> tuple[int, int]:
    """Return (files, bytes) of every regular file below *root*."""
    entries = [path for path in root.rglob("*") if path.is_file()]
    return len(entries), sum(path.stat().st_size for path in entries)


@dataclass(frozen=True)
class _BasisEnvironment:
    """Synthetic workspace plus the config a real run would fingerprint."""

    project_root: Path
    site_root: Path
    config: MutmutConfig
    excluded_paths: tuple[Path, ...]
    inventory: _DatasetInventory


@contextlib.contextmanager
def _hermetic_sys_path(site_root: Path) -> Iterator[None]:
    """Pin sys.path to the flat project root plus the synthetic site only."""
    saved = list(sys.path)
    try:
        sys.path[:] = ["", str(site_root)]
        yield
    finally:
        sys.path[:] = saved


@dataclass(frozen=True)
class _PassResult:
    """One instrumented basis pass: wall/CPU time plus observed outcome."""

    label: str
    wall_s: float
    cpu_s: float
    digest: str
    complete: bool


def _timed_call(label: str, call: Callable[[], tuple[str, bool]]) -> _PassResult:
    """Execute *call* once, measuring wall and CPU time around it."""
    wall_start = time.perf_counter()
    cpu_start = time.process_time()
    digest, complete = call()
    wall_s = time.perf_counter() - wall_start
    cpu_s = time.process_time() - cpu_start
    return _PassResult(label, wall_s, cpu_s, digest, complete)


def _run_basis_pass(environment: _BasisEnvironment) -> tuple[str, bool]:
    """One ``build_run_basis_evidence`` pass (prelude/end shape)."""
    evidence = build_run_basis_evidence(
        environment.config, excluded_paths=environment.excluded_paths
    )
    return evidence.digest, evidence.complete


def _stats_context_pass(environment: _BasisEnvironment) -> tuple[str, bool]:
    """One ``build_stats_context_fingerprint`` pass (step-3 shape)."""
    fingerprint = build_stats_context_fingerprint(
        environment.config, excluded_paths=environment.excluded_paths
    )
    return fingerprint, True


def _five_pass_sequence(environment: _BasisEnvironment) -> list[_PassResult]:
    """Execute the five real basis builds of one completed run, in order."""
    with _hermetic_sys_path(environment.site_root):
        plan: tuple[tuple[str, Callable[[], tuple[str, bool]]], ...] = (
            (
                "pass 1/5 prelude-a   build_run_basis_evidence",
                lambda: _run_basis_pass(environment),
            ),
            (
                "pass 2/5 prelude-b   build_run_basis_evidence",
                lambda: _run_basis_pass(environment),
            ),
            (
                "pass 3/5 step-3      build_stats_context_fingerprint",
                lambda: _stats_context_pass(environment),
            ),
            (
                "pass 4/5 end-a       build_run_basis_evidence",
                lambda: _run_basis_pass(environment),
            ),
            (
                "pass 5/5 end-b       build_run_basis_evidence",
                lambda: _run_basis_pass(environment),
            ),
        )
        return [_timed_call(label, call) for label, call in plan]


def _report_dataset(environment: _BasisEnvironment) -> None:
    """Print the dataset identity line every before/after run must match."""
    inventory = environment.inventory
    executable_bytes = Path(sys.executable).stat().st_size
    print(
        f"[ar12] dataset: distributions={inventory.distribution_count} "
        f"project_files={inventory.project_files} project_bytes={inventory.project_bytes} "
        f"site_files={inventory.site_files} site_bytes={inventory.site_bytes} "
        f"hashed_files_per_pass={inventory.hashed_files} "
        f"dataset_bytes={inventory.dataset_bytes} "
        f"interpreter_executable_bytes={executable_bytes} (machine-dependent)"
    )


def _report_pass(result: _PassResult, files: int, payload_bytes: int) -> None:
    """Print one measured pass with wall/CPU time and throughput."""
    throughput = payload_bytes / result.wall_s
    print(
        f"[ar12] {result.label}: wall={result.wall_s:.4f}s cpu={result.cpu_s:.4f}s "
        f"files={files} bytes={payload_bytes} complete={result.complete} "
        f"throughput={throughput / (1024 * 1024):.2f} MiB/s digest={result.digest[:12]}…"
    )


def _pedantic(benchmark: BenchmarkFixture, run: Callable[[], None], *, rounds: int) -> None:
    """``benchmark.pedantic`` with one iteration per round.

    pytest-benchmark 5.2.3 ships ``py.typed`` but leaves ``pedantic``
    itself unannotated; this helper keeps the single ``type: ignore``
    site required for a mypy-strict benchmarks directory.
    """
    benchmark.pedantic(run, rounds=rounds, iterations=1)  # type: ignore[no-untyped-call]


@pytest.fixture(scope="module")
def basis_environment(
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[_BasisEnvironment]:
    """Yield the synthetic dataset with cwd switched into the project."""
    root = tmp_path_factory.mktemp("ar12-basis-bench")
    project_root = root / "project"
    site_root = root / "site-packages"
    project_files, project_bytes = _build_project(project_root)
    site_files, site_bytes = _build_site(site_root)
    inventory = _DatasetInventory(
        distribution_count=_DISTRIBUTION_COUNT,
        project_files=project_files,
        project_bytes=project_bytes,
        site_files=site_files,
        site_bytes=site_bytes,
    )
    assert _tree_stats(project_root) == (inventory.project_files, inventory.project_bytes)
    assert _tree_stats(site_root) == (inventory.site_files, inventory.site_bytes)
    # Mirror the orchestrator's cache-database exclusions (none of these
    # exist in the synthetic workspace; they only shape the call).
    database = (project_root / DEFAULT_DB_PATH).absolute()
    excluded_paths = (
        database,
        Path(f"{database}-journal"),
        Path(f"{database}-wal"),
        Path(f"{database}-shm"),
    )
    with contextlib.chdir(project_root):
        config = MutmutConfig(paths_to_mutate=["src"], max_children=1)
        yield _BasisEnvironment(
            project_root=project_root,
            site_root=site_root,
            config=config,
            excluded_paths=excluded_paths,
            inventory=inventory,
        )


def test_completed_run_five_pass_sequence(
    benchmark: BenchmarkFixture, basis_environment: _BasisEnvironment
) -> None:
    """Cost of the five real basis builds of one completed run (stage 1).

    The instrumented first execution (coldest observable state in this
    process, see module docstring) prints the per-pass wall/CPU table the
    AR-12 receipt archives; the pytest-benchmark rounds that follow are
    the warm sequence measurements.  Watchdog containment is not counted
    as an acceleration anywhere.
    """
    environment = basis_environment
    _report_dataset(environment)
    results = _five_pass_sequence(environment)
    for result in results:
        _report_pass(
            result,
            environment.inventory.hashed_files,
            environment.inventory.dataset_bytes,
        )
    basis_results = (results[0], results[1], results[3], results[4])
    assert all(result.complete for result in results)
    assert len({result.digest for result in basis_results}) == 1, (
        "the synthetic basis must be stable across all four run-basis passes"
    )
    benchmark.extra_info["first_sequence"] = [
        {
            "label": result.label,
            "wall_s": round(result.wall_s, 6),
            "cpu_s": round(result.cpu_s, 6),
            "complete": result.complete,
        }
        for result in results
    ]

    def sequence() -> None:
        _five_pass_sequence(environment)

    _pedantic(benchmark, sequence, rounds=3)


def test_run_basis_evidence_pass_warm(
    benchmark: BenchmarkFixture, basis_environment: _BasisEnvironment
) -> None:
    """Warm cost of one ``build_run_basis_evidence`` pass (pass 1/2/4/5)."""
    environment = basis_environment
    with _hermetic_sys_path(environment.site_root):
        first = _timed_call("run-basis first", lambda: _run_basis_pass(environment))

        def run() -> None:
            _run_basis_pass(environment)

        _pedantic(benchmark, run, rounds=5)
    assert first.complete
    _report_pass(first, environment.inventory.hashed_files, environment.inventory.dataset_bytes)
    benchmark.extra_info["first_execution"] = {
        "wall_s": round(first.wall_s, 6),
        "cpu_s": round(first.cpu_s, 6),
    }


def test_stats_context_fingerprint_pass_warm(
    benchmark: BenchmarkFixture, basis_environment: _BasisEnvironment
) -> None:
    """Warm cost of one ``build_stats_context_fingerprint`` pass (step 3)."""
    environment = basis_environment
    with _hermetic_sys_path(environment.site_root):
        first = _timed_call("stats-context first", lambda: _stats_context_pass(environment))

        def run() -> None:
            _stats_context_pass(environment)

        _pedantic(benchmark, run, rounds=5)
    assert first.complete
    _report_pass(first, environment.inventory.hashed_files, environment.inventory.dataset_bytes)
    benchmark.extra_info["first_execution"] = {
        "wall_s": round(first.wall_s, 6),
        "cpu_s": round(first.cpu_s, 6),
    }
