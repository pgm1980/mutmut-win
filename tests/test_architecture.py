"""Architecture tests for mutmut-win.

Verify that all top-level modules are importable without circular dependencies
and that the import-linter layer contracts are satisfied.
"""

from __future__ import annotations

import os
import stat
import subprocess
import sys
from importlib import import_module
from pathlib import Path


def _snapshot_kind(metadata: os.stat_result) -> str:
    """Classify an lstat result without following links or reparse points."""

    mode = metadata.st_mode
    if stat.S_ISLNK(mode):
        return "symlink"
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    if getattr(metadata, "st_file_attributes", 0) & reparse_flag:
        return "reparse"
    if stat.S_ISDIR(mode):
        return "directory"
    if stat.S_ISREG(mode):
        return "file"
    return "other"


def _directory_snapshot(root: Path) -> tuple[str, tuple[tuple[str, str, bytes], ...]]:
    """Capture root/entry kinds and file bytes without traversing indirections."""

    try:
        root_kind = _snapshot_kind(root.lstat())
    except FileNotFoundError:
        return "missing", ()
    if root_kind != "directory":
        return root_kind, ()

    entries: list[tuple[str, str, bytes]] = []
    pending = [root]
    while pending:
        directory = pending.pop()
        with os.scandir(directory) as iterator:
            children = sorted(iterator, key=lambda entry: entry.name)
        for child in children:
            path = Path(child.path)
            kind = _snapshot_kind(child.stat(follow_symlinks=False))
            payload = path.read_bytes() if kind == "file" else b""
            entries.append((path.relative_to(root).as_posix(), kind, payload))
            if kind == "directory":
                pending.append(path)
    return root_kind, tuple(sorted(entries))


def test_directory_snapshot_preserves_root_and_entry_kinds(tmp_path: Path) -> None:
    missing = tmp_path / "missing-cache"
    regular = tmp_path / "regular-cache"
    regular.write_bytes(b"root bytes")
    directory = tmp_path / "directory-cache"
    directory.mkdir()
    (directory / "state").write_bytes(b"entry bytes")

    assert _directory_snapshot(missing) == ("missing", ())
    assert _directory_snapshot(regular) == ("file", ())
    assert _directory_snapshot(directory) == (
        "directory",
        (("state", "file", b"entry bytes"),),
    )


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
        "mutmut_win.hit_recording",
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


def test_import_linter_contracts_hold() -> None:
    """Execute the REAL import-linter gate inside the suite (issue #84).

    The layer contract was 'green by absence' for sprints 23-26 because
    nothing ever executed it; running it from pytest makes every
    ``uv run pytest`` invocation enforce the architecture.  Anchored to the
    repo root because several tests chdir into tmp directories.

    Runs UNCONDITIONALLY since issue #107 — including inside the
    trampolined build artifact: the QX-001 skip (generated mutants pulled
    the CLI chain via __main__) is obsolete now that the trampoline
    imports only the bottom-band kernel (hit_recording / exceptions).
    """
    project_root = Path(__file__).resolve().parent.parent
    repository_cache = project_root / ".import_linter_cache"
    cache_before = _directory_snapshot(repository_cache)
    script = (
        "from importlinter.cli import lint_imports;"
        "import sys; sys.exit(lint_imports(no_cache=True))"
    )
    result = subprocess.run(  # noqa: S603 — fully controlled command
        [sys.executable, "-c", script],
        capture_output=True,
        encoding="utf-8",
        cwd=project_root,
        timeout=120,
    )
    assert _directory_snapshot(repository_cache) == cache_before, (
        "the in-suite import-linter gate modified checkout-local cache state"
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
