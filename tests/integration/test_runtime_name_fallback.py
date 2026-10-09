"""Runtime-name authority must survive loss of optional timing statistics."""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.parametrize(
    ("layout", "fail_stats"),
    [("alias", False), ("alias", True), ("canonical", False), ("canonical", True),
     ("canonical_loaded_alias_called", True), ("alias_loaded_canonical_called", True),
     ("double_called", True)],
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
    (tests / "test_value.py").write_text(
        "import os\n" + "\n".join(imports) + "\n\ndef test_value():\n"
        + ("    assert os.environ.get('MUTANT_UNDER_TEST') != 'stats'\n" if fail_stats else "")
        + "    " + calls[layout] + "\n", encoding="utf-8",
    )
    (project / "pyproject.toml").write_text(
        '[tool.mutmut]\npaths_to_mutate = ["src/pkg/mod.py"]\n'
        'tests_dir = ["tests"]\nmutation_profile = "advanced"\nmax_children = 1\n'
        '[tool.pytest.ini_options]\npythonpath = [".", "src"]\n', encoding="utf-8",
    )
    uv = shutil.which("uv")
    assert uv is not None
    env = os.environ.copy()
    env["UV_PROJECT_ENVIRONMENT"] = str(Path(os.environ["VIRTUAL_ENV"]).resolve())
    # The controlled CLI runs through uv in the externally synchronized parent environment.
    result = subprocess.run(  # noqa: S603
        [uv, "run", "--no-sync", "python", "-m", "mutmut_win", "run",
         "--no-progress", "--output", "json"], cwd=project, env=env,
        capture_output=True, timeout=300,
    )
    (tmp_path / "stdout.bin").write_bytes(result.stdout)
    (tmp_path / "stderr.bin").write_bytes(result.stderr)
    stderr = result.stderr.decode("utf-8", errors="replace")
    if layout in {"alias", "canonical_loaded_alias_called"}:
        assert result.returncode == 1, (result.stdout, stderr)
        assert "src.pkg.mod.x_value" in stderr
        assert "pkg.mod.x_value" in stderr
        assert "cannot address" in stderr
    else:
        assert result.returncode == 0, (result.stdout, stderr)
        payload = json.loads(result.stdout)
        (tmp_path / "result.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
        assert payload["total_mutants"] == 5
        assert payload["killed"] == 5
        assert payload["survived"] == 0
        assert payload["mutation_score"] == 100.0
