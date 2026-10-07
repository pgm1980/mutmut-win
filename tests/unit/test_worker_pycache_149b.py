"""M-149b: dispatch workers reuse the run-scoped shared pycache.

The executor forwards `_worker_shared_pycache` through config_data; the
worker's `_process_task` passes it to `configure_ephemeral_pytest_environment`
so every mutant's pytest child reads from the shared bytecode cache instead
of recompiling ~80 MB of trampolined source per mutant.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from mutmut_win.process.worker import configure_ephemeral_pytest_environment

if TYPE_CHECKING:
    from pathlib import Path


class TestWorkerSharedPycacheForwarding:
    """Worker reads _worker_shared_pycache from config_data and uses it."""

    def test_worker_env_gets_shared_pycache(self, tmp_path: Path) -> None:
        """When _worker_shared_pycache is in config, the pytest child env
        points PYTHONPYCACHEPREFIX at it and allows bytecode writing."""

        shared = tmp_path / "run-pycache"
        shared.mkdir()
        env: dict[str, str] = {}
        runtime_dir = tmp_path / "worker-runtime"
        runtime_dir.mkdir()
        config_data: dict[str, object] = {"_worker_shared_pycache": str(shared)}

        # Simulate what _process_task does with the config value
        shared_pycache_raw = config_data.get("_worker_shared_pycache")
        shared_pycache = None
        if shared_pycache_raw is not None:
            import pathlib

            candidate = pathlib.Path(str(shared_pycache_raw))
            if candidate.is_dir():
                shared_pycache = candidate

        configure_ephemeral_pytest_environment(env, runtime_dir, shared_pycache=shared_pycache)
        assert env.get("PYTHONPYCACHEPREFIX") == str(shared)
        assert env.get("PYTHONDONTWRITEBYTECODE") != "1"

    def test_worker_falls_back_to_ephemeral_without_config(self, tmp_path: Path) -> None:
        """Without _worker_shared_pycache, the ephemeral default applies."""

        env: dict[str, str] = {}
        runtime_dir = tmp_path / "worker-runtime"
        runtime_dir.mkdir()
        config_data: dict[str, object] = {}

        shared_pycache_raw = config_data.get("_worker_shared_pycache")
        shared_pycache = None
        if shared_pycache_raw is not None:
            import pathlib

            candidate = pathlib.Path(str(shared_pycache_raw))
            if candidate.is_dir():
                shared_pycache = candidate

        configure_ephemeral_pytest_environment(env, runtime_dir, shared_pycache=shared_pycache)
        assert env.get("PYTHONDONTWRITEBYTECODE") == "1"
        assert env.get("PYTHONPYCACHEPREFIX") != str(tmp_path)

    def test_worker_invalid_shared_pycache_falls_back(self, tmp_path: Path) -> None:
        """An invalid _worker_shared_pycache path degrades to ephemeral."""

        env: dict[str, str] = {}
        runtime_dir = tmp_path / "worker-runtime"
        runtime_dir.mkdir()
        config_data: dict[str, object] = {"_worker_shared_pycache": str(tmp_path / "nonexistent")}

        shared_pycache_raw = config_data.get("_worker_shared_pycache")
        shared_pycache = None
        if shared_pycache_raw is not None:
            import pathlib

            candidate = pathlib.Path(str(shared_pycache_raw))
            if candidate.is_dir():
                shared_pycache = candidate

        # Falls back to None because the directory doesn't exist
        assert shared_pycache is None
        configure_ephemeral_pytest_environment(env, runtime_dir, shared_pycache=shared_pycache)
        assert env.get("PYTHONDONTWRITEBYTECODE") == "1"
