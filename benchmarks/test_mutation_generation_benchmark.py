"""Performance benchmarks for mutmut-win mutation generation (closes #23).

These benchmarks measure the throughput of the core ``mutate_file_contents``
function on the bundled E2E reference fixtures. They establish a baseline so
future commits can be flagged for performance regressions.

Run with:

    uv run pytest benchmarks/ --benchmark-only

The output is a pytest-benchmark table (mean / median / min / max / stddev /
ops/s / rounds). Results can be saved to JSON via ``--benchmark-save=NAME``
and compared across runs with ``--benchmark-compare``.

Comparison against upstream ``mutmut 3.5.0`` is out of scope here — that
would require installing both tools in the same environment and is left as
a manual exercise. The pytest-benchmark output of these tests is the
reference shape that such a comparison would use.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from mutmut_win.mutation import mutate_file_contents

if TYPE_CHECKING:
    from pytest_benchmark.fixture import BenchmarkFixture

#: Project-root-relative paths to the source files under benchmark.
_E2E_PROJECTS_DIR = Path(__file__).parent.parent / "tests" / "e2e_projects"

_BENCH_FIXTURES = [
    pytest.param(
        _E2E_PROJECTS_DIR / "simple_lib" / "src" / "simple_lib" / "__init__.py",
        id="simple_lib",
    ),
    pytest.param(
        _E2E_PROJECTS_DIR / "my_lib" / "src" / "my_lib" / "__init__.py",
        id="my_lib",
    ),
]


@pytest.mark.parametrize("source_path", _BENCH_FIXTURES)
def test_mutate_file_contents_throughput(
    benchmark: BenchmarkFixture, source_path: Path
) -> None:
    """Measure ``mutate_file_contents`` throughput on the reference fixtures.

    Captures the wall-clock cost of full CST parse + mutation generation +
    trampoline injection for each fixture, which is the inner loop of the
    full ``mutmut-win run`` pipeline.
    """
    source = source_path.read_text(encoding="utf-8")

    result = benchmark(mutate_file_contents, str(source_path), source)

    _mutated_code, mutant_names = result
    assert mutant_names, (
        f"Benchmark generated 0 mutants for {source_path.name} — "
        "fixture content unexpectedly empty or generation regressed."
    )
