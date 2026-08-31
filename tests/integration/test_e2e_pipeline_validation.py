"""Full-pipeline E2E validation tests (closes #38, #49).

These tests run the complete ``mutmut-win run`` pipeline as a subprocess on
the bundled reference fixtures (``simple_lib`` and ``my_lib``) and validate
the resulting per-mutant status against an expected snapshot.

The existing tests gave us two pieces in isolation:
- ``test_e2e_reference.py`` — mutation *generation* only, no run.
- ``test_e2e.py`` — full pipeline but only checks "at least one killed".

These tests close the gap: full pipeline + per-mutant comparison against
``tests/e2e_projects/expected_results.py``.

Marked ``slow`` + ``integration`` because each test runs ``mutmut-win run``
end-to-end against an isolated fixture copy (approximately 30-60 s per test).
"""

from __future__ import annotations

import shutil
import sqlite3
import subprocess
import sys
from contextlib import closing
from pathlib import Path

import pytest

from tests.e2e_projects.expected_results import EXPECTED_MY_LIB

_E2E_PROJECTS_DIR = Path(__file__).parent.parent / "e2e_projects"
_SIMPLE_LIB_DIR = _E2E_PROJECTS_DIR / "simple_lib"
_MY_LIB_DIR = _E2E_PROJECTS_DIR / "my_lib"

pytestmark = [pytest.mark.integration, pytest.mark.slow]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _copy_project(src: Path, tmp_path: Path) -> Path:
    """Copy a fixture project into *tmp_path* and return the destination root."""
    dst = tmp_path / src.name
    shutil.copytree(src, dst)
    return dst


