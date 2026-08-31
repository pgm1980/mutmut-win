"""Adversarial dependency/run-context fingerprint regressions."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import TYPE_CHECKING, cast

import pytest

import mutmut_win.stats as stats_module
from mutmut_win.config import MutmutConfig
from mutmut_win.constants import INTERNAL_CHILD_ENVIRONMENT_VARS, WORKSPACE_EXCLUDED_DIR_NAMES
from mutmut_win.models import MutationTask
from mutmut_win.orchestrator import _build_tests_fingerprints
from mutmut_win.stats import (
    MutmutStats,
    _DependencyBasis,
    _hash_runtime_identity,
    _installed_distribution_basis,
    build_run_basis_evidence,
    build_stats_context_fingerprint,
    collect_or_load_stats,
    context_allows_result_reuse,
)

if TYPE_CHECKING:
    from importlib.metadata import Distribution

    from mutmut_win.runner import PytestRunner


class _FakeDistribution:
    def __init__(
        self,
        root: Path,
        *,
        name: str = "demo-dependency",
        version: str = "1.0",
        files: list[Path] | None = None,
        direct_url: str | None = None,
    ) -> None:
        self.root = root
        self.metadata = {"Name": name}
        self.version = version
        self.files = files
        self._direct_url = direct_url

    def locate_file(self, entry: object) -> Path:
        return self.root / str(entry)

    def read_text(self, filename: str) -> str | None:
        return self._direct_url if filename == "direct_url.json" else None


def _project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, MutmutConfig]:
    project = tmp_path / "project"
    (project / "src").mkdir(parents=True)
    (project / "tests").mkdir()
    (project / "src" / "target.py").write_text("VALUE = 1\n", encoding="utf-8")
    (project / "tests" / "test_target.py").write_text(
        "def test_target(): assert True\n", encoding="utf-8"
    )
    monkeypatch.chdir(project)
    return project, MutmutConfig(paths_to_mutate=["src"], tests_dir=["tests"])


@pytest.mark.parametrize(
    "manifest",
    [
        "requirements.txt",
        "requirements-dev.txt",
        "poetry.lock",
        "Pipfile",
        "Pipfile.lock",
        "pdm.lock",
        "pylock.toml",
    ],
)
def test_common_dependency_manifest_content_invalidates_context(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    manifest: str,
) -> None:
    project, config = _project(tmp_path, monkeypatch)
    monkeypatch.setattr(
        stats_module,
        "_installed_distribution_basis",
        lambda _root, _seen: _DependencyBasis("stable-environment", True),
    )
    path = project / manifest
    path.write_text("demo==1\n", encoding="utf-8")
    before = build_stats_context_fingerprint(config)
    original = path.stat()

    path.write_text("demo==2\n", encoding="utf-8")
    os.utime(path, ns=(original.st_atime_ns, original.st_mtime_ns))

    assert build_stats_context_fingerprint(config) != before


def test_automatically_staged_root_fixture_invalidates_context(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project, config = _project(tmp_path, monkeypatch)
    monkeypatch.setattr(
        stats_module,
        "_installed_distribution_basis",
        lambda _root, _seen: _DependencyBasis("stable-environment", True),
    )
    fixture = project / "cases.json"
    fixture.write_text('{"value":1}\n', encoding="utf-8")
    before = build_stats_context_fingerprint(config)
    original = fixture.stat()

    fixture.write_text('{"value":2}\n', encoding="utf-8")
    os.utime(fixture, ns=(original.st_atime_ns, original.st_mtime_ns))

    assert build_stats_context_fingerprint(config) != before


@pytest.mark.parametrize("directory_name", sorted(WORKSPACE_EXCLUDED_DIR_NAMES))
def test_non_execution_workspace_directory_drift_does_not_invalidate_context(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    directory_name: str,
) -> None:
    project, config = _project(tmp_path, monkeypatch)
    monkeypatch.setattr(
        stats_module,
        "_installed_distribution_basis",
        lambda _root, _seen: _DependencyBasis("stable-environment", True),
    )
    before = build_stats_context_fingerprint(config)

    ignored = project / directory_name
    ignored.mkdir()
    (ignored / "tool-state.bin").write_bytes(b"first")
    created = build_stats_context_fingerprint(config)
    (ignored / "tool-state.bin").write_bytes(b"second")
    changed = build_stats_context_fingerprint(config)

    assert created == before
    assert changed == before


def test_missing_optional_copy_paths_are_complete_observed_absence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project, _config = _project(tmp_path, monkeypatch)
    config = MutmutConfig(
        paths_to_mutate=["src"],
        tests_dir=["tests"],
        also_copy=[
            "tests/",
            "test/",
            "setup.cfg",
            "pyproject.toml",
            "pytest.ini",
            ".gitignore",
        ],
    )
    monkeypatch.setattr(
        stats_module,
        "_installed_distribution_basis",
        lambda _root, _seen: _DependencyBasis("stable-environment", True),
    )

    absent = build_run_basis_evidence(config, project_root=project)
    (project / "setup.cfg").write_text("[tool:pytest]\n", encoding="utf-8")
    present = build_run_basis_evidence(config, project_root=project)

    assert absent.complete is True
    assert present.complete is True
    assert present.digest != absent.digest


def test_broken_configured_link_is_not_treated_as_observed_absence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project, _config = _project(tmp_path, monkeypatch)
    link = project / "optional-link"
    try:
        link.symlink_to(project / "missing-target")
    except OSError as exc:
        pytest.skip(f"file symlinks are unavailable: {exc}")
    config = MutmutConfig(
        paths_to_mutate=["src"],
        tests_dir=["tests"],
        also_copy=["optional-link"],
    )
    monkeypatch.setattr(
        stats_module,
        "_installed_distribution_basis",
        lambda _root, _seen: _DependencyBasis("stable-environment", True),
    )

    context = build_stats_context_fingerprint(config, project_root=project)

    assert context.startswith("no-reuse:")


def test_installed_distribution_bytes_bind_same_version_environment_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    distribution_root = tmp_path / "site-packages"
    project.mkdir()
    distribution_root.mkdir()
    module = distribution_root / "demo_dependency.py"
    module.write_text("VALUE = 1\n", encoding="utf-8")
    distribution = _FakeDistribution(distribution_root, files=[Path(module.name)])
    monkeypatch.setattr(stats_module.sys, "path", [str(project), str(distribution_root)])
    monkeypatch.setattr(
        stats_module.importlib.metadata,
        "distributions",
        lambda: [cast("Distribution", distribution)],
    )
    before = _installed_distribution_basis(project, set())
    original = module.stat()

    module.write_text("VALUE = 2\n", encoding="utf-8")
    os.utime(module, ns=(original.st_atime_ns, original.st_mtime_ns))
    after = _installed_distribution_basis(project, set())

    assert before.reuse_safe is True
    assert after.reuse_safe is True
    assert after.digest != before.digest


def test_installed_distribution_version_invalidates_environment_basis(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    distribution_root = tmp_path / "site-packages"
    project.mkdir()
    distribution_root.mkdir()
    module = distribution_root / "demo_dependency.py"
    module.write_text("VALUE = 1\n", encoding="utf-8")
    distribution = _FakeDistribution(distribution_root, files=[Path(module.name)])
    monkeypatch.setattr(stats_module.sys, "path", [str(project), str(distribution_root)])
    monkeypatch.setattr(
        stats_module.importlib.metadata,
        "distributions",
        lambda: [cast("Distribution", distribution)],
    )
    before = _installed_distribution_basis(project, set())

    distribution.version = "2.0"

    assert _installed_distribution_basis(project, set()).digest != before.digest


def test_editable_distribution_source_bytes_bind_local_environment_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    distribution_root = tmp_path / "site-packages"
    editable_root = tmp_path / "editable-dependency"
    project.mkdir()
    distribution_root.mkdir()
    editable_root.mkdir()
    source = editable_root / "editable_dependency.py"
    source.write_text("VALUE = 1\n", encoding="utf-8")
    direct_url = json.dumps(
        {"url": editable_root.as_uri(), "dir_info": {"editable": True}},
        separators=(",", ":"),
    )
    direct_url_path = distribution_root / "direct_url.json"
    direct_url_path.write_text(direct_url, encoding="utf-8")
    distribution = _FakeDistribution(
        distribution_root,
        files=[Path(direct_url_path.name)],
        direct_url=direct_url,
    )
    monkeypatch.setattr(
        stats_module.sys,
        "path",
        [str(project), str(distribution_root), str(editable_root)],
    )
    monkeypatch.setattr(
        stats_module.importlib.metadata,
        "distributions",
        lambda: [cast("Distribution", distribution)],
    )
    before = _installed_distribution_basis(project, set())

    source.write_text("VALUE = 2\n", encoding="utf-8")
    after = _installed_distribution_basis(project, set())

    assert before.reuse_safe is True
    assert after.reuse_safe is True
    assert after.digest != before.digest


def test_uninventoried_distribution_marks_context_and_disables_verdict_reuse(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project, config = _project(tmp_path, monkeypatch)
    distribution = _FakeDistribution(tmp_path / "site-packages", files=None)
    monkeypatch.setattr(
        stats_module.sys,
        "path",
        [str(project), str(tmp_path / "site-packages")],
    )
    monkeypatch.setattr(
        stats_module.importlib.metadata,
        "distributions",
        lambda: [cast("Distribution", distribution)],
    )

    context = build_stats_context_fingerprint(config, project_root=project)
    evidence = build_run_basis_evidence(config, project_root=project)
    task = MutationTask(mutant_name="pkg.target__mutmut_1", tests=["tests/test_target.py"])

    assert context.startswith("no-reuse:")
    assert context_allows_result_reuse(context) is False
    assert evidence.complete is False
    assert _build_tests_fingerprints([task], context_fingerprint=context) == {}


def test_incomplete_context_never_reuses_the_stats_mapping(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cached = MutmutStats(context_fingerprint="no-reuse:unchanged")
    fresh = MutmutStats(context_fingerprint="no-reuse:unchanged")
    monkeypatch.setattr(stats_module, "load_stats", lambda _directory: cached)
    monkeypatch.setattr(
        stats_module,
        "_run_stats_collection",
        lambda *_args, **_kwargs: fresh,
    )

    result = collect_or_load_stats(
        cast("PytestRunner", object()),
        context_fingerprint="no-reuse:unchanged",
    )

    assert result is fresh


def test_generic_type_checker_command_fails_closed_for_reuse_and_run_basis(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project, _config = _project(tmp_path, monkeypatch)
    config = MutmutConfig(
        paths_to_mutate=["src"],
        tests_dir=["tests"],
        type_check_command=["python", str(tmp_path / "external-checker.py")],
    )
    monkeypatch.setattr(
        stats_module,
        "_installed_distribution_basis",
        lambda _root, _seen: _DependencyBasis("stable-environment", True),
    )

    context = build_stats_context_fingerprint(config, project_root=project)
    evidence = build_run_basis_evidence(config, project_root=project)

    assert context.startswith("no-reuse:")
    assert context_allows_result_reuse(context) is False
    assert evidence.complete is False


def test_arbitrary_inherited_environment_drift_changes_dependency_basis(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.setattr(stats_module.sys, "path", [str(project)])
    monkeypatch.setattr(stats_module.importlib.metadata, "distributions", list)
    monkeypatch.setenv("DEMO_TEST_INPUT", "before")

    before = _installed_distribution_basis(project, set())
    monkeypatch.setenv("DEMO_TEST_INPUT", "after")
    after = _installed_distribution_basis(project, set())

    assert before.reuse_safe is True
    assert after.reuse_safe is True
    assert after.digest != before.digest


@pytest.mark.parametrize("name", sorted(INTERNAL_CHILD_ENVIRONMENT_VARS))
def test_every_inherited_internal_control_remains_bound_to_dependency_basis(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    name: str,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.setattr(stats_module.sys, "path", [str(project)])
    monkeypatch.setattr(stats_module.importlib.metadata, "distributions", list)
    monkeypatch.setenv(name, "before")

    before = _installed_distribution_basis(project, set())
    monkeypatch.setenv(name, "after")
    after = _installed_distribution_basis(project, set())

    assert before.reuse_safe is True
    assert after.reuse_safe is True
    assert after.digest != before.digest


@pytest.mark.skipif(os.name == "nt", reason="POSIX environment names are case-sensitive")
def test_posix_case_variant_of_internal_environment_name_remains_bound(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.setattr(stats_module.sys, "path", [str(project)])
    monkeypatch.setattr(stats_module.importlib.metadata, "distributions", list)
    monkeypatch.setenv("mutant_under_test", "before")

    before = _installed_distribution_basis(project, set())
    monkeypatch.setenv("mutant_under_test", "after")
    after = _installed_distribution_basis(project, set())

    assert before.reuse_safe is True
    assert after.reuse_safe is True
    assert after.digest != before.digest


def test_ordered_sys_path_and_unclaimed_module_bytes_bind_import_basis(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    project.mkdir()
    first_root.mkdir()
    second_root.mkdir()
    module = first_root / "unclaimed_module.py"
    module.write_text("VALUE = 1\n", encoding="utf-8")
    path_hook = first_root / "unclaimed-import-hook.pth"
    path_hook.write_text("import unclaimed_module\n", encoding="utf-8")
    monkeypatch.setattr(stats_module.importlib.metadata, "distributions", list)
    monkeypatch.setattr(
        stats_module.sys,
        "path",
        [str(project), str(first_root), str(second_root)],
    )

    before = _installed_distribution_basis(project, set())
    monkeypatch.setattr(
        stats_module.sys,
        "path",
        [str(project), str(second_root), str(first_root)],
    )
    reordered = _installed_distribution_basis(project, set())
    module.write_text("VALUE = 2\n", encoding="utf-8")
    changed = _installed_distribution_basis(project, set())
    path_hook.write_text("import another_module\n", encoding="utf-8")
    path_hook_changed = _installed_distribution_basis(project, set())

    assert before.reuse_safe is True
    assert reordered.reuse_safe is True
    assert changed.reuse_safe is True
    assert path_hook_changed.reuse_safe is True
    assert reordered.digest != before.digest
    assert changed.digest != reordered.digest
    assert path_hook_changed.digest != changed.digest


def test_overlapping_sys_path_roots_are_content_walked_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    environment = tmp_path / "environment"
    site_packages = environment / "Lib" / "site-packages"
    project.mkdir()
    site_packages.mkdir(parents=True)
    (site_packages / "unclaimed_module.py").write_text("VALUE = 1\n", encoding="utf-8")
    monkeypatch.setattr(stats_module.importlib.metadata, "distributions", list)
    monkeypatch.setattr(
        stats_module.sys,
        "path",
        [str(project), str(environment), str(site_packages)],
    )
    real_hash_tree = stats_module._hash_context_tree
    walked: list[Path] = []

    def recording_hash_tree(*args: object, **kwargs: object) -> bool:
        label = str(kwargs["label_prefix"])
        if label.startswith("sys.path:content:"):
            walked.append(Path(cast("Path", args[1])).resolve())
        return real_hash_tree(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(stats_module, "_hash_context_tree", recording_hash_tree)

    basis = _installed_distribution_basis(project, set())

    assert basis.reuse_safe is True
    assert walked == [environment.resolve()]


def test_nested_skipped_project_directory_is_not_falsely_treated_as_covered(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    nested_import_root = project / "outer" / ".venv" / "Lib" / "site-packages"
    nested_import_root.mkdir(parents=True)
    module = nested_import_root / "unclaimed_module.py"
    module.write_text("VALUE = 1\n", encoding="utf-8")
    monkeypatch.setattr(stats_module.importlib.metadata, "distributions", list)
    monkeypatch.setattr(stats_module.sys, "path", [str(project), str(nested_import_root)])

    before = _installed_distribution_basis(project, set())
    module.write_text("VALUE = 2\n", encoding="utf-8")
    after = _installed_distribution_basis(project, set())

    assert before.reuse_safe is True
    assert after.reuse_safe is True
    assert after.digest != before.digest


def test_broken_sys_path_link_makes_dependency_basis_incomplete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    broken = tmp_path / "broken-import-root"
    try:
        broken.symlink_to(tmp_path / "missing-import-target", target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"directory symlinks are unavailable: {exc}")
    monkeypatch.setattr(stats_module.importlib.metadata, "distributions", list)
    monkeypatch.setattr(stats_module.sys, "path", [str(project), str(broken)])

    basis = _installed_distribution_basis(project, set())

    assert basis.reuse_safe is False


def test_runtime_version_drift_changes_dependency_basis(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.setattr(stats_module.sys, "path", [str(project)])
    monkeypatch.setattr(stats_module.importlib.metadata, "distributions", list)
    before = _installed_distribution_basis(project, set())

    monkeypatch.setattr(stats_module.sys, "version", f"{stats_module.sys.version} drift")
    after = _installed_distribution_basis(project, set())

    assert before.reuse_safe is True
    assert after.reuse_safe is True
    assert after.digest != before.digest


@pytest.mark.parametrize(
    ("attribute", "replacement"),
    [
        ("flags", "synthetic-optimize=1"),
        ("_xoptions", {"dev": True}),
        ("warnoptions", ["error", "ignore::DeprecationWarning"]),
        ("pycache_prefix", "synthetic-pycache-prefix"),
    ],
)
def test_runtime_startup_controls_change_dependency_basis(
    monkeypatch: pytest.MonkeyPatch,
    attribute: str,
    replacement: object,
) -> None:
    before = hashlib.sha256()
    assert _hash_runtime_identity(before, set()) is True

    monkeypatch.setattr(stats_module.sys, attribute, replacement)
    after = hashlib.sha256()
    assert _hash_runtime_identity(after, set()) is True

    assert after.hexdigest() != before.hexdigest()


@pytest.mark.skipif(os.name != "nt", reason="Windows handle/path stat regression")
def test_real_windows_environment_has_a_complete_dependency_basis() -> None:
    basis = _installed_distribution_basis(Path.cwd(), set())

    assert basis.reuse_safe is True
    assert len(basis.digest) == 64
