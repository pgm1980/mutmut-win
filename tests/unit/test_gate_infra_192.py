"""Issue #192: reliable targeted mutation gates.

Root causes fixed together:

* **F-A** — the stats recorder was itself trampolined whenever the engine
  mutated its own source tree, so under ``MUTANT_UNDER_TEST=stats`` every
  recorded hit called the recorder's own trampoline, which recorded again
  and recursed without bound.  The stats phase failed for every such gate
  and every task fell back to the full-suite budget (the M-102 symptom).
  ``mutmut_win.hit_recording`` now stages verbatim and is never mutated.
* **F-B** — ``--tests-dir`` was not repeatable: click's last-wins silently
  dropped every earlier occurrence, so combined gates lost every kill that
  only the dropped test files carried.
* **F-C** — stats and forced-fail failures swallowed the captured pytest
  tail, making the remaining failure modes unnecessarily hard to diagnose.
"""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from click.testing import CliRunner

import mutmut_win.cli as cli_module
from mutmut_win import __main__ as _  # noqa: F401  # ensure package import side effects
from mutmut_win.cli import cli as cli_entry
from mutmut_win.config import MutmutConfig
from mutmut_win.file_setup import (
    _is_generation_excluded_self_module,
    copy_src_dir,
    create_mutants_for_file,
)
from mutmut_win.runner import PytestRunner

if TYPE_CHECKING:
    import pytest


class TestStatsRecorderExclusion:
    """F-A: the recorder module stages verbatim and never mutates."""

    def test_recorder_module_is_recognized_by_resolved_identity(self) -> None:
        recorder = importlib.import_module("mutmut_win.hit_recording")
        recorder_file = Path(recorder.__file__)
        assert recorder_file is not None
        assert _is_generation_excluded_self_module(recorder_file) is True

    def test_foreign_file_with_the_same_basename_stays_mutable(
        self,
        tmp_path: Path,
    ) -> None:
        foreign = tmp_path / "hit_recording.py"
        foreign.write_text("def value():\n    return 1\n", encoding="utf-8")
        assert _is_generation_excluded_self_module(foreign) is False

    def test_generation_stages_recorder_verbatim_without_trampolines(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / "mutants" / "src").mkdir(parents=True)
        recorder = importlib.import_module("mutmut_win.hit_recording")
        source_file = Path(recorder.__file__)
        output = Path("mutants") / "src" / "hit_recording.py"

        names, warns, took_fast_path = create_mutants_for_file(source_file, output)

        assert names == []
        assert warns == []
        assert took_fast_path is False
        staged = output.read_text(encoding="utf-8")
        assert "record_trampoline_hit" in staged
        assert "__mutmut_orig" not in staged
        assert staged == source_file.read_text(encoding="utf-8")

    def test_normal_project_file_still_generates_mutants(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        source = tmp_path / "src" / "mod.py"
        source.parent.mkdir()
        source.write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
        config = MutmutConfig(paths_to_mutate=["src"])
        copy_src_dir(config)
        names, _warns, _fast = create_mutants_for_file(
            Path("src/mod.py"),
            Path("mutants/src/mod.py"),
        )
        assert names, "the exclusion must not leak into ordinary files"


class TestRepeatableTestsDirOption:
    """F-B: every ``--tests-dir`` occurrence reaches the configuration."""

    def test_two_tests_dir_values_are_both_applied(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        captured_configs: list[MutmutConfig] = []

        class _StubOrchestrator:
            def __init__(self, config: MutmutConfig, *_args: object, **_kwargs: object) -> None:
                captured_configs.append(config)

            class _Result:
                total_mutants = 0
                killed = 0
                survived = 0
                timeout = 0
                suspicious = 0
                skipped = 0
                no_tests = 0
                caught_by_type_check = 0
                unchecked = 0
                killed_by_infinite_loop = 0
                duration_seconds = 0.0
                was_interrupted = False
                run_aborted = False
                degraded_files: ClassVar[list[str]] = []

                def compute_score(self, *_args: object, **_kwargs: object) -> float:
                    return 0.0

            def run(self) -> object:
                return self._Result()

            def dry_run(self) -> object:
                return self._Result()

        monkeypatch.setattr(cli_module, "MutationOrchestrator", _StubOrchestrator)
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "mod.py").write_text("VALUE = 1\n", encoding="utf-8")

        result = CliRunner().invoke(
            cli_entry,
            [
                "run",
                "--tests-dir",
                "tests/unit/test_a.py",
                "--tests-dir",
                "tests/unit/test_b.py",
                "--dry-run",
            ],
        )
        assert result.exit_code == 0, result.output
        assert captured_configs, "the orchestrator must be constructed"
        assert captured_configs[0].tests_dir == [
            "tests/unit/test_a.py",
            "tests/unit/test_b.py",
        ]


class TestPhaseDiagnostics:
    """F-C: stats and forced-fail failures publish the captured tail."""

    def _runner_with_phase_result(
        self,
        exit_code: int,
        tail: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> PytestRunner:
        runner = PytestRunner(MutmutConfig(paths_to_mutate=["src"]))

        def fake_phase(
            *_args: object,
            **_kwargs: object,
        ) -> int:
            runner._last_diagnostic_output = tail
            return exit_code

        monkeypatch.setattr(runner, "_run_phase", fake_phase)
        return runner

    def test_stats_failure_prints_captured_tail(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.Capsys,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / "mutants").mkdir()
        runner = self._runner_with_phase_result(
            1,
            "ImportError: no module named 'demo'",
            monkeypatch,
        )
        exit_code = runner.run_stats()
        assert exit_code == 1
        out = capsys.readouterr().out
        assert "stats collection failed" in out
        assert "stats pytest output (tail)" in out
        assert "ImportError: no module named 'demo'" in out

    def test_forced_fail_timeout_prints_captured_tail(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.Capsys,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / "mutants").mkdir()
        runner = self._runner_with_phase_result(
            36,
            " hypothesis is shrinking and will not stop",
            monkeypatch,
        )
        exit_code = runner.run_forced_fail("mod.value__mutmut_1")
        assert exit_code == 36
        assert runner.last_forced_fail_attributed is None
        out = capsys.readouterr().out
        assert "forced-fail output before timeout (tail)" in out
        assert "hypothesis is shrinking" in out
