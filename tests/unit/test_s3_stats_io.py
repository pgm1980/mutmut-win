"""S3-022: unreadable optional stats use existing diagnostic paths."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner
from hypothesis import given
from hypothesis import strategies as st

from mutmut_win.cli import cli
from mutmut_win.stats import (
    MutmutStats,
    collect_or_load_stats,
    load_stats,
    save_stats,
)
from tests.unit.windows_fs_util import sharing_violation_holder

if TYPE_CHECKING:
    from pathlib import Path


def test_directory_collision_is_unusable_stats(tmp_path: Path) -> None:
    """A real Windows directory cannot be read as the optional stats file."""
    stats_path = tmp_path / "mutmut-stats.json"
    stats_path.mkdir()
    sentinel = stats_path / "user-owned.txt"
    sentinel.write_text("preserve", encoding="utf-8")
    assert load_stats(tmp_path) is None
    assert sentinel.read_text(encoding="utf-8") == "preserve"


def test_native_locked_stats_are_unusable_until_released(tmp_path: Path) -> None:
    """A sharing violation is diagnostic; releasing it restores the same stats."""
    original = MutmutStats(duration_by_test={"test_mod.py::test_a": 0.5})
    save_stats(original, tmp_path)
    path = tmp_path / "mutmut-stats.json"
    before = path.read_bytes()
    with sharing_violation_holder(path):
        assert load_stats(tmp_path) is None
    assert path.read_bytes() == before
    restored = load_stats(tmp_path)
    assert restored is not None
    assert restored.duration_by_test == original.duration_by_test


def test_read_error_after_successful_open_is_unusable_stats(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An IO error during JSON input has the same optional-cache boundary."""
    save_stats(MutmutStats(), tmp_path)
    failed_read = MagicMock(side_effect=OSError("injected read failure"))
    monkeypatch.setattr("mutmut_win.stats.json.load", failed_read)
    assert load_stats(tmp_path) is None
    failed_read.assert_called_once()


@pytest.mark.parametrize("command", [["tests-for-mutant", "mod.x_f__mutmut_1"], ["time-estimates"]])
@pytest.mark.parametrize("collision", [False, True])
def test_cli_stats_readers_use_diagnostic_channel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, command: list[str], collision: bool
) -> None:
    """Missing and directory stats produce the existing useful CLI error."""
    monkeypatch.chdir(tmp_path)
    if collision:
        (tmp_path / ".mutmut-cache" / "mutmut-stats.json").mkdir(parents=True)
    result = CliRunner().invoke(cli, command)
    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)
    assert "No stats found." in result.stderr
    assert result.stdout == ""


def test_collection_diagnoses_directory_without_displacing_it(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """An unrevocable cache cannot be refreshed or grant mapping authority."""
    path = tmp_path / "mutmut-stats.json"
    path.mkdir()
    runner = MagicMock()
    result = collect_or_load_stats(runner, tmp_path)
    assert result.tests_by_mangled_function_name == {}
    assert result.duration_by_test == {}
    assert result.mapping_is_authoritative is False
    runner.run_stats.assert_not_called()
    assert path.is_dir()
    output = capsys.readouterr().out
    assert "stats" in output
    assert "full test suite" in output


def test_missing_and_valid_stats_remain_distinct(tmp_path: Path) -> None:
    """Generated valid durations survive real persistence, unlike missing input."""
    assert load_stats(tmp_path) is None

    @given(st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False))
    def check(duration: float) -> None:
        stats = MutmutStats(duration_by_test={"test_mod.py::test_a": duration})
        save_stats(stats, tmp_path)
        loaded = load_stats(tmp_path)
        assert loaded is not None
        assert loaded.duration_by_test == stats.duration_by_test
        assert loaded.mapping_is_authoritative is False

    check()
