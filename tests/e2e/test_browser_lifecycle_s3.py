"""Actual headless Textual lifecycle over a real campaign, separate from CLI doubles.

This exercises Textual's event loop and diff thread, not terminal rendering or
every browser action. The existing unit layer covers additional lifecycle arms.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

import pytest
from rich.syntax import Syntax
from textual.widgets import DataTable, Static

from mutmut_win.browser import ResultBrowser
from mutmut_win.db import known_run_basis_incompleteness, load_latest_run_results
from tests.e2e.e2e_util import SIMPLE_LIB, cache_db, copy_project, run_cli

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.e2e, pytest.mark.slow]


@pytest.fixture(scope="module")
def browser_campaign(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Persist a genuine completed campaign for the actual browser to load."""
    project = copy_project(SIMPLE_LIB, tmp_path_factory.mktemp("textual-campaign"))
    result = run_cli(project, "run", "--no-progress", timeout=900)
    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"
    state, verdicts = load_latest_run_results(cache_db(project))
    assert state is not None
    assert state.status == "completed"
    assert state.planned_names
    assert not state.pending_names
    assert state.is_full_run
    assert known_run_basis_incompleteness(state) is None
    assert len(verdicts) == len(state.planned_names)
    return project


@pytest.mark.asyncio
async def test_browser_loads_campaign_renders_diff_and_stops_worker(
    browser_campaign: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mount, select rows through Textual, publish a real diff, and unmount."""
    monkeypatch.chdir(browser_campaign)
    state, verdicts = load_latest_run_results(cache_db(browser_campaign))
    assert state is not None
    expected = {result.mutant_name for result in verdicts}
    app = ResultBrowser(show_killed=True, db_path=cache_db(browser_campaign))
    async with app.run_test(size=(140, 45)) as pilot:
        await pilot.pause()
        banner = str(app.query_one("#run_status", Static).content)
        assert state.run_id[:8] in banner
        assert "status=completed" in banner
        files = app.query_one("#files", DataTable)
        mutants = app.query_one("#mutants", DataTable)
        assert files.row_count > 0
        displayed: set[str] = set()
        for row in range(files.row_count):
            files.move_cursor(row=row)
            await pilot.pause()
            displayed.update(
                str(mutants.get_row_at(index)[0]) for index in range(mutants.row_count)
            )
        assert displayed == expected
        assert mutants.row_count > 0
        mutants.focus()
        mutants.move_cursor(row=0)
        await pilot.pause()
        selected = str(mutants.get_row_at(0)[0])
        deadline = time.monotonic() + 10
        diff_view = app.query_one("#diff_view", Static)
        while not isinstance(diff_view.content, Syntax) and time.monotonic() < deadline:
            await pilot.pause(0.05)
        content = diff_view.content
        assert isinstance(content, Syntax), f"Diff was not published: {content!r}"
        assert "@@" in content.code
        assert "-" in content.code
        assert "+" in content.code
        cli_diff = run_cli(browser_campaign, "show", selected)
        assert cli_diff.returncode == 0
        cli_header, separator, cli_body = cli_diff.stdout.partition("\n")
        assert cli_header == f"# {selected}"
        assert separator == "\n"
        assert content.code.strip() == cli_body.strip()
        worker = app._diff_worker
        assert worker is not None
        assert worker.is_alive()
    worker.join(timeout=5)
    assert not worker.is_alive(), "Unmount must stop the actual diff worker"
    assert app._diff_worker_stop
    print(f"UI population={len(displayed)}; real diff published; worker stopped")


@pytest.mark.asyncio
async def test_browser_surfaces_corrupt_cache_and_shuts_down(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mount with actual corrupt bytes and display a domain error without evidence."""
    monkeypatch.chdir(tmp_path)
    database = cache_db(tmp_path)
    database.parent.mkdir()
    database.write_bytes(b"not a sqlite database")
    app = ResultBrowser(db_path=database)
    async with app.run_test() as pilot:
        await pilot.pause()
        banner = app.query_one("#run_status", Static)
        text = str(banner.content)
        assert "CORRUPT PERSISTED RUN EVIDENCE" in text
        assert "execution_basis_complete=false" in text
        assert "release_ready=false" in text
        assert banner.has_class("evidence-invalidated")
        assert app.query_one("#files", DataTable).row_count == 0
    assert app._diff_worker is None
    assert app._diff_worker_stop
    assert database.read_bytes() == b"not a sqlite database"
