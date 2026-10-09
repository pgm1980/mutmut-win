"""The type-filter shortcut must preserve native clean-suite validation."""

import hashlib
from typing import TYPE_CHECKING

import pytest

from mutmut_win.config import MutmutConfig
from mutmut_win.db import load_results
from mutmut_win.orchestrator import CleanTestFailedError, MutationOrchestrator
from mutmut_win.runner import PytestRunner

if TYPE_CHECKING:
    from pathlib import Path

    from mutmut_win.models import MutationTask, SourceFileMutationData


@pytest.mark.parametrize("catch_all", [True, False], ids=["all-caught", "remaining"])
@pytest.mark.parametrize("healthy", [False, True], ids=["failing-clean", "healthy-clean"])
def test_type_filter_preserves_real_clean_and_basis_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    catch_all: bool,
    healthy: bool,
) -> None:
    """Exercise real generation, clean subprocess, run identity and basis hashing."""
    import mutmut_win.orchestrator as orchestrator_module

    monkeypatch.chdir(tmp_path)
    source = tmp_path / "src"
    source.mkdir()
    (source / "target.py").write_text("def value():\n    return 2\n", encoding="utf-8")
    tests = tmp_path / "tests"
    tests.mkdir()
    clean_marker = tmp_path.with_name(tmp_path.name + "-clean-success.txt")
    assert clean_marker.parent == tmp_path.parent
    assert not clean_marker.exists()
    expected = 2 if healthy else 3
    (tests / "test_target.py").write_text(
        "import hashlib\nimport os\nfrom pathlib import Path\nfrom target import value\n"
        f"def test_value():\n    assert value() == {expected}\n"
        "    if os.environ.get('MUTANT_UNDER_TEST') == '' and "
        "os.environ.get('MUTMUT_CLEAN_NAMES_TOKEN'):\n"
        "        proof = hashlib.sha256(\n"
        "            os.environ['MUTMUT_CLEAN_NAMES_TOKEN'].encode()).hexdigest()\n"
        f"        Path({str(clean_marker)!r}).write_text(proof, encoding='utf-8')\n",
        encoding="utf-8",
    )
    (tmp_path / "pyproject.toml").write_text(
        '[tool.mutmut]\npaths_to_mutate = ["src"]\n'
        'type_check_command = ["mypy", "--output=json", "."]\n',
        encoding="utf-8",
    )
    filter_calls: list[int] = []
    clean_tokens: list[str] = []
    clean_exits: list[int] = []
    real_phase = PytestRunner._run_phase

    def observe_phase(
        runner: PytestRunner,
        phase_name: str,
        cmd: list[str],
        env: dict[str, str],
        timeout: int | None = None,
        timeout_hint: str = "clean_run_timeout",
        shared_pycache: Path | None = None,
        coverage_data_file: Path | None = None,
    ) -> int:
        if phase_name == "clean test suite":
            assert not clean_marker.exists()
            assert env["MUTANT_UNDER_TEST"] == ""
            clean_tokens.append(
                hashlib.sha256(env["MUTMUT_CLEAN_NAMES_TOKEN"].encode()).hexdigest()
            )
        result = real_phase(
            runner,
            phase_name,
            cmd,
            env,
            timeout=timeout,
            timeout_hint=timeout_hint,
            shared_pycache=shared_pycache,
            coverage_data_file=coverage_data_file,
        )
        if phase_name == "clean test suite":
            clean_exits.append(result)
        return result

    monkeypatch.setattr(PytestRunner, "_run_phase", observe_phase)

    def type_filter(
        tasks: list[MutationTask],
        _sources: dict[Path, SourceFileMutationData],
        _command: list[str],
    ) -> tuple[list[MutationTask], set[str]]:
        filter_calls.append(len(tasks))
        if healthy:
            # Only the successful body in the real clean-phase subprocess can
            # create this external marker; all-caught must not bypass it.
            assert clean_exits == [0]
            assert len(clean_tokens) == 1
            assert clean_marker.read_text(encoding="utf-8") == clean_tokens[0]
        if catch_all:
            return [], {task.mutant_name for task in tasks}
        return tasks, set()

    monkeypatch.setattr(orchestrator_module, "_filter_with_type_checker", type_filter)
    (tmp_path / ".mutmut-cache").mkdir()
    database = tmp_path / "cache.db"
    orchestrator = MutationOrchestrator(
        MutmutConfig(
            paths_to_mutate=["src"],
            type_check_command=["mypy", "--output=json", "."],
            max_children=1,
        ),
        db_path=database,
        no_progress=True,
    )
    if not healthy:
        with pytest.raises(CleanTestFailedError, match="Clean test run failed"):
            orchestrator.run()
        assert filter_calls == []
        assert load_results(database) == []
        assert not clean_marker.exists()
        assert clean_exits == [1]
        return

    result = orchestrator.run()
    assert len(filter_calls) == 1
    assert clean_exits == [0]
    assert clean_marker.read_text(encoding="utf-8") == clean_tokens[0]
    assert result.total_mutants == filter_calls[0] > 0
    assert result.type_check_caught == (result.total_mutants if catch_all else 0)
    assert result.killed == (0 if catch_all else result.total_mutants)
    assert result.score == pytest.approx(100.0)
    # A generic command is deliberately not an attested execution basis.
    # Real hashing and finalization must continue to revoke its authority.
    assert not result.execution_basis_complete
    rows = load_results(database)
    assert len(rows) == result.total_mutants
    assert all(row.tests_fingerprint is None for row in rows)
