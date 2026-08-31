"""Real process-boundary tests for the hard generation supervisor."""

from __future__ import annotations

import contextlib
import multiprocessing
import os
import signal
import subprocess
import sys
import textwrap
import time
from pathlib import Path
from typing import TYPE_CHECKING

import psutil  # type: ignore[import-untyped]
import pytest

from mutmut_win.process.generation_supervisor import (
    GenerationNoProgressTimeoutError,
    GenerationProgress,
    GenerationSupervisorCrashedError,
    GenerationSupervisorRemoteError,
    run_generation_supervised,
)

if TYPE_CHECKING:
    from collections.abc import Callable

pytestmark = [pytest.mark.integration, pytest.mark.slow]

_WORKER_SLEEP_SECONDS = 60.0
_PROGRESS_TIMEOUT_SECONDS = 3.0
_ABORT_JOIN_SECONDS = 3.0


def _identify_worker(value: int) -> tuple[int, int, int]:
    """Return enough identity to prove execution happened in a PPE child."""
    return value * 2, os.getpid(), os.getppid()


def _hang_worker(_value: int) -> None:
    time.sleep(_WORKER_SLEEP_SECONDS)


class _HangDuringPpeSerialization:
    """Pickles once to the supervisor, then wedges its PPE task feeder."""

    def __reduce__(
        self,
    ) -> tuple[Callable[[], _HangDuringPpeSerialization], tuple[()]]:
        if multiprocessing.current_process().name == "mutmut-generation-supervisor":
            time.sleep(_WORKER_SLEEP_SECONDS)
        return _restore_hanging_argument, ()


def _restore_hanging_argument() -> _HangDuringPpeSerialization:
    return _HangDuringPpeSerialization()


def _consume_argument(_value: object) -> int:
    return 1


def _raise_worker(_value: int) -> None:
    msg = "worker exploded"
    raise ValueError(msg)


def _kill_own_supervisor(_value: int) -> None:
    kill_signal = (
        signal.SIGTERM if sys.platform == "win32" else signal.SIGKILL  # type: ignore[attr-defined]  # Windows typeshed omission
    )
    os.kill(os.getppid(), kill_signal)
    time.sleep(_WORKER_SLEEP_SECONDS)


def _spawn_grandchild_and_hang(pid_file: str) -> None:
    grandchild = subprocess.Popen(  # noqa: S603 - controlled interpreter and script
        [sys.executable, "-c", f"import time; time.sleep({_WORKER_SLEEP_SECONDS})"],
    )
    Path(pid_file).write_text(str(grandchild.pid), encoding="ascii")
    time.sleep(_WORKER_SLEEP_SECONDS)


