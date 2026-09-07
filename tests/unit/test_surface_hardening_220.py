"""Adversarial contracts for the mutmut-win 2.20 surface hardening."""

from __future__ import annotations

import json
import os
import runpy
import subprocess
import sys
import tomllib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner, Result

from mutmut_win.cli import cli
from mutmut_win.config import MutmutConfig
from mutmut_win.db import MutationRunState
from mutmut_win.exceptions import (
    BadTestExecutionCommandsException,
    OrchestratorError,
    PytestBoundaryError,
)
from mutmut_win.models import MutationResult, MutationRunResult
from mutmut_win.process.worker import (
    PYTEST_PHASE_GUARD_PLUGIN,
    apply_pytest_boundary_environment,
    configure_ephemeral_pytest_environment,
    prepare_pytest_collection_guard,
    validated_pytest_args,
    validated_pytest_targets,
    worker_main,
)
from mutmut_win.pytest_boundary import prepare_pytest_boundary
from mutmut_win.runner import PytestRunner
from tests.unit.phase_mock_util import phase_popen

_VERIFIED_BASIS = "a" * 64


def _verified_current(rows: list[MutationResult]) -> MutationRunState:
    names = tuple(row.mutant_name for row in rows)
    return MutationRunState(
        run_id="verified-run",
        status="completed",
        started_at="2026-01-01T00:00:00+00:00",
        finished_at="2026-01-01T00:01:00+00:00",
        planned_names=names,
        completed_results=(),
        completed_names=names,
        pending_names=(),
        universe_fingerprint="b" * 64,
        plan_digest="c" * 64,
        basis_fingerprint=_VERIFIED_BASIS,
        basis_config_json="{}",
        is_full_run=True,
    )


