"""Unit tests for the reactivated coverage gating (Issue #95, audit A3-CM-003/013).

``mutate_only_covered_lines`` was dead since the subprocess rewrite: the old
``gather_coverage`` collected in the PARENT while pytest ran in a subprocess,
so ``lines()`` returned nothing, every mutant was filtered, and the run ended
with an uncaused "No mutants generated."  The rework runs coverage as a
subprocess bridge and loads the data file in the parent — with normcase path
keying (spike-verified: a case-deviating key returns None from ``lines()``)
and LOUD failure modes instead of silent emptiness.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import coverage
import pytest

import mutmut_win.code_coverage as code_coverage_module
from mutmut_win.code_coverage import gather_coverage, get_covered_lines_for_file
from mutmut_win.exceptions import CoverageCollectionError

if TYPE_CHECKING:
    from pathlib import Path


class TestGetCoveredLinesForFile:
    def test_none_mapping_means_feature_disabled(self) -> None:
        assert get_covered_lines_for_file("src/mod.py", None) is None

    def test_none_filename_returns_none(self) -> None:
        assert get_covered_lines_for_file(None, {}) is None  # type: ignore[arg-type]

    def test_exact_key_hit(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        key = os.path.normcase(str((tmp_path / "mutants" / "src" / "mod.py").absolute()))
        covered = {key: {1, 2, 5}}
        assert get_covered_lines_for_file("src/mod.py", covered) == {1, 2, 5}

    def test_case_deviating_lookup_still_hits(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # A3-CM-013: coverage stores the FS case form; the constructed lookup
        # key may differ in drive-letter or directory case on Windows.
        monkeypatch.chdir(tmp_path)
        raw = str((tmp_path / "mutants" / "src" / "mod.py").absolute())
        covered = {os.path.normcase(raw.upper()): {3}}
        assert get_covered_lines_for_file("src/mod.py", covered) == {3}

    def test_unmeasured_file_yields_empty_set(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        assert get_covered_lines_for_file("src/other.py", {}) == set()


class TestGatherCoverage:
    def _write_data_file(self, data_file: Path, measured: dict[str, list[int]]) -> None:
        cov = coverage.Coverage(data_file=str(data_file))
        data = cov.get_data()
        data.add_lines(dict(measured.items()))
        data.write()

    def test_happy_path_returns_normcased_mapping(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / "mutants").mkdir()
        measured_path = str((tmp_path / "mutants" / "src" / "mod.py").absolute())

        runner = MagicMock()

        def fake_collection(data_file: Path) -> int:
            self._write_data_file(data_file, {measured_path: [1, 2, 5]})
            return 0

        runner.run_coverage_collection.side_effect = fake_collection

        covered = gather_coverage(runner, ["src/mod.py"])
        assert covered[os.path.normcase(measured_path)] == {1, 2, 5}
        assert get_covered_lines_for_file("src/mod.py", covered) == {1, 2, 5}

    def test_collection_uses_fresh_data_file_outside_mutants(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        mutants_dir = tmp_path / "mutants"
        mutants_dir.mkdir()
        legacy_data_file = mutants_dir / ".coverage.mutmut"
        legacy_data_file.write_bytes(b"stale coverage data")
        measured_path = str((mutants_dir / "src" / "mod.py").absolute())

        runner = MagicMock()

        def fake_collection(data_file: Path) -> int:
            assert not data_file.is_relative_to(mutants_dir)
            assert not data_file.exists()
            self._write_data_file(data_file, {measured_path: [2, 7]})
            return 0

        runner.run_coverage_collection.side_effect = fake_collection

        covered = gather_coverage(runner, ["src/mod.py"])

        assert covered == {os.path.normcase(measured_path): {2, 7}}
        assert legacy_data_file.read_bytes() == b"stale coverage data"

    def test_external_temp_directory_contract_is_deterministic_and_cleanup_tolerant(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The coordination directory must stay external and tolerate cleanup races."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "mutants").mkdir()
        output_dir = tmp_path / "external-coverage-output"
        measured_path = str((tmp_path / "mutants" / "src" / "mod.py").absolute())
        calls: list[tuple[str, bool]] = []

        class FakeTemporaryDirectory:
            def __init__(self, *, prefix: str, ignore_cleanup_errors: bool) -> None:
                calls.append((prefix, ignore_cleanup_errors))

            def __enter__(self) -> str:
                output_dir.mkdir()
                return str(output_dir)

            def __exit__(self, *_args: object) -> None:
                return None

        monkeypatch.setattr(
            code_coverage_module.tempfile,
            "TemporaryDirectory",
            FakeTemporaryDirectory,
        )
        runner = MagicMock()

        def fake_collection(data_file: Path) -> int:
            self._write_data_file(data_file, {measured_path: [4]})
            return 0

        runner.run_coverage_collection.side_effect = fake_collection

        assert gather_coverage(runner, ["src/mod.py"]) == {os.path.normcase(measured_path): {4}}
        assert calls == [("mutmut-win-coverage-output-", True)]

    def test_measured_file_with_no_lines_is_handled_as_empty_coverage(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """CoverageData.lines may return None and must not crash collection."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "mutants").mkdir()
        measured_path = str((tmp_path / "mutants" / "src" / "mod.py").absolute())

        class FakeCoverageData:
            def measured_files(self) -> set[str]:
                return {measured_path}

            def lines(self, filename: str) -> None:
                assert filename == measured_path

        class FakeCoverage:
            def __init__(self, *, data_file: str) -> None:
                assert data_file.endswith(".coverage.mutmut")

            def load(self) -> None:
                return None

            def get_data(self) -> FakeCoverageData:
                return FakeCoverageData()

        monkeypatch.setattr(code_coverage_module.coverage, "Coverage", FakeCoverage)
        runner = MagicMock()

        def fake_collection(data_file: Path) -> int:
            data_file.write_bytes(b"coverage proof")
            return 0

        runner.run_coverage_collection.side_effect = fake_collection

        with pytest.raises(CoverageCollectionError, match="measured no coverage"):
            gather_coverage(runner, ["src/mod.py"])

    def test_nonzero_exit_raises_loudly(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The old code turned ANY failure into "0 covered lines" and the run
        # ended with an uncaused "No mutants generated." (A3-CM-003).
        monkeypatch.chdir(tmp_path)
        (tmp_path / "mutants").mkdir()
        measured_path = str((tmp_path / "mutants" / "src" / "mod.py").absolute())
        runner = MagicMock()

        def fake_collection(data_file: Path) -> int:
            # A valid data file ensures the exit-code failure cannot be
            # accidentally replaced by a later missing/empty-data failure.
            self._write_data_file(data_file, {measured_path: [1]})
            return 17

        runner.run_coverage_collection.side_effect = fake_collection

        with pytest.raises(CoverageCollectionError) as exc_info:
            gather_coverage(runner, ["src/mod.py"])

        assert str(exc_info.value) == (
            "coverage collection run failed with exit code 17 — "
            "the test suite must pass before mutate_only_covered_lines can "
            "measure it."
        )

    def test_missing_data_file_raises(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / "mutants").mkdir()
        runner = MagicMock()
        runner.run_coverage_collection.return_value = 0  # but writes nothing
        with pytest.raises(CoverageCollectionError) as exc_info:
            gather_coverage(runner, ["src/mod.py"])

        assert str(exc_info.value) == (
            "coverage collection produced no data file — coverage did not record anything."
        )

    def test_mixed_measurement_preserves_empty_set_for_unmeasured_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        mutants_dir = tmp_path / "mutants"
        mutants_dir.mkdir()
        measured_path = str((mutants_dir / "src" / "measured.py").absolute())
        unmeasured_path = str((mutants_dir / "src" / "unmeasured.py").absolute())

        runner = MagicMock()

        def fake_collection(data_file: Path) -> int:
            self._write_data_file(data_file, {measured_path: [3, 9]})
            return 0

        runner.run_coverage_collection.side_effect = fake_collection

        covered = gather_coverage(runner, ["src/measured.py", "src/unmeasured.py"])

        assert covered == {
            os.path.normcase(measured_path): {3, 9},
            os.path.normcase(unmeasured_path): set(),
        }

    def test_empty_measurement_raises_with_subprocess_hint(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # xdist / subprocess-spawning suites execute the code outside the
        # measured process: every source file would look uncovered and EVERY
        # mutant would be silently filtered. Fail loudly instead.
        monkeypatch.chdir(tmp_path)
        (tmp_path / "mutants").mkdir()
        unrelated = str((tmp_path / "mutants" / "tests" / "test_x.py").absolute())

        runner = MagicMock()

        def fake_collection(data_file: Path) -> int:
            self._write_data_file(data_file, {unrelated: [1]})
            return 0

        runner.run_coverage_collection.side_effect = fake_collection

        with pytest.raises(CoverageCollectionError) as exc_info:
            gather_coverage(runner, ["src/mod.py"])

        assert str(exc_info.value) == (
            "coverage collection measured no coverage in any source file — "
            "suites that run their code in subprocesses or pytest-xdist "
            "workers are not supported with mutate_only_covered_lines "
            "(their execution is invisible to the bridge)."
        )
