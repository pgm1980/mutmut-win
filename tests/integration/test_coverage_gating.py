"""End-to-end test for the reactivated coverage gating (Issue #95).

Drives the REAL chain — `coverage run -m pytest` as a subprocess inside a
mutants tree, parent-side data-file loading, normcase keying, and the
MutationVisitor's covered-lines filter — against a tiny project with one
covered and one never-called function.  Spike-verified design
(`_issues/spike_coverage_bridge.py`); this is the regression pin.
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
import textwrap
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import coverage
import pytest
from pydantic import BaseModel

from mutmut_win.code_coverage import gather_coverage, get_covered_lines_for_file
from mutmut_win.config import MutmutConfig
from mutmut_win.models import MutationRunResult
from mutmut_win.mutation import mutate_file_contents
from mutmut_win.runner import PytestRunner

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.integration, pytest.mark.slow]


class _ChildTerminationEvidence(BaseModel):
    parent_pid: int
    child_pid: int
    reported_pid: int
    product_value: int
    child_exit: int
    parent_lines: set[int]
    part_names: list[str]


class _CoverageMetadata(BaseModel):
    exit_code_by_key: dict[str, int]
    generation_fingerprint: str
    generated_hash: str


class _CoverageCliEvidence(BaseModel):
    phase: str
    started: str
    ended: str
    command: list[str]
    cwd: str
    exit_code: int
    config_hash: str
    source_hash: str
    test_hash: str
    summary: MutationRunResult
    metadata: _CoverageMetadata


def _run_coverage_cli(project: Path, evidence: Path, phase: str) -> _CoverageCliEvidence:
    uv = shutil.which("uv")
    assert uv is not None
    command = [
        uv,
        "run",
        "--no-sync",
        "--python",
        sys.executable,
        "python",
        "-I",
        "-m",
        "mutmut_win",
        "run",
        "--no-progress",
        "--output",
        "json",
        "--min-score",
        "80",
    ]
    started = datetime.now(UTC).isoformat()
    # S603: fixed CLI and an independently resolved uv executable; no shell input.
    completed = subprocess.run(  # noqa: S603
        command,
        cwd=project,
        capture_output=True,
        timeout=600,
    )
    # Keep original Windows diagnostic bytes. The machine channel is UTF-8 JSON;
    # stderr may use the inherited Windows codepage and is not parsed as data.
    (evidence / f"{phase}.stdout").write_bytes(completed.stdout)
    (evidence / f"{phase}.stderr").write_bytes(completed.stderr)
    summary = MutationRunResult.model_validate_json(completed.stdout)
    metadata = _CoverageMetadata.model_validate_json(
        (project / "mutants/src/pkg/mod.py.meta").read_text(encoding="utf-8")
    )
    result = _CoverageCliEvidence(
        phase=phase,
        started=started,
        ended=datetime.now(UTC).isoformat(),
        command=command,
        cwd=str(project),
        exit_code=completed.returncode,
        config_hash=hashlib.sha256((project / "pyproject.toml").read_bytes()).hexdigest(),
        source_hash=hashlib.sha256((project / "src/pkg/mod.py").read_bytes()).hexdigest(),
        test_hash=hashlib.sha256((project / "tests/test_mod.py").read_bytes()).hexdigest(),
        summary=summary,
        metadata=metadata,
    )
    (evidence / f"{phase}.json").write_text(result.model_dump_json(indent=2), encoding="utf-8")
    assert summary.execution_basis_complete
    assert not summary.run_aborted
    assert not summary.was_interrupted
    assert summary.killed + summary.survived == summary.total_mutants
    assert not summary.degraded_files
    assert completed.returncode == int(summary.score < 80)
    assert len(metadata.exit_code_by_key) == summary.total_mutants
    return result


_MODULE_SOURCE = textwrap.dedent(
    """
    def covered(value):
        return value + 1


    def never_called(value):
        return value - 1
    """
).lstrip()

_TEST_SOURCE = textwrap.dedent(
    """
    import sys
    sys.path.insert(0, "src")
    from pkg.mod import covered


    def test_covered():
        assert covered(1) == 2
    """
).lstrip()


def _build_mutants_tree(tmp_path: Path) -> None:
    files = {
        "mutants/src/pkg/__init__.py": "",
        "mutants/src/pkg/mod.py": _MODULE_SOURCE,
        "mutants/tests/test_mod.py": _TEST_SOURCE,
    }
    for rel, content in files.items():
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


class TestCoverageGatingEndToEnd:
    def test_hard_stopped_spawn_child_cannot_shrink_the_universe(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A child reports completed product work before Windows terminates it."""
        monkeypatch.chdir(tmp_path)
        _build_mutants_tree(tmp_path)
        source = "def covered():\n    return 1\n\ndef only_in_child():\n    return 2\n"
        (tmp_path / "mutants/src/pkg/mod.py").write_text(source, encoding="utf-8")
        (tmp_path / "mutants/pyproject.toml").write_text(
            '[tool.pytest.ini_options]\npythonpath=["src"]\n'
            '[tool.coverage.run]\nconcurrency=["multiprocessing"]\n',
            encoding="utf-8",
        )
        proof_path = tmp_path / "child-proof.txt"
        (tmp_path / "mutants/tests/test_mod.py").write_text(
            textwrap.dedent("""
                import multiprocessing
                import os
                import time
                from pathlib import Path
                from pkg.mod import covered, only_in_child

                def execute_then_wait(sender):
                    value = only_in_child()
                    sender.send((os.getpid(), value))
                    sender.close()
                    time.sleep(120)

                def test_parent_and_hard_stopped_child():
                    assert covered() == 1
                    ctx = multiprocessing.get_context("spawn")
                    receiver, sender = ctx.Pipe(duplex=False)
                    process = ctx.Process(target=execute_then_wait, args=(sender,))
                    process.start()
                    sender.close()
                    try:
                        assert receiver.poll(30), "child never acknowledged product work"
                        reported_pid, value = receiver.recv()
                        assert reported_pid == process.pid and value == 2
                        assert process.is_alive()
                        process.terminate()
                        process.join(10)
                        assert not process.is_alive()
                        assert process.exitcode not in (None, 0)
                        proof = (
                            f"{os.getpid()} {process.pid} {reported_pid} "
                            f"{value} {process.exitcode}"
                        )
                        Path(PROOF_PATH).write_text(proof, encoding="utf-8")
                    finally:
                        receiver.close()
                        if process.is_alive():
                            process.terminate()
                            process.join(10)
                        process.close()
            """).replace("PROOF_PATH", repr(str(proof_path))),
            encoding="utf-8",
        )
        runner = PytestRunner(MutmutConfig(tests_dir=["tests"]))
        collect = runner.run_coverage_collection
        records: list[_ChildTerminationEvidence] = []

        def observe_collection(data_file: Path) -> int:
            result = collect(data_file)
            parent_pid, child_pid, reported_pid, value, child_exit = map(
                int, proof_path.read_text(encoding="utf-8").split()
            )
            parts = sorted(data_file.parent.glob(".coverage.mutmut.*"))
            parent_parts = [part for part in parts if f".pid{parent_pid}." in part.name]
            assert len(parent_parts) == 1, (parent_pid, [part.name for part in parts])
            assert not any(f".pid{child_pid}." in part.name for part in parts)
            data = coverage.CoverageData(basename=str(parent_parts[0]))
            data.read()
            parent_lines: set[int] = set()
            for filename in data.measured_files():
                if filename.replace("\\", "/").endswith("/pkg/mod.py"):
                    parent_lines.update(data.lines(filename) or [])
            records.append(
                _ChildTerminationEvidence(
                    parent_pid=parent_pid,
                    child_pid=child_pid,
                    reported_pid=reported_pid,
                    product_value=value,
                    child_exit=child_exit,
                    parent_lines=parent_lines,
                    part_names=[part.name for part in parts],
                )
            )
            return result

        monkeypatch.setattr(runner, "run_coverage_collection", observe_collection)
        selected = gather_coverage(runner, ["src/pkg/mod.py"])
        assert selected is None
        assert len(records) == 1
        record = records[0]
        assert record.child_pid == record.reported_pid != record.parent_pid
        assert record.product_value == 2
        assert record.child_exit != 0
        assert 2 in record.parent_lines
        assert 5 not in record.parent_lines
        _, actual = mutate_file_contents(
            "src/pkg/mod.py",
            source,
            get_covered_lines_for_file(
                "src/pkg/mod.py",
                selected,
            ),
        )
        _, expected = mutate_file_contents("src/pkg/mod.py", source, None)
        _, parent_only = mutate_file_contents("src/pkg/mod.py", source, record.parent_lines)
        assert actual == expected
        assert len(actual) > len(parent_only) > 0
        assert any("only_in_child" in name for name in actual)
        (tmp_path / "hard-child-evidence.json").write_text(
            record.model_dump_json(indent=2),
            encoding="utf-8",
        )

    def test_cli_mode_switch_replaces_stale_reduced_generation(self, tmp_path: Path) -> None:
        """Real repeated CLI runs bind selection, generation, verdicts and score."""
        evidence = tmp_path / "evidence"
        evidence.mkdir()
        project = tmp_path / "transition"
        reference = tmp_path / "reference"
        source = "def covered():\n    return 1\n\ndef never_called():\n    return 2\n"
        tests = "from pkg.mod import covered\n\ndef test_covered():\n    assert covered() == 1\n"
        config = (
            '[tool.mutmut]\npaths_to_mutate=["src/pkg"]\ntests_dir=["tests"]\n'
            "max_children=1\nmutate_only_covered_lines=true\n"
            '[tool.pytest.ini_options]\npythonpath=["src"]\n'
        )
        for root in (project, reference):
            (root / "src/pkg").mkdir(parents=True)
            (root / "tests").mkdir()
            (root / "src/pkg/__init__.py").write_text("", encoding="utf-8")
            (root / "src/pkg/mod.py").write_text(source, encoding="utf-8")
            (root / "tests/test_mod.py").write_text(tests, encoding="utf-8")
        config_path = project / "pyproject.toml"
        config_path.write_text(config, encoding="utf-8")
        (reference / "pyproject.toml").write_text(
            config.replace("mutate_only_covered_lines=true", "mutate_only_covered_lines=false"),
            encoding="utf-8",
        )
        selective = _run_coverage_cli(project, evidence, "selective-before")
        staged = project / "mutants/src/pkg/mod.py"
        sidecar = staged.with_name("mod.py.meta")
        old_source, old_meta = staged.read_bytes(), sidecar.read_bytes()
        assert selective.summary.score == 100
        assert selective.summary.survived == 0
        assert all("covered__" in key for key in selective.metadata.exit_code_by_key)
        full_config = config + '[tool.coverage.run]\nconcurrency=["multiprocessing"]\n'
        config_path.write_text(full_config, encoding="utf-8")
        full = _run_coverage_cli(project, evidence, "multiprocessing-after-selective")
        assert full.summary.total_mutants > selective.summary.total_mutants > 0
        assert full.summary.survived > 0
        assert full.summary.score < 80
        assert full.metadata.generation_fingerprint != selective.metadata.generation_fingerprint
        # Reinsert authentic older generated bytes and ownership metadata while
        # retaining the new full-mode config fingerprint and verdict database.
        staged.write_bytes(old_source)
        sidecar.write_bytes(old_meta)
        stale = _run_coverage_cli(project, evidence, "multiprocessing-stale-sidecar")
        independent = _run_coverage_cli(reference, evidence, "independent-all-lines")
        for observed in (full, stale):
            assert observed.metadata.exit_code_by_key == independent.metadata.exit_code_by_key
            assert observed.summary.score == independent.summary.score
            assert observed.summary.total_mutants == independent.summary.total_mutants
            assert observed.metadata.generated_hash == independent.metadata.generated_hash
            assert "Mutating all configured source lines" in (
                evidence / f"{observed.phase}.stderr"
            ).read_bytes().decode("utf-8", errors="backslashreplace")
        config_path.write_text(config, encoding="utf-8")
        restored = _run_coverage_cli(project, evidence, "selective-restored")
        assert restored.metadata.exit_code_by_key == selective.metadata.exit_code_by_key
        assert restored.metadata.generation_fingerprint == selective.metadata.generation_fingerprint
        assert restored.metadata.generated_hash == selective.metadata.generated_hash
        assert restored.summary.score == selective.summary.score
        assert "Mutating all configured source lines" not in (
            evidence / "selective-restored.stderr"
        ).read_bytes().decode("utf-8", errors="backslashreplace")

    def test_real_subprocess_coverage_filters_uncovered_mutants(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        _build_mutants_tree(tmp_path)
        runner = PytestRunner(MutmutConfig(tests_dir=["tests"]))

        covered_map = gather_coverage(runner, ["src/pkg/mod.py"])
        file_covered = get_covered_lines_for_file("src/pkg/mod.py", covered_map)

        assert file_covered is not None
        assert 2 in file_covered  # body of covered()
        assert 6 not in file_covered  # body of never_called() was never run

        # The actual value of the feature: mutants are only generated on
        # covered lines.
        _mutated, gated_names = mutate_file_contents("src/pkg/mod.py", _MODULE_SOURCE, file_covered)
        _mutated_all, all_names = mutate_file_contents("src/pkg/mod.py", _MODULE_SOURCE, None)

        assert gated_names, "covered() mutants must survive the gate"
        assert len(gated_names) < len(all_names), (
            "never_called() mutants must be filtered out by the coverage gate"
        )
        assert all("never_called" not in name for name in gated_names)

    def test_relative_files_config_is_collected_end_to_end(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """M-018: the staged project coverage config may set relative_files=true.

        ``coverage run`` then stores every measured path RELATIVE to its
        working directory (``mutants/``); the parent must still match those
        keys against the staged source files instead of rejecting the
        measurement as "no coverage".
        """
        monkeypatch.chdir(tmp_path)
        _build_mutants_tree(tmp_path)
        (tmp_path / "mutants" / "pyproject.toml").write_text(
            "[tool.coverage.run]\nrelative_files = true\n", encoding="utf-8"
        )
        runner = PytestRunner(MutmutConfig(tests_dir=["tests"]))

        covered_map = gather_coverage(runner, ["src/pkg/mod.py"])
        file_covered = get_covered_lines_for_file("src/pkg/mod.py", covered_map)

        assert file_covered is not None
        assert 2 in file_covered  # body of covered()
        assert 6 not in file_covered  # body of never_called() was never run

    def test_parallel_true_config_is_collected_end_to_end(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """M-019: parallel=true writes suffixed parts that must be merged.

        The staged project coverage configuration may force parallel data
        files (``parallel = true``; ``concurrency = multiprocessing`` forces
        it too): coverage then never writes the suffixless data file, so the
        parent must collect and merge every part of the exclusive output
        directory instead of failing with "produced no data file".
        """
        monkeypatch.chdir(tmp_path)
        _build_mutants_tree(tmp_path)
        (tmp_path / "mutants" / "pyproject.toml").write_text(
            "[tool.coverage.run]\nparallel = true\n", encoding="utf-8"
        )
        runner = PytestRunner(MutmutConfig(tests_dir=["tests"]))

        covered_map = gather_coverage(runner, ["src/pkg/mod.py"])
        file_covered = get_covered_lines_for_file("src/pkg/mod.py", covered_map)

        assert file_covered is not None
        assert 2 in file_covered  # body of covered()
        assert 6 not in file_covered  # body of never_called() was never run

    @pytest.mark.parametrize("relative_files", [False, True])
    @pytest.mark.parametrize("drop_child_part", [False, True])
    def test_spawn_child_lines_remain_in_the_mutation_universe(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        relative_files: bool,
        drop_child_part: bool,
    ) -> None:
        """S3-002: real spawn children contribute their executed source lines."""
        monkeypatch.chdir(tmp_path)
        _build_mutants_tree(tmp_path)
        source = (
            "def covered():\n    return 1\n\n"
            "def only_in_child():\n    value = 2\n    return value + 1\n\n"
            "def never_called():\n    return 42\n"
        )
        (tmp_path / "mutants/src/pkg/mod.py").write_text(source, encoding="utf-8")
        (tmp_path / "mutants/pyproject.toml").write_text(
            '[tool.pytest.ini_options]\npythonpath = ["src"]\n'
            '[tool.coverage.run]\nconcurrency = ["multiprocessing"]\n'
            f"relative_files = {str(relative_files).lower()}\n",
            encoding="utf-8",
        )
        (tmp_path / "mutants/tests/test_mod.py").write_text(
            textwrap.dedent(
                """
                import multiprocessing
                from pkg.mod import covered, only_in_child

                def test_both():
                    assert covered() == 1
                    process = multiprocessing.get_context("spawn").Process(target=only_in_child)
                    process.start()
                    try:
                        process.join(30)
                        assert process.exitcode == 0
                    finally:
                        if process.is_alive():
                            process.terminate()
                            process.join(10)
                        process.close()
                """
            ),
            encoding="utf-8",
        )
        runner = PytestRunner(MutmutConfig(tests_dir=["tests"]))

        collect = runner.run_coverage_collection
        observed_parts: list[set[int]] = []

        def observe_collection(data_file: Path) -> int:
            result = collect(data_file)
            for part in data_file.parent.iterdir():
                if not part.name.startswith(".coverage.mutmut"):
                    continue
                data = coverage.CoverageData(basename=str(part))
                data.read()
                for filename in data.measured_files():
                    if filename.replace("\\", "/").endswith("/pkg/mod.py"):
                        body = set(data.lines(filename) or [])
                        observed_parts.append(body)
                        if drop_child_part and {5, 6} <= body:
                            part.unlink()
            return result

        monkeypatch.setattr(runner, "run_coverage_collection", observe_collection)
        covered_map = gather_coverage(runner, ["src/pkg/mod.py"])

        assert any(2 in lines and 5 not in lines for lines in observed_parts)
        assert any({5, 6} <= lines and 2 not in lines for lines in observed_parts)
        assert covered_map is None, "Multiprocessing cannot authorize line exclusion"

    def test_followup_run_measures_original_lines_not_generator_lines(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """M-002 (issue #144): a follow-up run restores unmutated bytes first.

        The previous run left trampolined generator output plus an owned
        sidecar in the staging tree.  Without the retain policy the coverage
        phase measured the generator module's shifted lines and silently
        selected the wrong mutant lines.
        """
        import hashlib

        from mutmut_win.file_setup import copy_src_dir
        from mutmut_win.models import SourceFileMutationData

        monkeypatch.chdir(tmp_path)
        _build_mutants_tree(tmp_path)
        live = tmp_path / "src" / "pkg" / "mod.py"
        live.parent.mkdir(parents=True, exist_ok=True)
        live.write_text(_MODULE_SOURCE, encoding="utf-8")
        # The automatic mirror walks the live project root, so the test
        # module must exist live as well or the follow-up copy run would
        # remove the staged tests/ tree as stale.
        live_tests = tmp_path / "tests"
        live_tests.mkdir(exist_ok=True)
        (live_tests / "test_mod.py").write_text(_TEST_SOURCE, encoding="utf-8")
        staged = tmp_path / "mutants" / "src" / "pkg" / "mod.py"

        # Simulate the previous run: trampolined output + owned sidecar.
        generated, _names = mutate_file_contents("src/pkg/mod.py", _MODULE_SOURCE, None)
        staged.write_text(generated, encoding="utf-8")
        SourceFileMutationData(
            path="src/pkg/mod.py",
            source_hash=hashlib.sha256(live.read_bytes()).hexdigest(),
            generation_fingerprint="a" * 64,
            generated_hash=hashlib.sha256(staged.read_bytes()).hexdigest(),
        ).save_generation_metadata()

        cfg = MutmutConfig(
            tests_dir=["tests"],
            paths_to_mutate=["src/pkg/mod.py"],
            max_children=1,
            mutate_only_covered_lines=True,
        )
        copy_src_dir(cfg)

        # The retain policy must have restored the unmutated bytes before
        # any coverage phase can execute against this tree.
        assert staged.read_text(encoding="utf-8") == _MODULE_SOURCE
        assert not staged.with_name(staged.name + ".meta").exists()

        runner = PytestRunner(cfg)
        covered_map = gather_coverage(runner, ["src/pkg/mod.py"])
        file_covered = get_covered_lines_for_file("src/pkg/mod.py", covered_map)
        assert file_covered is not None
        assert 2 in file_covered  # body of covered() — ORIGINAL line numbering
        assert 6 not in file_covered  # body of never_called() was never run
