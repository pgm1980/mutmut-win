"""S3-027/028: browser failures retain their real exit and database category."""

from __future__ import annotations

import _winapi
import hashlib
import os
import sqlite3
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner
from pydantic import BaseModel
from textual.widgets import Static

from mutmut_win import db
from mutmut_win.browser import ResultBrowser
from mutmut_win.cli import cli
from mutmut_win.exceptions import MutmutWinError

_BROWSER_LAUNCH = """
import os
from textual.widgets import Static
from mutmut_win.browser import ResultBrowser
from mutmut_win.cli import cli

original_run = ResultBrowser.run

async def shutdown(pilot):
    await pilot.pause()
    print("S3_BANNER=" + str(pilot.app.query_one("#run_status", Static).render()))
    pilot.app.exit(return_code=int(os.environ["S3_BROWSER_EXIT"]))

def headless(self):
    value = original_run(self, headless=True, auto_pilot=shutdown)
    print("S3_TEXTUAL_CODE=" + str(self.return_code))
    return value

ResultBrowser.run = headless
cli()
"""


class _BrowserReceipt(BaseModel):
    command: list[str]
    cwd: str
    exit_code: int
    textual_code: int
    stdout: str
    stderr: str


def _browse_process(workspace: Path, *, requested_exit: int = 0) -> _BrowserReceipt:
    environment = os.environ.copy()
    environment["PYTHONIOENCODING"] = "utf-8"
    environment["S3_BROWSER_EXIT"] = str(requested_exit)
    command = [sys.executable, "-c", _BROWSER_LAUNCH, "browse"]
    completed = subprocess.run(
        command,
        cwd=workspace,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        check=False,
    )
    codes = [
        line.removeprefix("S3_TEXTUAL_CODE=")
        for line in completed.stdout.splitlines()
        if line.startswith("S3_TEXTUAL_CODE=")
    ]
    assert len(codes) == 1, completed.stderr
    receipt = _BrowserReceipt(
        command=command,
        cwd=str(workspace),
        exit_code=completed.returncode,
        textual_code=int(codes[0]),
        stdout=completed.stdout,
        stderr=completed.stderr,
    )
    (workspace / "browser-receipt.json").write_text(
        receipt.model_dump_json(indent=2), encoding="utf-8"
    )
    print(receipt.model_dump_json())
    return receipt


def test_browse_propagates_real_junction_load_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A real unsafe cache parent must fail both Textual and the outer command."""
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "actual-cache"
    target.mkdir()
    sentinel = target / "untouched.bin"
    sentinel.write_bytes(b"outside browser cache ownership")
    junction = tmp_path / ".mutmut-cache"
    _winapi.CreateJunction(str(target), str(junction))
    assert junction.is_junction()

    receipt = _browse_process(tmp_path)
    results = CliRunner().invoke(cli, ["results"])

    assert receipt.textual_code == 1
    assert "UnsafeWorkspaceStateError" in receipt.stderr
    assert results.exit_code == 1
    assert "Refusing workspace state access" in results.output
    assert sentinel.read_bytes() == b"outside browser cache ownership"
    assert receipt.exit_code == 1


@pytest.mark.parametrize("requested_exit", [0, 4])
def test_browse_retains_actual_healthy_lifecycle_exit(
    tmp_path: Path, requested_exit: int
) -> None:
    """A mounted empty database exits cleanly or preserves its explicit status."""
    db.create_db(tmp_path / ".mutmut-cache" / "mutmut-cache.db")
    receipt = _browse_process(tmp_path, requested_exit=requested_exit)
    assert "S3_BANNER=No persisted mutation run" in receipt.stdout
    assert receipt.textual_code == requested_exit
    assert "Traceback" not in receipt.stderr
    assert receipt.exit_code == requested_exit


def test_browse_constructor_domain_handler_remains_reachable() -> None:
    """Construction failures still use the established domain diagnostic."""
    with patch("mutmut_win.cli.ResultBrowser", side_effect=MutmutWinError("constructor control")):
        result = CliRunner().invoke(cli, ["browse"])
    assert result.exit_code == 1
    assert "Could not open result browser: constructor control" in result.stderr


@pytest.mark.asyncio
async def test_browser_classifies_real_sqlite_cantopen_and_clears_refresh(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A controlled SQLite opening failure is environmental and can recover."""
    monkeypatch.chdir(tmp_path)
    cache = tmp_path / ".mutmut-cache" / "mutmut-cache.db"
    db.create_db(cache)
    before = hashlib.sha256(cache.read_bytes()).hexdigest()
    missing = tmp_path / "absent.db"
    original_connect = sqlite3.connect
    observed_codes: list[int] = []

    def cannot_open(_path: Path) -> sqlite3.Connection:
        try:
            return original_connect(missing.as_uri() + "?mode=rw", uri=True)
        except sqlite3.OperationalError as exc:
            observed_codes.append(exc.sqlite_errorcode)
            raise

    app = ResultBrowser(db_path=cache)
    async with app.run_test() as pilot:
        with monkeypatch.context() as local:
            local.setattr(sqlite3, "connect", cannot_open)
            app._read_data()
            app._update_run_status()
            await pilot.pause()
            banner = str(app.query_one("#run_status", Static).render())
        print("CANTOPEN_BANNER=" + banner)
        assert observed_codes == [sqlite3.SQLITE_CANTOPEN]
        assert "environment problem" in banner
        assert "must not be deleted" in banner
        assert "NOT RELEASE-READY" in banner
        assert "CORRUPT PERSISTED RUN EVIDENCE" not in banner

        app._read_data()
        app._update_run_status()
        await pilot.pause()
        healthy = str(app.query_one("#run_status", Static).render())
        assert healthy == "No persisted mutation run"
        assert not app.query_one("#run_status", Static).has_class("evidence-invalidated")

    assert hashlib.sha256(cache.read_bytes()).hexdigest() == before
    assert not missing.exists()


@pytest.mark.asyncio
async def test_browser_retains_real_corruption_banner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Actual non-database bytes keep the corruption diagnostic and bytes."""
    monkeypatch.chdir(tmp_path)
    cache = tmp_path / ".mutmut-cache" / "mutmut-cache.db"
    cache.parent.mkdir()
    corrupt = b"not a sqlite database" * 32
    cache.write_bytes(corrupt)
    app = ResultBrowser(db_path=cache)
    async with app.run_test() as pilot:
        await pilot.pause()
        banner = str(app.query_one("#run_status", Static).render())
        print("CORRUPT_BANNER=" + banner)
        assert "CORRUPT PERSISTED RUN EVIDENCE" in banner
        assert "NOT RELEASE-READY" in banner
        assert "environment problem" not in banner
    assert cache.read_bytes() == corrupt


@pytest.mark.asyncio
async def test_browser_empty_cache_is_healthy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The actual empty app remains non-corrupt and creates no database."""
    monkeypatch.chdir(tmp_path)
    app = ResultBrowser()
    async with app.run_test() as pilot:
        await pilot.pause()
        banner = str(app.query_one("#run_status", Static).render())
        assert banner == "No persisted mutation run"
        assert not app.query_one("#run_status", Static).has_class("evidence-invalidated")
    assert not (tmp_path / ".mutmut-cache").exists()

