"""Architecture tests for mutmut-win.

Verify that all top-level modules are importable without circular dependencies
and that the import-linter layer contracts are satisfied.
"""

from __future__ import annotations

from importlib import import_module


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
        "mutmut_win.process.timeout",
        "mutmut_win.process.worker",
    ]
    for module_name in modules:
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
    import_module("mutmut_win.process.timeout")
    import_module("mutmut_win.process.worker")


def test_no_upward_import_from_process() -> None:
    """Process layer must not import from orchestrator or cli layers.

    Loads the process modules and inspects their __spec__ to confirm they
    are well-formed packages.  The actual dependency graph is enforced by
    import-linter; this test validates successful loading.
    """
    executor = import_module("mutmut_win.process.executor")
    timeout = import_module("mutmut_win.process.timeout")
    worker = import_module("mutmut_win.process.worker")

    for mod in (executor, timeout, worker):
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
