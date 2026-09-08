"""Browser truthfulness for source-invalidated run evidence."""

from __future__ import annotations

import contextlib
import sqlite3
from typing import TYPE_CHECKING

import pytest
from textual.widgets import Static

from mutmut_win.browser import ResultBrowser
from mutmut_win.config import MutmutConfig
from mutmut_win.db import (
    finish_run,
    invalidate_latest_run_evidence,
    save_result,
    start_run,
)
from mutmut_win.stats import canonical_run_basis_config

if TYPE_CHECKING:
    from pathlib import Path


def _basis_config() -> str:
    return canonical_run_basis_config(MutmutConfig(paths_to_mutate=["src"]))


def _legacy_type_check_basis_config() -> str:
    return canonical_run_basis_config(
        MutmutConfig(
            paths_to_mutate=["src"],
            type_check_command=["python", "C:/outside/checker.py"],
        )
    )


@pytest.mark.asyncio
async def test_browser_marks_invalidated_completed_run_stale_and_not_release_ready(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    db_path = tmp_path / ".mutmut-cache" / "mutmut-cache.db"
    run_id = start_run(
        db_path,
        ["pkg.mod.x_f__mutmut_1"],
        basis_fingerprint="a" * 64,
        basis_config_json=_basis_config(),
        is_full_run=True,
    )
    save_result(db_path, "pkg.mod.x_f__mutmut_1", "killed", 1, 0.1)
    finish_run(db_path, run_id, "completed")
    assert invalidate_latest_run_evidence(db_path) is True

    app = ResultBrowser(db_path=db_path)
    async with app.run_test():
        banner = app.query_one("#run_status", Static)
        rendered = banner.render()

        status_text = str(rendered)
        assert "STALE / INVALIDATED EVIDENCE" in status_text
        assert "NOT RELEASE-READY" in status_text
        assert "evidence_invalidated=true" in status_text
        assert "release_ready=false" in status_text
        assert "recorded_run_state=completed" in status_text
        assert f"run={run_id[:8]}" in status_text
        assert f"Run {run_id[:8]}: status=completed" not in status_text
        assert banner.has_class("evidence-invalidated")


@pytest.mark.asyncio
async def test_browser_keeps_normal_completed_run_status_compatible(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    db_path = tmp_path / ".mutmut-cache" / "mutmut-cache.db"
    run_id = start_run(
        db_path,
        ["pkg.mod.x_f__mutmut_1"],
        basis_fingerprint="a" * 64,
        basis_config_json=_basis_config(),
        is_full_run=True,
    )
    save_result(db_path, "pkg.mod.x_f__mutmut_1", "killed", 1, 0.1)
    finish_run(db_path, run_id, "completed")

    app = ResultBrowser(db_path=db_path)
    async with app.run_test():
        banner = app.query_one("#run_status", Static)
        status_text = str(banner.render())

        assert f"Run {run_id[:8]}: status=completed" in status_text
        assert "completed=1/1" in status_text
        assert "evidence_invalidated=true" not in status_text
        assert not banner.has_class("evidence-invalidated")


@pytest.mark.asyncio
async def test_browser_marks_completed_run_with_incomplete_basis_not_release_ready(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    db_path = tmp_path / ".mutmut-cache" / "mutmut-cache.db"
    run_id = start_run(db_path, ["pkg.mod.x_f__mutmut_1"], is_full_run=True)
    save_result(db_path, "pkg.mod.x_f__mutmut_1", "killed", 1, 0.1)
    finish_run(db_path, run_id, "completed")

    app = ResultBrowser(db_path=db_path)
    async with app.run_test():
        banner = app.query_one("#run_status", Static)
        status_text = str(banner.render())

        assert "INCOMPLETE EXECUTION BASIS" in status_text
        assert "NOT RELEASE-READY" in status_text
        assert "execution_basis_complete=false" in status_text
        assert "release_ready=false" in status_text
        assert banner.has_class("evidence-invalidated")


@pytest.mark.asyncio
async def test_browser_marks_legacy_generic_type_checker_basis_not_release_ready(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    db_path = tmp_path / ".mutmut-cache" / "mutmut-cache.db"
    run_id = start_run(
        db_path,
        ["pkg.mod.x_f__mutmut_1"],
        basis_fingerprint="a" * 64,
        basis_config_json=_legacy_type_check_basis_config(),
        is_full_run=True,
    )
    save_result(db_path, "pkg.mod.x_f__mutmut_1", "killed", 1, 0.1)
    finish_run(db_path, run_id, "completed")

    app = ResultBrowser(db_path=db_path)
    async with app.run_test():
        banner = app.query_one("#run_status", Static)
        status_text = str(banner.render())

        assert "INCOMPLETE EXECUTION BASIS" in status_text
        assert "basis_reason=generic-type-check-command" in status_text
        assert "release_ready=false" in status_text
        assert banner.has_class("evidence-invalidated")


@pytest.mark.asyncio
async def test_browser_surfaces_malformed_persisted_basis_as_corrupt_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    db_path = tmp_path / ".mutmut-cache" / "mutmut-cache.db"
    run_id = start_run(
        db_path,
        ["pkg.mod.x_f__mutmut_1"],
        basis_fingerprint="a" * 64,
        basis_config_json=_basis_config(),
        is_full_run=True,
    )
    save_result(db_path, "pkg.mod.x_f__mutmut_1", "killed", 1, 0.1)
    finish_run(db_path, run_id, "completed")
    with contextlib.closing(sqlite3.connect(db_path)) as connection:
        connection.execute(
            "UPDATE mutation_run SET basis_config_json = ? WHERE run_id = ?",
            ("{", run_id),
        )
        connection.commit()

    app = ResultBrowser(db_path=db_path)
    async with app.run_test():
        banner = app.query_one("#run_status", Static)
        status_text = str(banner.render())

        assert "CORRUPT PERSISTED RUN EVIDENCE" in status_text
        assert "NOT RELEASE-READY" in status_text
        assert "execution_basis_complete=false" in status_text
        assert "release_ready=false" in status_text
        assert "invalid run basis" in status_text
        assert banner.has_class("evidence-invalidated")


@pytest.mark.asyncio
async def test_browser_marks_subset_run_and_displayed_population(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    db_path = tmp_path / ".mutmut-cache" / "mutmut-cache.db"
    run_id = start_run(
        db_path,
        ["pkg.mod.x_f__mutmut_1"],
        basis_fingerprint="a" * 64,
        basis_config_json=_basis_config(),
        is_full_run=False,
    )
    save_result(db_path, "pkg.mod.x_f__mutmut_1", "killed", 1, 0.1)
    finish_run(db_path, run_id, "completed")

    app = ResultBrowser(db_path=db_path)
    async with app.run_test():
        banner = app.query_one("#run_status", Static)
        status_text = str(banner.render())

        assert "SUBSET RUN" in status_text
        assert "NOT RELEASE-READY" in status_text
        assert "execution_basis_complete=true" in status_text
        assert "release_ready=false" in status_text
        assert "run_scope=subset" in status_text
        assert banner.has_class("evidence-invalidated")


@pytest.mark.asyncio
async def test_browser_keeps_no_run_legacy_status_compatible(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    app = ResultBrowser(db_path=tmp_path / "absent.db")

    async with app.run_test():
        banner = app.query_one("#run_status", Static)

        assert str(banner.render()) == "No persisted mutation run"
        assert not banner.has_class("evidence-invalidated")
