"""Real POSIX regressions for pre-interpreter spawn and task gating."""

from __future__ import annotations

import contextlib
import os
import signal
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import psutil
import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.name != "posix", reason="POSIX process-session hardening"),
]

_OVERSIZED_BOOTSTRAP_BYTES = 2_500_000
_START_TIMEOUT_SECONDS = 15.0
_PROJECT_SRC = Path(__file__).resolve().parents[2] / "src"
_STARTUP_PROBE = textwrap.dedent(
    """
    import os, pathlib, subprocess, sys, time

    if (
        os.environ.get("MUTMUT_POSIX_STARTUP_PROBE") == "1"
        and os.getpgrp() == os.getpid()
    ):
        child_env = os.environ.copy()
        child_env["MUTMUT_POSIX_STARTUP_PROBE"] = "0"
        child = subprocess.Popen(
            [sys.executable, "-S", "-c", "import time; time.sleep(120)"],
            env=child_env,
        )
        marker = pathlib.Path(os.environ["MUTMUT_POSIX_STARTUP_MARKER"])
        pending_marker = marker.with_suffix(".tmp")
        pending_marker.write_text(
            f"{os.getpid()}:{os.getpgrp()},{child.pid}:{os.getpgid(child.pid)}",
            encoding="ascii",
        )
        pending_marker.replace(marker)
        while True:
            time.sleep(1)
    """
)


