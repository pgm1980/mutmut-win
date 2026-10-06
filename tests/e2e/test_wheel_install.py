"""E2E: Wheel-install boundary — build, install outside checkout, run (T9, TM-12).

Builds a real wheel, installs it into an isolated venv outside the checkout,
drives a full mutation run from that installation against a fixture project,
and verifies every imported mutmut_win module originates from the wheel.
"""

from __future__ import annotations

import json
import subprocess
import sys
import venv
from pathlib import Path

import pytest

from tests.e2e.e2e_util import SIMPLE_LIB, copy_project

pytestmark = [pytest.mark.e2e, pytest.mark.slow]

REPO_ROOT = Path(__file__).parent.parent.parent


class TestWheelInstallBoundary:
    """The built wheel is a self-contained product boundary (TM-12)."""

    @pytest.fixture(scope="class")
    def wheel_path(self, tmp_path_factory: pytest.TempPathFactory) -> Path:
        """Build the wheel once for all tests in this class."""

        dist_dir = tmp_path_factory.mktemp("dist")
        result = subprocess.run(  # noqa: S603
            [sys.executable, "-m", "hatchling", "build", "-t", "wheel", "-d", str(dist_dir)],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
            check=False,
        )
        assert result.returncode == 0, f"wheel build failed:\n{result.stdout}\n{result.stderr}"
        wheels = list(dist_dir.glob("*.whl"))
        assert len(wheels) == 1, f"expected exactly one wheel, got {wheels}"
        return wheels[0]

    @pytest.fixture(scope="class")
    def isolated_venv(self, tmp_path_factory: pytest.TempPathFactory, wheel_path: Path) -> Path:
        """Create an isolated venv outside the checkout with only the wheel."""

        venv_dir = tmp_path_factory.mktemp("wheel-venv")
        venv.create(venv_dir, with_pip=True)
        pip = venv_dir / "Scripts" / "pip"
        result = subprocess.run(  # noqa: S603
            [str(pip), "install", str(wheel_path), "pytest"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
            check=False,
        )
        assert result.returncode == 0, f"pip install failed:\n{result.stdout}\n{result.stderr}"
        return venv_dir

    def test_a_wheel_installs_and_imports(self, isolated_venv: Path) -> None:
        """The wheel-installed engine imports and reports its version."""

        python = isolated_venv / "Scripts" / "python"
        result = subprocess.run(  # noqa: S603
            [
                str(python),
                "-c",
                "import mutmut_win; "
                "print(getattr(mutmut_win, '__version__', 'ok'))",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
            check=False,
        )
        assert result.returncode == 0, f"import failed:\n{result.stdout}\n{result.stderr}"

    def test_b_modules_originate_from_wheel(self, isolated_venv: Path) -> None:
        """Every imported mutmut_win module lives inside the venv (wheel provenance)."""

        python = isolated_venv / "Scripts" / "python"
        probe = (
            "import mutmut_win, mutmut_win.cli, mutmut_win.db, mutmut_win.stats; "
            "import json, sys; "
            "mods = [mutmut_win, mutmut_win.cli, mutmut_win.db, mutmut_win.stats]; "
            "print(json.dumps([str(m.__file__) for m in mods]))"
        )
        result = subprocess.run(  # noqa: S603
            [str(python), "-c", probe],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
            check=False,
        )
        assert result.returncode == 0, f"provenance probe failed:\n{result.stdout}\n{result.stderr}"
        locations = json.loads(result.stdout.strip())
        venv_prefix = str(isolated_venv).lower()
        for location in locations:
            assert location.lower().startswith(venv_prefix), (
                f"module at {location} does not originate from the wheel venv {isolated_venv}"
            )

    def test_c_full_run_from_wheel(self, isolated_venv: Path, tmp_path: Path) -> None:
        """A complete mutation run succeeds from the wheel installation."""

        project = copy_project(SIMPLE_LIB, tmp_path)
        python = isolated_venv / "Scripts" / "python"
        result = subprocess.run(  # noqa: S603
            [str(python), "-m", "mutmut_win", "run", "--no-progress"],
            cwd=project,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=600,
            check=False,
        )
        assert result.returncode == 0, f"wheel run failed:\n{result.stdout}\n{result.stderr}"
        assert "Score" in result.stdout, "the run summary must be present"
