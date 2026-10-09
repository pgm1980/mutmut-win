"""Native import-value and collection-environment controls for S3-019/024."""

import importlib.util
import multiprocessing
import os
import py_compile
import sys
from pathlib import Path
from typing import Literal

import pytest
from pydantic import BaseModel, ConfigDict

from mutmut_win.config import MutmutConfig
from mutmut_win.exceptions import OrchestratorError
from mutmut_win.models import MutationTask, TaskCompleted, TaskStarted
from mutmut_win.orchestrator import _validate_staging_unchanged
from mutmut_win.process.worker import _process_task
from mutmut_win.pytest_boundary import prepare_pytest_boundary
from mutmut_win.runner import PytestRunner
from mutmut_win.stats import build_staging_context_evidence


class ImportObservation(BaseModel):
    """Values observed inside the actual collection or test interpreter."""

    value: int
    prefix: str
    writing_disabled: bool
    pid: int
    mutant: str


class ProbeProject(BaseModel):
    """Own all paths and the runner used by one native import control."""

    model_config = ConfigDict(arbitrary_types_allowed=True)
    project: Path
    execution_root: Path
    source: Path
    observation: Path
    runner: PytestRunner


def _probe_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, staging: bool = True
) -> ProbeProject:
    project = tmp_path / "project"
    project.mkdir()
    root = project / "mutants" if staging else project
    (root / "src").mkdir(parents=True)
    (root / "tests").mkdir()
    config = "[pytest]\npythonpath = src\n"
    (project / "pytest.ini").write_text(config, encoding="utf-8")
    (root / "pytest.ini").write_text(config, encoding="utf-8")
    source = root / "src" / "cachetarget.py"
    source.write_bytes(b"VALUE = 1\n")
    observation = tmp_path / "native-observation.json"
    (root / "tests" / "test_probe.py").write_text(
        "import os, sys\nfrom pathlib import Path\nfrom pydantic import BaseModel\n"
        "import cachetarget\n"
        "class ImportObservation(BaseModel):\n"
        "    value: int\n    prefix: str\n    writing_disabled: bool\n"
        "    pid: int\n    mutant: str\n"
        f"Path({str(observation)!r}).write_text(ImportObservation("
        "value=cachetarget.VALUE, prefix=sys.pycache_prefix, "
        "writing_disabled=sys.dont_write_bytecode, pid=os.getpid(), "
        "mutant=os.environ.get('MUTANT_UNDER_TEST', '')).model_dump_json(), encoding='utf-8')\n"
        "def test_probe():\n    assert True\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(project)
    runner = PytestRunner(
        MutmutConfig(paths_to_mutate=["src"], tests_dir=["tests"], clean_run_timeout=60)
    )
    if staging:
        runner.write_pth_blocker()
    return ProbeProject(
        project=project, execution_root=root, source=source, observation=observation, runner=runner
    )


def _poison_shared_cache(case: ProbeProject, shared: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    alternate = case.project.parent / "off-source.py"
    alternate.write_bytes(b"VALUE = 2\n")
    with monkeypatch.context() as context:
        context.setattr(sys, "pycache_prefix", str(shared))
        destination = importlib.util.cache_from_source(str(case.source))
        py_compile.compile(
            str(alternate),
            cfile=destination,
            dfile=str(case.source),
            doraise=True,
            invalidation_mode=py_compile.PycInvalidationMode.UNCHECKED_HASH,
        )
    assert int.from_bytes(Path(destination).read_bytes()[4:8], "little") == 1


def _run_worker(case: ProbeProject, shared: Path | None) -> None:
    config = MutmutConfig(
        paths_to_mutate=["src"], tests_dir=["tests"], infinite_loop_detection=False
    )
    config_data = config.model_dump()
    if shared is not None:
        config_data["_worker_shared_pycache"] = str(shared)
    task = MutationTask(mutant_name="cachetarget.x_value__mutmut_1", timeout_seconds=60)
    boundary = prepare_pytest_boundary(
        project_root=case.project, staging_root=case.execution_root, tests_dir=["tests"]
    )
    events = multiprocessing.get_context("spawn").Queue()
    try:
        _process_task(task.model_dump(), events, os.getpid(), [], config_data, boundary, ["tests"])
        started = TaskStarted.model_validate(events.get(timeout=5))
        completed = TaskCompleted.model_validate(events.get(timeout=5))
        assert started.mutant_name == completed.mutant_name == task.mutant_name
        assert completed.exit_code == 0, completed.last_output
        assert completed.duration > 0
    finally:
        events.close()
        events.join_thread()


@pytest.mark.integration
@pytest.mark.parametrize("shared_enabled", [True, False], ids=["shared", "fresh"])
@pytest.mark.parametrize("phase", ["clean", "stats", "coverage", "worker"])
def test_off_source_unchecked_pyc_cannot_change_native_import(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    shared_enabled: bool,
    phase: Literal["clean", "stats", "coverage", "worker"],
) -> None:
    """An off-source pyc cannot change an unchanged authorized source's value."""
    case = _probe_project(tmp_path, monkeypatch)
    shared = tmp_path / "shared"
    before = build_staging_context_evidence()
    _poison_shared_cache(case, shared, monkeypatch)
    assert build_staging_context_evidence() == before
    _validate_staging_unchanged(before, {})
    case.runner.shared_pycache = shared if shared_enabled else None
    if phase == "worker":
        _run_worker(case, case.runner.shared_pycache)
    else:
        if phase == "clean":
            result = case.runner.run_clean_test()
        elif phase == "stats":
            result = case.runner.run_stats()
        else:
            result = case.runner.run_coverage_collection(tmp_path / ".coverage")
        assert result == 0, case.runner.last_diagnostic_output
    observed = ImportObservation.model_validate_json(case.observation.read_bytes())
    print(phase, shared_enabled, observed.model_dump_json())
    assert observed.pid > 0
    assert case.source.read_bytes() == b"VALUE = 1\n"
    _validate_staging_unchanged(before, {})
    assert observed.value == 1, "off-source UNCHECKED_HASH bytecode changed the native import"
    assert observed.writing_disabled is not shared_enabled
    if shared_enabled:
        assert observed.prefix == str(shared)
    else:
        assert observed.prefix != str(shared)


@pytest.mark.integration
@pytest.mark.parametrize("staging", [True, False], ids=["staged", "fallback"])
@pytest.mark.parametrize("shared_enabled", [True, False], ids=["shared", "isolated"])
def test_collection_child_observes_runner_pycache_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, staging: bool, shared_enabled: bool
) -> None:
    """Actual collect-only imports honor the same prefix as other runner phases."""
    case = _probe_project(tmp_path, monkeypatch, staging=staging)
    shared = tmp_path / "shared"
    case.runner.shared_pycache = shared if shared_enabled else None
    assert case.runner.collect_tests() == ["tests/test_probe.py::test_probe"]
    observed = ImportObservation.model_validate_json(case.observation.read_bytes())
    print(staging, shared_enabled, observed.model_dump_json())
    assert observed.value == 1
    assert observed.pid != os.getpid()
    assert observed.writing_disabled is not shared_enabled
    if shared_enabled:
        assert observed.prefix == str(shared)
    else:
        assert observed.prefix != str(shared)
        assert not Path(observed.prefix).is_relative_to(case.project)


def test_source_aba_remains_rejected_by_staging_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The corrected pyc control does not weaken the existing source-ABA backstop."""
    case = _probe_project(tmp_path, monkeypatch)
    before = build_staging_context_evidence()
    original = case.source.read_bytes()
    original_stat = case.source.stat()
    case.source.write_bytes(b"VALUE = 2\n")
    case.source.write_bytes(original)
    os.utime(case.source, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns + 1_000_000))
    assert case.source.read_bytes() == original
    with pytest.raises(OrchestratorError, match="staging files changed"):
        _validate_staging_unchanged(before, {})
