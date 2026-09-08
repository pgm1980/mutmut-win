"""Shared test fixtures for mutmut-win."""

from __future__ import annotations

from pathlib import Path

import pytest

# Reference fixture projects copied from mutmut 3.5.0 — they import their own
# packages (my_lib, string_utils, …) that only resolve when an E2E harness
# installs them into a staging venv. Collecting them from the repo root used
# to abort the whole run with 16 collection errors, which made
# `--ignore=tests/e2e_projects` a load-bearing flag that lived only in
# backlog prose (issue #98). This makes the canon real: `uv run pytest` works
# bare; the E2E harnesses run those projects in subprocesses regardless.
collect_ignore_glob = ["e2e_projects/*"]


@pytest.fixture
def isolated_cli_workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Keep real CLI lock artifacts out of the repository checkout."""

    current = Path.cwd().resolve(strict=True)
    temporary_root = tmp_path.resolve(strict=True)
    try:
        current.relative_to(temporary_root)
    except ValueError:
        pass
    else:
        return current

    workspace = tmp_path / "cli-workspace"
    (workspace / "src").mkdir(parents=True)
    (workspace / "tests").mkdir()
    monkeypatch.chdir(workspace)
    return workspace
