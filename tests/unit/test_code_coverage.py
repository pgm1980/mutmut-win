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

from mutmut_win.code_coverage import gather_coverage, get_covered_lines_for_file

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

    def test_nonzero_exit_raises_loudly(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The old code turned ANY failure into "0 covered lines" and the run
        # ended with an uncaused "No mutants generated." (A3-CM-003).
        monkeypatch.chdir(tmp_path)
        (tmp_path / "mutants").mkdir()
        runner = MagicMock()
        runner.run_coverage_collection.return_value = 1
        with pytest.raises(Exception, match="coverage"):
            gather_coverage(runner, ["src/mod.py"])

    def test_missing_data_file_raises(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / "mutants").mkdir()
        runner = MagicMock()
        runner.run_coverage_collection.return_value = 0  # but writes nothing
        with pytest.raises(Exception, match="data file"):
            gather_coverage(runner, ["src/mod.py"])

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

        with pytest.raises(Exception, match="no coverage"):
            gather_coverage(runner, ["src/mod.py"])
