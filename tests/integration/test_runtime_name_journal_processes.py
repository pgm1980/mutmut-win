"""Real Windows process boundaries for cumulative clean-call journals."""

from __future__ import annotations

import json
import os
from pathlib import Path

import psutil
import pytest

from mutmut_win.config import MutmutConfig
from mutmut_win.file_setup import create_mutants_for_file
from mutmut_win.runner import PytestRunner

pytestmark = pytest.mark.integration


def _project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, helper: str, test: str
) -> PytestRunner:
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.chdir(project)
    Path("mod.py").write_text("def a():\n    return 2\ndef b():\n    return 3\n", encoding="utf-8")
    create_mutants_for_file(Path("mod.py"), Path("mutants/mod.py"))
    for root in (project, project / "mutants"):
        (root / "tests").mkdir()
        (root / "child_support.py").write_text(helper, encoding="utf-8")
        (root / "tests/test_child.py").write_text(test, encoding="utf-8")
    return PytestRunner(MutmutConfig(tests_dir=["tests"], clean_run_timeout=60))


@pytest.mark.parametrize("point", ["before_call", "pending", "after_payload", "ready"])
def test_killed_child_preserves_only_completed_publications(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, point: str
) -> None:
    marker = tmp_path / "child.json"
    joined = tmp_path / "joined.json"
    helper = (
        "import json, os, time\nfrom pathlib import Path\n"
        "from mutmut_win import runtime_names as names\nfrom mod import a\n"
        "def exercise(reached):\n"
        "    recorder = names._ensure_recorder()\n"
        "    def stop_here(name):\n"
        "        payload = {'pid': os.getpid(), 'name': name, 'state': recorder.control[0]}\n"
        f"        Path({str(marker)!r}).write_text(json.dumps(payload))\n"
        "        reached.set()\n        time.sleep(60)\n"
    )
    if point == "before_call":
        helper += "    stop_here(None)\n    a()\n"
    elif point in {"pending", "after_payload"}:
        helper += (
            "    original = names._write_part\n"
            "    def publish(path, entry):\n"
            + ("        original(path, entry)\n" if point == "after_payload" else "")
            + "        stop_here(entry.value)\n"
            "    names._write_part = publish\n    a()\n"
        )
    else:
        helper += "    assert a() == 2\n    stop_here('mod.x_a')\n"
    test = (
        "import json, multiprocessing\nfrom pathlib import Path\n"
        "from child_support import exercise\n"
        "def test_child():\n"
        "    context = multiprocessing.get_context('spawn')\n"
        "    reached = context.Event()\n"
        "    child = context.Process(target=exercise, args=(reached,))\n"
        "    child.start()\n"
        "    try:\n        assert reached.wait(20)\n"
        "    finally:\n        child.terminate()\n        child.join(10)\n"
        "    assert not child.is_alive()\n    assert child.exitcode != 0\n"
        "    payload = {'pid': child.pid, 'exit_code': child.exitcode, 'joined': True}\n"
        f"    Path({str(joined)!r}).write_text(json.dumps(payload))\n"
    )
    runner = _project(tmp_path, monkeypatch, helper, test)
    assert runner.run_clean_test() == 0, runner.last_diagnostic_output
    child = json.loads(marker.read_text(encoding="utf-8"))
    terminal = json.loads(joined.read_text(encoding="utf-8"))
    assert child["pid"] == terminal["pid"]
    assert child["pid"] != os.getpid()
    assert terminal["joined"]
    assert terminal["exit_code"] != 0
    if point in {"pending", "after_payload"}:
        assert child["state"] == 2
        assert child["name"] == "mod.x_a"
        assert runner.clean_runtime_names is None
        assert "participant is incomplete" in (runner.clean_runtime_names_diagnostic or "")
    else:
        assert child["state"] == 1
        assert runner.clean_runtime_names == (set() if point == "before_call" else {"mod.x_a"})


