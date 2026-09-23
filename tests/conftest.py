"""Shared test fixtures for mutmut-win."""

from __future__ import annotations

import contextlib
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable

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


# --------------------------------------------------------------------------
# Windows filesystem state fixtures (remediation AP-00 / Q-02). The state
# logic lives in tests/unit/windows_fs_util.py; these fixtures only adapt it
# to pytest with guaranteed cleanup inside tmp_path.
# --------------------------------------------------------------------------


@pytest.fixture
def readonly_file(tmp_path: Path):
    """Factory creating a read-only file; write mode restored on teardown."""

    from tests.unit import windows_fs_util

    stack = contextlib.ExitStack()

    def _make(name: str) -> Path:
        path = tmp_path / name
        path.write_text("read-only payload", encoding="utf-8")
        stack.enter_context(windows_fs_util.readonly_leaf(path))
        return path

    yield _make

    stack.close()


@pytest.fixture
def junction_factory(tmp_path: Path):
    """Factory creating a junction with automatic link removal.

    Yields a callable ``(link_name, target_dir) -> link``; the junction link
    itself is removed in teardown (the target stays owned by the test).
    """

    created: list[Path] = []

    def _make(link_name: str, target_dir: Path) -> Path:
        from tests.unit import windows_fs_util

        link = tmp_path / link_name
        windows_fs_util.make_junction(link, target_dir)
        created.append(link)
        return link

    yield _make

    for link in created:
        # Best-effort removal of the link itself; everything lives in tmp_path.
        with contextlib.suppress(OSError):
            link.rmdir()


@pytest.fixture
def locked_file(tmp_path: Path):
    """Factory holding an msvcrt byte-range lock for the current test."""

    from tests.unit import windows_fs_util

    stack = contextlib.ExitStack()

    def _make(name: str) -> Path:
        path = tmp_path / name
        path.write_bytes(b"locked payload")
        stack.enter_context(windows_fs_util.byte_range_locked_file(path))
        return path

    yield _make

    stack.close()


@pytest.fixture
def sharing_violation_file(tmp_path: Path):
    """Factory holding an exclusive share-mode handle for the current test."""

    from tests.unit import windows_fs_util

    stack = contextlib.ExitStack()

    def _make(name: str) -> Path:
        path = tmp_path / name
        path.write_bytes(b"shared payload")
        stack.enter_context(windows_fs_util.sharing_violation_holder(path))
        return path

    yield _make

    stack.close()


@pytest.fixture
def long_name_factory(tmp_path: Path) -> Callable[[str], Path]:
    """Factory returning a near-255-UTF-16-unit file path (not created)."""

    def _make(suffix: str = ".txt") -> Path:
        from tests.unit import windows_fs_util

        return windows_fs_util.near_max_length_path(tmp_path, suffix=suffix)

    return _make
