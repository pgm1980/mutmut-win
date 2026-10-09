"""Unit tests for process hygiene: staging invariance of pool start (M-107)
and the worker's pytest command (audit A4-QX-008)."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING
from unittest.mock import patch

from mutmut_win.config import MutmutConfig
from mutmut_win.process.executor import SpawnPoolExecutor
from mutmut_win.process.worker import _pytest_base_cmd
from mutmut_win.pytest_boundary import prepare_pytest_boundary

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


class _FakeWorkerProcess:
    """In-process worker stand-in: start() must not spawn a real interpreter."""

    def __init__(self) -> None:
        self._alive = False
        self.pid: int | None = None

    def start(self) -> None:
        self._alive = True
        self.pid = 99999

    def is_alive(self) -> bool:
        return self._alive

    def kill(self) -> None:
        self._alive = False

    def join(self, timeout: float | None = None) -> None:  # noqa: ARG002  # signature of multiprocessing.Process.join
        self._alive = False

    def close(self) -> None:
        self._alive = False


class TestStartDoesNotTouchStaging:
    """M-107: after the staging snapshot is frozen, no engine component may
    modify ``mutants/``.  ``start()`` used to delete ``mutmut_out_*.log`` /
    ``mutmut_tests_*.txt`` from the staging root — files that can be live,
    mirrored project content and are part of the hashed evidence between
    snapshot and final validation."""

    def test_start_leaves_staging_files_untouched(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        mutants = tmp_path / "mutants"
        mutants.mkdir()
        argfile = mutants / "mutmut_tests_user.txt"
        log = mutants / "mutmut_out_user.log"
        argfile.write_text("tests/test_x.py\n", encoding="utf-8")
        log.write_text("user output\n", encoding="utf-8")

        config = MutmutConfig()
        executor = SpawnPoolExecutor(max_workers=1, config=config)
        boundary = prepare_pytest_boundary(
            project_root=tmp_path,
            staging_root=mutants,
            tests_dir=list(config.tests_dir),
        )
        executor.configure_pytest_boundary(boundary.to_dict())
        try:
            with patch.object(executor, "_make_worker_process", return_value=_FakeWorkerProcess()):
                executor.start([])
            assert argfile.read_text(encoding="utf-8") == "tests/test_x.py\n"
            assert log.read_text(encoding="utf-8") == "user output\n"
        finally:
            executor.shutdown(timeout=10.0)


class TestWorkerPytestCommand:
    def test_uses_sys_executable_module_invocation(self) -> None:
        """A4-QX-008: bare 'pytest' from PATH can hit a different interpreter
        than the venv the clean gate validated — pin sys.executable."""
        cmd = _pytest_base_cmd()
        assert cmd[:5] == [sys.executable, "--check-hash-based-pycs", "always", "-m", "pytest"]
        assert "--tb=no" in cmd
        assert "-q" in cmd