def test_real_child_closed_map_and_denied_marker_revoke_old_ready(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    marker = tmp_path / "child.json"
    helper = (
        "import json, os\nfrom pathlib import Path\n"
        "from mutmut_win import runtime_names as names\nfrom mod import a, b\n"
        "def exercise():\n"
        "    assert a() == 2\n"
        "    recorder = names._ensure_recorder()\n"
        "    recorder.control.close()\n"
        "    original_touch = Path.touch\n"
        "    def denied(path, *args, **kwargs):\n"
        "        if path.suffix == '.invalid':\n"
        "            raise PermissionError('injected poison marker denial')\n"
        "        return original_touch(path, *args, **kwargs)\n"
        "    Path.touch = denied\n"
        "    errors = []\n"
        "    for call in (b, a):\n"
        "        try:\n            call()\n"
        "        except (OSError, ValueError, RuntimeError) as error:\n"
        "            errors.append(type(error).__name__)\n"
        "    payload = {'pid': os.getpid(), 'errors': errors, 'invalid': recorder.invalid}\n"
        f"    Path({str(marker)!r}).write_text(json.dumps(payload))\n"
        "    assert len(errors) == 2\n"
    )
    test = (
        "import multiprocessing\nfrom child_support import exercise\n"
        "def test_child():\n"
        "    child = multiprocessing.get_context('spawn').Process(target=exercise)\n"
        "    child.start()\n    child.join(20)\n"
        "    assert not child.is_alive()\n    assert child.exitcode == 0\n"
    )
    runner = _project(tmp_path, monkeypatch, helper, test)
    assert runner.run_clean_test() == 0, runner.last_diagnostic_output
    child = json.loads(marker.read_text(encoding="utf-8"))
    assert child["pid"] != os.getpid()
    assert child["invalid"]
    assert len(child["errors"]) == 2
    assert runner.clean_runtime_names is None
    assert "runtime-name" in (runner.clean_runtime_names_diagnostic or "")


@pytest.mark.parametrize("kind", ["joined_empty", "daemon_empty", "pool_empty", "pool_one_task"])
def test_empty_and_idle_spawn_participants_are_healthy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    helper = (
        "from mod import a\n"
        "def empty():\n    return None\n"
        "def wait_forever(ready):\n"
        "    import time\n    ready.set()\n    time.sleep(60)\n"
        "def exercise(number):\n    assert a() == 2\n    return number\n"
    )
    test = "import multiprocessing\nfrom child_support import empty, wait_forever, exercise\n"
    test += "def test_child():\n    context = multiprocessing.get_context('spawn')\n"
    if kind == "joined_empty":
        test += (
            "    child = context.Process(target=empty)\n"
            "    child.start()\n    child.join(20)\n    assert child.exitcode == 0\n"
        )
    elif kind == "daemon_empty":
        test += (
            "    ready = context.Event()\n"
            "    child = context.Process(target=wait_forever, args=(ready,), daemon=True)\n"
            "    child.start()\n    assert ready.wait(20)\n"
        )
    else:
        test += "    with context.Pool(2) as pool:\n"
        test += (
            "        assert pool.map(exercise, [1]) == [1]\n"
            if kind == "pool_one_task"
            else "        assert pool.map(exercise, []) == []\n"
        )
    runner = _project(tmp_path, monkeypatch, helper, test)
    assert runner.run_clean_test() == 0, runner.last_diagnostic_output
    assert runner.clean_runtime_names == ({"mod.x_a"} if kind == "pool_one_task" else set()), (
        runner.clean_runtime_names_diagnostic
    )


@pytest.mark.parametrize("has_task", [False, True])
def test_pool_start_waits_for_delayed_unused_worker_bootstrap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, has_task: bool
) -> None:
    markers = tmp_path / "bootstraps"
    markers.mkdir()
    release = tmp_path / "release"
    helper = (
        "import json, os, time\nfrom pathlib import Path\n"
        "from mutmut_win import runtime_names as names\nfrom mod import a\n"
        f"MARKERS = Path({str(markers)!r})\nRELEASE = Path({str(release)!r})\n"
        "def delayed_resume(raw):\n"
        "    second = bool(list(MARKERS.iterdir()))\n"
        "    payload = {'pid': os.getpid(), 'delayed': second}\n"
        "    (MARKERS / f'{os.getpid()}.json').write_text(json.dumps(payload))\n"
        "    deadline = time.monotonic() + 20\n"
        "    while second and not RELEASE.exists():\n"
        "        if time.monotonic() > deadline: raise RuntimeError('test barrier expired')\n"
        "        time.sleep(0.005)\n"
        "    names._resume_spawn(raw)\n"
        "def delayed_reduce(self):\n"
        "    return delayed_resume, (self.ticket.model_dump_json(),)\n"
        "def exercise(number):\n    assert a() == 2\n    return number\n"
    )
    test = (
        "import multiprocessing, threading, time\n"
        "from mutmut_win import runtime_names as names\n"
        "from child_support import MARKERS, RELEASE, delayed_reduce, exercise\n"
        "def test_child(monkeypatch):\n"
        "    monkeypatch.setattr(names._SpawnObserver, '__reduce__', delayed_reduce)\n"
        "    constructed = threading.Event()\n    failures = []\n"
        "    def use_pool():\n"
        "        try:\n"
        "            with multiprocessing.get_context('spawn').Pool(2) as pool:\n"
        "                constructed.set()\n"
        + (
            "                assert pool.map(exercise, [1]) == [1]\n"
            if has_task
            else "                assert pool.map(exercise, []) == []\n"
        )
        + "        except BaseException as error:\n            failures.append(repr(error))\n"
        "    thread = threading.Thread(target=use_pool)\n    thread.start()\n"
        "    try:\n"
        "        deadline = time.monotonic() + 15\n"
        "        while len(list(MARKERS.iterdir())) != 2:\n"
        "            assert time.monotonic() < deadline\n            time.sleep(0.005)\n"
        "        assert not constructed.is_set()\n"
        "    finally:\n        RELEASE.touch()\n        thread.join(30)\n"
        "    assert not thread.is_alive()\n    assert not failures, failures\n"
        "    assert constructed.is_set()\n"
    )
    runner = _project(tmp_path, monkeypatch, helper, test)
    assert runner.run_clean_test() == 0, runner.last_diagnostic_output
    children = [json.loads(path.read_text(encoding="utf-8")) for path in markers.iterdir()]
    assert len(children) == 2
    assert sum(child["delayed"] for child in children) == 1
    assert runner.clean_runtime_names == ({"mod.x_a"} if has_task else set())


