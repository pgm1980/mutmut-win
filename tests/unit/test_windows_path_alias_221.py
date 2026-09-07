"""Windows path aliases must not be mistaken for link indirection (MW221-004)."""

from __future__ import annotations

import ctypes
import os
import sys
from pathlib import Path
from queue import Queue
from unittest.mock import MagicMock, patch

import pytest

from mutmut_win.atomic_file import atomic_write_bytes
from mutmut_win.config import MutmutConfig
from mutmut_win.db import create_db, load_results
from mutmut_win.exceptions import StagingNamespaceCollisionError
from mutmut_win.file_setup import (
    _validated_mutants_root,
    _validated_staging_destination,
    copy_also_copy_files,
    validate_staging_namespace,
)
from mutmut_win.models import MutationTask
from mutmut_win.process.worker import worker_main
from mutmut_win.pytest_boundary import _real_path_snapshot
from mutmut_win.runner import PytestRunner
from tests.unit.phase_mock_util import frozen_worker_config

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows path-alias contract")


def _short_path(path: Path) -> Path:
    get_short_path = ctypes.WinDLL("kernel32", use_last_error=True).GetShortPathNameW
    buffer = ctypes.create_unicode_buffer(32768)
    length = get_short_path(str(path), buffer, len(buffer))
    if length == 0:
        pytest.skip(f"8.3 aliases unavailable (WinError {ctypes.get_last_error()})")
    if length >= len(buffer):
        pytest.skip("8.3 alias exceeds the Windows extended-path buffer")
    short = Path(buffer.value)
    if os.path.normcase(str(short)) == os.path.normcase(str(path)):
        pytest.skip("the test volume does not expose a distinct 8.3 alias")
    return short


def test_short_path_alias_is_accepted_by_all_identity_boundaries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "Alias Regression Workspace Long Name"
    atomic_parent = workspace / "Atomic Publication Parent"
    database_parent = workspace / "Database Parent"
    staging_parent = workspace / "mutants" / "Nested Stage Parent"
    test_parent = workspace / "Tests With Long Name"
    for parent in (atomic_parent, database_parent, staging_parent, test_parent):
        parent.mkdir(parents=True, exist_ok=True)
    test_file = test_parent / "test_alias.py"
    test_file.write_text("def test_ok(): pass\n", encoding="utf-8")

    short_workspace = _short_path(workspace)

    atomic_target = short_workspace / atomic_parent.relative_to(workspace) / "payload.bin"
    atomic_write_bytes(atomic_target, b"published")
    assert (atomic_parent / "payload.bin").read_bytes() == b"published"

    database = short_workspace / database_parent.relative_to(workspace) / "cache.db"
    create_db(database)
    assert load_results(database) == []

    monkeypatch.chdir(workspace)
    mutants_root = _validated_mutants_root()
    staging_target = short_workspace / staging_parent.relative_to(workspace) / "module.py"
    assert _validated_staging_destination(staging_target, mutants_root) == staging_target.absolute()

    short_test_file = short_workspace / test_file.relative_to(workspace)
    canonical, metadata = _real_path_snapshot(
        short_test_file,
        kind="file",
        description="pytest test target",
    )
    assert canonical.samefile(test_file)
    assert (metadata.st_dev, metadata.st_ino) == (
        test_file.stat().st_dev,
        test_file.stat().st_ino,
    )


def test_short_cwd_and_long_absolute_extra_path_share_one_staging_mapping(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "Extra Path Alias Workspace Long Name"
    live_root = workspace / "Support Modules Long Name"
    staged_root = workspace / "mutants" / live_root.name
    live_root.mkdir(parents=True)
    (workspace / "mutants").mkdir()
    (live_root / "live_probe.py").write_text("VALUE = 'bound'\n", encoding="utf-8")
    short_workspace = _short_path(workspace)
    monkeypatch.chdir(short_workspace)
    monkeypatch.setenv("PYTHONPATH", str(live_root))
    config = MutmutConfig(paths_to_mutate=["src"], extra_paths=[str(live_root)])

    validate_staging_namespace(config)
    copy_also_copy_files(config)

    assert (staged_root / "live_probe.py").read_text(encoding="utf-8") == "VALUE = 'bound'\n"
    python_paths = [
        Path(value) for value in PytestRunner(config)._mutants_env()["PYTHONPATH"].split(os.pathsep)
    ]
    assert any(path.samefile(staged_root) for path in python_paths)
    assert not any(path.samefile(live_root) for path in python_paths)


def test_worker_short_cwd_and_long_absolute_extra_path_share_staging_mapping(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "Worker Extra Path Alias Workspace Long Name"
    live_root = workspace / "Support Modules Long Name"
    staged_root = workspace / "mutants" / live_root.name
    live_root.mkdir(parents=True)
    staged_root.mkdir(parents=True)
    short_workspace = _short_path(workspace)
    monkeypatch.chdir(short_workspace)
    monkeypatch.setenv("PYTHONPATH", str(live_root))

    captured_env: dict[str, str] = {}

    def fake_popen(_cmd: list[str], **kwargs: object) -> MagicMock:
        env = kwargs.get("env", {})
        captured_env.update(env)  # type: ignore[arg-type]
        proc = MagicMock()
        proc.pid = 12345
        proc.wait.return_value = 0
        proc.poll.return_value = 0
        return proc

    task_q: Queue[object] = Queue()
    event_q: Queue[object] = Queue()
    task_q.put(MutationTask(mutant_name="src/foo.py::bar__mutmut_1").model_dump())
    task_q.put(None)
    config_data = frozen_worker_config(
        {
            "paths_to_mutate": ["src/"],
            "tests_dir": ["tests/"],
            "extra_paths": [str(live_root)],
            "pytest_add_cli_args": [],
            "pytest_add_cli_args_test_selection": [],
            "timeout_multiplier": 10.0,
            "infinite_loop_detection": False,
        }
    )

    with patch("mutmut_win.process.worker.subprocess.Popen", side_effect=fake_popen):
        worker_main(task_q, event_q, config_data)  # type: ignore[arg-type]

    python_paths = [
        Path(value) for value in captured_env.get("PYTHONPATH", "").split(os.pathsep) if value
    ]
    assert any(path.samefile(staged_root) for path in python_paths)
    assert not any(path.samefile(live_root) for path in python_paths)


def test_short_cwd_and_long_absolute_extra_path_bind_helper_namespace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "Extra Path Preflight Workspace Long Name"
    live_root = workspace / "Support Modules Long Name"
    live_root.mkdir(parents=True)
    (workspace / "src").mkdir()
    (live_root / "_mutmut_stats_plugin.py").write_text("USER_DATA = True\n", encoding="utf-8")
    short_workspace = _short_path(workspace)
    monkeypatch.chdir(short_workspace)
    config = MutmutConfig(paths_to_mutate=["src"], extra_paths=[str(live_root)])

    with pytest.raises(StagingNamespaceCollisionError):
        validate_staging_namespace(config)
