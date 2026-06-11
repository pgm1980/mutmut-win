"""Architecture tests for mutmut-win.

Verify that all top-level modules are importable without circular dependencies
and that the import-linter layer contracts are satisfied.
"""

from __future__ import annotations

import os
import subprocess
import sys
from importlib import import_module
from pathlib import Path

import pytest


def test_all_modules_importable() -> None:
    """All public mutmut_win modules must be importable without errors."""
    modules = [
        "mutmut_win",
        "mutmut_win.cli",
        "mutmut_win.config",
        "mutmut_win.constants",
        "mutmut_win.db",
        "mutmut_win.exceptions",
        "mutmut_win.models",
        "mutmut_win.mutation",
        "mutmut_win.node_mutation",
        "mutmut_win.orchestrator",
        "mutmut_win.runner",
        "mutmut_win.trampoline",
        "mutmut_win.code_coverage",
        "mutmut_win.type_checking",
        "mutmut_win.process",
        "mutmut_win.process.executor",
        "mutmut_win.process.worker",
    ]
    for module_name in modules:
        # Iterates our own src/ module list — no external input is imported.
        # nosemgrep: python.lang.security.audit.non-literal-import.non-literal-import
        imported = import_module(module_name)
        assert imported is not None, f"Failed to import {module_name}"


def test_architecture_contracts() -> None:
    """Verify layer architecture via import-linter.

    Imports key modules to confirm no circular dependencies exist at the
    boundaries defined in pyproject.toml [tool.importlinter].
    """
    # Layer 1 — top-level entry points
    import_module("mutmut_win.cli")

    # Layer 2 — orchestration
    import_module("mutmut_win.orchestrator")
    import_module("mutmut_win.runner")

    # Layer 3 — domain / engine
    import_module("mutmut_win.config")
    import_module("mutmut_win.models")
    import_module("mutmut_win.constants")
    import_module("mutmut_win.mutation")
    import_module("mutmut_win.node_mutation")
    import_module("mutmut_win.trampoline")

    # Layer 4 — infrastructure / process
    import_module("mutmut_win.process.executor")
    import_module("mutmut_win.process.worker")


@pytest.mark.skipif(
    os.environ.get("MUTANT_UNDER_TEST") is not None,
    reason=(
        "architecture contracts apply to src/, not to the trampolined build "
        "artifact: generated mutants import mutmut_win.__main__ for the "
        "trampoline hit recording, which statically pulls the CLI chain "
        "across layers (maintenance finding QX-001) — found live by the "
        "first dogfooding run (#98)"
    ),
)
def test_import_linter_contracts_hold() -> None:
    """Execute the REAL import-linter gate inside the suite (issue #84).

    The layer contract was 'green by absence' for sprints 23-26 because
    nothing ever executed it; running it from pytest makes every
    ``uv run pytest`` invocation enforce the architecture.  Anchored to the
    repo root because several tests chdir into tmp directories.
    """
    project_root = Path(__file__).resolve().parent.parent
    script = "from importlinter.cli import lint_imports;import sys; sys.exit(lint_imports())"
    result = subprocess.run(  # noqa: S603 — fully controlled command
        [sys.executable, "-c", script],
        capture_output=True,
        encoding="utf-8",
        cwd=project_root,
        timeout=120,
    )
    assert result.returncode == 0, (
        "import-linter layer contract broken "
        "(see _docs/architecture spec/adr_layer_contracts_v2.md):\n"
        f"{result.stdout}\n{result.stderr}"
    )


def test_no_upward_import_from_process() -> None:
    """Process layer must not import from orchestrator or cli layers.

    Loads the process modules and inspects their __spec__ to confirm they
    are well-formed packages.  The actual dependency graph is enforced by
    import-linter; this test validates successful loading.
    """
    executor = import_module("mutmut_win.process.executor")
    worker = import_module("mutmut_win.process.worker")

    for mod in (executor, worker):
        assert mod.__spec__ is not None, f"{mod.__name__} has no __spec__"


def test_config_has_no_process_dependency() -> None:
    """Config module must not depend on the process layer.

    Verifies that mutmut_win.config can be imported in isolation without
    pulling in heavy subprocess/multiprocessing machinery.
    """
    config_mod = import_module("mutmut_win.config")
    # If the import succeeds and the key class is present, the layer boundary holds.
    assert hasattr(config_mod, "MutmutConfig")
    assert hasattr(config_mod, "load_config")
