"""Regression tests for the v2.21.0 runtime-isolation false-green fixes."""

from __future__ import annotations

import os
import py_compile
import subprocess
import sys
from pathlib import Path

import pytest

from mutmut_win.file_setup import purge_staging_runtime_artifacts
from mutmut_win.process.worker import configure_ephemeral_pytest_environment


def test_purge_staging_runtime_artifacts_removes_only_runtime_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "project"
    staging = project / "mutants"
    package = staging / "src" / "package"
    tests = staging / "tests"
    package.mkdir(parents=True)
    tests.mkdir()
    monkeypatch.chdir(project)

    source = package / "module.py"
    fixture = tests / "fixture.bin"
    source.write_text("VALUE = 'source survives'\n", encoding="utf-8")
    fixture.write_bytes(b"normal fixture survives")

    runtime_files = [
        staging / "__pycache__" / "root.cpython-314.pyc",
        package / "__pycache__" / "module.cpython-314.pyc",
        staging / ".pytest_cache" / "v" / "cache" / "nodeids",
        package / ".pytest_cache" / "state",
        staging / ".hypothesis" / "examples" / "state",
        tests / ".hypothesis" / "examples" / "state",
    ]
    for runtime_file in runtime_files:
        runtime_file.parent.mkdir(parents=True, exist_ok=True)
        runtime_file.write_bytes(b"runtime state")

    loose_bytecode = [
        staging / "root.pyc",
        staging / "root.PYO",
        package / "loose.pyc",
        tests / "fixture.pyo",
    ]
    for bytecode_file in loose_bytecode:
        bytecode_file.write_bytes(b"stale bytecode")

    purge_staging_runtime_artifacts()

    for runtime_file in runtime_files:
        assert not runtime_file.exists()
    for bytecode_file in loose_bytecode:
        assert not bytecode_file.exists()
    assert not any(
        path.suffix.casefold() in {".pyc", ".pyo"} for path in staging.rglob("*") if path.is_file()
    )
    assert source.read_text(encoding="utf-8") == "VALUE = 'source survives'\n"
    assert fixture.read_bytes() == b"normal fixture survives"


@pytest.mark.skipif(
    sys.platform != "win32"
    or sys.implementation.name != "cpython"
    or sys.version_info[:3] != (3, 14, 7),
    reason="requires Windows CPython 3.14.7",
)
def test_fresh_pycache_prefix_bypasses_staged_unchecked_hash_bytecode(
    tmp_path: Path,
) -> None:
    staging = tmp_path / "project" / "mutants"
    staging.mkdir(parents=True)
    source = staging / "runtime_probe.py"
    source.write_text('VALUE = "old"\n', encoding="utf-8")
    compiled_path = Path(
        py_compile.compile(
            str(source),
            doraise=True,
            invalidation_mode=py_compile.PycInvalidationMode.UNCHECKED_HASH,
        )
    )
    compiled_before = compiled_path.read_bytes()
    source.write_text('VALUE = "new"\n', encoding="utf-8")

    control_environment = os.environ.copy()
    control_environment["PYTHONDONTWRITEBYTECODE"] = "1"
    control_environment.pop("PYTHONPYCACHEPREFIX", None)
    control = subprocess.run(
        [sys.executable, "-B", "-c", "import runtime_probe; print(runtime_probe.VALUE)"],
        cwd=staging,
        env=control_environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert control.returncode == 0, control.stdout + control.stderr
    assert control.stdout.strip() == "old"

    isolated_environment = os.environ.copy()
    runtime_dir = tmp_path / "runtime-state"
    configure_ephemeral_pytest_environment(isolated_environment, runtime_dir)
    isolated = subprocess.run(
        [sys.executable, "-B", "-c", "import runtime_probe; print(runtime_probe.VALUE)"],
        cwd=staging,
        env=isolated_environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )

    assert isolated.returncode == 0, isolated.stdout + isolated.stderr
    assert isolated.stdout.strip() == "new"
    assert compiled_path.read_bytes() == compiled_before
    external_pycache = Path(isolated_environment["PYTHONPYCACHEPREFIX"])
    assert external_pycache.is_dir()
    assert not external_pycache.is_relative_to(staging)
    assert not any(path.is_file() for path in external_pycache.rglob("*"))


def test_ephemeral_pytest_environment_keeps_runtime_state_outside_staging(
    tmp_path: Path,
) -> None:
    staging = (tmp_path / "project" / "mutants").resolve()
    staging.mkdir(parents=True)
    runtime_dir = (tmp_path / "ephemeral-runtime").resolve()
    environment = {
        "PYTHONPYCACHEPREFIX": str(staging / "stale-python-cache"),
        "HYPOTHESIS_STORAGE_DIRECTORY": str(staging / "stale-hypothesis"),
        "COVERAGE_FILE": str(staging / ".coverage"),
    }

    pytest_cache = configure_ephemeral_pytest_environment(environment, runtime_dir)

    expected_paths = {
        "pytest": runtime_dir / "pytest-cache",
        "python": runtime_dir / "python-cache",
        "hypothesis": runtime_dir / "hypothesis",
        "coverage": runtime_dir / ".coverage",
    }
    assert pytest_cache == expected_paths["pytest"]
    assert environment["PYTHONDONTWRITEBYTECODE"] == "1"
    assert Path(environment["PYTHONPYCACHEPREFIX"]) == expected_paths["python"]
    assert Path(environment["HYPOTHESIS_STORAGE_DIRECTORY"]) == expected_paths["hypothesis"]
    assert Path(environment["COVERAGE_FILE"]) == expected_paths["coverage"]
    assert expected_paths["pytest"].is_dir()
    assert expected_paths["python"].is_dir()
    assert expected_paths["hypothesis"].is_dir()
    assert not expected_paths["coverage"].exists()
    assert all(not path.is_relative_to(staging) for path in expected_paths.values())
    assert all(path.is_relative_to(runtime_dir) for path in expected_paths.values())
