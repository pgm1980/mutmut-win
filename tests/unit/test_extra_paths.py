"""Regression tests for Bug #69 / Bug #2 — sibling packages support via extra_paths.

When a project ships a wheel-package via ``[tool.hatch.build.targets.wheel].packages``
and tests import from sibling directories (e.g. ``benchmarks/``) that are *not*
part of the wheel, mutmut-win's editable install inside ``mutants/`` fails the
clean-test phase with ``ImportError: No module named 'benchmarks'``.

The Sprint 25 fix is a new ``[tool.mutmut].extra_paths`` config field plus a
``--extra-paths-to-copy`` CLI flag. Listed paths are copied into ``mutants/``
(like ``also_copy``) AND added to the worker's ``PYTHONPATH`` so the imports
resolve.

See the issue body of #69 for the original Sprint-3 critique-model-service
repro and the three fix-path options. This is "Option B": new explicit flag.
"""

from __future__ import annotations

import os
from pathlib import Path
from queue import Queue
from typing import Any
from unittest.mock import MagicMock, patch

from mutmut_win.config import MutmutConfig, load_config
from mutmut_win.file_setup import copy_also_copy_files
from mutmut_win.models import MutationTask
from mutmut_win.process.worker import worker_main


def _config(**overrides: Any) -> MutmutConfig:
    defaults: dict[str, Any] = {"max_children": 1}
    defaults.update(overrides)
    return MutmutConfig(**defaults)


class TestExtraPathsConfig:
    """Pydantic config field."""

    def test_default_is_empty_list(self) -> None:
        cfg = _config()
        assert cfg.extra_paths == []

    def test_accepts_list_of_strings(self) -> None:
        cfg = _config(extra_paths=["benchmarks/", "tools/"])
        assert cfg.extra_paths == ["benchmarks/", "tools/"]

    def test_pyproject_extra_paths_loaded(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            '[tool.mutmut]\nextra_paths = ["benchmarks/", "tools/"]\n',
            encoding="utf-8",
        )
        cfg = load_config(tmp_path)
        assert cfg.extra_paths == ["benchmarks/", "tools/"]

    def test_pyproject_kebab_case_extra_paths_also_loaded(self, tmp_path: Path) -> None:
        """``extra-paths`` (kebab) and ``extra_paths`` (snake) must both work,
        matching the existing kebab→snake mapping for other keys."""
        (tmp_path / "pyproject.toml").write_text(
            '[tool.mutmut]\nextra-paths = ["benchmarks/"]\n',
            encoding="utf-8",
        )
        cfg = load_config(tmp_path)
        assert cfg.extra_paths == ["benchmarks/"]


class TestExtraPathsCopy:
    """extra_paths must be mirrored into mutants/ alongside also_copy."""

    def test_extra_paths_are_copied(self, tmp_path: Path) -> None:
        bench = tmp_path / "benchmarks"
        bench.mkdir()
        (bench / "bench_pkg").mkdir()
        (bench / "bench_pkg" / "__init__.py").write_text("", encoding="utf-8")
        (bench / "bench_pkg" / "speed.py").write_text(
            "def measure(): return 42\n", encoding="utf-8"
        )
        (tmp_path / "mutants").mkdir()

        original_cwd = Path.cwd()
        os.chdir(tmp_path)
        try:
            cfg = _config(extra_paths=["benchmarks/"])
            copy_also_copy_files(cfg)
            assert (tmp_path / "mutants" / "benchmarks" / "bench_pkg" / "speed.py").exists()
        finally:
            os.chdir(original_cwd)

    def test_extra_paths_and_also_copy_compose(self, tmp_path: Path) -> None:
        (tmp_path / "data.json").write_text("{}\n", encoding="utf-8")
        bench = tmp_path / "benchmarks"
        bench.mkdir()
        (bench / "bench.py").write_text("x = 1\n", encoding="utf-8")
        (tmp_path / "mutants").mkdir()

        original_cwd = Path.cwd()
        os.chdir(tmp_path)
        try:
            cfg = _config(also_copy=["data.json"], extra_paths=["benchmarks/"])
            copy_also_copy_files(cfg)
            assert (tmp_path / "mutants" / "data.json").exists()
            assert (tmp_path / "mutants" / "benchmarks" / "bench.py").exists()
        finally:
            os.chdir(original_cwd)


class TestExtraPathsPythonPath:
    """Worker must add extra_paths to PYTHONPATH so siblings are importable."""

    def test_worker_pythonpath_includes_extra_paths(self, tmp_path: Path) -> None:
        # Set up a mutants/ tree that contains the extra_paths directory so the
        # worker's existence-check (only adds paths that actually exist) succeeds.
        mutants = tmp_path / "mutants"
        (mutants / "benchmarks").mkdir(parents=True)

        original_cwd = Path.cwd()
        os.chdir(tmp_path)
        try:
            captured_env: dict[str, str] = {}

            def fake_popen(_cmd: list[str], **kwargs: Any) -> MagicMock:
                env = kwargs.get("env", {})
                captured_env.update(env)
                proc = MagicMock()
                proc.pid = 12345
                proc.wait.return_value = 0
                proc.poll.return_value = 0
                return proc

            task_q: Queue[Any] = Queue()
            event_q: Queue[Any] = Queue()
            task_q.put(MutationTask(mutant_name="src/foo.py::bar__mutmut_1").model_dump())
            task_q.put(None)

            config_data = {
                "paths_to_mutate": ["src/"],
                "tests_dir": ["tests/"],
                "do_not_mutate": [],
                "also_copy": [],
                "extra_paths": ["benchmarks/"],
                "max_children": 1,
                "timeout_multiplier": 10.0,
                "max_stack_depth": -1,
                "debug": False,
                "pytest_add_cli_args": [],
                "pytest_add_cli_args_test_selection": [],
                "mutate_only_covered_lines": False,
                "type_check_command": [],
                "infinite_loop_detection": False,
            }

            with patch("mutmut_win.process.worker.subprocess.Popen", side_effect=fake_popen):
                worker_main(task_q, event_q, config_data)  # type: ignore[arg-type]

            python_path = captured_env.get("PYTHONPATH", "")
            assert "benchmarks" in python_path, (
                f"Worker PYTHONPATH must include extra_paths under mutants/. Got: {python_path!r}"
            )
        finally:
            os.chdir(original_cwd)
