"""M-146: parent-managed run runtime root lifecycle (integration).

``SpawnPoolExecutor.start`` creates a run runtime root before any worker
spawns; per-task worker runtime directories live under it, and
``shutdown()`` removes the whole tree after a successful pool Job close —
covering exactly the workers that were hard-killed at the shutdown deadline
and therefore ran neither ``finally`` blocks nor finalizers.

The scenarios run out of process with a watchdog timeout so a regression
fails the test instead of hanging CI (same pattern as test_pool_shutdown).
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration

_DRIVER = textwrap.dedent(
    """
    import os
    import pathlib
    import sys
    import tempfile

    from mutmut_win.config import MutmutConfig
    from mutmut_win.process.executor import SpawnPoolExecutor
    from mutmut_win.pytest_boundary import prepare_pytest_boundary

    mode = sys.argv[2]

    def marker(text: str) -> None:
        print(f"M146:{text}", flush=True)

    def main() -> None:
        project = pathlib.Path(sys.argv[1])
        os.chdir(project)
        # Minimal staged project layout for a valid pytest boundary.
        (project / "mutants" / "tests").mkdir(parents=True, exist_ok=True)

        executor = SpawnPoolExecutor(max_workers=1, config=MutmutConfig())
        executor.configure_pytest_boundary(
            prepare_pytest_boundary(
                project_root=project,
                staging_root=project / "mutants",
                tests_dir=["tests"],
            ).to_dict()
        )
        if mode == "jobclose-fails":
            import mutmut_win.process.job_object as job_object

            def _boom(_handle: int) -> None:
                raise OSError("simulated job close failure")

            job_object.close_job = _boom

        # No tasks: the worker drains its sentinel immediately and exits.
        executor.start([])
        root = executor._runtime_root
        assert root is not None and root.is_dir(), "start() must create the root"
        marker(f"ROOT={root}")

        # Simulate a hard-killed worker's leftovers: a plain file, a
        # read-only file, and a junction pointing OUTSIDE the root.
        leftover = root / "mutmut-win-worker-runtime-leftover"
        leftover.mkdir()
        (leftover / "plain.txt").write_text("x", encoding="utf-8")
        readonly = leftover / "readonly.txt"
        readonly.write_text("x", encoding="utf-8")
        os.chmod(readonly, 0o444)
        outside = pathlib.Path(tempfile.mkdtemp(prefix="m146-outside-"))
        (outside / "keep.txt").write_text("precious", encoding="utf-8")
        junction = leftover / "junction"
        import _winapi

        _winapi.CreateJunction(str(outside), str(junction))

        executor.shutdown()

        marker(f"ROOT_EXISTS={root.exists()}")
        marker(f"OUTSIDE_INTACT={(outside / 'keep.txt').read_text(encoding='utf-8') == 'precious'}")
        # Manual cleanup of the outside dir (never touched by shutdown).
        import shutil

        shutil.rmtree(outside, ignore_errors=True)
        marker("DONE")

    if __name__ == "__main__":
        main()
    """
)


def _run_driver(mode: str, tmp_path: Path) -> dict[str, str]:
    project = tmp_path / "project"
    project.mkdir()
    result = subprocess.run(  # noqa: S603 - sys.executable with an in-tree driver
        [sys.executable, "-c", _DRIVER, str(project), mode],
        capture_output=True,
        text=True,
        timeout=120,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    markers: dict[str, str] = {}
    for line in result.stdout.splitlines():
        if line.startswith("M146:"):
            key, _, value = line[len("M146:") :].partition("=")
            markers[key] = value
    assert result.returncode == 0, f"driver failed:\n{result.stdout}\n{result.stderr}"
    return markers


class TestRunRuntimeRootLifecycle:
    def test_shutdown_removes_root_leftovers_and_never_follows_junctions(
        self, tmp_path: Path
    ) -> None:
        markers = _run_driver("ok", tmp_path)
        assert markers.get("DONE") == ""
        assert markers.get("ROOT_EXISTS") == "False"
        assert markers.get("OUTSIDE_INTACT") == "True"

    def test_failed_pool_job_close_leaves_root_in_place(self, tmp_path: Path) -> None:
        """With the pool Job close failed, pytest children may still hold
        files under the root; it stays for forensics instead of fighting
        locks (bounded, documented leak of exactly one directory)."""
        markers = _run_driver("jobclose-fails", tmp_path)
        assert markers.get("DONE") == ""
        assert markers.get("ROOT_EXISTS") == "True"
        assert markers.get("OUTSIDE_INTACT") == "True"