def _wait_until_dead(pid: int, timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not psutil.pid_exists(pid):
            return True
        with contextlib.suppress(psutil.NoSuchProcess):
            if psutil.Process(pid).status() == psutil.STATUS_ZOMBIE:
                return True
        time.sleep(0.05)
    return not psutil.pid_exists(pid)


def _cleanup_pid(pid: int) -> None:
    with contextlib.suppress(psutil.NoSuchProcess, psutil.AccessDenied):
        root = psutil.Process(pid)
        for process in [*root.children(recursive=True), root]:
            with contextlib.suppress(psutil.NoSuchProcess, psutil.AccessDenied):
                process.kill()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows generation Job containment")
def test_sitecustomize_descendant_dies_on_parent_hard_exit(tmp_path: Path) -> None:
    """Supervisor startup code is inside the Job before it can execute."""
    site_dir = tmp_path / "startup_probe"
    site_dir.mkdir()
    marker = tmp_path / "startup_pids.txt"
    (site_dir / "sitecustomize.py").write_text(
        textwrap.dedent(
            """
            import os, pathlib, subprocess, sys, time
            if os.environ.get("MUTMUT_GENERATION_SITE_PROBE") == "1":
                env = os.environ.copy()
                env["MUTMUT_GENERATION_SITE_PROBE"] = "0"
                child = subprocess.Popen(
                    [sys.executable, "-S", "-c", "import time; time.sleep(120)"],
                    env=env,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                marker = pathlib.Path(os.environ["MUTMUT_GENERATION_SITE_MARKER"])
                temporary = marker.with_suffix(".tmp")
                temporary.write_text(f"{os.getpid()},{child.pid}", encoding="ascii")
                temporary.replace(marker)
                while True:
                    time.sleep(1)
            """
        ),
        encoding="utf-8",
    )
    driver = tmp_path / "generation_site_hard_exit.py"
    driver.write_text(
        textwrap.dedent(
            """
            import os, pathlib, sys, threading, time
            from mutmut_win.process.generation_supervisor import run_generation_supervised

            if __name__ == "__main__":
                site_dir = pathlib.Path(sys.argv[1])
                marker = pathlib.Path(sys.argv[2])
                prior = os.environ.get("PYTHONPATH", "")
                os.environ["PYTHONPATH"] = os.pathsep.join(
                    [str(site_dir), *([prior] if prior else [])]
                )
                os.environ["MUTMUT_GENERATION_SITE_PROBE"] = "1"
                os.environ["MUTMUT_GENERATION_SITE_MARKER"] = str(marker)
                def hard_exit_after_startup():
                    deadline = time.monotonic() + 15
                    while time.monotonic() < deadline and not marker.is_file():
                        time.sleep(0.01)
                    os._exit(93 if marker.is_file() else 94)
                threading.Thread(target=hard_exit_after_startup, daemon=True).start()
                run_generation_supervised(
                    [1], worker=int, max_children=1, no_progress_timeout=30
                )
            """
        ),
        encoding="utf-8",
    )

    launcher = subprocess.Popen(  # noqa: S603
        [sys.executable, str(driver), str(site_dir), str(marker)],
        cwd=tmp_path,
    )
    launcher.wait(timeout=20)
    assert launcher.returncode == 93
    pids = [int(value) for value in marker.read_text(encoding="ascii").split(",")]
    try:
        assert all(_wait_until_dead(pid, timeout=10.0) for pid in pids)
    finally:
        for pid in pids:
            _cleanup_pid(pid)


def test_max_children_one_still_uses_ppe_and_reports_each_file() -> None:
    progress: list[GenerationProgress[tuple[int, int, int]]] = []
    callback_pid = os.getpid()

    results = run_generation_supervised(
        [3, 5],
        max_children=1,
        no_progress_timeout=10.0,
        worker=_identify_worker,
        on_progress=progress.append,
    )

    assert [result[0] for result in results] == [6, 10]
    assert {event.index for event in progress} == {0, 1}
    assert [event.completed for event in progress] == [1, 2]
    assert all(event.total == 2 for event in progress)
    for event in progress:
        _doubled, worker_pid, worker_parent_pid = event.result
        assert worker_pid not in {callback_pid, event.supervisor_pid}
        assert worker_parent_pid == event.supervisor_pid


def test_hung_generation_is_bounded_and_supervisor_is_reaped() -> None:
    started = time.monotonic()

    with pytest.raises(GenerationNoProgressTimeoutError) as exc_info:
        run_generation_supervised(
            [1],
            max_children=1,
            no_progress_timeout=_PROGRESS_TIMEOUT_SECONDS,
            worker=_hang_worker,
            abort_join_timeout=_ABORT_JOIN_SECONDS,
        )

    elapsed = time.monotonic() - started
    assert elapsed < _PROGRESS_TIMEOUT_SECONDS + _ABORT_JOIN_SECONDS + 2.0
    diagnostics = exc_info.value.cleanup
    assert diagnostics is not None
    assert not diagnostics.join_timed_out
    assert diagnostics.residual_pids == ()
    assert diagnostics.supervisor_pid is not None
    assert not psutil.pid_exists(diagnostics.supervisor_pid)


def test_no_progress_timeout_covers_ppe_submit_serialization() -> None:
    started = time.monotonic()

    with pytest.raises(GenerationNoProgressTimeoutError) as exc_info:
        run_generation_supervised(
            [_HangDuringPpeSerialization()],
            max_children=1,
            no_progress_timeout=_PROGRESS_TIMEOUT_SECONDS,
            worker=_consume_argument,
            abort_join_timeout=_ABORT_JOIN_SECONDS,
        )

    assert time.monotonic() - started < _PROGRESS_TIMEOUT_SECONDS + _ABORT_JOIN_SECONDS + 2.0
    diagnostics = exc_info.value.cleanup
    assert diagnostics is not None
    assert not diagnostics.join_timed_out
    assert diagnostics.residual_pids == ()


def test_supervisor_crash_is_detected_before_progress_timeout() -> None:
    started = time.monotonic()

    with pytest.raises(GenerationSupervisorCrashedError) as exc_info:
        run_generation_supervised(
            [1],
            max_children=1,
            no_progress_timeout=20.0,
            worker=_kill_own_supervisor,
            abort_join_timeout=_ABORT_JOIN_SECONDS,
        )

    assert time.monotonic() - started < 5.0
    diagnostics = exc_info.value.cleanup
    assert diagnostics is not None
    assert diagnostics.residual_pids == ()


def test_abort_reaps_worker_grandchild(tmp_path: Path) -> None:
    pid_file = tmp_path / "grandchild.pid"
    grandchild_pid: int | None = None

    try:
        with pytest.raises(GenerationNoProgressTimeoutError):
            run_generation_supervised(
                [str(pid_file)],
                max_children=1,
                # A cold Windows spawn can exceed the generic 3 s watchdog
                # under CI load before the PPE worker reaches user code.
                no_progress_timeout=10.0,
                worker=_spawn_grandchild_and_hang,
                abort_join_timeout=_ABORT_JOIN_SECONDS,
            )

        assert pid_file.is_file(), "PPE worker never reached the grandchild spawn"
        grandchild_pid = int(pid_file.read_text(encoding="ascii"))
        assert _wait_until_dead(grandchild_pid), (
            f"generation grandchild PID {grandchild_pid} survived containment abort"
        )
    finally:
        if grandchild_pid is not None:
            _cleanup_pid(grandchild_pid)


def test_remote_worker_error_is_diagnosed_and_bounded() -> None:
    with pytest.raises(GenerationSupervisorRemoteError, match="worker exploded") as exc_info:
        run_generation_supervised(
            [1],
            max_children=1,
            no_progress_timeout=10.0,
            worker=_raise_worker,
            abort_join_timeout=_ABORT_JOIN_SECONDS,
        )

    assert "ValueError" in str(exc_info.value)
    assert exc_info.value.cleanup is not None


@pytest.mark.parametrize(
    ("exception_factory", "message_pattern"),
    [
        (KeyboardInterrupt, None),
        (lambda: RuntimeError("progress callback failed"), "callback"),
    ],
)
def test_progress_callback_cause_survives_cleanup(
    exception_factory: Callable[[], BaseException],
    message_pattern: str | None,
) -> None:
    def fail_after_progress(_progress: GenerationProgress[tuple[int, int, int]]) -> None:
        raise exception_factory()

    expected_type = type(exception_factory())
    with pytest.raises(expected_type, match=message_pattern):
        run_generation_supervised(
            [1],
            max_children=1,
            no_progress_timeout=10.0,
            worker=_identify_worker,
            on_progress=fail_after_progress,
            abort_join_timeout=_ABORT_JOIN_SECONDS,
        )


@pytest.mark.parametrize("timeout", [0.0, -1.0, float("inf"), float("nan")])
def test_invalid_progress_timeout_is_rejected(timeout: float) -> None:
    with pytest.raises(ValueError, match="no_progress_timeout"):
        run_generation_supervised(
            [],
            max_children=1,
            no_progress_timeout=timeout,
            worker=_identify_worker,
        )


@pytest.mark.parametrize("max_children", [0, -1, True])
def test_invalid_worker_count_is_rejected(max_children: int) -> None:
    with pytest.raises(ValueError, match="max_children"):
        run_generation_supervised(
            [],
            max_children=max_children,
            no_progress_timeout=1.0,
            worker=_identify_worker,
        )


def test_empty_file_list_completes_without_progress_events() -> None:
    progress: list[GenerationProgress[tuple[int, int, int]]] = []

    assert (
        run_generation_supervised(
            [],
            max_children=1,
            no_progress_timeout=10.0,
            worker=_identify_worker,
            on_progress=progress.append,
        )
        == []
    )
    assert progress == []
