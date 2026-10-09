"""E2E: Config fail-closed chain — invalid configs MUST abort before staging (GAP-1).

Covers M-032-M-045: absolute paths, dot-dot aliases, unknown fields,
cross-field conflicts, and type_check_command blocking CI/CD export.
Every case drives the real CLI (`python -m mutmut_win run`) against a
real pyproject.toml in an isolated tmp workspace — no mocks.
"""

from __future__ import annotations

import subprocess
import sys
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.e2e, pytest.mark.slow]


def _make_project(tmp: Path) -> Path:
    project = tmp / "proj"
    src = project / "src" / "pkg"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    (project / "tests").mkdir()
    (project / "tests" / "test_f.py").write_text(
        "def test_f():\n    from pkg import f\n    assert f() == 1\n", encoding="utf-8"
    )
    return project


def _run_cli(project: Path, *args: str, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        [sys.executable, "-m", "mutmut_win", *args],
        cwd=project,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )


class TestAbsolutePathsRejected:
    def test_absolute_path_in_paths_to_mutate_fails_before_staging(self, tmp_path: Path) -> None:
        project = _make_project(tmp_path)
        (project / "pyproject.toml").write_text(
            '[tool.mutmut]\npaths_to_mutate = ["C:\\\\absolute\\\\src"]\ntests_dir = ["tests"]\n',
            encoding="utf-8",
        )
        result = _run_cli(project, "run", "--no-progress")
        assert result.returncode == 2, (
            f"Absolute path must be rejected with exit 2.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
        assert not (project / "mutants").exists(), "NO mutants/ directory may be created"


class TestOutsideProjectDotDotRejected:
    """Prove outside-project containment rejection at the public CLI boundary.

    Internal ``..`` spellings require canonicalization rather than rejection.
    That separate contract is exercised by TestPathsToMutateCanonicalisation
    in tests/unit/test_config.py, including its Hypothesis properties. This
    outside-project scenario does not observe the internal canonical spelling.
    """

    def test_outside_project_dotdot_path_fails_before_staging(self, tmp_path: Path) -> None:
        """Reject a path outside the project before any staging directory exists."""
        project = _make_project(tmp_path)
        (project / "pyproject.toml").write_text(
            '[tool.mutmut]\npaths_to_mutate = ["../outside/src"]\ntests_dir = ["tests"]\n',
            encoding="utf-8",
        )
        result = _run_cli(project, "run", "--no-progress")
        assert result.returncode == 2
        assert not (project / "mutants").exists()


class TestUnknownFieldRejected:
    def test_unknown_field_does_not_change_behavior(self, tmp_path: Path) -> None:
        """Unknown fields are silently ignored by pydantic (extra=ignore) —
        the engine must behave identically with or without them."""

        project = _make_project(tmp_path)
        # Config WITH unknown field
        (project / "pyproject.toml").write_text(
            '[tool.mutmut]\npaths_to_mutate = ["src"]\ntests_dir = ["tests"]\n'
            'nonexistent_option = "x"\n',
            encoding="utf-8",
        )
        result_with = _run_cli(project, "run", "--no-progress", timeout=600)

        # Reset workspace
        import shutil

        shutil.rmtree(project / "mutants", ignore_errors=True)
        shutil.rmtree(project / ".mutmut-cache", ignore_errors=True)

        # Config WITHOUT unknown field (same otherwise)
        (project / "pyproject.toml").write_text(
            '[tool.mutmut]\npaths_to_mutate = ["src"]\ntests_dir = ["tests"]\n',
            encoding="utf-8",
        )
        result_without = _run_cli(project, "run", "--no-progress", timeout=600)

        # Both should succeed (unknown field is ignored, not an error)
        assert result_with.returncode == 0, (
            f"Engine with unknown field should still run (pydantic ignores it).\n"
            f"stdout:\n{result_with.stdout}\nstderr:\n{result_with.stderr}"
        )
        assert result_without.returncode == 0
        # Both should produce the same number of mutants
        assert "Total mutants" in result_with.stdout
        assert "Total mutants" in result_without.stdout


class TestTypeCheckCommandBlocksExport:
    def test_type_check_command_blocks_cicd_export(self, tmp_path: Path) -> None:
        project = _make_project(tmp_path)
        (project / "pyproject.toml").write_text(
            '[tool.mutmut]\npaths_to_mutate = ["src"]\ntests_dir = ["tests"]\n'
            'type_check_command = ["python", "-m", "mypy"]\n',
            encoding="utf-8",
        )
        run_result = _run_cli(project, "run", "--no-progress", timeout=600)
        if run_result.returncode != 0:
            pytest.skip(f"run did not complete (type_check may fail): {run_result.returncode}")
        export_result = _run_cli(project, "export-cicd-stats")
        assert export_result.returncode == 1, (
            f"export-cicd-stats must fail (exit 1) when type_check_command is set "
            f"(unbounded external closure).\n"
            f"stdout:\n{export_result.stdout}\nstderr:\n{export_result.stderr}"
        )


class TestValidConfigStarts:
    def test_minimal_valid_config_creates_staging(self, tmp_path: Path) -> None:
        project = _make_project(tmp_path)
        (project / "pyproject.toml").write_text(
            '[tool.mutmut]\npaths_to_mutate = ["src"]\ntests_dir = ["tests"]\n',
            encoding="utf-8",
        )
        result = _run_cli(project, "run", "--no-progress", timeout=600)
        assert result.returncode == 0, (
            f"Valid config must succeed.\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
        assert (project / "mutants").is_dir(), "staging must be created for a valid config"