def test_bootstrap_wait_failure_reaps_spawned_child_before_raising(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    started = tmp_path / "started.json"
    observed = tmp_path / "observed.json"
    helper = (
        "import json, os, time\nfrom pathlib import Path\n"
        "from mutmut_win import runtime_names as names\n"
        f"STARTED = Path({str(started)!r})\n"
        "def never_ready(raw):\n"
        "    STARTED.write_text(json.dumps({'pid': os.getpid()}))\n"
        "    STARTED.with_suffix('.ready').touch()\n"
        "    time.sleep(60)\n    names._resume_spawn(raw)\n"
        "def delayed_reduce(self):\n"
        "    return never_ready, (self.ticket.model_dump_json(),)\n"
        "def empty():\n    pass\n"
    )
    test = (
        "import json, multiprocessing, time\nfrom pathlib import Path\n"
        "from mutmut_win import runtime_names as names\n"
        "from child_support import STARTED, delayed_reduce, empty\n"
        "def test_child(monkeypatch):\n"
        "    def expired(ticket):\n"
        "        deadline = time.monotonic() + 15\n"
        "        while not STARTED.with_suffix('.ready').exists():\n"
        "            assert time.monotonic() < deadline\n            time.sleep(0.005)\n"
        "        raise RuntimeError('injected bootstrap wait timeout after OS spawn')\n"
        "    monkeypatch.setattr(names._SpawnObserver, '__reduce__', delayed_reduce)\n"
        "    monkeypatch.setattr(names, '_wait_bootstrap', expired)\n"
        "    child = multiprocessing.get_context('spawn').Process(target=empty)\n"
        "    try:\n"
        "        try:\n            child.start()\n"
        "        except RuntimeError as error:\n"
        "            assert 'bootstrap wait timeout' in str(error)\n"
        "        else:\n            raise AssertionError('start unexpectedly succeeded')\n"
        "        payload = {'pid': child.pid, 'alive_after_error': child.is_alive()}\n"
        f"        Path({str(observed)!r}).write_text(json.dumps(payload))\n"
        "        assert not child.is_alive(), 'bootstrap failure leaked started child'\n"
        "    finally:\n"
        "        if child.is_alive(): child.terminate()\n        child.join(10)\n"
    )
    runner = _project(tmp_path, monkeypatch, helper, test)
    exit_code = runner.run_clean_test()
    child = json.loads(started.read_text(encoding="utf-8"))
    actual = json.loads(observed.read_text(encoding="utf-8"))
    assert child["pid"] == actual["pid"]
    assert not psutil.pid_exists(child["pid"])
    assert not actual["alive_after_error"], runner.last_diagnostic_output
    assert exit_code == 0, runner.last_diagnostic_output
    assert runner.clean_runtime_names is None


@pytest.mark.parametrize("point", ["main_import", "target_unpickle"])
def test_calls_before_child_target_are_observed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, point: str
) -> None:
    marker = tmp_path / "early.json"
    helper = (
        "import json, os\nfrom pathlib import Path\nfrom mod import a\n"
        "from mutmut_win import runtime_names as names\n"
        "def empty():\n    pass\n"
        "def restore_target():\n"
        "    assert a() == 2\n"
        "    payload = {'pid': os.getpid(), 'point': 'target_unpickle'}\n"
        "    payload['bootstrapped'] = names._ensure_recorder().control[1]\n"
        f"    Path({str(marker)!r}).write_text(json.dumps(payload))\n"
        "    return empty\n"
        "class EarlyTarget:\n"
        "    def __call__(self):\n        pass\n"
        "    def __reduce__(self):\n        return restore_target, ()\n"
    )
    test = (
        "import multiprocessing, sys\nfrom pathlib import Path\n"
        "from child_support import empty, EarlyTarget\n"
        "def test_child(monkeypatch):\n"
    )
    if point == "main_import":
        test += (
            "    monkeypatch.setattr(sys.modules['__main__'], '__spec__', None)\n"
            "    main_path = str(Path('main_probe.py').resolve())\n"
            "    monkeypatch.setattr(sys.modules['__main__'], '__file__', main_path)\n"
        )
    test += (
        f"    target = {'EarlyTarget()' if point == 'target_unpickle' else 'empty'}\n"
        "    child = multiprocessing.get_context('spawn').Process(target=target)\n"
        "    child.start()\n    child.join(20)\n"
        "    assert not child.is_alive()\n    assert child.exitcode == 0\n"
    )
    runner = _project(tmp_path, monkeypatch, helper, test)
    if point == "main_import":
        main_source = (
            "import json, os\nfrom pathlib import Path\nfrom mod import a\n"
            "from mutmut_win import runtime_names as names\n"
            "assert a() == 2\n"
            "payload = {'pid': os.getpid(), 'point': 'main_import'}\n"
            "payload['bootstrapped'] = names._ensure_recorder().control[1]\n"
            f"Path({str(marker)!r}).write_text(json.dumps(payload))\n"
        )
        Path("main_probe.py").write_text(main_source, encoding="utf-8")
        Path("mutants/main_probe.py").write_text(main_source, encoding="utf-8")
    assert runner.run_clean_test() == 0, runner.last_diagnostic_output
    actual = json.loads(marker.read_text(encoding="utf-8"))
    assert actual["point"] == point
    assert actual["bootstrapped"] == 1
    assert actual["pid"] != os.getpid()
    assert runner.clean_runtime_names == {"mod.x_a"}, runner.clean_runtime_names_diagnostic


