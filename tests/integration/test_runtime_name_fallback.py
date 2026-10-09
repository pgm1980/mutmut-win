"""Runtime-name authority must survive loss of optional timing statistics."""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from mutmut_win.config import MutmutConfig
from mutmut_win.db import DEFAULT_DB_PATH, load_results
from mutmut_win.file_setup import create_mutants_for_file
from mutmut_win.runner import PytestRunner


@pytest.mark.integration
@pytest.mark.parametrize("import_name", ["pkg.mod", "src.pkg.mod"])
@pytest.mark.parametrize(
    "kind",
    [
        "spawn",
        "default",
        "pool",
        "pool_context",
        "executor",
        "descendant",
        "terminated",
        "registration_failed",
    ],
)
def test_clean_spawn_transports_actual_child_calls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, import_name: str, kind: str
) -> None:
    """A healthy spawned child supplies actual names without parent calls."""
    project = tmp_path / "project"
    source = project / "src/pkg/mod.py"
    source.parent.mkdir(parents=True)
    source.write_text("def value():\n    return 2\n", encoding="utf-8")
    monkeypatch.chdir(project)
    create_mutants_for_file(Path("src/pkg/mod.py"), Path("mutants/src/pkg/mod.py"))
    child_markers = tmp_path / "children"
    child_markers.mkdir()
    helper = (
        "import json, os, multiprocessing, time\nfrom pathlib import Path\n"
        "def exercise(_number=None):\n"
        f"    from {import_name} import value\n"
        "    result = value()\n"
        f"    root = Path({str(child_markers)!r})\n"
        "    payload = {'pid': os.getpid(), 'value': result}\n"
        "    (root / f'{os.getpid()}.json').write_text(json.dumps(payload))\n"
        "    assert result == 2\n"
        "    return os.getpid()\n"
        "def descendant():\n"
        "    child = multiprocessing.get_context('spawn').Process(target=exercise)\n"
        "    child.start()\n    child.join(20)\n    assert child.exitcode == 0\n"
        "def awaiting_kill(event):\n"
        "    exercise()\n    event.set()\n    time.sleep(60)\n"
        "def failed_registration():\n"
        "    from mutmut_win import runtime_names\n"
        f"    from {import_name} import value\n"
        "    original_record = runtime_names.record_runtime_name\n"
        "    def fail_write(*args):\n        raise OSError('injected first-part failure')\n"
        "    def record(name):\n"
        f"        root = Path({str(child_markers)!r})\n"
        "        payload = {'pid': os.getpid(), 'trampoline_entered': name}\n"
        "        (root / f'{os.getpid()}.json').write_text(json.dumps(payload))\n"
        "        original_record(name)\n"
        "    runtime_names._write_part = fail_write\n"
        "    runtime_names.record_runtime_name = record\n"
        "    value()\n"
    )
    test = (
        "import multiprocessing\nfrom child_support import exercise\n"
        "def test_value():\n"
        "    child = multiprocessing.get_context('spawn').Process(target=exercise)\n"
        "    child.start()\n"
        "    try:\n        child.join(30)\n        assert child.exitcode == 0\n"
        "    finally:\n        if child.is_alive():\n            child.terminate()\n"
        "        child.join(10)\n"
    )
    if kind == "default":
        test = test.replace(
            "multiprocessing.get_context('spawn').Process", "multiprocessing.Process"
        )
    elif kind == "descendant":
        test = test.replace("import exercise", "import descendant as exercise")
    elif kind == "registration_failed":
        test = test.replace("import exercise", "import failed_registration as exercise")
        test = test.replace("assert child.exitcode == 0", "assert child.exitcode != 0")
    elif kind == "pool":
        test = (
            "import multiprocessing\nfrom child_support import exercise\n"
            "def test_value():\n"
            "    pool = multiprocessing.get_context('spawn').Pool(2, maxtasksperchild=1)\n"
            "    try:\n        pids = pool.map(exercise, range(4), chunksize=1)\n"
            "        assert len(set(pids)) == 4\n"
            "    finally:\n        pool.close()\n        pool.join()\n"
        )
    elif kind == "pool_context":
        test = (
            "import multiprocessing\nfrom child_support import exercise\n"
            "def test_value():\n"
            "    with multiprocessing.get_context('spawn').Pool(2) as pool:\n"
            "        assert len(pool.map(exercise, range(4), chunksize=1)) == 4\n"
        )
    elif kind == "executor":
        test = (
            "from concurrent.futures import ProcessPoolExecutor\n"
            "from child_support import exercise\n"
            "def test_value():\n"
            "    with ProcessPoolExecutor(max_workers=2, max_tasks_per_child=1) as pool:\n"
            "        assert len(set(pool.map(exercise, range(4)))) == 4\n"
        )
    elif kind == "terminated":
        test = (
            "import multiprocessing\nfrom child_support import awaiting_kill\n"
            "def test_value():\n"
            "    context = multiprocessing.get_context('spawn')\n"
            "    called = context.Event()\n"
            "    child = context.Process(target=awaiting_kill, args=(called,))\n"
            "    child.start()\n"
            "    try:\n        assert called.wait(20)\n"
            "    finally:\n        child.terminate()\n        child.join(10)\n"
            "    assert not child.is_alive()\n    assert child.exitcode != 0\n"
        )
    for root in (project, project / "mutants"):
        (root / "tests").mkdir(exist_ok=True)
        (root / "tests/test_value.py").write_text(test, encoding="utf-8")
        (root / "child_support.py").write_text(helper, encoding="utf-8")
    (project / "pyproject.toml").write_text(
        '[tool.pytest.ini_options]\npythonpath = [".", "src"]\n', encoding="utf-8"
    )
    runner = PytestRunner(MutmutConfig(tests_dir=["tests"], clean_run_timeout=60))
    assert runner.run_clean_test() == 0, runner.last_diagnostic_output
    children = [json.loads(path.read_text(encoding="utf-8")) for path in child_markers.iterdir()]
    if kind == "pool_context":
        assert 1 <= len(children) <= 2
    else:
        assert len(children) == (4 if kind in {"pool", "executor"} else 1)
    assert all(child["pid"] != os.getpid() for child in children)
    if kind == "registration_failed":
        assert children[0]["trampoline_entered"] == f"{import_name}.x_value"
        assert runner.clean_runtime_names is None
    elif kind == "terminated":
        assert children[0]["value"] == 2
        assert runner.clean_runtime_names is None
        assert ".complete.json" in (runner.clean_runtime_names_diagnostic or "")
    else:
        assert all(child["value"] == 2 for child in children)
        assert runner.clean_runtime_names == {f"{import_name}.x_value"}, (
            runner.clean_runtime_names_diagnostic
        )


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.parametrize(
    ("layout", "fail_stats"),
    [
        ("alias", False),
        ("alias", True),
        ("canonical", False),
        ("canonical", True),
        ("canonical_loaded_alias_called", True),
        ("alias_loaded_canonical_called", True),
        ("double_called", True),
        ("spawn_canonical", False),
        ("spawn_alias", False),
    ],
)
def test_cli_runtime_name_proof_is_independent_of_stats(
    tmp_path: Path, layout: str, fail_stats: bool
) -> None:
    """Compare real calls, unused imports, and full stats/fallback CLI outcomes."""
    project = tmp_path / "project"
    module = project / "src/pkg/mod.py"
    module.parent.mkdir(parents=True)
    module.write_text("def value():\n    return 2\n", encoding="utf-8")
    tests = project / "tests"
    tests.mkdir()
    imports = []
    if layout != "alias":
        imports.append("import pkg.mod as canonical")
    if layout != "canonical":
        imports.append("import src.pkg.mod as alias")
    calls = {
        "alias": "assert alias.value() == 2",
        "canonical": "assert canonical.value() == 2",
        "canonical_loaded_alias_called": "assert alias.value() == 2",
        "alias_loaded_canonical_called": "assert canonical.value() == 2",
        "double_called": "assert canonical.value() == alias.value() == 2",
    }
    test_source = (
        "import os\n"
        + "\n".join(imports)
        + "\n\ndef test_value():\n"
        + ("    assert os.environ.get('MUTANT_UNDER_TEST') != 'stats'\n" if fail_stats else "")
        + "    "
        + calls.get(layout, "pass")
        + "\n"
    )
    child_marker = tmp_path / "child-called.json"
    if layout.startswith("spawn_"):
        imported = "pkg.mod" if layout == "spawn_canonical" else "src.pkg.mod"
        (project / "child_support.py").write_text(
            "import json, os\nfrom pathlib import Path\n"
            "def exercise():\n"
            f"    from {imported} import value\n"
            "    result = value()\n"
            "    payload = {'pid': os.getpid(), 'value': result}\n"
            f"    Path({str(child_marker)!r}).write_text(json.dumps(payload))\n",
            encoding="utf-8",
        )
        test_source = (
            "import multiprocessing\nfrom child_support import exercise\n"
            "def test_value():\n"
            "    child = multiprocessing.get_context('spawn').Process(target=exercise)\n"
            "    child.start()\n"
            "    try:\n        child.join(30)\n        assert child.exitcode == 0\n"
            "    finally:\n        if child.is_alive():\n            child.terminate()\n"
            "        child.join(10)\n"
        )
    (tests / "test_value.py").write_text(test_source, encoding="utf-8")
    (project / "pyproject.toml").write_text(
        '[tool.mutmut]\npaths_to_mutate = ["src/pkg/mod.py"]\n'
        'tests_dir = ["tests"]\nmutation_profile = "advanced"\nmax_children = 1\n'
        '[tool.pytest.ini_options]\npythonpath = [".", "src"]\n',
        encoding="utf-8",
    )
    uv = shutil.which("uv")
    assert uv is not None
    env = os.environ.copy()
    env["UV_PROJECT_ENVIRONMENT"] = str(Path(os.environ["VIRTUAL_ENV"]).resolve())
    score_options = (
        ["--min-score", "80"]
        if layout in {"canonical", "alias_loaded_canonical_called", "double_called"}
        else []
    )
    # The controlled CLI runs through uv in the externally synchronized parent environment.
    result = subprocess.run(  # noqa: S603
        [
            uv,
            "run",
            "--no-sync",
            "python",
            "-m",
            "mutmut_win",
            "run",
            "--no-progress",
            "--output",
            "json",
            *score_options,
        ],
        cwd=project,
        env=env,
        capture_output=True,
        timeout=300,
    )
    (tmp_path / "stdout.bin").write_bytes(result.stdout)
    (tmp_path / "stderr.bin").write_bytes(result.stderr)
    stderr = result.stderr.decode("utf-8", errors="replace")
    if layout.startswith("spawn_"):
        child = json.loads(child_marker.read_text())
        assert child["pid"] != os.getpid()
    if layout in {"alias", "canonical_loaded_alias_called", "spawn_alias"}:
        assert result.returncode == 1, (result.stdout, stderr)
        assert "src.pkg.mod.x_value" in stderr
        assert "pkg.mod.x_value" in stderr
        assert "cannot address" in stderr
    else:
        assert result.returncode == 0, (result.stdout, stderr)
        payload = json.loads(result.stdout)
        (tmp_path / "result.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
        assert payload["total_mutants"] == 5
        expected_killed = 0 if layout == "spawn_canonical" else 5
        assert payload["killed"] == expected_killed
        assert payload["survived"] == 5 - expected_killed
        assert payload["score"] == expected_killed * 20.0
        assert payload["execution_basis_complete"]
        verdicts = load_results(project / DEFAULT_DB_PATH)
        assert len(verdicts) == 5
        assert {row.mutant_name for row in verdicts} == {
            f"pkg.mod.x_value__mutmut_{number}" for number in range(1, 6)
        }
        assert {row.status for row in verdicts} == (
            {"survived"} if layout == "spawn_canonical" else {"killed"}
        )
        (tmp_path / "verdicts.json").write_text(
            "[" + ",".join(row.model_dump_json() for row in verdicts) + "]", encoding="utf-8"
        )
        # Exercise the public export guard against the same completed CLI basis.
        exported = subprocess.run(  # noqa: S603
            [uv, "run", "--no-sync", "python", "-m", "mutmut_win", "export-cicd-stats"],
            cwd=project,
            env=env,
            capture_output=True,
            timeout=180,
        )
        (tmp_path / "export-stdout.bin").write_bytes(exported.stdout)
        (tmp_path / "export-stderr.bin").write_bytes(exported.stderr)
        assert exported.returncode == 0, exported.stderr
        export = project / "mutants/mutmut-cicd-stats.json"
        assert export.is_file()
        (tmp_path / "export.json").write_bytes(export.read_bytes())
