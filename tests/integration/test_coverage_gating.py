"""End-to-end test for the reactivated coverage gating (Issue #95).

Drives the REAL chain — `coverage run -m pytest` as a subprocess inside a
mutants tree, parent-side data-file loading, normcase keying, and the
MutationVisitor's covered-lines filter — against a tiny project with one
covered and one never-called function.  Spike-verified design
(`_issues/spike_coverage_bridge.py`); this is the regression pin.
"""

from __future__ import annotations

import textwrap
from typing import TYPE_CHECKING

import coverage
import pytest

from mutmut_win.code_coverage import gather_coverage, get_covered_lines_for_file
from mutmut_win.config import MutmutConfig
from mutmut_win.mutation import mutate_file_contents
from mutmut_win.runner import PytestRunner

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.integration, pytest.mark.slow]

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