@pytest.mark.parametrize("kill_parent", [False, True])
def test_grandchild_completed_names_survive_parent_kill_and_job_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kill_parent: bool
) -> None:
    child_marker = tmp_path / "child.json"
    grandchild_marker = tmp_path / "grandchild.json"
    observed = tmp_path / "observed.json"
    helper = (
        "import json, multiprocessing, os, time\nfrom pathlib import Path\n"
        "from mod import a, b\n"
        "def grandchild(reached):\n"
        "    assert a() == 2\n    assert b() == 3\n"
        "    payload = {'pid': os.getpid(), 'parent_pid': os.getppid()}\n"
        f"    Path({str(grandchild_marker)!r}).write_text(json.dumps(payload))\n"
        "    reached.set()\n"
        + ("    time.sleep(60)\n" if kill_parent else "")
        + "def child(reached):\n"
        "    process = multiprocessing.get_context('spawn').Process(\n"
        "        target=grandchild, args=(reached,))\n"
        "    process.start()\n"
        "    payload = {'pid': os.getpid(), 'grandchild_pid': process.pid}\n"
        f"    Path({str(child_marker)!r}).write_text(json.dumps(payload))\n"
        f"    Path({str(child_marker.with_suffix('.ready'))!r}).touch()\n"
        + ("    time.sleep(60)\n" if kill_parent else "    process.join(20)\n")
        + ("" if kill_parent else "    assert process.exitcode == 0\n")
    )
    test = (
        "import json, multiprocessing, time\nfrom pathlib import Path\nimport psutil\n"
        "from child_support import child\n"
        "def test_tree():\n"
        "    context = multiprocessing.get_context('spawn')\n"
        "    reached = context.Event()\n"
        "    process = context.Process(target=child, args=(reached,))\n"
        "    process.start()\n"
        "    try:\n"
        "        assert reached.wait(20)\n"
        "        deadline = time.monotonic() + 10\n"
        f"        while not Path({str(child_marker.with_suffix('.ready'))!r}).exists():\n"
        "            assert time.monotonic() < deadline\n            time.sleep(0.005)\n"
        + ("        process.terminate()\n" if kill_parent else "")
        + "        process.join(20)\n        assert not process.is_alive()\n"
        f"        assert process.exitcode {'!=' if kill_parent else '=='} 0\n"
        f"        descendant = json.loads(Path({str(grandchild_marker)!r}).read_text())\n"
        "        payload = {'child_pid': process.pid, 'child_exitcode': process.exitcode}\n"
        "        alive = psutil.pid_exists(descendant['pid'])\n"
        "        payload['grandchild_alive_before_cleanup'] = alive\n"
        f"        Path({str(observed)!r}).write_text(json.dumps(payload))\n"
        "    finally:\n"
        "        if process.is_alive(): process.terminate()\n        process.join(10)\n"
    )
    runner = _project(tmp_path, monkeypatch, helper, test)
    assert runner.run_clean_test() == 0, runner.last_diagnostic_output
    child = json.loads(child_marker.read_text(encoding="utf-8"))
    grandchild = json.loads(grandchild_marker.read_text(encoding="utf-8"))
    terminal = json.loads(observed.read_text(encoding="utf-8"))
    assert child["pid"] == grandchild["parent_pid"] == terminal["child_pid"]
    assert child["grandchild_pid"] == grandchild["pid"]
    assert terminal["grandchild_alive_before_cleanup"] is kill_parent
    assert not psutil.pid_exists(child["pid"])
    assert not psutil.pid_exists(grandchild["pid"])
    assert runner.clean_runtime_names == {"mod.x_a", "mod.x_b"}


