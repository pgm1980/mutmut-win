"""Unit tests for process hygiene (Issue #82): stale-artifact sweep and the
worker's pytest command (audit A2-EW-007, A4-QX-008)."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from mutmut_win.process.executor import _sweep_stale_artifacts
from mutmut_win.process.worker import _pytest_base_cmd

if TYPE_CHECKING:
    from pathlib import Path


class TestStaleArtifactSweep:
    def test_removes_stale_logs_and_argfiles_only(self, tmp_path: Path) -> None:
        mutants = tmp_path / "mutants"
        mutants.mkdir()
        (mutants / "mutmut_out_abc123.log").write_text("stale", encoding="utf-8")
        (mutants / "mutmut_tests_xyz.txt").write_text("stale", encoding="utf-8")
        (mutants / "keep_me.log").write_text("keep", encoding="utf-8")
        (mutants / "mutmut-stats.json").write_text("{}", encoding="utf-8")

        _sweep_stale_artifacts(mutants)

        assert not (mutants / "mutmut_out_abc123.log").exists()
        assert not (mutants / "mutmut_tests_xyz.txt").exists()
        assert (mutants / "keep_me.log").exists()
        assert (mutants / "mutmut-stats.json").exists()

    def test_missing_mutants_dir_is_a_noop(self, tmp_path: Path) -> None:
        _sweep_stale_artifacts(tmp_path / "does_not_exist")  # must not raise


class TestWorkerPytestCommand:
    def test_uses_sys_executable_module_invocation(self) -> None:
        """A4-QX-008: bare 'pytest' from PATH can hit a different interpreter
        than the venv the clean gate validated — pin sys.executable."""
        cmd = _pytest_base_cmd()
        assert cmd[:3] == [sys.executable, "-m", "pytest"]
        assert "--tb=no" in cmd
        assert "-q" in cmd
