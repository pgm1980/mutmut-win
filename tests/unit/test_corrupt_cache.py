"""CACHE-001: a corrupt ``.mutmut-cache`` DB surfaces a clean error, not a traceback.

External QA on v2.19.0 found that garbage bytes in ``mutmut-cache.db`` escaped as a
raw ``sqlite3.DatabaseError`` from ``run`` / ``results`` / ``export-cicd-stats``.
``db.create_db`` now wraps it in :class:`CorruptCacheError` (a ``MutmutWinError``),
so the existing CLI domain-error handlers render it cleanly. ``run --force`` recovers.

M-037 / issue #164 extends the split: environment failures (SQLITE_READONLY,
SQLITE_IOERR, SQLITE_FULL, SQLITE_CANTOPEN) are NOT corruption and must never
advise deleting the cache — they raise :class:`CacheEnvironmentError` instead.
"""

from __future__ import annotations

import sqlite3
import stat
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from click.testing import CliRunner
from hypothesis import given
from hypothesis import strategies as st
from textual.widgets import Static

from mutmut_win.browser import ResultBrowser
from mutmut_win.cli import _load_results_or_exit, cli
from mutmut_win.db import RunStateError, _raise_database_error, create_db, load_results, save_result
from mutmut_win.exceptions import CacheEnvironmentError, CorruptCacheError, MutmutWinError