@pytest.mark.parametrize("observer_fails", [False, True])
def test_bootstrap_requires_successful_child_observer_install(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, observer_fails: bool
) -> None:
    marker = tmp_path / "observer.json"
    observed = tmp_path / "parent.json"
    helper = (
        "import json, os\nfrom pathlib import Path\n"
        "from mutmut_win import runtime_names as names\n"
        "def observed_resume(raw):\n"
        "    original = names.install_spawn_observer\n"
        "    def install():\n"
        "        recorder = names._ensure_recorder()\n"
        "        payload = {'pid': os.getpid(), 'bootstrap_before': recorder.control[1]}\n"
        "        payload['recorder_attached'] = True\n"
        f"        Path({str(marker)!r}).write_text(json.dumps(payload))\n"
        + (
            "        raise RuntimeError('injected child observer install failure')\n"
            if observer_fails
            else ""
        )
        + "        original()\n"
        "        payload['observer_installed'] = names._installed\n"
        f"        Path({str(marker)!r}).write_text(json.dumps(payload))\n"
        "    names.install_spawn_observer = install\n"
        "    names._resume_spawn(raw)\n"
        "def observed_reduce(self):\n"
        "    return observed_resume, (self.ticket.model_dump_json(),)\n"
        "def empty():\n    pass\n"
    )
    test = (
        "import json, multiprocessing\nfrom pathlib import Path\n"
        "from mutmut_win import runtime_names as names\n"
        "from child_support import observed_reduce, empty\n"
        "def test_child(monkeypatch):\n"
        "    monkeypatch.setattr(names._SpawnObserver, '__reduce__', observed_reduce)\n"
        "    child = multiprocessing.get_context('spawn').Process(target=empty)\n"
        "    caught = None\n"
        "    try:\n"
        "        try:\n            child.start()\n"
        "        except RuntimeError as error:\n"
        "            assert 'bootstrap incomplete' in str(error)\n            caught = str(error)\n"
        "        child.join(10)\n        assert not child.is_alive()\n"
        f"        assert child.exitcode {'!=' if observer_fails else '=='} 0\n"
        "        payload = {'pid': child.pid, 'exit_code': child.exitcode, 'caught': caught}\n"
        f"        Path({str(observed)!r}).write_text(json.dumps(payload))\n"
        "    finally:\n"
        "        if child.is_alive(): child.terminate()\n        child.join(10)\n"
    )
    runner = _project(tmp_path, monkeypatch, helper, test)
    assert runner.run_clean_test() == 0, runner.last_diagnostic_output
    child = json.loads(marker.read_text(encoding="utf-8"))
    parent = json.loads(observed.read_text(encoding="utf-8"))
    assert child["pid"] == parent["pid"]
    assert child["recorder_attached"]
    assert not psutil.pid_exists(child["pid"])
    if observer_fails:
        assert parent["exit_code"] != 0
        assert runner.clean_runtime_names is None
        assert "incomplete" in (runner.clean_runtime_names_diagnostic or "")
    else:
        assert child["observer_installed"]
        assert parent["exit_code"] == 0
        assert runner.clean_runtime_names == set()