def _wait_until_dead(pid: int, timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            process = psutil.Process(pid)
            if not process.is_running() or process.status() == psutil.STATUS_ZOMBIE:
                return True
        except psutil.NoSuchProcess:
            return True
        time.sleep(0.02)
    return False


def _cleanup_process_groups(pids: list[int]) -> None:
    for pid in pids:
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(pid, signal.SIGKILL)
        with contextlib.suppress(psutil.NoSuchProcess, psutil.AccessDenied):
            psutil.Process(pid).kill()


def _driver_environment() -> dict[str, str]:
    environment = os.environ.copy()
    prior = environment.get("PYTHONPATH", "")
    environment["PYTHONPATH"] = os.pathsep.join([str(_PROJECT_SRC), *([prior] if prior else [])])
    return environment


def _install_startup_probe(tmp_path: Path) -> tuple[Path, Path]:
    site_dir = tmp_path / "startup_probe"
    site_dir.mkdir()
    marker = tmp_path / "startup_pids.txt"
    (site_dir / "sitecustomize.py").write_text(_STARTUP_PROBE, encoding="utf-8")
    return site_dir, marker


def _read_startup_identities(marker: Path) -> list[tuple[int, int]]:
    return [
        tuple(int(value) for value in identity.split(":"))
        for identity in marker.read_text(encoding="ascii").split(",")
    ]


def test_seekable_session_bootstrap_does_not_wait_for_sitecustomize(tmp_path: Path) -> None:
    site_dir, marker = _install_startup_probe(tmp_path)
    driver = tmp_path / "seekable_spawn_driver.py"
    driver.write_text(
        textwrap.dedent(
            f"""
            import os, pathlib, signal, sys, time
            from mutmut_win.process.posix_spawn import SessionContainedSpawnProcess

            if __name__ == "__main__":
                site_dir = pathlib.Path(sys.argv[1])
                marker = pathlib.Path(sys.argv[2])
                prior = os.environ.get("PYTHONPATH", "")
                os.environ["PYTHONPATH"] = os.pathsep.join(
                    [str(site_dir), *([prior] if prior else [])]
                )
                os.environ["MUTMUT_POSIX_STARTUP_PROBE"] = "1"
                os.environ["MUTMUT_POSIX_STARTUP_MARKER"] = str(marker)
                process = SessionContainedSpawnProcess(
                    target=len,
                    args=("x" * {_OVERSIZED_BOOTSTRAP_BYTES},),
                    daemon=False,
                )
                started = time.monotonic()
                process.start()
                elapsed = time.monotonic() - started
                print(f"START_RETURNED {{elapsed:.3f}} {{process.pid}}", flush=True)
                deadline = time.monotonic() + 10
                while not marker.is_file() and time.monotonic() < deadline:
                    time.sleep(0.01)
                os.killpg(process.pid, signal.SIGKILL)
                process.join(timeout=3)
                print("CLEANUP_RETURNED", flush=True)
                os._exit(94 if process.is_alive() or not marker.is_file() else 0)
            """
        ),
        encoding="utf-8",
    )

    pids: list[int] = []
    try:
        result = subprocess.run(  # noqa: S603
            [sys.executable, str(driver), str(site_dir), str(marker)],
            cwd=tmp_path,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=_START_TIMEOUT_SECONDS,
            env=_driver_environment(),
        )
        if marker.is_file():
            identities = _read_startup_identities(marker)
            pids = [pid for pid, _process_group in identities]
        assert result.returncode == 0
        assert len(pids) == 2
        assert all(process_group == pids[0] for _pid, process_group in identities)
        assert all(_wait_until_dead(pid) for pid in pids)
    finally:
        _cleanup_process_groups(pids)


def test_normal_worker_bootstrap_uses_same_nonblocking_channel(tmp_path: Path) -> None:
    site_dir, marker = _install_startup_probe(tmp_path)
    driver = tmp_path / "worker_spawn_driver.py"
    driver.write_text(
        textwrap.dedent(
            f"""
            import os, pathlib, sys, time
            from mutmut_win.config import MutmutConfig
            from mutmut_win.process.executor import SpawnPoolExecutor
            from mutmut_win.pytest_boundary import prepare_pytest_boundary

            if __name__ == "__main__":
                site_dir = pathlib.Path(sys.argv[1])
                marker = pathlib.Path(sys.argv[2])
                prior = os.environ.get("PYTHONPATH", "")
                os.environ["PYTHONPATH"] = os.pathsep.join(
                    [str(site_dir), *([prior] if prior else [])]
                )
                os.environ["MUTMUT_POSIX_STARTUP_PROBE"] = "1"
                os.environ["MUTMUT_POSIX_STARTUP_MARKER"] = str(marker)
                config = MutmutConfig()
                executor = SpawnPoolExecutor(1, config)
                staging = pathlib.Path("mutants")
                staging.mkdir(exist_ok=True)
                boundary = prepare_pytest_boundary(
                    project_root=pathlib.Path.cwd(),
                    staging_root=staging,
                    tests_dir=list(config.tests_dir),
                )
                executor.configure_pytest_boundary(boundary.to_dict())
                executor._config_data["oversized_probe"] = "x" * {_OVERSIZED_BOOTSTRAP_BYTES}
                started = time.monotonic()
                executor.start([])
                print(f"START_RETURNED {{time.monotonic() - started:.3f}}", flush=True)
                deadline = time.monotonic() + 10
                while not marker.is_file() and time.monotonic() < deadline:
                    time.sleep(0.01)
                executor.shutdown(timeout=0.1)
                print("SHUTDOWN_RETURNED", flush=True)
                os._exit(0 if marker.is_file() else 94)
            """
        ),
        encoding="utf-8",
    )

    pids: list[int] = []
    try:
        result = subprocess.run(  # noqa: S603
            [sys.executable, str(driver), str(site_dir), str(marker)],
            cwd=tmp_path,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=_START_TIMEOUT_SECONDS,
            env=_driver_environment(),
        )
        if marker.is_file():
            identities = _read_startup_identities(marker)
            pids = [pid for pid, _process_group in identities]
        assert result.returncode == 0
        assert len(pids) == 2
        assert all(process_group == pids[0] for _pid, process_group in identities)
        assert all(_wait_until_dead(pid) for pid in pids)
    finally:
        _cleanup_process_groups(pids)


def test_worker_hard_exit_during_registration_cannot_strand_gate_child(tmp_path: Path) -> None:
    driver = tmp_path / "gate_hard_exit_driver.py"
    driver.write_text(
        textwrap.dedent(
            """
            import os, subprocess, sys
            from mutmut_win.process.worker import _popen_contained

            def hard_exit_after_publish(process_group):
                print(process_group, flush=True)
                os._exit(93)

            if __name__ == "__main__":
                _popen_contained(
                    [sys.executable, "-c", "import time; time.sleep(120)"],
                    posix_start_stopped=True,
                    posix_register=hard_exit_after_publish,
                    start_new_session=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            """
        ),
        encoding="utf-8",
    )

    child_pid: int | None = None
    try:
        result = subprocess.run(  # noqa: S603
            [sys.executable, str(driver)],
            cwd=tmp_path,
            text=True,
            capture_output=True,
            timeout=10,
            env=_driver_environment(),
        )
        assert result.returncode == 93, result.stderr
        child_pid = int(result.stdout.strip())
        assert _wait_until_dead(child_pid), (
            f"pre-exec gate child {child_pid} survived its worker's hard exit"
        )
    finally:
        if child_pid is not None:
            _cleanup_process_groups([child_pid])


def test_session_child_dies_when_parent_hard_exits(tmp_path: Path) -> None:
    marker = tmp_path / "hard_parent_exit_child.txt"
    driver = tmp_path / "hard_parent_exit_driver.py"
    driver.write_text(
        textwrap.dedent(
            """
            import os, pathlib, sys, time
            from mutmut_win.process.posix_spawn import SessionContainedSpawnProcess

            if __name__ == "__main__":
                process = SessionContainedSpawnProcess(
                    target=time.sleep,
                    args=(120,),
                    daemon=False,
                )
                process.start()
                pathlib.Path(sys.argv[1]).write_text(str(process.pid), encoding="ascii")
                os._exit(0)
            """
        ),
        encoding="utf-8",
    )

    child_pid: int | None = None
    try:
        result = subprocess.run(  # noqa: S603
            [sys.executable, str(driver), str(marker)],
            cwd=tmp_path,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10,
            env=_driver_environment(),
        )
        assert result.returncode == 0
        child_pid = int(marker.read_text(encoding="ascii"))
        assert _wait_until_dead(child_pid), (
            f"session child {child_pid} survived its parent's hard exit"
        )
    finally:
        if child_pid is not None:
            _cleanup_process_groups([child_pid])


def test_session_tree_dies_when_parent_hard_exits_after_bootstrap(tmp_path: Path) -> None:
    marker = tmp_path / "hard_parent_exit_tree.txt"
    driver = tmp_path / "hard_parent_exit_tree_driver.py"
    driver.write_text(
        textwrap.dedent(
            """
            import os, pathlib, subprocess, sys, time
            from mutmut_win.process.posix_spawn import SessionContainedSpawnProcess

            def child_main(marker_path):
                descendant = subprocess.Popen(
                    [sys.executable, "-S", "-c", "import time; time.sleep(120)"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                pathlib.Path(marker_path).write_text(
                    f"{os.getpid()} {descendant.pid}",
                    encoding="ascii",
                )
                time.sleep(120)

            if __name__ == "__main__":
                marker = pathlib.Path(sys.argv[1])
                process = SessionContainedSpawnProcess(
                    target=child_main,
                    args=(str(marker),),
                    daemon=False,
                )
                process.start()
                deadline = time.monotonic() + 10
                while not marker.is_file() and time.monotonic() < deadline:
                    time.sleep(0.01)
                os._exit(0 if marker.is_file() else 95)
            """
        ),
        encoding="utf-8",
    )

    pids: list[int] = []
    try:
        result = subprocess.run(  # noqa: S603
            [sys.executable, str(driver), str(marker)],
            cwd=tmp_path,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=15,
            env=_driver_environment(),
        )
        assert result.returncode == 0
        pids = [int(value) for value in marker.read_text(encoding="ascii").split()]
        assert len(pids) == 2
        assert all(_wait_until_dead(pid) for pid in pids), (
            f"session tree survived its parent's hard exit: {pids}"
        )
    finally:
        _cleanup_process_groups(pids)


def test_session_spawn_is_bounded_with_busy_parent_threads(tmp_path: Path) -> None:
    driver = tmp_path / "threaded_spawn_driver.py"
    driver.write_text(
        textwrap.dedent(
            """
            import hashlib, os, threading, time
            from mutmut_win.process.posix_spawn import SessionContainedSpawnProcess

            def churn(stop):
                payload = b"x" * 8192
                while not stop.is_set():
                    hashlib.sha256(payload).digest()
                    os.stat(__file__)

            if __name__ == "__main__":
                stop = threading.Event()
                threads = [threading.Thread(target=churn, args=(stop,)) for _ in range(8)]
                for thread in threads:
                    thread.start()
                try:
                    for _ in range(24):
                        process = SessionContainedSpawnProcess(
                            target=time.sleep,
                            args=(0.01,),
                            daemon=False,
                        )
                        process.start()
                        process.join(timeout=3)
                        if process.is_alive() or process.exitcode != 0:
                            os._exit(96)
                finally:
                    stop.set()
                    for thread in threads:
                        thread.join(timeout=2)
                os._exit(0)
            """
        ),
        encoding="utf-8",
    )

    result = subprocess.run(  # noqa: S603
        [sys.executable, str(driver)],
        cwd=tmp_path,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=45,
        env=_driver_environment(),
    )
    assert result.returncode == 0
