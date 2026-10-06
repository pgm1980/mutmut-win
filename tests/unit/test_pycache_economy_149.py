"""M-149: pycache reuse across pytest phases (compile economy).

Each `_run_phase` creates a fresh ephemeral pycache (PYTHONDONTWRITEBYTECODE=1
+ unique PYTHONPYCACHEPREFIX), forcing every phase to recompile the ~80 MB
trampolined staging tree.  The fix: a run-scoped shared pycache directory
that survives across phases; the first phase compiles + writes bytecode,
subsequent phases get cache hits.

Red proof: `configure_ephemeral_pytest_environment` has no shared_pycache
parameter; `_run_phase` always creates a fresh TemporaryDirectory.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from mutmut_win.process.worker import configure_ephemeral_pytest_environment

if TYPE_CHECKING:
    from pathlib import Path


class TestSharedPycacheParameter:
    """configure_ephemeral_pytest_environment accepts shared_pycache."""

    def test_shared_pycache_uses_provided_directory(self, tmp_path: Path) -> None:
        """With shared_pycache, PYTHONPYCACHEPREFIX points to it (not fresh)."""

        shared = tmp_path / "run-pycache"
        shared.mkdir()
        env: dict[str, str] = {}
        runtime_dir = tmp_path / "phase-runtime"
        runtime_dir.mkdir()

        configure_ephemeral_pytest_environment(env, runtime_dir, shared_pycache=shared)

        assert env.get("PYTHONPYCACHEPREFIX") == str(shared), (
            "PYTHONPYCACHEPREFIX must point to the shared run-scoped pycache"
        )

    def test_shared_pycache_allows_bytecode_writing(self, tmp_path: Path) -> None:
        """With shared_pycache, PYTHONDONTWRITEBYTECODE is not set to '1'."""

        shared = tmp_path / "run-pycache"
        shared.mkdir()
        env: dict[str, str] = {}
        runtime_dir = tmp_path / "phase-runtime"
        runtime_dir.mkdir()

        configure_ephemeral_pytest_environment(env, runtime_dir, shared_pycache=shared)

        assert env.get("PYTHONDONTWRITEBYTECODE") != "1", (
            "bytecode writing must be allowed when the pycache is shared "
            "across phases (M-149: the first phase writes, later phases read)"
        )

    def test_ephemeral_default_unchanged(self, tmp_path: Path) -> None:
        """Without shared_pycache, the ephemeral behavior is preserved."""

        env: dict[str, str] = {}
        runtime_dir = tmp_path / "phase-runtime"
        runtime_dir.mkdir()

        cache_dir = configure_ephemeral_pytest_environment(env, runtime_dir)

        assert env.get("PYTHONDONTWRITEBYTECODE") == "1"
        assert env.get("PYTHONPYCACHEPREFIX") != str(tmp_path)
        assert cache_dir.is_dir()


class TestRunnerPycacheReuse:
    """PytestRunner._run_phase forwards the shared pycache."""

    def test_run_phase_accepts_shared_pycache(self, tmp_path: Path) -> None:
        """_run_phase passes shared_pycache through to configure_ephemeral."""

        from mutmut_win.config import MutmutConfig
        from mutmut_win.runner import PytestRunner

        runner = PytestRunner(MutmutConfig(paths_to_mutate=["src/"]))
        shared = tmp_path / "run-pycache"
        shared.mkdir()
        captured_env: dict[str, str] = {}

        import contextlib
        from unittest.mock import patch

        original = configure_ephemeral_pytest_environment

        def capturing(env: dict[str, str], runtime_dir: Path, **kwargs: object) -> Path:
            captured_env.update(env)
            captured_env["_shared_pycache"] = str(kwargs.get("shared_pycache", ""))
            return original(env, runtime_dir, **kwargs)  # type: ignore[arg-type]

        with (
            patch(
                "mutmut_win.runner.configure_ephemeral_pytest_environment",
                side_effect=capturing,
            ),
            contextlib.suppress(Exception),
        ):
            try:
                runner._run_phase(
                    "test-phase",
                    ["python", "-c", "pass"],
                    {},
                    shared_pycache=shared,
                )
            except TypeError:
                pytest.fail(
                    "_run_phase must accept shared_pycache (M-149); "
                    "got TypeError — parameter not yet implemented"
                )

        assert captured_env.get("_shared_pycache") == str(shared)