@pytest.fixture
def staged_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Run runner phases in an isolated project with a staging directory."""
    monkeypatch.chdir(tmp_path)
    mutants = tmp_path / "mutants"
    mutants.mkdir()
    return mutants


def _worker_config(staging: Path, **overrides: object) -> dict[str, object]:
    """Build the same frozen worker payload the production executor receives."""

    config = MutmutConfig(**overrides)
    runner = PytestRunner(config)
    runner.prepare_pytest_boundary(staging)
    payload: dict[str, object] = config.model_dump()
    payload["_pytest_boundary"] = runner.pytest_boundary_data
    return payload


@pytest.mark.parametrize("phase", ["clean", "stats", "coverage", "forced-fail"])
def test_test_selection_args_reach_every_parent_phase(
    phase: str,
    staged_project: Path,
) -> None:
    runner = PytestRunner(
        MutmutConfig(
            pytest_add_cli_args=["--strict-markers"],
            pytest_add_cli_args_test_selection=["-k", "surface and not slow"],
        )
    )

    with phase_popen(0) as popen:
        if phase == "clean":
            runner.run_clean_test()
        elif phase == "stats":
            runner.run_stats()
        elif phase == "coverage":
            runner.run_coverage_collection(staged_project / ".coverage.mutmut")
        else:
            runner.run_forced_fail("pkg.x_f__mutmut_1")

    cmd: list[str] = popen.call_args.args[0]
    assert "--strict-markers" in cmd
    selection_index = cmd.index("-k")
    assert cmd[selection_index : selection_index + 2] == ["-k", "surface and not slow"]
    config_index = cmd.index("-c")
    assert config_index > selection_index
    assert Path(cmd[config_index + 1]).parent == staged_project
    assert f"--rootdir={staged_project}" in cmd
    assert f"--confcutdir={staged_project}" in cmd
    separator_index = cmd.index("--")
    assert separator_index > config_index
    assert cmd[separator_index + 1 :] == ["tests/"]


class _Queue:
    def __init__(self, *items: object) -> None:
        self._items = list(items)

    def get(self) -> object:
        return self._items.pop(0)

    def put(self, item: object) -> None:
        self._items.append(item)


def test_worker_refuses_a_task_without_a_serialized_boundary() -> None:
    task_queue = _Queue({"mutant_name": "pkg.x_f__mutmut_1"}, None)

    with pytest.raises(PytestBoundaryError, match="supplied no frozen pytest boundary"):
        worker_main(task_queue, _Queue(), {"tests_dir": []})  # type: ignore[arg-type]


def test_test_selection_args_reach_spawned_workers(staged_project: Path) -> None:
    task_queue = _Queue({"mutant_name": "pkg.x_f__mutmut_1"}, None)
    event_queue = _Queue()
    config = _worker_config(
        staged_project,
        pytest_add_cli_args=["--strict-markers"],
        pytest_add_cli_args_test_selection=["-k", "surface"],
    )

    with patch("mutmut_win.process.worker._process_task") as process_task:
        worker_main(task_queue, event_queue, config)  # type: ignore[arg-type]

    forwarded: list[str] = process_task.call_args.args[3]
    assert forwarded == ["--strict-markers", "-k", "surface"]


def test_test_selection_args_reach_the_worker_pytest_command(staged_project: Path) -> None:
    task_queue = _Queue(
        {
            "mutant_name": "pkg.x_f__mutmut_1",
            "tests": ["test_target.py::test_one"],
        },
        None,
    )
    event_queue = _Queue()
    proc = MagicMock()
    proc.pid = 99999
    proc.wait.return_value = 0
    config = _worker_config(
        staged_project,
        pytest_add_cli_args=["--strict-markers"],
        pytest_add_cli_args_test_selection=["-k", "surface"],
        infinite_loop_detection=False,
    )

    def fake_popen(*_args: object, **kwargs: object) -> MagicMock:
        env = kwargs["env"]
        assert isinstance(env, dict)
        Path(env["MUTMUT_PYTEST_PHASE_SENTINEL_PATH"]).write_text(
            env["MUTMUT_PYTEST_PHASE_SENTINEL_PROOF"],
            encoding="utf-8",
        )
        return proc

    with (
        patch("mutmut_win.process.worker.subprocess.Popen", side_effect=fake_popen) as popen,
        patch("mutmut_win.process.worker._create_task_job", return_value=None),
        patch("mutmut_win.process.worker._maybe_start_loop_monitor", return_value=None),
    ):
        worker_main(task_queue, event_queue, config)  # type: ignore[arg-type]

    cmd: list[str] = popen.call_args.args[0]
    assert "--strict-markers" in cmd
    selection_index = cmd.index("-k")
    assert cmd[selection_index : selection_index + 2] == ["-k", "surface"]
    config_index = cmd.index("-c")
    assert config_index > selection_index
    assert Path(cmd[config_index + 1]).parent == staged_project
    assert f"--rootdir={staged_project}" in cmd
    assert f"--confcutdir={staged_project}" in cmd
    separator_index = cmd.index("--")
    assert separator_index > config_index
    assert len(cmd[separator_index + 1 :]) == 1
    argfile = Path(cmd[separator_index + 1].removeprefix("@"))
    assert argfile.name.startswith("mutmut_tests_")
    assert not argfile.is_relative_to(staged_project)
    assert staged_project.exists()


@pytest.mark.parametrize(
    "override",
    [
        "-cexternal.ini",
        "--config-file=external.ini",
        "--rootdir=..",
        "--confcutdir=..",
        "@external-args.txt",
        "--",
    ],
)
def test_user_args_cannot_override_the_pytest_boundary(
    override: str,
    staged_project: Path,  # noqa: ARG001
) -> None:
    runner = PytestRunner(MutmutConfig(pytest_add_cli_args=[override]))

    with (
        patch("subprocess.Popen") as popen,
        pytest.raises(BadTestExecutionCommandsException),
    ):
        runner.run_clean_test()

    popen.assert_not_called()


@pytest.mark.parametrize(
    "target",
    [
        "-c",
        "--rootdir=..",
        "--confcutdir=..",
        "@external-args.txt",
        "--",
        "bad\n-c\n../../pytest.ini",
        "bad\0target",
        "",
    ],
)
def test_tests_dir_accepts_targets_only_and_cannot_override_the_boundary(
    target: str,
    staged_project: Path,  # noqa: ARG001
) -> None:
    runner = PytestRunner(MutmutConfig(tests_dir=[target]))

    with (
        patch("subprocess.Popen") as popen,
        pytest.raises(BadTestExecutionCommandsException),
    ):
        runner.run_clean_test()

    popen.assert_not_called()


@pytest.mark.parametrize("target", ["-c", "@args.txt", "x\n--rootdir=..", "x\0y"])
def test_direct_mutation_task_targets_reject_option_and_argfile_injection(target: str) -> None:
    with pytest.raises(BadTestExecutionCommandsException):
        validated_pytest_targets([target], field_name="MutationTask.tests")


def test_pytest_expands_the_internal_argfile_after_end_of_options(tmp_path: Path) -> None:
    test_file = tmp_path / "test_argfile_target.py"
    test_file.write_text("def test_target():\n    assert True\n", encoding="utf-8")
    argfile = tmp_path / "targets.txt"
    argfile.write_text("test_argfile_target.py::test_target\n", encoding="utf-8")

    result = subprocess.run(  # noqa: S603
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            "--",
            f"@{argfile}",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_pytest_addopts_is_validated_once_then_removed_from_child_environment(
    staged_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PYTEST_ADDOPTS", "--strict-markers")
    runner = PytestRunner(MutmutConfig())

    with phase_popen(0) as popen:
        runner.run_clean_test()

    cmd: list[str] = popen.call_args.args[0]
    child_environment: dict[str, str] = popen.call_args.kwargs["env"]
    assert cmd.count("--strict-markers") == 1
    assert "PYTEST_ADDOPTS" not in child_environment
    assert Path(cmd[cmd.index("-c") + 1]).parent == staged_project


def test_ancestor_pytest_config_and_conftest_cannot_change_collection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    outer = tmp_path / "outer"
    project = outer / "project"
    staging = project / "mutants"
    staging.mkdir(parents=True)
    (outer / "pytest.ini").write_text(
        "[pytest]\npython_files = spec_*.py\n",
        encoding="utf-8",
    )
    (outer / "conftest.py").write_text(
        "raise RuntimeError('ancestor conftest must not load')\n",
        encoding="utf-8",
    )
    (staging / "test_regular.py").write_text(
        "def test_regular():\n    assert True\n",
        encoding="utf-8",
    )
    (staging / "spec_special.py").write_text(
        "def spec_special():\n    assert True\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(project)
    monkeypatch.delenv("PYTEST_ADDOPTS", raising=False)
    runner = PytestRunner(MutmutConfig(tests_dir=["."]))

    before = runner.collect_tests()
    (outer / "pytest.ini").write_text(
        "[pytest]\npython_files = other_*.py\n",
        encoding="utf-8",
    )
    after = runner.collect_tests()

    assert before == ["test_regular.py::test_regular"]
    assert after == before
    boundary_config = Path(str(runner.pytest_boundary_data["config_path"]))
    assert boundary_config.parent == staging
    assert boundary_config.name.startswith(".mutmut-win-pytest-")
    assert boundary_config.read_bytes() == b"[pytest]\n"


def test_staged_config_cannot_collect_an_unbound_external_test_tree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    outer = tmp_path / "outer"
    project = outer / "project"
    staging = project / "mutants"
    external = outer / "external_tests"
    staging.mkdir(parents=True)
    external.mkdir()
    (staging / "pytest.ini").write_text(
        "[pytest]\ntestpaths = ../../external_tests\n",
        encoding="utf-8",
    )
    (external / "conftest.py").write_text("BOUNDARY_MARKER = True\n", encoding="utf-8")
    (external / "test_external.py").write_text(
        "def test_external():\n    assert True\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(project)
    runner = PytestRunner(MutmutConfig(tests_dir=[]))

    with pytest.raises(OrchestratorError, match="outside the frozen mutmut-win execution basis"):
        runner.collect_tests()


def test_child_guard_rejects_external_directory_replacement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The child authenticates the parent's target ID, not only its path."""

    project = tmp_path / "project"
    staging = project / "mutants"
    external = tmp_path / "external-tests"
    retired = tmp_path / "retired-external-tests"
    conftest_sentinel = tmp_path / "replacement-conftest-ran"
    staging.mkdir(parents=True)
    external.mkdir()
    (external / "conftest.py").write_text(
        "from pathlib import Path\n"
        f"Path({str(conftest_sentinel)!r}).write_text('ran', encoding='utf-8')\n",
        encoding="utf-8",
    )
    (external / "test_external.py").write_text(
        "def test_external():\n    assert True\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(project)
    boundary = prepare_pytest_boundary(
        project_root=project,
        staging_root=staging,
        tests_dir=[str(external)],
    )
    boundary_arguments = boundary.arguments()
    environment = os.environ.copy()
    apply_pytest_boundary_environment(boundary, environment)
    prepare_pytest_collection_guard()

    external.rename(retired)
    external.mkdir()
    (external / "test_external.py").write_text(
        "def test_replacement():\n    assert True\n",
        encoding="utf-8",
    )

    repo_src = Path(__file__).resolve().parents[2] / "src"
    inherited_pythonpath = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = os.pathsep.join(
        [
            str(staging),
            str(repo_src),
            *([inherited_pythonpath] if inherited_pythonpath else []),
        ]
    )
    environment["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    runtime_dir = tmp_path / "identity-swap-runtime"
    configure_ephemeral_pytest_environment(environment, runtime_dir)

    result = subprocess.run(  # noqa: S603 - controlled interpreter and test paths
        [
            sys.executable,
            "-m",
            "pytest",
            *boundary_arguments,
            "-p",
            PYTEST_PHASE_GUARD_PLUGIN,
            "--",
            str(external),
        ],
        cwd=project,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert "boundary identity changed" in output
    assert not conftest_sentinel.exists()


def test_exact_external_file_does_not_authorize_adjacent_conftest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exact-file authorization must block conftest code in its parent tree."""

    project = tmp_path / "project"
    staging = project / "mutants"
    routing_parent = tmp_path / "untrusted-routing-parent"
    external = routing_parent / "external-tests"
    conftest_sentinel = tmp_path / "adjacent-conftest-ran"
    exact_test = external / "test_exact.py"
    staging.mkdir(parents=True)
    external.mkdir(parents=True)
    (external / "conftest.py").write_text(
        "from pathlib import Path\n"
        f"Path({str(conftest_sentinel)!r}).write_text('ran', encoding='utf-8')\n",
        encoding="utf-8",
    )
    exact_test.write_text("def test_exact():\n    assert True\n", encoding="utf-8")
    monkeypatch.chdir(project)
    boundary = prepare_pytest_boundary(
        project_root=project,
        staging_root=staging,
        tests_dir=[str(exact_test)],
    )
    environment = os.environ.copy()
    apply_pytest_boundary_environment(boundary, environment)
    prepare_pytest_collection_guard()

    repo_src = Path(__file__).resolve().parents[2] / "src"
    inherited_pythonpath = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = os.pathsep.join(
        [
            str(staging),
            str(repo_src),
            *([inherited_pythonpath] if inherited_pythonpath else []),
        ]
    )
    environment["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    runtime_dir = tmp_path / "exact-file-runtime"
    configure_ephemeral_pytest_environment(environment, runtime_dir)

    result = subprocess.run(  # noqa: S603 - controlled interpreter and test paths
        [
            sys.executable,
            "-m",
            "pytest",
            *boundary.arguments(),
            "-p",
            PYTEST_PHASE_GUARD_PLUGIN,
            "--",
            str(exact_test),
        ],
        cwd=project,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert not conftest_sentinel.exists()


def test_external_directory_authorizes_only_its_own_conftest_tree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An explicit directory root includes itself, never ancestor conftests."""

    project = tmp_path / "project"
    staging = project / "mutants"
    routing_parent = tmp_path / "untrusted-routing-parent"
    external = routing_parent / "external-tests"
    own_sentinel = tmp_path / "allowed-conftest-ran"
    ancestor_sentinel = tmp_path / "ancestor-conftest-ran"
    staging.mkdir(parents=True)
    external.mkdir(parents=True)
    (routing_parent / "conftest.py").write_text(
        "from pathlib import Path\n"
        f"Path({str(ancestor_sentinel)!r}).write_text('ran', encoding='utf-8')\n",
        encoding="utf-8",
    )
    (external / "conftest.py").write_text(
        "from pathlib import Path\n"
        f"Path({str(own_sentinel)!r}).write_text('ran', encoding='utf-8')\n",
        encoding="utf-8",
    )
    (external / "test_allowed.py").write_text(
        "def test_allowed():\n    assert True\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(project)
    boundary = prepare_pytest_boundary(
        project_root=project,
        staging_root=staging,
        tests_dir=[str(external)],
    )
    environment = os.environ.copy()
    apply_pytest_boundary_environment(boundary, environment)
    prepare_pytest_collection_guard()

    repo_src = Path(__file__).resolve().parents[2] / "src"
    inherited_pythonpath = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = os.pathsep.join(
        [
            str(staging),
            str(repo_src),
            *([inherited_pythonpath] if inherited_pythonpath else []),
        ]
    )
    environment["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    runtime_dir = tmp_path / "external-directory-runtime"
    configure_ephemeral_pytest_environment(environment, runtime_dir)

    result = subprocess.run(  # noqa: S603 - controlled interpreter and test paths
        [
            sys.executable,
            "-m",
            "pytest",
            *boundary.arguments(),
            "-p",
            PYTEST_PHASE_GUARD_PLUGIN,
            "--",
            str(external),
        ],
        cwd=project,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert own_sentinel.read_text(encoding="utf-8") == "ran"
    assert not ancestor_sentinel.exists()


def test_staged_pytest_config_tamper_fails_before_process_launch(
    staged_project: Path,
) -> None:
    (staged_project / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    runner = PytestRunner(MutmutConfig())
    runner.prepare_pytest_boundary()
    (staged_project / "pytest.ini").write_text(
        "[pytest]\naddopts = --collect-only\n",
        encoding="utf-8",
    )

    with (
        patch("subprocess.Popen") as popen,
        pytest.raises(OrchestratorError, match="changed after the run boundary"),
    ):
        runner.run_clean_test()

    popen.assert_not_called()


def test_worker_boundary_drift_is_fatal_and_stops_the_worker(
    staged_project: Path,
) -> None:
    config_path = staged_project / "pytest.ini"
    config_path.write_text("[pytest]\n", encoding="utf-8")
    config = _worker_config(staged_project, tests_dir=[])

    class _TamperingQueue(_Queue):
        def get(self) -> object:
            item = super().get()
            if isinstance(item, dict):
                config_path.write_text("[pytest]\naddopts = -q\n", encoding="utf-8")
            return item

    task_queue = _TamperingQueue(
        {"mutant_name": "pkg.x_f__mutmut_1"},
        {"mutant_name": "pkg.x_f__mutmut_2"},
        None,
    )
    event_queue = _Queue()

    with patch("mutmut_win.process.worker.subprocess.Popen") as popen:
        worker_main(task_queue, event_queue, config)  # type: ignore[arg-type]

    popen.assert_not_called()
    completed = [
        event for event in event_queue._items if isinstance(event, dict) and "exit_code" in event
    ]
    assert len(completed) == 1
    assert completed[0]["fatal"] is True
    assert completed[0]["mutant_name"] == "pkg.x_f__mutmut_1"
    assert "PytestBoundaryError" in str(completed[0]["last_output"])


def test_boundary_export_and_pth_setup_cannot_reauthorize_config_drift(
    staged_project: Path,
) -> None:
    config = staged_project / "pytest.ini"
    config.write_text("[pytest]\n", encoding="utf-8")
    runner = PytestRunner(MutmutConfig())
    runner.prepare_pytest_boundary()
    config.write_text("[pytest]\naddopts = --collect-only\n", encoding="utf-8")

    with pytest.raises(OrchestratorError, match="changed after the run boundary"):
        _ = runner.pytest_boundary_data
    with pytest.raises(OrchestratorError, match="changed after the run boundary"):
        runner.write_pth_blocker()


def test_fallback_boundary_cannot_switch_to_newly_appearing_config(
    staged_project: Path,
) -> None:
    runner = PytestRunner(MutmutConfig())
    runner.prepare_pytest_boundary()
    frozen = dict(runner.pytest_boundary_data)
    (staged_project / "pytest.ini").write_text(
        "[pytest]\naddopts = --collect-only\n",
        encoding="utf-8",
    )

    assert runner.pytest_boundary_data == frozen
    assert Path(str(frozen["config_path"])).name.startswith(".mutmut-win-pytest-")


def test_worker_uses_a_unique_execution_proof_for_each_task(staged_project: Path) -> None:
    task_queue = _Queue(
        {"mutant_name": "pkg.x_f__mutmut_1"},
        {"mutant_name": "pkg.x_f__mutmut_2"},
        None,
    )
    event_queue = _Queue()
    marker_paths: list[str] = []

    def fake_popen(*_args: object, **kwargs: object) -> MagicMock:
        env = kwargs["env"]
        assert isinstance(env, dict)
        marker = env["MUTMUT_PYTEST_PHASE_SENTINEL_PATH"]
        token = env["MUTMUT_PYTEST_PHASE_SENTINEL_PROOF"]
        assert isinstance(marker, str)
        assert isinstance(token, str)
        marker_paths.append(marker)
        Path(marker).write_text(token, encoding="utf-8")
        proc = MagicMock()
        proc.pid = 99999
        proc.wait.return_value = 0
        return proc

    with (
        patch("mutmut_win.process.worker.subprocess.Popen", side_effect=fake_popen),
        patch("mutmut_win.process.worker._create_task_job", return_value=None),
        patch("mutmut_win.process.worker._maybe_start_loop_monitor", return_value=None),
    ):
        worker_main(
            task_queue,  # type: ignore[arg-type]
            event_queue,  # type: ignore[arg-type]
            _worker_config(staged_project, infinite_loop_detection=False),
        )

    assert len(marker_paths) == 2
    assert len(set(marker_paths)) == 2
    completed = [
        event for event in event_queue._items if isinstance(event, dict) and "exit_code" in event
    ]
    assert [event["exit_code"] for event in completed] == [0, 0]
    assert staged_project.exists()


def test_worker_exit_zero_without_execution_proof_is_suspicious(staged_project: Path) -> None:
    task_queue = _Queue({"mutant_name": "pkg.x_f__mutmut_1"}, None)
    event_queue = _Queue()
    proc = MagicMock()
    proc.pid = 99999
    proc.wait.return_value = 0

    with (
        patch("mutmut_win.process.worker.subprocess.Popen", return_value=proc),
        patch("mutmut_win.process.worker._create_task_job", return_value=None),
        patch("mutmut_win.process.worker._maybe_start_loop_monitor", return_value=None),
    ):
        worker_main(
            task_queue,  # type: ignore[arg-type]
            event_queue,  # type: ignore[arg-type]
            _worker_config(staged_project, infinite_loop_detection=False),
        )

    completed = [
        event for event in event_queue._items if isinstance(event, dict) and "exit_code" in event
    ]
    assert len(completed) == 1
    assert completed[0]["exit_code"] == 35
    assert "without executing a test call" in str(completed[0]["last_output"])
    assert staged_project.exists()


@pytest.mark.parametrize(
    "neutralizer",
    [
        "--collect-only",
        "--collect-only=true",
        "--co",
        "--fixtures",
        "--fixtures-per-test",
        "--funcargs",
        "--help",
        "-h",
        "--markers",
        "--setup-only",
        "--setup-plan",
        "--version",
        "-V",
    ],
)
def test_phase_neutralizers_are_rejected_before_pytest(
    neutralizer: str,
    staged_project: Path,  # noqa: ARG001
) -> None:
    runner = PytestRunner(MutmutConfig(pytest_add_cli_args_test_selection=[neutralizer]))

    with (
        patch("subprocess.Popen") as popen,
        pytest.raises(BadTestExecutionCommandsException, match="without executing test bodies"),
    ):
        runner.run_clean_test()

    popen.assert_not_called()


def test_legitimate_selection_flags_remain_allowed() -> None:
    assert validated_pytest_args(
        ["--strict-markers"],
        ["-k", "fast and not slow", "-m", "unit", "tests/unit/test_example.py"],
    ) == [
        "--strict-markers",
        "-k",
        "fast and not slow",
        "-m",
        "unit",
        "tests/unit/test_example.py",
    ]


@pytest.mark.parametrize(
    "stateful_option",
    [
        "--lf",
        "--last-failed",
        "--ff",
        "--failed-first",
        "--nf",
        "--new-first",
        "--sw",
        "--stepwise",
        "--sw-skip",
        "--stepwise-skip",
        "--last-failed-no-failures=none",
        "--cache-show",
    ],
)
def test_cache_driven_pytest_options_are_rejected(stateful_option: str) -> None:
    with pytest.raises(
        BadTestExecutionCommandsException,
        match="cache-driven selection or ordering",
    ):
        validated_pytest_args([], [stateful_option])


def test_real_clean_phase_accepts_a_test_call_proof(
    staged_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PYTEST_ADDOPTS", raising=False)
    (staged_project / "test_guard_happy.py").write_text(
        "def test_guard_happy():\n    assert True\n",
        encoding="utf-8",
    )
    runner = PytestRunner(MutmutConfig(tests_dir=["test_guard_happy.py"], clean_run_timeout=30))

    assert runner.run_clean_test() == 0
    assert list(staged_project.glob(".mutmut_pytest_executed_*.sentinel")) == []


def test_real_clean_phase_rejects_only_call_time_skips(
    staged_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PYTEST_ADDOPTS", raising=False)
    (staged_project / "test_guard_skipped.py").write_text(
        "import pytest\n\n"
        "def test_guard_skipped():\n"
        "    pytest.skip('runtime precondition unavailable')\n",
        encoding="utf-8",
    )
    runner = PytestRunner(MutmutConfig(tests_dir=["test_guard_skipped.py"], clean_run_timeout=30))

    with pytest.raises(OrchestratorError, match="without executing a pytest test call"):
        runner.run_clean_test()


def test_real_clean_phase_preserves_cache_fixture_in_an_isolated_directory(
    staged_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PYTEST_ADDOPTS", raising=False)
    (staged_project / "test_cache_fixture.py").write_text(
        "def test_cache_fixture(cache):\n"
        "    cache.set('demo/value', 42)\n"
        "    assert cache.get('demo/value', None) == 42\n",
        encoding="utf-8",
    )
    runner = PytestRunner(MutmutConfig(tests_dir=["test_cache_fixture.py"], clean_run_timeout=30))

    assert runner.run_clean_test() == 0
    assert not (staged_project / ".pytest_cache").exists()


@pytest.mark.parametrize("neutralizer_source", ["environment", "pytest.ini"])
def test_real_clean_phase_rejects_collect_only_outside_mutmut_config(
    neutralizer_source: str,
    staged_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (staged_project / "test_guard_neutralized.py").write_text(
        "def test_guard_neutralized():\n    assert True\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("PYTEST_ADDOPTS", raising=False)
    if neutralizer_source == "environment":
        monkeypatch.setenv("PYTEST_ADDOPTS", "--collect-only")
    else:
        (staged_project / "pytest.ini").write_text(
            "[pytest]\naddopts = --collect-only\n",
            encoding="utf-8",
        )
    runner = PytestRunner(
        MutmutConfig(tests_dir=["test_guard_neutralized.py"], clean_run_timeout=30)
    )

    if neutralizer_source == "environment":
        with pytest.raises(
            BadTestExecutionCommandsException,
            match="without executing test bodies",
        ):
            runner.run_clean_test()
    else:
        with pytest.raises(OrchestratorError, match="without executing a pytest test call"):
            runner.run_clean_test()


def test_staged_pytest_config_cannot_enable_last_failed_selection(
    staged_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Disabling cacheprovider closes config-file ingress, not just argv."""

    monkeypatch.delenv("PYTEST_ADDOPTS", raising=False)
    (staged_project / "test_guard_stateful.py").write_text(
        "def test_guard_stateful():\n    assert True\n",
        encoding="utf-8",
    )
    (staged_project / "pytest.ini").write_text(
        "[pytest]\naddopts = --lf\n",
        encoding="utf-8",
    )
    runner = PytestRunner(MutmutConfig(tests_dir=["test_guard_stateful.py"], clean_run_timeout=30))

    # The config is parsed only inside pytest.  The generated boundary plugin
    # inspects the effective option state and fails closed as a usage error
    # before this can become a green subset.
    assert runner.run_clean_test() == 4


def test_run_phase_base_exception_removes_proof_and_reaps_tree(staged_project: Path) -> None:
    marker_path = staged_project / "phase-proof.sentinel"
    marker_path.write_text("expected-proof", encoding="utf-8")
    proc = MagicMock(pid=99999)
    proc.wait.side_effect = KeyboardInterrupt
    runner = PytestRunner(MutmutConfig())

    with (
        patch(
            "mutmut_win.runner.prepare_pytest_phase_guard",
            return_value=(marker_path, "expected-proof"),
        ),
        patch("subprocess.Popen", return_value=proc),
        patch("mutmut_win.process.worker._create_task_job", return_value=None),
        patch("mutmut_win.process.worker._kill_proc_tree") as kill_tree,
        pytest.raises(KeyboardInterrupt),
    ):
        runner.run_clean_test()

    assert not marker_path.exists()
    kill_tree.assert_called_once_with(proc, None)
    assert not list(staged_project.glob("mutmut_phase_*.log"))


@pytest.mark.parametrize("returncode", [2, 4, 5])
def test_failed_live_collection_raises_domain_error_without_returning_empty_suite(
    returncode: int,
    staged_project: Path,  # noqa: ARG001
) -> None:
    completed = subprocess.CompletedProcess(
        args=[sys.executable, "-m", "pytest"],
        returncode=returncode,
        stdout="collection stdout",
        stderr="collection stderr",
    )
    runner = PytestRunner(MutmutConfig())

    with (
        patch("mutmut_win.runner._run_collection_process", return_value=completed),
        pytest.raises(OrchestratorError, match=rf"collection failed .*exit {returncode}"),
    ):
        runner.collect_tests()


@pytest.mark.parametrize(
    "xdist_args",
    [["-n", "2"], ["-nauto"], ["--numprocesses=4"], ["--dist=load"]],
)
def test_stats_phase_rejects_xdist_before_writing_plugin(
    xdist_args: list[str],
    staged_project: Path,
) -> None:
    runner = PytestRunner(MutmutConfig(pytest_add_cli_args=xdist_args))

    with (
        patch("subprocess.Popen") as popen,
        pytest.raises(BadTestExecutionCommandsException, match="pytest-xdist"),
    ):
        runner.run_stats()

    popen.assert_not_called()
    assert not (staged_project / "_mutmut_stats_plugin.py").exists()


def test_stats_plugin_preserves_collection_hits_for_all_collected_tests(tmp_path: Path) -> None:
    """Import-time trampoline hits must survive the first per-test clear."""
    PytestRunner._write_stats_plugin(tmp_path)
    (tmp_path / "test_collection_hits.py").write_text(
        """\
from mutmut_win._state import _stats

_stats.add("pkg.collection")

def test_one():
    _stats.add("pkg.one")

def test_two():
    _stats.add("pkg.two")
""",
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    stats_output = tmp_path / "stats-output.json"
    env["MUTMUT_STATS_OUTPUT_PATH"] = str(stats_output)
    repo_src = Path(__file__).resolve().parents[2] / "src"
    inherited_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = os.pathsep.join(
        [str(tmp_path), str(repo_src), *([inherited_pythonpath] if inherited_pythonpath else [])]
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "_mutmut_stats_plugin",
            "test_collection_hits.py",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(stats_output.read_text(encoding="utf-8"))
    mapping = payload["tests_by_mangled_function_name"]
    assert mapping["pkg.collection"] == [
        "test_collection_hits.py::test_one",
        "test_collection_hits.py::test_two",
    ]
    assert mapping["pkg.one"] == ["test_collection_hits.py::test_one"]
    assert mapping["pkg.two"] == ["test_collection_hits.py::test_two"]
    assert not (tmp_path / "mutmut-stats.json").exists()


@pytest.mark.parametrize(
    ("option_values", "as_worker"),
    [
        ({"numprocesses": 2}, False),
        ({"numprocesses": None, "tx": ["popen"]}, False),
        ({"numprocesses": None}, True),
    ],
)
def test_generated_stats_plugin_refuses_active_xdist(
    tmp_path: Path,
    option_values: dict[str, object],
    as_worker: bool,
) -> None:
    PytestRunner._write_stats_plugin(tmp_path)
    plugin = runpy.run_path(str(tmp_path / "_mutmut_stats_plugin.py"))
    config = SimpleNamespace(option=SimpleNamespace(**option_values))
    if as_worker:
        config.workerinput = {}

    with pytest.raises(pytest.UsageError, match="does not support pytest-xdist"):
        plugin["pytest_configure"](config)


def _invoke_empty_run(*args: str) -> tuple[Result, MagicMock]:
    orchestrator = MagicMock()
    orchestrator.run.return_value = MutationRunResult()
    orchestrator.dry_run.return_value = MutationRunResult()
    with (
        patch("mutmut_win.cli.load_config", return_value=MutmutConfig(paths_to_mutate=[])),
        patch("mutmut_win.cli.MutationOrchestrator", return_value=orchestrator),
        patch("mutmut_win.cli.PytestRunner"),
        patch("mutmut_win.cli.SpawnPoolExecutor"),
    ):
        result = CliRunner().invoke(cli, ["run", *args])
    return result, orchestrator


def test_empty_full_run_fails_closed_but_empty_dry_run_remains_informational() -> None:
    full_result, _orchestrator = _invoke_empty_run()
    dry_result, _orchestrator = _invoke_empty_run("--dry-run")

    assert full_result.exit_code == 1
    assert "failed closed" in full_result.output
    assert dry_result.exit_code == 0


def test_explicit_empty_selection_is_usage_failure_with_valid_json() -> None:
    result, _orchestrator = _invoke_empty_run("--output", "json", "pkg.missing_f__mutmut_1")

    assert result.exit_code == 2
    assert json.loads(result.stdout)["total_mutants"] == 0
    assert "explicit run selection" in result.stderr


def test_since_commit_noop_succeeds_and_keeps_json_machine_readable() -> None:
    completed = subprocess.CompletedProcess(
        args=["git", "diff", "--name-only", "HEAD"],
        returncode=0,
        stdout="",
        stderr="",
    )
    with (
        patch("mutmut_win.cli.load_config", return_value=MutmutConfig(paths_to_mutate=[])),
        patch("subprocess.run", return_value=completed),
    ):
        result = CliRunner().invoke(cli, ["run", "--since-commit", "HEAD", "--output", "json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["total_mutants"] == 0
    assert payload["score"] == 0.0
    assert "error" not in payload


def test_since_commit_uses_effective_custom_tests_dir_before_filtering() -> None:
    completed = subprocess.CompletedProcess(
        args=["git", "diff", "--name-only", "HEAD"],
        returncode=0,
        stdout="custom_tests/test_changed.py\n",
        stderr="",
    )
    with (
        patch("mutmut_win.cli.load_config", return_value=MutmutConfig(paths_to_mutate=[])),
        patch("subprocess.run", return_value=completed),
        patch("mutmut_win.cli.MutationOrchestrator") as orchestrator,
    ):
        result = CliRunner().invoke(
            cli,
            ["run", "--tests-dir", "custom_tests", "--since-commit", "HEAD"],
        )

    assert result.exit_code == 0
    assert "No mutation-target .py files changed" in result.output
    orchestrator.assert_not_called()


def test_domain_failure_keeps_json_machine_readable() -> None:
    orchestrator = MagicMock()
    orchestrator.run.side_effect = OrchestratorError("collection contract failed")
    with (
        patch("mutmut_win.cli.load_config", return_value=MutmutConfig(paths_to_mutate=[])),
        patch("mutmut_win.cli.MutationOrchestrator", return_value=orchestrator),
        patch("mutmut_win.cli.PytestRunner"),
        patch("mutmut_win.cli.SpawnPoolExecutor"),
    ):
        result = CliRunner().invoke(cli, ["run", "--output", "json"])

    assert result.exit_code == 1
    assert json.loads(result.stdout) == {
        "error": "Error: collection contract failed",
        "exit_code": 1,
    }


def test_force_partial_deletion_fails_closed_with_valid_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    source = tmp_path / "src" / "mod.py"
    source.parent.mkdir()
    source.write_text("def value():\n    return 1\n", encoding="utf-8")
    (tmp_path / "mutants").mkdir()
    with patch("shutil.rmtree", return_value=None):
        result = CliRunner().invoke(cli, ["run", "--force", "--output", "json"])

    expected_message = (
        "Could not fully remove mutants/ (files in use?); refusing to run with stale state."
    )
    assert result.exit_code == 1
    assert json.loads(result.stdout) == {
        "error": expected_message,
        "exit_code": 1,
    }
    assert (tmp_path / "mutants").exists()


def test_results_and_cicd_export_exclude_unchecked_rows_from_score(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = [
        MutationResult(mutant_name="pkg.x_f__mutmut_1", status="killed", exit_code=1),
        MutationResult(mutant_name="pkg.x_f__mutmut_2", status="survived", exit_code=0),
        MutationResult(mutant_name="pkg.x_f__mutmut_3", status="not checked"),
    ]
    # Mock the snapshot boundary, not only its legacy ``load_results``
    # fallback: a real current Dogfood run in the repository cache must never
    # replace this test's synthetic population.
    with patch(
        "mutmut_win.cli._load_result_snapshot_or_exit",
        return_value=(None, rows),
    ):
        displayed = CliRunner().invoke(cli, ["results"])
    assert displayed.exit_code == 0
    assert "Score:      50.0%" in displayed.output

    monkeypatch.chdir(tmp_path)
    (tmp_path / "mutants").mkdir()
    with (
        patch(
            "mutmut_win.cli._load_result_snapshot_or_exit",
            return_value=(_verified_current(rows), rows),
        ),
        patch("mutmut_win.cli._stable_live_basis", return_value=_VERIFIED_BASIS),
    ):
        exported = CliRunner().invoke(cli, ["export-cicd-stats"])
    payload = json.loads(Path("mutants/mutmut-cicd-stats.json").read_text(encoding="utf-8"))

    assert exported.exit_code == 0
    assert payload["total"] == 2
    assert payload["score"] == 50.0


def test_cicd_export_with_only_unchecked_rows_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rows = [MutationResult(mutant_name="pkg.x_f__mutmut_1", status="not checked")]
    monkey_runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    with (
        patch(
            "mutmut_win.cli._load_result_snapshot_or_exit",
            return_value=(_verified_current(rows), rows),
        ),
        patch("mutmut_win.cli._stable_live_basis", return_value=_VERIFIED_BASIS),
    ):
        result = monkey_runner.invoke(cli, ["export-cicd-stats"])
    assert not Path("mutants/mutmut-cicd-stats.json").exists()

    assert result.exit_code == 1
    assert "failed closed" in result.output


def test_distribution_configuration_is_curated_and_licensed() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    with (repo_root / "pyproject.toml").open("rb") as pyproject_file:
        pyproject = tomllib.load(pyproject_file)

    assert pyproject["project"]["license"] == "ISC AND BSD-3-Clause AND PSF-2.0"
    assert pyproject["project"]["license-files"] == ["LICENSE"]
    assert "click>=8.3.3" in pyproject["project"]["dependencies"]
    assert {"msgpack>=1.2.1", "pip>=26.2"} <= set(
        pyproject["project"]["optional-dependencies"]["dev"]
    )
    assert "extend-exclude" in pyproject["tool"]["ruff"]
    assert "exclude" not in pyproject["tool"]["ruff"]
    sdist_include = set(pyproject["tool"]["hatch"]["build"]["targets"]["sdist"]["include"])
    assert {"/src", "/tests", "/README.md", "/LICENSE", "/pyproject.toml", "/uv.lock"} <= (
        sdist_include
    )
    license_text = (repo_root / "LICENSE").read_text(encoding="utf-8")
    assert "ISC License" in license_text
    assert "Copyright (c) 2016, Anders Hovmøller" in license_text
    assert "PYTHON SOFTWARE FOUNDATION LICENSE VERSION 2" in license_text
    assert "Copyright (c) 2001-2024 Python Software Foundation; All Rights Reserved" in license_text
    assert "atomic STARTUPINFOEX Job-list assignment" in license_text
