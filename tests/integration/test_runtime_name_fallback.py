"""Runtime-name authority must survive loss of optional timing statistics."""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from mutmut_win.db import DEFAULT_DB_PATH, load_results
from mutmut_win.config import MutmutConfig
from mutmut_win.file_setup import create_mutants_for_file
from mutmut_win.runner import PytestRunner


@pytest.mark.integration
@pytest.mark.parametrize("import_name", ["pkg.mod", "src.pkg.mod"])
def test_clean_spawn_transports_actual_child_calls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, import_name: str
) -> None:
    """A healthy spawned child supplies actual names without parent calls."""
    project = tmp_path / "project"
    source = project / "src/pkg/mod.py"
    source.parent.mkdir(parents=True)
    source.write_text("def value():\n    return 2\n", encoding="utf-8")
    monkeypatch.chdir(project)
    create_mutants_for_file(Path("src/pkg/mod.py"), Path("mutants/src/pkg/mod.py"))
    child_marker = tmp_path / "child.json"
    helper = (
        "import json, os\nfrom pathlib import Path\n"
        "def exercise():\n"
        f"    from {import_name} import value\n"
        "    result = value()\n"
        f"    Path({str(child_marker)!r}).write_text(json.dumps({{'pid': os.getpid(), 'value': result}}))\n"
        "    assert result == 2\n"
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
    for root in (project, project / "mutants"):
        (root / "tests").mkdir(exist_ok=True)
        (root / "tests/test_value.py").write_text(test, encoding="utf-8")
        (root / "child_support.py").write_text(helper, encoding="utf-8")
    (project / "pyproject.toml").write_text(
        '[tool.pytest.ini_options]\npythonpath = [".", "src"]\n', encoding="utf-8"
    )
    runner = PytestRunner(MutmutConfig(tests_dir=["tests"], clean_run_timeout=60))
    assert runner.run_clean_test() == 0, runner.last_diagnostic_output
    child = json.loads(child_marker.read_text(encoding="utf-8"))
    assert child["pid"] != os.getpid()
    assert child["value"] == 2
    assert runner.clean_runtime_names == {f"{import_name}.x_value"}


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
            f"    Path({str(child_marker)!r}).write_text(json.dumps({{'pid': os.getpid(), 'value': result}}))\n",
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
