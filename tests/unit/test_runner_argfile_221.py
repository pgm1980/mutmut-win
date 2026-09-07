"""CX221-070: every parent pytest phase owns an external target argument file."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from _pytest.config.argparsing import Parser

import mutmut_win.runner as runner_module
from mutmut_win.config import MutmutConfig
from mutmut_win.exceptions import BadTestExecutionCommandsException, OrchestratorError
from mutmut_win.runner import PytestRunner
from mutmut_win.stats import build_staging_context_evidence

_PHASES = (
    "clean",
    "stats",
    "coverage",
    "forced_fail",
    "collection_staged",
    "collection_unstaged",
)


@pytest.fixture(autouse=True)
def _isolated_no_process_workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("PYTEST_ADDOPTS", raising=False)

    def forbid_process(*_args: Any, **_kwargs: Any) -> None:
        pytest.fail("argument-file tests must never start a process")

    monkeypatch.setattr(subprocess, "Popen", forbid_process)


def _make_runner(tmp_path: Path, phase: str, targets: list[str]) -> PytestRunner:
    """Create real target functions without collecting or executing any of them."""
    roots = [tmp_path]
    if phase != "collection_unstaged":
        roots.append(tmp_path / "mutants")
    sources: dict[str, list[str]] = {}
    for target in targets:
        filename, function = target.split("::", 1)
        sources.setdefault(filename, []).append(function)
    for root in roots:
        root.mkdir(parents=True, exist_ok=True)
        (root / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
        for filename, functions in sources.items():
            source = root / filename
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_text(
                "".join(f"def {name}():\n    assert 2 + 2 == 4\n\n" for name in functions),
                encoding="utf-8",
            )
    runner = PytestRunner(MutmutConfig(paths_to_mutate=["."], tests_dir=targets))
    if phase != "collection_unstaged":
        runner.write_pth_blocker()
    return runner


def _invoke(runner: PytestRunner, phase: str, tmp_path: Path) -> int | list[str]:
    if phase == "clean":
        return runner.run_clean_test()
    if phase == "stats":
        return runner.run_stats()
    if phase == "coverage":
        return runner.run_coverage_collection(tmp_path / "external-coverage-data")
    if phase == "forced_fail":
        return runner.run_forced_fail("unused")
    return runner.collect_tests()


def _track_runtime_directories(monkeypatch: pytest.MonkeyPatch) -> list[Path]:
    created: list[Path] = []
    real_temporary_directory = runner_module.tempfile.TemporaryDirectory

    def create(*args: Any, **kwargs: Any) -> Any:
        context = real_temporary_directory(*args, **kwargs)
        if kwargs.get("prefix") == "mutmut-win-pytest-runtime-":
            created.append(Path(context.name))
        return context

    monkeypatch.setattr(runner_module.tempfile, "TemporaryDirectory", create)
    return created


def _fake_process_boundaries(
    monkeypatch: pytest.MonkeyPatch,
    runner: PytestRunner,
    inspect_command: Any,
    *,
    outcome: str = "success",
) -> None:
    def complete(cmd: list[str]) -> int:
        inspect_command(cmd)
        if outcome == "error":
            raise RuntimeError("simulated process-boundary failure")
        return 2 if outcome == "nonzero" else 0

    def phase_process(_phase: str, cmd: list[str], _env: dict[str, str], **_kwargs: Any) -> int:
        return complete(cmd)

    def collection_process(cmd: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(cmd, complete(cmd), stdout="", stderr="")

    monkeypatch.setattr(runner, "_run_phase_process", phase_process)
    monkeypatch.setattr(runner_module, "_run_collection_process", collection_process)


@pytest.mark.parametrize("phase", _PHASES)
@pytest.mark.parametrize("outcome", ["success", "nonzero", "error"])
def test_parent_phases_transport_large_targets_and_cleanup_runtime(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    phase: str,
    outcome: str,
) -> None:
    targets = [
        f"tests/services/invoicing/test_invoice_rules_{module:02d}.py::test_valid_invoice_case_{case:02d}"
        for module in range(30)
        for case in range(20)
    ]
    targets.reverse()
    targets.insert(233, "tests/test invoice café.py::test_münchen")
    assert len(subprocess.list2cmdline([sys.executable, "--", *targets])) > 32_767
    runner = _make_runner(tmp_path, phase, targets)
    runtime_directories = _track_runtime_directories(monkeypatch)
    staging_before = (
        build_staging_context_evidence(tmp_path) if phase != "collection_unstaged" else None
    )
    observed: list[Path] = []

    def inspect_command(cmd: list[str]) -> None:
        assert len(runtime_directories) == 1
        target_tail = cmd[cmd.index("--") + 1 :]
        assert len(target_tail) == 1
        assert target_tail[0].startswith("@")
        argument_file = Path(target_tail[0][1:])
        assert argument_file.is_absolute()
        assert argument_file.is_relative_to(runtime_directories[0])
        assert not argument_file.is_relative_to(tmp_path / "mutants")
        assert argument_file.read_bytes() == "".join(f"{target}\n" for target in targets).encode(
            "utf-8"
        )
        parsed = Parser(_ispytest=True).parse_known_args(["--", *target_tail])
        assert parsed.file_or_dir == targets
        assert len(subprocess.list2cmdline(cmd).encode("utf-16-le")) // 2 + 1 <= 32_767
        observed.append(argument_file)

    _fake_process_boundaries(monkeypatch, runner, inspect_command, outcome=outcome)

    if outcome == "error":
        with pytest.raises(RuntimeError, match="simulated process-boundary failure"):
            _invoke(runner, phase, tmp_path)
    elif outcome == "nonzero" and phase.startswith("collection"):
        with pytest.raises(OrchestratorError, match="pytest test collection failed"):
            _invoke(runner, phase, tmp_path)
    else:
        result = _invoke(runner, phase, tmp_path)
        assert result == (
            [] if phase.startswith("collection") else 2 if outcome == "nonzero" else 0
        )

    assert len(observed) == 1
    assert len(runtime_directories) == 1
    assert not observed[0].exists()
    assert not runtime_directories[0].exists()
    if staging_before is not None:
        assert staging_before.complete
        assert build_staging_context_evidence(tmp_path) == staging_before
    else:
        assert not (tmp_path / "mutants").exists()


@pytest.mark.parametrize("phase", _PHASES)
def test_empty_parent_target_list_creates_no_argument_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    phase: str,
) -> None:
    runner = _make_runner(tmp_path, phase, [])
    runtime_directories = _track_runtime_directories(monkeypatch)
    calls: list[list[str]] = []

    def inspect_command(cmd: list[str]) -> None:
        assert "--" not in cmd
        assert not any(token.startswith("@") for token in cmd)
        assert list(runtime_directories[0].glob("mutmut_tests_*.txt")) == []
        calls.append(cmd)

    _fake_process_boundaries(monkeypatch, runner, inspect_command)

    _invoke(runner, phase, tmp_path)

    assert len(calls) == 1
    assert len(runtime_directories) == 1
    assert not runtime_directories[0].exists()


@pytest.mark.parametrize("phase", _PHASES)
def test_argument_file_preparation_failure_cleans_parent_runtime(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    phase: str,
) -> None:
    runner = _make_runner(tmp_path, phase, ["tests/test_example.py::test_example"])
    runtime_directories = _track_runtime_directories(monkeypatch)
    prepared: list[Path] = []

    def fail_publication(targets: list[str], output_dir: Path) -> Path:
        assert targets == ["tests/test_example.py::test_example"]
        partial_file = output_dir / "partial-argument-file.txt"
        partial_file.write_bytes(b"partial setup output")
        prepared.append(partial_file)
        raise OSError("simulated argument-file preparation failure")

    def forbid_launch(_cmd: list[str]) -> None:
        pytest.fail("argument-file preparation failure must precede the process boundary")

    monkeypatch.setattr(runner_module, "_write_pytest_argfile", fail_publication, raising=False)
    _fake_process_boundaries(monkeypatch, runner, forbid_launch)

    with pytest.raises(OSError, match="simulated argument-file preparation failure"):
        _invoke(runner, phase, tmp_path)

    assert len(prepared) == 1
    assert not prepared[0].exists()
    assert len(runtime_directories) == 1
    assert not runtime_directories[0].exists()


@pytest.mark.parametrize("phase", _PHASES)
def test_user_argument_file_is_rejected_before_parent_runtime(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    phase: str,
) -> None:
    (tmp_path / "user-targets.txt").write_text("tests/test_example.py\n", encoding="utf-8")
    if phase != "collection_unstaged":
        (tmp_path / "mutants").mkdir()
    runner = PytestRunner(MutmutConfig(paths_to_mutate=["."], tests_dir=["@user-targets.txt"]))
    runtime_directories = _track_runtime_directories(monkeypatch)

    with pytest.raises(BadTestExecutionCommandsException, match="test paths/node IDs only"):
        _invoke(runner, phase, tmp_path)

    assert runtime_directories == []


@pytest.mark.parametrize("phase", _PHASES)
def test_parser_line_break_is_rejected_before_parent_runtime(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    phase: str,
) -> None:
    if phase != "collection_unstaged":
        (tmp_path / "mutants").mkdir()
    target = "tests/test_example.py::test_value[first\u2028second]"
    runner = PytestRunner(MutmutConfig(paths_to_mutate=["."], tests_dir=[target]))
    runtime_directories = _track_runtime_directories(monkeypatch)

    with pytest.raises(BadTestExecutionCommandsException, match="NUL or line breaks"):
        _invoke(runner, phase, tmp_path)

    assert runtime_directories == []
