"""Process identity verification and Popen-double protection (M-009/M-144, #149)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import psutil
import pytest

import mutmut_win.process.worker as worker_module
from mutmut_win.exceptions import ProcessContainmentError


@pytest.mark.skipif(worker_module.sys.platform != "win32", reason="Windows Job Objects only")
class TestIterDescendantsIdentity:
    """M-009: the PPID walker filters stale edges via create_time."""

    def _fake_process(self, pid: int, ppid: int, ctime: float | None) -> MagicMock:
        proc = MagicMock()
        proc.pid = pid
        proc.info = {"pid": pid, "ppid": ppid, "create_time": ctime}
        proc.create_time.return_value = ctime
        return proc

    def test_stale_ppid_edge_is_filtered(self) -> None:
        """A foreign orphan with an older ctime is NOT returned."""
        root = self._fake_process(4242, 1, 1000.0)
        foreign_orphan = self._fake_process(5001, 4242, 900.0)
        foreign_grandchild = self._fake_process(5002, 5001, 950.0)
        legit_child = self._fake_process(5003, 4242, 1000.5)
        legit_grandchild = self._fake_process(5004, 5003, 1001.0)
        processes = [root, foreign_orphan, foreign_grandchild, legit_child, legit_grandchild]

        with patch("psutil.process_iter", return_value=processes):
            result = worker_module._iter_descendants(4242, root_create_time=1000.0)

        pids = {p.pid for p in result}
        assert pids == {5003, 5004}

    def test_equal_ctime_is_accepted(self) -> None:
        """A child with the same ctime as its parent IS returned (>= rule)."""
        root = self._fake_process(4242, 1, 1000.0)
        child = self._fake_process(5003, 4242, 1000.0)

        with patch("psutil.process_iter", return_value=[root, child]):
            result = worker_module._iter_descendants(4242, root_create_time=1000.0)

        assert {p.pid for p in result} == {5003}

    def test_unreadable_ctime_is_neither_traversed_nor_returned(self) -> None:
        """A node with create_time=None is skipped entirely."""
        root = self._fake_process(4242, 1, 1000.0)
        unreadable = self._fake_process(5001, 4242, None)
        unreadable_child = self._fake_process(5002, 5001, 1001.0)

        with patch("psutil.process_iter", return_value=[root, unreadable, unreadable_child]):
            result = worker_module._iter_descendants(4242, root_create_time=1000.0)

        assert result == []

    def test_without_root_time_the_walk_is_fail_closed(self) -> None:
        """AR-01: root_create_time=None means no verified root identity.

        There is deliberately no unverified fallback walk on any platform:
        without the captured identity the walker returns nothing, so callers
        cannot kill by PPID at all (fail-closed)."""
        root = self._fake_process(4242, 1, 1000.0)
        orphan = self._fake_process(5001, 4242, 900.0)

        with patch("psutil.process_iter", return_value=[root, orphan]):
            result = worker_module._iter_descendants(4242)

        assert result == []

    def test_kill_proc_tree_skips_sweep_without_root_time(self) -> None:
        """_kill_proc_tree fail-closed: no root time → no sweep."""
        proc = MagicMock(spec=worker_module.subprocess.Popen)
        proc.pid = 4242
        proc.kill = MagicMock()
        proc.wait = MagicMock(return_value=0)

        with (
            patch.object(worker_module, "_REAL_POPEN_TYPE", type(proc)),
            patch("mutmut_win.process.loop_monitor.has_psutil", return_value=True),
            patch("psutil.Process", side_effect=psutil.NoSuchProcess(4242)),
            patch.object(worker_module, "_iter_descendants") as iter_mock,
        ):
            worker_module._kill_proc_tree(proc)

        iter_mock.assert_not_called()
        proc.kill.assert_called_once()

    def test_kill_proc_tree_uses_verified_walk(self) -> None:
        """_kill_proc_tree passes the root create_time to the walker."""
        proc = MagicMock(spec=worker_module.subprocess.Popen)
        proc.pid = 4242
        proc.kill = MagicMock()
        proc.wait = MagicMock(return_value=0)

        with (
            patch.object(worker_module, "_REAL_POPEN_TYPE", type(proc)),
            patch("mutmut_win.process.loop_monitor.has_psutil", return_value=True),
            patch("psutil.Process") as process_mock,
            patch.object(worker_module, "_iter_descendants", return_value=[]) as iter_mock,
        ):
            process_mock.return_value.create_time.return_value = 1234.5
            worker_module._kill_proc_tree(proc)

        iter_mock.assert_called_with(4242, 1234.5)


@pytest.mark.skipif(worker_module.sys.platform != "win32", reason="Windows Job Objects only")
class TestPopenDoubleNeverAssigned:
    """M-144 stage 1: test double PIDs never reach kernel operations."""

    def test_double_pid_never_assigned_to_job(self) -> None:
        """A Popen test double's pid is never passed to _create_task_job."""
        fake_proc = MagicMock()
        fake_proc.pid = 12345

        with (
            patch("mutmut_win.process.worker.subprocess.Popen", return_value=fake_proc),
            patch("mutmut_win.process.worker._create_task_job") as job_spy,
            patch("mutmut_win.process.job_object.assign_process_to_job") as assign_spy,
        ):
            job_spy.return_value = 42
            result_proc, result_job = worker_module._popen_contained(
                ["python", "-c", "pass"], creationflags=0
            )

        # The job IS created (with None, not the double's pid).
        job_spy.assert_called_once_with(None)
        assign_spy.assert_not_called()
        assert result_proc is fake_proc
        assert result_job == 42


@pytest.mark.skipif(worker_module.sys.platform != "win32", reason="Windows Job Objects only")
class TestPopenSubclassRefused:
    """M-144 stage 2: a Popen subclass replacement is refused before launch."""

    def test_subclass_replacement_raises_before_start(self) -> None:
        """Setting subprocess.Popen to a subclass raises ProcessContainmentError."""

        class FakePopenSubclass(worker_module.subprocess.Popen):  # type: ignore[misc, unused-ignore]
            def __init__(self, *_args: object, **_kwargs: object) -> None:
                pytest.fail("Process must never be started when a subclass is detected")

        with (
            patch("mutmut_win.process.worker.subprocess.Popen", FakePopenSubclass),
            pytest.raises(ProcessContainmentError, match="Popen subclass"),
        ):
            worker_module._popen_contained(["python", "-c", "pass"], creationflags=0)

    def test_function_wrapper_returning_real_instance_is_refused(self) -> None:
        """A wrapper returning a real Popen instance is refused after start."""

        class RealPopen(worker_module._REAL_POPEN_TYPE):  # type: ignore[misc, unused-ignore]
            pass

        real_instance = MagicMock(spec=RealPopen)
        real_instance.pid = 99999

        def wrapper_popen(*_args: object, **_kwargs: object) -> object:
            return real_instance

        with (
            patch("mutmut_win.process.worker.subprocess.Popen", wrapper_popen),
            patch.object(worker_module, "_kill_proc_tree") as kill_mock,
            pytest.raises(ProcessContainmentError, match="replaced after import"),
        ):
            worker_module._popen_contained(["python", "-c", "pass"], creationflags=0)

        kill_mock.assert_called_once_with(real_instance)