def _run_mutmut_win(project_dir: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run ``mutmut-win`` inside *project_dir* with the given CLI args."""
    return subprocess.run(  # noqa: S603
        [sys.executable, "-m", "mutmut_win", *args],
        cwd=project_dir,
        capture_output=True,
        encoding="utf-8",
        timeout=180,
        check=False,
    )


def _read_mutant_statuses(project_dir: Path) -> dict[str, str]:
    """Return ``{mutant_name: status}`` from the project's cache database."""
    db_path = project_dir / ".mutmut-cache" / "mutmut-cache.db"
    if not db_path.exists():
        return {}
    with closing(sqlite3.connect(db_path)) as conn:
        rows = conn.execute("SELECT mutant_name, status FROM mutant").fetchall()
    return dict(rows)


def _flatten_expected_my_lib() -> dict[str, int]:
    """Flatten the per-file ``EXPECTED_MY_LIB`` dict into a single ``{name: code}`` map.

    Keys are kept fully qualified (``module.x_func__mutmut_N``) to match what
    the mutmut-win runtime persists in the SQLite cache database.
    """
    flat: dict[str, int] = {}
    for mutant_map in EXPECTED_MY_LIB.values():
        flat.update(mutant_map)
    return flat


_KILL_LIKE_STATUSES = {"killed", "caught by type check", "timeout", "suspicious"}


def _is_upstream_kill(expected_exit_code: int) -> bool:
    """``True`` if the upstream snapshot reports the mutant as killed/caught."""
    return expected_exit_code in {1, 37, -11}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_simple_lib_pipeline_no_survived_mutants(tmp_path: Path) -> None:
    """simple_lib has a complete test suite — every mutant must be killed.

    No expected snapshot exists for simple_lib (it's the trivial case), so the
    invariant we assert is the project's design property: a complete test
    suite must kill *every* mutant. ``survived`` mutants would mean a real
    regression in either mutmut-win or the simple_lib fixture.
    """
    project_dir = _copy_project(_SIMPLE_LIB_DIR, tmp_path)
    result = _run_mutmut_win(project_dir, "run", "--no-progress")
    assert result.returncode in {0, 1}, (
        f"mutmut-win run crashed with exit {result.returncode}.\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )

    statuses = _read_mutant_statuses(project_dir)
    assert statuses, f"No mutants in cache DB.\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"

    survived = [name for name, status in statuses.items() if status == "survived"]
    assert not survived, (
        f"{len(survived)} mutant(s) survived simple_lib's complete test suite — "
        f"either mutmut-win or the fixture regressed. Surviving mutants:\n"
        + "\n".join(f"  {n}" for n in sorted(survived))
    )


def test_my_lib_pipeline_matches_expected_snapshot(tmp_path: Path) -> None:
    """my_lib pipeline result must match the mutmut 3.5.0 reference snapshot.

    my_lib is the bigger fixture with intentional weak tests (``badly_tested``,
    ``untested``). The expected snapshot encodes which mutants should
    survive vs. be killed when the official mutmut runs against it. mutmut-win
    must reproduce the same distribution within platform-tolerance.

    Sprint 23 (#70 default-param skip) drops ``x_some_func__mutmut_4`` from
    the generation set — handled by ``_flatten_expected_my_lib`` keying on
    the mutant names that *are* still generated.
    """
    project_dir = _copy_project(_MY_LIB_DIR, tmp_path)
    # my_lib's pyproject.toml declares ``readme = "README.md"`` but the fixture
    # ships without one — drop a stub so the editable install can read metadata.
    readme = project_dir / "README.md"
    if not readme.exists():
        readme.write_text("# my_lib fixture\n", encoding="utf-8")
    result = _run_mutmut_win(
        project_dir,
        "run",
        "--no-progress",
        # The snapshot encodes mutmut 3.5.0's mutants, so pin the run to the
        # basic profile (mutmut's 15 base operators). advanced operators
        # (Phase 2+) insert mutants *inside* functions and renumber the rest —
        # wave-by-wave __mutmut_N drift that has nothing to do with pipeline
        # correctness. advanced generation is pinned by test_e2e_reference.py's
        # layered invariants instead.
        "--profile",
        "basic",
        "--paths-to-mutate",
        "src/my_lib/",
        "--tests-dir",
        "tests/",
    )
    assert result.returncode in {0, 1}, (
        f"mutmut-win run on my_lib crashed with exit {result.returncode}.\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )

    actual = _read_mutant_statuses(project_dir)
    expected = _flatten_expected_my_lib()

    # Restrict comparison to the intersection: mutants present in BOTH actual
    # generation (post-#70) and the expected snapshot.
    common = set(actual) & set(expected)
    assert common, (
        f"No overlap between generated mutants and expected snapshot.\n"
        f"actual sample: {list(actual)[:5]}\nexpected sample: {list(expected)[:5]}"
    )

    # Sanity 1: every common mutant has an actual status (no crashes/missing).
    no_status = [name for name in common if not actual[name]]
    assert not no_status, (
        f"{len(no_status)} common mutant(s) have no recorded status (pipeline "
        f"crashed before recording):\n" + "\n".join(f"  {n}" for n in no_status[:10])
    )

    # Sanity 2: one-directional kill-consistency. If upstream reports a mutant
    # as killed (exit_code in {1, 37, -11}), mutmut-win must also classify it as
    # kill-like — anything else would mean we lost detection power. The reverse
    # (mutmut-win killing what upstream marks survived) is acceptable: it just
    # means our test environment is stricter, which is a healthy direction.
    kill_regressions = []
    for name in sorted(common):
        status = actual[name]
        exit_code = expected[name]
        if _is_upstream_kill(exit_code) and status not in _KILL_LIKE_STATUSES:
            kill_regressions.append(
                f"  {name}: upstream killed (exit={exit_code}) but mutmut-win status={status!r}"
            )

    assert not kill_regressions, (
        f"{len(kill_regressions)} mutant(s) in my_lib lost detection vs. upstream snapshot:\n"
        + "\n".join(kill_regressions[:20])
        + (f"\n  …and {len(kill_regressions) - 20} more" if len(kill_regressions) > 20 else "")
    )

    # Sanity 3: at least 80 % of expected-killed mutants are also killed locally.
    # Cheap guard against a regression that lets many through without surfacing
    # as a hard kill-regression (e.g. moving everything to "no tests").
    expected_kills = {name for name in common if _is_upstream_kill(expected[name])}
    if expected_kills:
        actual_kills_in_subset = sum(
            1 for name in expected_kills if actual[name] in _KILL_LIKE_STATUSES
        )
        kill_ratio = actual_kills_in_subset / len(expected_kills)
        assert kill_ratio >= 0.8, (
            f"Only {actual_kills_in_subset}/{len(expected_kills)} "
            f"({kill_ratio:.0%}) of expected-killed mutants were killed locally. "
            f"Required minimum: 80 %."
        )
