"""CACHE-001: a corrupt ``.mutmut-cache`` DB surfaces a clean error, not a traceback.

External QA on v2.19.0 found that garbage bytes in ``mutmut-cache.db`` escaped as a
raw ``sqlite3.DatabaseError`` from ``run`` / ``results`` / ``export-cicd-stats``.
``db.create_db`` now wraps it in :class:`CorruptCacheError` (a ``MutmutWinError``),
so the existing CLI domain-error handlers render it cleanly. ``run --force`` recovers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from mutmut_win.cli import _load_results_or_exit, cli
from mutmut_win.db import create_db, load_results
from mutmut_win.exceptions import CorruptCacheError, MutmutWinError

if TYPE_CHECKING:
    from pathlib import Path

#: Bytes that are NOT a valid SQLite header ("SQLite format 3\x00").
_GARBAGE = b"this is not a sqlite database -- just garbage bytes\x00\xff" * 8


def _corrupt_db(tmp_path: Path) -> Path:
    db = tmp_path / "mutmut-cache.db"
    db.write_bytes(_GARBAGE)
    return db


class TestDbLayer:
    def test_create_db_raises_corrupt_cache_error(self, tmp_path: Path) -> None:
        with pytest.raises(CorruptCacheError, match="corrupt or unreadable"):
            create_db(_corrupt_db(tmp_path))

    def test_corrupt_cache_error_is_a_mutmut_win_error(self, tmp_path: Path) -> None:
        # subclassing MutmutWinError is what lets the existing CLI handlers catch it
        with pytest.raises(MutmutWinError):
            create_db(_corrupt_db(tmp_path))

    def test_load_results_raises_corrupt_cache_error(self, tmp_path: Path) -> None:
        with pytest.raises(CorruptCacheError):
            load_results(_corrupt_db(tmp_path))

    def test_fresh_path_is_not_treated_as_corrupt(self, tmp_path: Path) -> None:
        create_db(tmp_path / "fresh.db")
        assert (tmp_path / "fresh.db").exists()

    def test_message_is_specific_and_unwrapped(self, tmp_path: Path) -> None:
        with pytest.raises(CorruptCacheError) as exc_info:
            create_db(_corrupt_db(tmp_path))
        msg = str(exc_info.value)
        assert msg.startswith("cache database at")  # kills a leading XX string-wrap
        assert "corrupt or unreadable" in msg
        assert "Delete the .mutmut-cache/" in msg  # case-exact -> kills the lowercase mutant
        assert "re-run with --force" in msg
        assert "XX" not in msg  # kills the string-XX-wrap mutants on the message

    def test_helper_exits_one_on_a_real_corrupt_db(self, tmp_path: Path) -> None:
        with pytest.raises(SystemExit) as exc_info:
            _load_results_or_exit(_corrupt_db(tmp_path))
        assert exc_info.value.code == 1

    def test_helper_forwards_its_path_to_load_results(self, tmp_path: Path) -> None:
        # a real (un-patched) load_results on an absent path returns [] — guards
        # the helper actually forwarding its path argument (not a hardcoded one)
        assert _load_results_or_exit(tmp_path / "absent.db") == []


class TestCliRendersCleanly:
    _ERR = CorruptCacheError(
        "cache database at '.mutmut-cache\\mutmut-cache.db' is corrupt or unreadable "
        "(file is not a database). Delete the .mutmut-cache/ directory or re-run with --force."
    )

    def test_results_renders_clean_exit(self) -> None:
        runner = CliRunner()
        with patch("mutmut_win.cli.load_results", side_effect=self._ERR):
            result = runner.invoke(cli, ["results"])
        assert result.exit_code == 1
        # the message goes to STDERR (errors must not pollute stdout pipelines)
        assert "corrupt or unreadable" in result.stderr
        assert "--force" in result.stderr

    def test_export_cicd_stats_renders_clean_exit(self) -> None:
        runner = CliRunner()
        with patch("mutmut_win.cli.load_results", side_effect=self._ERR):
            result = runner.invoke(cli, ["export-cicd-stats"])
        assert result.exit_code == 1
        assert "corrupt or unreadable" in result.stderr
