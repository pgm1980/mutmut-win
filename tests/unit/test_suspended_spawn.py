"""Contracts for the private Windows suspended-spawn safety boundary."""

from __future__ import annotations

import sys
import tempfile
from types import SimpleNamespace
from typing import Any
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


# ---------------------------------------------------------------------------
# M-112: abort signals during the Windows start must stay aborts
# ---------------------------------------------------------------------------


class _RecordingBootstrapFile:
    """TemporaryFile wrapper that records its close() for cleanup proofs."""

    def __init__(self, real: Any) -> None:
        self._real = real
        self.closed = False

    def fileno(self) -> int:
        return self._real.fileno()

    def close(self) -> None:
        self.closed = True
        self._real.close()

    def flush(self) -> None:
        self._real.flush()

    def seek(self, offset: int, whence: int = 0) -> int:
        return self._real.seek(offset, whence)

    def write(self, data: Any) -> int:
        return self._real.write(data)


@pytest.fixture
def windows_spawn_fakes(monkeypatch: pytest.MonkeyPatch) -> list[_RecordingBootstrapFile]:
    """Fake the audited Windows runtime and record every bootstrap file."""
    runtime = SimpleNamespace(
        platform="win32",
        version_info=(3, 14, 7),
        implementation=SimpleNamespace(name="cpython"),
        executable=sys.executable,
    )
    monkeypatch.setattr(suspended_spawn, "sys", runtime)
    monkeypatch.setattr(
        "multiprocessing.spawn.get_preparation_data",
        lambda data_name: {"main_module_name": data_name},
    )
    bootstrap_files: list[_RecordingBootstrapFile] = []
    real_temporary_file = tempfile.TemporaryFile

    def recording_temporary_file(*args: Any, **kwargs: Any) -> _RecordingBootstrapFile:
        wrapper = _RecordingBootstrapFile(real_temporary_file(*args, **kwargs))
        bootstrap_files.append(wrapper)
        return wrapper

    monkeypatch.setattr(suspended_spawn.tempfile, "TemporaryFile", recording_temporary_file)
    return bootstrap_files


@pytest.mark.parametrize("interrupt", [KeyboardInterrupt, SystemExit])
def test_abort_signals_propagate_after_inner_cleanup(
    monkeypatch: pytest.MonkeyPatch,
    windows_spawn_fakes: list[_RecordingBootstrapFile],
    interrupt: type[BaseException],
) -> None:
    """M-112: a Ctrl-C/SystemExit during the suspended Windows start must not
    be wrapped into ProcessContainmentError — the callers keep their interrupt
    semantics (worker start: run status 'interrupted', CLI exit 130) while the
    inner cleanup still terminates/closes the partially created child."""
    bootstrap_files = windows_spawn_fakes

    def interrupting_create(*_args: object, **_kwargs: object) -> None:
        raise interrupt("simulated abort during CreateProcess")

    monkeypatch.setattr(atomic_spawn, "atomic_create_process_in_job", interrupting_create)
    fake_process = SimpleNamespace(_name="test_worker")

    with pytest.raises(interrupt, match="simulated abort"):
        suspended_spawn._windows_suspended_popen(fake_process, job_handle=0)

    assert len(bootstrap_files) == 1
    assert bootstrap_files[0].closed, "inner cleanup must still close the bootstrap file"


def test_real_start_errors_remain_containment_failures(
    monkeypatch: pytest.MonkeyPatch,
    windows_spawn_fakes: list[_RecordingBootstrapFile],
) -> None:
    """Control: every other start failure stays fail-closed ProcessContainmentError."""
    bootstrap_files = windows_spawn_fakes

    def failing_create(*_args: object, **_kwargs: object) -> None:
        raise OSError("simulated start failure")

    monkeypatch.setattr(atomic_spawn, "atomic_create_process_in_job", failing_create)
    fake_process = SimpleNamespace(_name="test_worker")

    with pytest.raises(
        ProcessContainmentError, match="Could not create, assign, and resume"
    ) as excinfo:
        suspended_spawn._windows_suspended_popen(fake_process, job_handle=0)

    assert isinstance(excinfo.value.__cause__, OSError)
    assert len(bootstrap_files) == 1
    assert bootstrap_files[0].closed
