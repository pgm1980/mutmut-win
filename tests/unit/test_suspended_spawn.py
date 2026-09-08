"""Contracts for the private Windows suspended-spawn safety boundary."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from mutmut_win.exceptions import ProcessContainmentError
from mutmut_win.process import atomic_spawn, posix_spawn, suspended_spawn


def test_exact_supported_runtime_is_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime = SimpleNamespace(
        platform="win32",
        version_info=(3, 14, 7),
        implementation=SimpleNamespace(name="cpython"),
    )
    monkeypatch.setattr(suspended_spawn, "sys", runtime)

    suspended_spawn._require_supported_runtime()


@pytest.mark.parametrize(
    ("platform", "implementation", "version"),
    [
        ("win32", "pypy", (3, 14, 7)),
        ("win32", "cpython", (3, 13, 13)),
        ("win32", "cpython", (3, 14, 6)),
        ("win32", "cpython", (3, 14, 8)),
        ("linux", "cpython", (3, 14, 7)),
    ],
)
def test_unsupported_runtime_or_platform_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    platform: str,
    implementation: str,
    version: tuple[int, int, int],
) -> None:
    runtime = SimpleNamespace(
        platform=platform,
        version_info=version,
        implementation=SimpleNamespace(name=implementation),
    )
    monkeypatch.setattr(suspended_spawn, "sys", runtime)

    with pytest.raises(ProcessContainmentError, match=r"Windows with CPython 3\.14\.7"):
        suspended_spawn._require_supported_runtime()


def test_atomic_spawn_uses_the_same_exact_runtime_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = SimpleNamespace(
        platform="win32",
        version_info=(3, 14, 7),
        implementation=SimpleNamespace(name="cpython"),
    )
    monkeypatch.setattr(atomic_spawn, "sys", runtime)

    atomic_spawn.require_atomic_spawn_runtime()

    runtime.version_info = (3, 14, 6)
    with pytest.raises(ProcessContainmentError, match=r"Windows with CPython 3\.14\.7"):
        atomic_spawn.require_atomic_spawn_runtime()


def test_retained_posix_backend_is_explicitly_unsupported() -> None:
    with pytest.raises(ProcessContainmentError, match=r"supports only Windows"):
        posix_spawn._require_supported_runtime()


def test_pre_resume_abort_terminates_waits_and_closes_both_handles() -> None:
    api = MagicMock()

    suspended_spawn._abort_created_process(api, process_handle=101, thread_handle=202)

    api.TerminateProcess.assert_called_once_with(101, 70)
    api.WaitForSingleObject.assert_called_once_with(101, 5_000)
    assert [entry.args for entry in api.CloseHandle.call_args_list] == [(202,), (101,)]