if TYPE_CHECKING:
    import os

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

    def test_live_lock_contention_is_not_misreported_as_corruption(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        database = tmp_path / "busy.db"
        create_db(database)
        real_connect = sqlite3.connect
        blocker = real_connect(database)
        blocker.execute("BEGIN EXCLUSIVE")

        def fast_connect(database: str | os.PathLike[str], **_kwargs: object) -> sqlite3.Connection:
            return real_connect(database, timeout=0.01)

        monkeypatch.setattr(sqlite3, "connect", fast_connect)
        try:
            with pytest.raises(RunStateError, match=r"busy or locked.*must not be deleted"):
                load_results(database)
        finally:
            blocker.rollback()
            blocker.close()

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

    def test_results_renders_clean_exit(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        runner = CliRunner()
        monkeypatch.chdir(tmp_path)
        with patch("mutmut_win.cli.load_current_run", side_effect=self._ERR):
            result = runner.invoke(cli, ["results"])
        assert result.exit_code == 1
        # the message goes to STDERR (errors must not pollute stdout pipelines)
        assert "corrupt or unreadable" in result.stderr
        assert "--force" in result.stderr

    def test_export_cicd_stats_renders_clean_exit(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        runner = CliRunner()
        monkeypatch.chdir(tmp_path)
        (tmp_path / "mutants").mkdir()
        with patch("mutmut_win.cli.load_current_run", side_effect=self._ERR):
            result = runner.invoke(cli, ["export-cicd-stats"])
        assert result.exit_code == 1
        assert "corrupt or unreadable" in result.stderr


class TestEnvironmentFailuresAreNotCorruption:
    """M-037 / issue #164: environment codes must not diagnose cache corruption."""

    @pytest.mark.parametrize(
        "code",
        [
            sqlite3.SQLITE_READONLY,
            sqlite3.SQLITE_IOERR,
            sqlite3.SQLITE_FULL,
            sqlite3.SQLITE_CANTOPEN,
            778,  # SQLITE_IOERR_WRITE (10 | 2 << 8): an extended IOERR code
        ],
    )
    def test_environment_sqlite_code_is_not_misreported_as_corruption(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, code: int
    ) -> None:
        database = tmp_path / "env.db"
        create_db(database)

        def failing_connect(*_args: object, **_kwargs: object) -> sqlite3.Connection:
            exc = sqlite3.OperationalError("simulated environment failure")
            exc.sqlite_errorcode = code
            raise exc

        monkeypatch.setattr(sqlite3, "connect", failing_connect)
        with pytest.raises(MutmutWinError) as exc_info:
            load_results(database)

        assert isinstance(exc_info.value, CacheEnvironmentError)
        assert not isinstance(exc_info.value, CorruptCacheError)
        message = str(exc_info.value)
        assert f"sqlite error code {code}" in message
        assert "environment problem" in message
        assert "Delete the .mutmut-cache" not in message
        assert "--force" not in message
        assert "must not be deleted" in message

    def test_readonly_file_attribute_is_not_misreported_as_corruption(self, tmp_path: Path) -> None:
        # FILE_ATTRIBUTE_READONLY: SQLite opens the file read-only under Windows
        # and fails the write with base code 8 instead of corrupting anything.
        database = tmp_path / "readonly.db"
        create_db(database)
        database.chmod(stat.S_IREAD)
        try:
            with pytest.raises(MutmutWinError) as exc_info:
                save_result(database, "pkg_mod_x_f__mutmut_1", "killed", 0, 0.1)
        finally:
            database.chmod(stat.S_IWRITE | stat.S_IREAD)
        assert isinstance(exc_info.value, CacheEnvironmentError)
        assert not isinstance(exc_info.value, CorruptCacheError)
        message = str(exc_info.value)
        assert "SQLITE_READONLY" in message
        assert "environment problem" in message
        assert "Delete the .mutmut-cache" not in message
        assert "--force" not in message
        assert "must not be deleted" in message

    def test_database_error_without_error_code_stays_corrupt_cache(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # A manually constructed DatabaseError carries no sqlite_errorcode
        # attribute; unclassified failures must stay conservative (corrupt).
        database = tmp_path / "uncoded.db"
        create_db(database)

        def failing_connect(*_args: object, **_kwargs: object) -> sqlite3.Connection:
            raise sqlite3.DatabaseError("constructed without sqlite_errorcode")

        monkeypatch.setattr(sqlite3, "connect", failing_connect)
        with pytest.raises(CorruptCacheError):
            load_results(database)


class TestSqliteCodeClassificationProperty:
    """M-037: base-code classification must hold for every extended-code variant."""

    @given(
        base=st.sampled_from([3, 8, 10, 13, 14, 22]),
        ext=st.integers(min_value=0, max_value=60),
    )
    def test_environment_base_codes_never_advise_deletion(self, base: int, ext: int) -> None:
        exc = sqlite3.OperationalError("simulated")
        exc.sqlite_errorcode = base | (ext << 8)
        with pytest.raises(CacheEnvironmentError) as exc_info:
            _raise_database_error(Path("x.db"), exc)
        assert not isinstance(exc_info.value, CorruptCacheError)
        assert "Delete" not in str(exc_info.value)

    @given(
        base=st.sampled_from([1, 5, 6, 11, 26]),
        ext=st.integers(min_value=0, max_value=60),
    )
    def test_non_environment_base_codes_keep_their_classification(
        self, base: int, ext: int
    ) -> None:
        exc = sqlite3.OperationalError("simulated")
        exc.sqlite_errorcode = base | (ext << 8)
        if base in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED):
            with pytest.raises(RunStateError):
                _raise_database_error(Path("x.db"), exc)
        else:
            with pytest.raises(CorruptCacheError):
                _raise_database_error(Path("x.db"), exc)


class TestCliRendersEnvironmentErrorsCleanly:
    _ERR = CacheEnvironmentError(
        "cache database at '.mutmut-cache\\mutmut-cache.db' could not be read or "
        "written because of an environment problem (SQLITE_READONLY (8): attempt "
        "to write a readonly database). The cache is not known to be corrupt and "
        "must not be deleted."
    )

    def test_results_renders_clean_exit_without_delete_advice(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        runner = CliRunner()
        monkeypatch.chdir(tmp_path)
        with patch("mutmut_win.cli.load_current_run", side_effect=self._ERR):
            result = runner.invoke(cli, ["results"])
        assert result.exit_code == 1
        # the message goes to STDERR with guidance, never with delete advice
        assert "environment problem" in result.stderr
        assert "must not be deleted" in result.stderr
        assert "--force" not in result.stderr
        assert "Delete the .mutmut-cache" not in result.stderr

    def test_export_cicd_stats_renders_clean_exit_without_delete_advice(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        runner = CliRunner()
        monkeypatch.chdir(tmp_path)
        (tmp_path / "mutants").mkdir()
        with patch("mutmut_win.cli.load_current_run", side_effect=self._ERR):
            result = runner.invoke(cli, ["export-cicd-stats"])
        assert result.exit_code == 1
        assert "environment problem" in result.stderr
        assert "--force" not in result.stderr
        assert "Delete the .mutmut-cache" not in result.stderr


@pytest.mark.asyncio
async def test_browser_shows_environment_error_instead_of_crashing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The TUI banner surfaces a cache environment failure, not a traceback (M-037)."""
    monkeypatch.chdir(tmp_path)
    db_path = tmp_path / ".mutmut-cache" / "mutmut-cache.db"
    db_path.parent.mkdir()

    def raise_environment_error(*_args: object, **_kwargs: object) -> object:
        raise CacheEnvironmentError(
            "cache database at 'x.db' could not be read or written because of "
            "an environment problem (SQLITE_FULL (13): database or disk is full). "
            "The cache is not known to be corrupt and must not be deleted."
        )

    monkeypatch.setattr("mutmut_win.db.load_latest_run_results", raise_environment_error)
    app = ResultBrowser(db_path=db_path)
    async with app.run_test():
        banner = app.query_one("#run_status", Static)
        status_text = str(banner.render())

        assert "environment problem" in status_text
        assert "must not be deleted" in status_text
        assert "NOT RELEASE-READY" in status_text
