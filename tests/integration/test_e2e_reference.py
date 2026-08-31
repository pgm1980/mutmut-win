"""Reference E2E tests pinning mutmut-win's mutation generation on 5 real projects.

For each reference project from the mutmut test suite we copy it to a temp
directory and run mutmut-win's generation under both profiles, then assert
*layered profile invariants* against the checked-in snapshot (the historical,
externally-validated v2.14 generation):

  1. advanced ⊇ snapshot  — no-regression floor: advanced never drops a
     validated mutant.
  2. basic ⊆ snapshot      — basic-parity purity: the base profile (the mutmut
     3.5.0 port) emits only validated mutants. Skipped where the snapshot was
     coverage-filtered (there basic legitimately exceeds the filtered subset).
  3. basic ⊆ advanced      — profile monotonicity.
  4. len(advanced) == N    — an exact per-project advanced count: the
     interaction-drift brake (one number per wave) that the per-operator
     acceptance tests in test_advanced_operators.py cannot see.

This keeps the suite stable across advanced-operator waves (each wave shifts
``advanced`` by design) while still anchoring on the validated snapshot.
advanced *exactness* lives per-operator in test_advanced_operators.py plus the
counts in invariant (4). Only mutation *generation* is tested here — execution
and exit codes are covered by test_e2e.py.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

from mutmut_win.constants import Profile
from mutmut_win.mutation import mutate_file_contents
from tests.e2e_projects.expected_results import (
    EXPECTED_CONFIG,
    EXPECTED_COVERAGE,
    EXPECTED_MY_LIB,
    EXPECTED_PY3_14,
    EXPECTED_TYPE_CHECKING,
)

#: Root of the checked-in reference E2E projects.
_E2E_PROJECTS_DIR = Path(__file__).parent.parent / "e2e_projects"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _copy_project(name: str, tmp_path: Path) -> Path:
    """Copy a reference project to *tmp_path* and return the project root.

    Args:
        name: Sub-directory name under ``tests/e2e_projects/``.
        tmp_path: pytest-provided temporary directory.

    Returns:
        Path to the copied project root inside *tmp_path*.
    """
    src = _E2E_PROJECTS_DIR / name
    dst = tmp_path / name
    shutil.copytree(src, dst)
    return dst


def _collect_mutant_names(source_file: Path, profile: Profile) -> set[str]:
    """Run mutation generation on *source_file* under *profile* and return the names.

    Args:
        source_file: Path to a Python source file to mutate.
        profile: The mutation profile to generate under (BASIC or ADVANCED).

    Returns:
        Set of mutant function names (without module prefix), e.g.
        ``{"x_hello__mutmut_1", "x_hello__mutmut_2"}``.
    """
    code = source_file.read_text(encoding="utf-8")
    _mutated_code, mutant_names = mutate_file_contents(
        str(source_file), code, active_profile=profile
    )
    return set(mutant_names)


def _expected_local_names(expected: dict[str, dict[str, int]]) -> set[str]:
    """Extract the function-name portion (after the last dot) from all snapshot keys.

    The snapshot keys have the form ``module.x_func__mutmut_N``.  mutmut-win's
    ``mutate_file_contents`` returns only the local part, so we strip the
    module prefix for comparison.

    Args:
        expected: A snapshot dict mapping file keys to ``{mutant_name: exit_code}``.

    Returns:
        Set of local mutant names across all file entries in *expected*.
    """
    names: set[str] = set()
    for mutant_map in expected.values():
        for full_name in mutant_map:
            # full_name example: "my_lib.x_hello__mutmut_1"
            # local part:        "x_hello__mutmut_1"
            local = full_name.rpartition(".")[-1]
            names.add(local)
    return names


def _assert_profile_layered(
    source_files: list[Path],
    snapshot: dict[str, dict[str, int]],
    expected_advanced_count: int,
    expected_all_count: int,
    *,
    basic_within_snapshot: bool = True,
    w5_static_prefixes: tuple[str, ...] = (),
) -> None:
    """Assert the layered profile invariants for one reference project.

    Args:
        source_files: Source files of the project to mutate (one or more).
        snapshot: The checked-in expected-results dict for the project.
        expected_advanced_count: Exact number of advanced mutants — the
            interaction-drift brake. Bump it per advanced-operator wave.
        expected_all_count: Exact number of all-profile mutants — the same brake
            for the aggressive all-tier operators. Bump it per all-tier wave.
        basic_within_snapshot: Whether ``basic ⊆ snapshot`` must hold. False for
            coverage-filtered snapshots, where the snapshot is a subset of a
            full generation and basic legitimately exceeds it.
        w5_static_prefixes: Mangled-name prefixes of @staticmethod methods that
            the W5 backport mutates but the mutmut-3.5.0 snapshot (which skipped
            decorated methods) does not list — allowed beyond the snapshot in the
            basic-purity check.
    """
    basic = set().union(*(_collect_mutant_names(f, Profile.BASIC) for f in source_files))
    advanced = set().union(*(_collect_mutant_names(f, Profile.ADVANCED) for f in source_files))
    all_mutants = set().union(*(_collect_mutant_names(f, Profile.ALL) for f in source_files))
    snap = _expected_local_names(snapshot)

    # (1) no-regression floor: advanced keeps every validated snapshot mutant.
    floor_missing = snap - advanced
    assert not floor_missing, (
        f"advanced dropped {len(floor_missing)} validated snapshot mutant(s):\n"
        + "\n".join(f"  {n}" for n in sorted(floor_missing))
    )
    # (2) basic-parity purity: basic emits only validated mutants — except the
    # W5 @staticmethod-backport mutants, which mutmut-win generates by design but
    # the mutmut-3.5.0 snapshot (decorated methods skipped upstream) does not list.
    if basic_within_snapshot:
        basic_phantom = {
            n
            for n in basic - snap
            if not any(n.startswith(prefix) for prefix in w5_static_prefixes)
        }
        assert not basic_phantom, (
            f"basic emitted {len(basic_phantom)} mutant(s) absent from the validated snapshot:\n"
            + "\n".join(f"  {n}" for n in sorted(basic_phantom))
        )
    # (3) profile monotonicity: basic ⊆ advanced ⊆ all.
    mono_missing = basic - advanced
    assert not mono_missing, (
        f"advanced is missing {len(mono_missing)} basic mutant(s) (profile non-monotonic):\n"
        + "\n".join(f"  {n}" for n in sorted(mono_missing))
    )
    all_mono_missing = advanced - all_mutants
    assert not all_mono_missing, (
        f"all is missing {len(all_mono_missing)} advanced mutant(s) (profile non-monotonic):\n"
        + "\n".join(f"  {n}" for n in sorted(all_mono_missing))
    )
    # (4) advanced + all exact counts — interaction-drift brakes (one number per wave).
    assert len(advanced) == expected_advanced_count, (
        f"advanced mutant count drifted: expected {expected_advanced_count}, "
        f"got {len(advanced)}. If this is an intended advanced-operator change, "
        "update the expected count."
    )
    assert len(all_mutants) == expected_all_count, (
        f"all mutant count drifted: expected {expected_all_count}, got {len(all_mutants)}. "
        "If this is an intended all-tier change, update the expected count."
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.slow
def test_my_lib_mutation_generation(tmp_path: Path) -> None:
    """Pin layered profile invariants for my_lib.

    The my_lib project has a single source file with functions, a class, async
    generators, segfault-triggering code, and various edge-case patterns.
    """
    project_dir = _copy_project("my_lib", tmp_path)
    source_file = project_dir / "src" / "my_lib" / "__init__.py"

    _assert_profile_layered(
        [source_file],
        EXPECTED_MY_LIB,
        # MW220 correctness hardening removes rendered no-ops/duplicates and
        # conservatively excludes the async generator (its full protocol cannot
        # be delegated transparently without async ``yield from``).
        expected_advanced_count=128,
        expected_all_count=161,
        # W5 backport: Point.from_coords (@staticmethod) now mutates (+11) — the
        # mutmut-3.5.0 snapshot skipped it, so allow its mutants in basic-purity.
        w5_static_prefixes=("xǁPointǁfrom_coords__mutmut_",),
    )


@pytest.mark.integration
@pytest.mark.slow
def test_config_mutation_generation(tmp_path: Path) -> None:
    """Pin layered profile invariants for the config project.

    The config project has two source files (``__init__.py`` and ``math.py``)
    and exercises mutmut configuration options (paths_to_mutate, do_not_mutate,
    max_stack_depth, tests_dir).
    """
    project_dir = _copy_project("config", tmp_path)

    init_file = project_dir / "config_pkg" / "__init__.py"
    math_file = project_dir / "config_pkg" / "math.py"

    _assert_profile_layered(
        [init_file, math_file], EXPECTED_CONFIG, expected_advanced_count=30, expected_all_count=40
    )


@pytest.mark.integration
@pytest.mark.slow
def test_mutate_only_covered_lines_mutation_generation(tmp_path: Path) -> None:
    """Pin layered profile invariants for mutate_only_covered_lines.

    The reference snapshot was generated WITH coverage filtering, so it is a
    *subset* of a full generation. We generate WITHOUT coverage filtering here,
    so ``basic ⊆ snapshot`` does not hold (basic exceeds the filtered subset) —
    only the no-regression floor, monotonicity, and the advanced count apply.
    """
    project_dir = _copy_project("mutate_only_covered_lines", tmp_path)
    source_file = project_dir / "src" / "mutate_only_covered_lines" / "__init__.py"

    _assert_profile_layered(
        [source_file],
        EXPECTED_COVERAGE,
        # Rendered no-op/cross-operator deduplication intentionally removes two
        # score-distorting candidates from both profiles.
        expected_advanced_count=111,
        expected_all_count=125,
        basic_within_snapshot=False,
    )


@pytest.mark.integration
@pytest.mark.slow
def test_type_checking_mutation_generation(tmp_path: Path) -> None:
    """Pin layered profile invariants for the type_checking project.

    The type_checking project uses pyrefly/pyright to catch mutants via static
    type checking.  We only test that the mutants are *generated* correctly;
    type-check execution is not performed here.
    """
    project_dir = _copy_project("type_checking", tmp_path)
    source_file = project_dir / "src" / "type_checking" / "__init__.py"

    _assert_profile_layered(
        [source_file], EXPECTED_TYPE_CHECKING, expected_advanced_count=17, expected_all_count=20
    )


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.skipif(
    sys.version_info < (3, 14),
    reason="py3_14_features project requires Python >= 3.14",
)
def test_py3_14_features_mutation_generation(tmp_path: Path) -> None:
    """Pin layered profile invariants for the py3_14_features project.

    The py3_14_features project exercises Python 3.14-specific syntax and
    lazy annotation evaluation.  This test is skipped on Python < 3.14.
    """
    project_dir = _copy_project("py3_14_features", tmp_path)
    source_file = project_dir / "src" / "py3_14_features" / "__init__.py"

    _assert_profile_layered(
        [source_file], EXPECTED_PY3_14, expected_advanced_count=10, expected_all_count=14
    )