@pytest.mark.slow
def test_actual_bootstrap_timeout_reaps_child_before_start_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    started = tmp_path / "started.json"
    observed = tmp_path / "timeout.json"
    helper = (
        "import json, os, time\nfrom pathlib import Path\n"
        "from mutmut_win import runtime_names as names\n"
        "def delayed_resume(raw):\n"
        "    payload = {'pid': os.getpid(), 'delay_seconds': 60}\n"
        f"    Path({str(started)!r}).write_text(json.dumps(payload))\n"
        "    time.sleep(60)\n    names._resume_spawn(raw)\n"
        "def delayed_reduce(self):\n"
        "    return delayed_resume, (self.ticket.model_dump_json(),)\n"
        "def empty():\n    pass\n"
    )
    test = (
        "import json, multiprocessing, time\nfrom pathlib import Path\n"
        "from mutmut_win import runtime_names as names\n"
        "from child_support import delayed_reduce, empty\n"
        "def test_child(monkeypatch):\n"
        "    monkeypatch.setattr(names._SpawnObserver, '__reduce__', delayed_reduce)\n"
        "    child = multiprocessing.get_context('spawn').Process(target=empty)\n"
        "    began = time.monotonic()\n"
        "    try:\n"
        "        try:\n            child.start()\n"
        "        except RuntimeError as error:\n"
        "            assert 'bootstrap incomplete' in str(error)\n"
        "            payload = {'pid': child.pid, 'error': str(error)}\n"
        "        else:\n            raise AssertionError('real bootstrap deadline did not fire')\n"
        "        payload['elapsed_seconds'] = time.monotonic() - began\n"
        "        payload['alive_after_error'] = child.is_alive()\n"
        f"        Path({str(observed)!r}).write_text(json.dumps(payload))\n"
        "        assert 29 <= payload['elapsed_seconds'] < 45\n"
        "        assert not child.is_alive(), 'real timeout leaked child before raising'\n"
        "    finally:\n"
        "        if child.is_alive(): child.terminate()\n        child.join(10)\n"
    )
    runner = _project(tmp_path, monkeypatch, helper, test)
    exit_code = runner.run_clean_test()
    child = json.loads(started.read_text(encoding="utf-8"))
    timeout = json.loads(observed.read_text(encoding="utf-8"))
    assert child["pid"] == timeout["pid"]
    assert child["delay_seconds"] == 60
    assert 29 <= timeout["elapsed_seconds"] < 45
    assert "bootstrap incomplete" in timeout["error"]
    assert not psutil.pid_exists(child["pid"])
    assert not timeout["alive_after_error"], runner.last_diagnostic_output
    assert exit_code == 0, runner.last_diagnostic_output
    assert runner.clean_runtime_names is None
