"""Reference E2E tests verifying mutmut-win generates the same mutants as mutmut 3.5.0.

For each of the 5 reference projects from the mutmut test suite, we copy the
project to a temporary directory, invoke mutmut-win's mutation generation on
the source files, and compare the generated mutant names against the expected
snapshot keys from mutmut's own E2E tests.

Only mutation *generation* is tested here — not execution or exit codes.
The full pipeline (run + kill verification) requires pytest to be installed
in the project's environment and is covered by test_e2e.py.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

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


def _collect_mutant_names(source_file: Path) -> set[str]:
    """Run mutation generation on *source_file* and return the set of mutant names.

    Args:
        source_file: Path to a Python source file to mutate.

    Returns:
        Set of mutant function names (without module prefix), e.g.
        ``{"x_hello__mutmut_1", "x_hello__mutmut_2"}``.
    """
    code = source_file.read_text(encoding="utf-8")
    _mutated_code, mutant_names = mutate_file_contents(str(source_file), code)
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


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.slow
def test_my_lib_mutation_generation(tmp_path: Path) -> None:
    """Verify mutmut-win generates the same mutants as mutmut for my_lib.

    The my_lib project has a single source file with functions, a class, async
    generators, segfault-triggering code, and various edge-case patterns.
    """
    project_dir = _copy_project("my_lib", tmp_path)
    source_file = project_dir / "src" / "my_lib" / "__init__.py"

    generated = _collect_mutant_names(source_file)
    expected = _expected_local_names(EXPECTED_MY_LIB)

    missing = expected - generated
    extra = generated - expected

    assert not missing, (
        f"mutmut-win failed to generate {len(missing)} expected mutant(s):\n"
        + "\n".join(f"  {n}" for n in sorted(missing))
    )
    assert not extra, (
        f"mutmut-win generated {len(extra)} unexpected mutant(s) not in the reference snapshot:\n"
        + "\n".join(f"  {n}" for n in sorted(extra))
    )


@pytest.mark.integration
@pytest.mark.slow
def test_config_mutation_generation(tmp_path: Path) -> None:
    """Verify mutmut-win generates the same mutants as mutmut for the config project.

    The config project has two source files (``__init__.py`` and ``math.py``)
    and exercises mutmut configuration options (paths_to_mutate, do_not_mutate,
    max_stack_depth, tests_dir).
    """
    project_dir = _copy_project("config", tmp_path)

    init_file = project_dir / "config_pkg" / "__init__.py"
    math_file = project_dir / "config_pkg" / "math.py"

    generated = _collect_mutant_names(init_file) | _collect_mutant_names(math_file)
    expected = _expected_local_names(EXPECTED_CONFIG)

    missing = expected - generated
    extra = generated - expected

    assert not missing, (
        f"mutmut-win failed to generate {len(missing)} expected mutant(s):\n"
        + "\n".join(f"  {n}" for n in sorted(missing))
    )
    assert not extra, (
        f"mutmut-win generated {len(extra)} unexpected mutant(s) not in the reference snapshot:\n"
        + "\n".join(f"  {n}" for n in sorted(extra))
    )


@pytest.mark.integration
@pytest.mark.slow
def test_mutate_only_covered_lines_mutation_generation(tmp_path: Path) -> None:
    """Verify mutmut-win generates a superset of the mutmut reference mutants.

    The mutate_only_covered_lines project tests that mutmut only mutates lines
    covered by the test suite.  The reference snapshot was generated WITH
    coverage filtering, so it contains fewer mutants than a full generation.
    We test *generation* here WITHOUT coverage filtering, so we expect all
    reference mutants to be present (subset check) — plus additional ones
    from uncovered lines.
    """
    project_dir = _copy_project("mutate_only_covered_lines", tmp_path)
    source_file = project_dir / "src" / "mutate_only_covered_lines" / "__init__.py"

    generated = _collect_mutant_names(source_file)
    expected = _expected_local_names(EXPECTED_COVERAGE)

    missing = expected - generated

    assert not missing, (
        f"mutmut-win failed to generate {len(missing)} expected mutant(s):\n"
        + "\n".join(f"  {n}" for n in sorted(missing))
    )
    # NOTE: extra mutants are expected here because we generate without
    # coverage filtering while the reference snapshot was generated with it.
    assert generated >= expected, "Generated mutants must be a superset of expected."


@pytest.mark.integration
@pytest.mark.slow
def test_type_checking_mutation_generation(tmp_path: Path) -> None:
    """Verify mutmut-win generates the same mutants as mutmut for the type_checking project.

    The type_checking project uses pyrefly/pyright to catch mutants via static
    type checking.  We only test that the mutants are *generated* correctly;
    type-check execution is not performed here.
    """
    project_dir = _copy_project("type_checking", tmp_path)
    source_file = project_dir / "src" / "type_checking" / "__init__.py"

    generated = _collect_mutant_names(source_file)
    expected = _expected_local_names(EXPECTED_TYPE_CHECKING)

    missing = expected - generated
    extra = generated - expected

    assert not missing, (
        f"mutmut-win failed to generate {len(missing)} expected mutant(s):\n"
        + "\n".join(f"  {n}" for n in sorted(missing))
    )
    assert not extra, (
        f"mutmut-win generated {len(extra)} unexpected mutant(s) not in the reference snapshot:\n"
        + "\n".join(f"  {n}" for n in sorted(extra))
    )


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.skipif(
    sys.version_info < (3, 14),
    reason="py3_14_features project requires Python >= 3.14",
)
def test_py3_14_features_mutation_generation(tmp_path: Path) -> None:
    """Verify mutmut-win generates the same mutants as mutmut for the py3_14_features project.

    The py3_14_features project exercises Python 3.14-specific syntax and
    lazy annotation evaluation.  This test is skipped on Python < 3.14.
    """
    project_dir = _copy_project("py3_14_features", tmp_path)
    source_file = project_dir / "src" / "py3_14_features" / "__init__.py"

    generated = _collect_mutant_names(source_file)
    expected = _expected_local_names(EXPECTED_PY3_14)

    missing = expected - generated
    extra = generated - expected

    assert not missing, (
        f"mutmut-win failed to generate {len(missing)} expected mutant(s):\n"
        + "\n".join(f"  {n}" for n in sorted(missing))
    )
    assert not extra, (
        f"mutmut-win generated {len(extra)} unexpected mutant(s) not in the reference snapshot:\n"
        + "\n".join(f"  {n}" for n in sorted(extra))
    )
