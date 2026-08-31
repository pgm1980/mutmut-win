"""Contracts for the private Windows suspended-spawn safety boundary."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from mutmut_win.exceptions import ProcessContainmentError
from mutmut_win.process import suspended_spawn


@pytest.mark.parametrize("minor", [12, 13, 14])
def test_audited_cpython_runtime_range_is_accepted(
    monkeypatch: pytest.MonkeyPatch, minor: int
) -> None:
    runtime = SimpleNamespace(
        version_info=(3, minor),
        implementation=SimpleNamespace(name="cpython"),
    )
    monkeypatch.setattr(suspended_spawn, "sys", runtime)

    suspended_spawn._require_supported_runtime()


@pytest.mark.parametrize(
    ("implementation", "version"),
    [("pypy", (3, 13)), ("cpython", (3, 11)), ("cpython", (3, 15))],
)
def test_unknown_private_backend_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    implementation: str,
    version: tuple[int, int],
) -> None:
    runtime = SimpleNamespace(
        version_info=version,
        implementation=SimpleNamespace(name=implementation),
    )
    monkeypatch.setattr(suspended_spawn, "sys", runtime)

    with pytest.raises(ProcessContainmentError, match=r"CPython 3\.12-3\.14"):
        suspended_spawn._require_supported_runtime()


def test_pre_resume_abort_terminates_waits_and_closes_both_handles() -> None:
    api = MagicMock()

    suspended_spawn._abort_created_process(api, process_handle=101, thread_handle=202)

    api.TerminateProcess.assert_called_once_with(101, 70)
    api.WaitForSingleObject.assert_called_once_with(101, 5_000)
    assert [entry.args for entry in api.CloseHandle.call_args_list] == [(202,), (101,)]
