"""Adversarial dependency/run-context fingerprint regressions."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, cast

import pytest

import mutmut_win.cli as cli_module
import mutmut_win.stats as stats_module
from mutmut_win.config import MutmutConfig
from mutmut_win.constants import (
    INTERNAL_CHILD_ENVIRONMENT_VARS,
    WORKSPACE_EXCLUDED_DIR_NAMES,
)
from mutmut_win.file_setup import copy_also_copy_files
from mutmut_win.models import MutationTask, SourceFileMutationData
from mutmut_win.orchestrator import _build_tests_fingerprints
from mutmut_win.stats import (
    MutmutStats,
    RunBasisEvidence,
    _DependencyBasis,
    _hash_runtime_identity,
    _installed_distribution_basis,
    build_run_basis_evidence,
    build_staging_context_evidence,
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


class _StatWithAdjustedLinkCount:
    """Proxy one real stat while simulating unrelated hardlink churn."""

    def __init__(self, original: os.stat_result, delta: int) -> None:
        self._original = original
        self.st_nlink = original.st_nlink + delta

    def __getattr__(self, name: str) -> object:
        return getattr(self._original, name)


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
        lambda _root, _seen, **_kwargs: _DependencyBasis("stable-environment", True),
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
        lambda _root, _seen, **_kwargs: _DependencyBasis("stable-environment", True),
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
        lambda _root, _seen, **_kwargs: _DependencyBasis("stable-environment", True),
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


def test_dotenv_bytes_bind_context_without_being_published(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project, config = _project(tmp_path, monkeypatch)
    monkeypatch.setattr(
        stats_module,
        "_installed_distribution_basis",
        lambda _root, _seen, **_kwargs: _DependencyBasis("stable-environment", True),
    )
    dotenv = project / ".env.test"
    dotenv.write_text("FEATURE=off\n", encoding="utf-8")
    before = build_stats_context_fingerprint(config)

    dotenv.write_text("FEATURE=on\n", encoding="utf-8")

    assert build_stats_context_fingerprint(config) != before


@pytest.mark.parametrize("directory_name", ["build", "dist", "html", "bug_reporting", "_docs"])
def test_generic_excluded_name_is_still_hashed_when_nested_in_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    directory_name: str,
) -> None:
    project, config = _project(tmp_path, monkeypatch)
    monkeypatch.setattr(
        stats_module,
        "_installed_distribution_basis",
        lambda _root, _seen, **_kwargs: _DependencyBasis("stable-environment", True),
    )
    nested = project / "src" / "package" / directory_name
    nested.mkdir(parents=True)
    module = nested / "feature.py"
    module.write_text("VALUE = 1\n", encoding="utf-8")
    before = build_stats_context_fingerprint(config)

    module.write_text("VALUE = 2\n", encoding="utf-8")

    assert build_stats_context_fingerprint(config) != before


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
        lambda _root, _seen, **_kwargs: _DependencyBasis("stable-environment", True),
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
        lambda _root, _seen, **_kwargs: _DependencyBasis("stable-environment", True),
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


@pytest.mark.skipif(os.name != "nt", reason="Windows uv hardlink-count regression")
def test_dependency_and_sys_path_context_ignore_alias_count_but_bind_shared_writes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A second uv-style alias is not an execution-input change; its bytes are."""

    project = tmp_path / "project"
    distribution_root = tmp_path / "site-packages"
    import_root = tmp_path / "unclaimed-import-root"
    aliases = tmp_path / "other-uv-environment"
    project.mkdir()
    distribution_root.mkdir()
    import_root.mkdir()
    aliases.mkdir()
    distribution_module = distribution_root / "demo_dependency.py"
    import_module = import_root / "unclaimed_dependency.py"
    distribution_module.write_text("VALUE = 1\n", encoding="utf-8")
    import_module.write_text("VALUE = 1\n", encoding="utf-8")
    distribution = _FakeDistribution(
        distribution_root,
        files=[Path(distribution_module.name)],
    )
    monkeypatch.setattr(
        stats_module.sys,
        "path",
        [str(project), str(distribution_root), str(import_root)],
    )
    monkeypatch.setattr(
        stats_module.importlib.metadata,
        "distributions",
        lambda: [cast("Distribution", distribution)],
    )
    # Isolate the two target domains from the real interpreter executable,
    # whose uv-cache link count can legitimately churn in parallel as well.
    monkeypatch.setattr(stats_module, "_hash_runtime_identity", lambda *_args: True)
    distribution_alias = aliases / distribution_module.name
    import_alias = aliases / import_module.name
    os.link(distribution_module, distribution_alias)
    os.link(import_module, import_alias)
    real_fstat = os.fstat
    link_count_delta = 0

    def fstat_with_external_link_churn(fd: int) -> os.stat_result:
        current = real_fstat(fd)
        return cast(
            "os.stat_result",
            _StatWithAdjustedLinkCount(current, link_count_delta),
        )

    monkeypatch.setattr(stats_module.os, "fstat", fstat_with_external_link_churn)

    before = _installed_distribution_basis(project, set())
    link_count_delta = 1
    with_external_aliases = _installed_distribution_basis(project, set())
    link_count_delta = 0
    aliases_removed = _installed_distribution_basis(project, set())

    distribution_alias.write_text("VALUE = 2\n", encoding="utf-8")
    import_alias.write_text("VALUE = 2\n", encoding="utf-8")
    shared_bytes_changed = _installed_distribution_basis(project, set())

    assert before.reuse_safe is True
    assert with_external_aliases == before
    assert aliases_removed == before
    assert shared_bytes_changed.reuse_safe is True
    assert shared_bytes_changed.digest != before.digest


def test_context_reopen_ignores_link_count_churn_but_strict_snapshot_rejects_it(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "dependency.py"
    target.write_text("VALUE = 1\n", encoding="utf-8")
    real_fstat = os.fstat
    calls = 0

    def fstat_with_reopen_link_churn(fd: int) -> os.stat_result:
        nonlocal calls
        calls += 1
        current = real_fstat(fd)
        if calls % 3 == 0:
            return cast("os.stat_result", _StatWithAdjustedLinkCount(current, 1))
        return current

    monkeypatch.setattr(stats_module.os, "fstat", fstat_with_reopen_link_churn)

    cross_run_complete = stats_module._hash_context_file(
        hashlib.sha256(),
        target,
        label="dependency",
        seen=set(),
    )
    strict_complete = stats_module._hash_context_file(
        hashlib.sha256(),
        target,
        label="strict-staging",
        seen=set(),
        hash_link_count=True,
    )

    assert cross_run_complete is True
    assert strict_complete is False


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
        lambda _root, _seen, **_kwargs: _DependencyBasis("stable-environment", True),
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


def test_run_basis_classifies_environment_drift_as_ambient(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project, config = _project(tmp_path, monkeypatch)
    monkeypatch.setattr(stats_module.importlib.metadata, "distributions", list)
    monkeypatch.setattr(stats_module.sys, "path", [str(project)])
    monkeypatch.setenv("DEMO_AMBIENT_INPUT", "before")

    before = build_run_basis_evidence(config, project_root=project)
    monkeypatch.setenv("DEMO_AMBIENT_INPUT", "after")
    after = build_run_basis_evidence(config, project_root=project)

    assert before.complete is True
    assert after.complete is True
    assert before.core_complete is True
    assert after.core_complete is True
    assert after.digest != before.digest
    assert after.core_digest == before.core_digest


def test_run_basis_classifies_source_drift_as_core(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project, config = _project(tmp_path, monkeypatch)
    monkeypatch.setattr(stats_module.importlib.metadata, "distributions", list)
    monkeypatch.setattr(stats_module.sys, "path", [str(project)])
    source = project / "src" / "target.py"

    before = build_run_basis_evidence(config, project_root=project)
    source.write_text("VALUE = 2\n", encoding="utf-8")
    after = build_run_basis_evidence(config, project_root=project)

    assert before.core_complete is True
    assert after.core_complete is True
    assert after.core_digest != before.core_digest


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


def test_generated_mutants_sys_path_binds_unexpected_legacy_stats_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    mutants = project / "mutants"
    mutants.mkdir(parents=True)
    stats_file = mutants / "mutmut-stats.json"
    stats_file.write_text('{"context_fingerprint":"first"}\n', encoding="utf-8")
    monkeypatch.setattr(stats_module.importlib.metadata, "distributions", list)
    monkeypatch.setattr(stats_module.sys, "path", [str(mutants), str(project)])

    before = _installed_distribution_basis(project, set())
    stats_file.write_text('{"context_fingerprint":"second"}\n', encoding="utf-8")
    after = _installed_distribution_basis(project, set())

    assert before.reuse_safe is True
    assert after.reuse_safe is True
    assert after.digest != before.digest


def test_generated_mutants_sys_path_hashes_stable_executable_staging(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    mutants = project / "mutants"
    mutants.mkdir(parents=True)
    staged_module = mutants / "helper.py"
    staged_module.write_text("VALUE = 1\n", encoding="utf-8")
    monkeypatch.setattr(stats_module.importlib.metadata, "distributions", list)
    monkeypatch.setattr(stats_module.sys, "path", [str(mutants), str(project)])

    before = _installed_distribution_basis(project, set())
    staged_module.write_text("VALUE = 2\n", encoding="utf-8")
    after = _installed_distribution_basis(project, set())

    assert before.reuse_safe is True
    assert after.reuse_safe is True
    assert after.digest != before.digest


def test_generation_metadata_normalization_is_stable_but_rich_results_are_bound(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    mutants = project / "mutants"
    staged = mutants / "src" / "module.py"
    staged.parent.mkdir(parents=True)
    staged.write_text("VALUE = 1\n", encoding="utf-8")
    metadata = SourceFileMutationData(
        path="src/module.py",
        exit_code_by_key={"module.x_f__mutmut_1": 1},
        durations_by_key={"module.x_f__mutmut_1": 0.1},
        source_hash="a" * 64,
        generation_fingerprint="b" * 64,
        generated_hash=hashlib.sha256(staged.read_bytes()).hexdigest(),
    )
    monkeypatch.chdir(project)
    monkeypatch.setattr(stats_module.importlib.metadata, "distributions", list)
    monkeypatch.setattr(stats_module.sys, "path", [str(mutants), str(project)])

    metadata.save()
    rich = _installed_distribution_basis(project, set())
    metadata.save_generation_metadata()
    normalized_first = _installed_distribution_basis(project, set())
    metadata.exit_code_by_key["module.x_f__mutmut_1"] = 0
    metadata.durations_by_key["module.x_f__mutmut_1"] = 0.2
    metadata.save()
    rich_changed = _installed_distribution_basis(project, set())
    metadata.save_generation_metadata()
    normalized_second = _installed_distribution_basis(project, set())

    assert rich.digest != normalized_first.digest
    assert rich_changed.digest != normalized_first.digest
    assert rich_changed.digest != rich.digest
    assert normalized_second == normalized_first


def test_generated_publication_timestamps_are_in_run_drift_not_cross_run_context(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Derived-file publish times must not disable reuse on an identical rerun."""

    project = tmp_path / "project"
    mutants = project / "mutants"
    staged_module = mutants / "src" / "module.py"
    staged_module.parent.mkdir(parents=True)
    staged_module.write_text("VALUE = 1\n", encoding="utf-8")
    monkeypatch.setattr(stats_module.importlib.metadata, "distributions", list)
    monkeypatch.setattr(stats_module.sys, "path", [str(mutants), str(project)])

    stable_before = _installed_distribution_basis(project, set())
    drift_before = build_staging_context_evidence(project)
    original = staged_module.stat()
    os.utime(
        staged_module,
        ns=(original.st_atime_ns, original.st_mtime_ns + 2_000_000_000),
    )
    stable_after = _installed_distribution_basis(project, set())
    drift_after = build_staging_context_evidence(project)

    assert stable_before.reuse_safe is True
    assert stable_after == stable_before
    assert drift_after.complete is True
    assert drift_after.digest != drift_before.digest


def test_project_file_timestamp_is_part_of_cross_run_context(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """User-controlled file metadata remains an observable test input."""

    project, config = _project(tmp_path, monkeypatch)
    monkeypatch.setattr(
        stats_module,
        "_installed_distribution_basis",
        lambda _root, _seen, **_kwargs: _DependencyBasis("stable-environment", True),
    )
    source = project / "src" / "target.py"
    before = build_stats_context_fingerprint(config)
    original = source.stat()
    os.utime(source, ns=(original.st_atime_ns, original.st_mtime_ns + 2_000_000_000))

    assert build_stats_context_fingerprint(config) != before


@pytest.mark.skipif(os.name != "nt", reason="Windows uv hardlink-count regression")
def test_export_live_basis_stays_stable_during_project_hardlink_churn(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The export's immediate double snapshot ignores a new external alias."""

    project, config = _project(tmp_path, monkeypatch)
    source = project / "src" / "target.py"
    external_alias = tmp_path / "other-environment-target.py"
    os.link(source, external_alias)
    monkeypatch.setattr(
        stats_module,
        "_installed_distribution_basis",
        lambda _root, _seen, **_kwargs: _DependencyBasis("stable-environment", True),
    )
    real_build = stats_module.build_run_basis_evidence
    real_fstat = os.fstat
    link_count_delta = 0
    captured: list[RunBasisEvidence] = []

    def fstat_with_external_link_churn(fd: int) -> os.stat_result:
        current = real_fstat(fd)
        return cast(
            "os.stat_result",
            _StatWithAdjustedLinkCount(current, link_count_delta),
        )

    def capture_then_add_alias(
        active_config: MutmutConfig,
        project_root: Path | None = None,
        *,
        excluded_paths: tuple[Path, ...] = (),
    ) -> RunBasisEvidence:
        nonlocal link_count_delta
        evidence = real_build(
            active_config,
            project_root,
            excluded_paths=excluded_paths,
        )
        captured.append(evidence)
        if len(captured) == 1:
            link_count_delta = 1
        return evidence

    monkeypatch.setattr(stats_module.os, "fstat", fstat_with_external_link_churn)
    monkeypatch.setattr(cli_module, "build_run_basis_evidence", capture_then_add_alias)

    digest = cli_module._stable_live_basis(config, project / ".mutmut-cache" / "cache.db")
    after_alias = real_build(config)
    external_alias.write_text("VALUE = 2\n", encoding="utf-8")
    after_shared_write = real_build(config)

    assert len(captured) == 2
    assert captured[0] == captured[1]
    assert after_alias.digest == digest
    assert after_shared_write.digest != digest


@pytest.mark.skipif(os.name != "nt", reason="NTFS directory allocation regression")
def test_excluded_cache_creation_does_not_leak_through_project_directory_size(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project, config = _project(tmp_path, monkeypatch)
    (project / "mutants").mkdir()
    (project / "pyproject.toml").write_text("[tool.mutmut]\n", encoding="utf-8")
    monkeypatch.setattr(
        stats_module,
        "_installed_distribution_basis",
        lambda _root, _seen, **_kwargs: _DependencyBasis("stable-environment", True),
    )
    before_size = project.stat().st_size
    before = build_stats_context_fingerprint(config)

    cache = project / ".mutmut-cache"
    cache.mkdir()
    (cache / "mutmut-cache.db").write_bytes(b"tool state")
    after_size = project.stat().st_size
    after = build_stats_context_fingerprint(config)

    assert after_size != before_size  # the original indirect invalidator
    assert after == before


def test_staging_evidence_binds_observed_directory_topology_metadata_and_file_mode(
    tmp_path: Path,
) -> None:
    mutants = tmp_path / "mutants"
    mutants.mkdir()
    fixture = mutants / "fixture.txt"
    fixture.write_text("stable\n", encoding="utf-8")
    before = build_staging_context_evidence(tmp_path)

    empty = mutants / "runtime-empty"
    empty.mkdir()
    with_empty = build_staging_context_evidence(tmp_path)
    empty.rmdir()
    restored = build_staging_context_evidence(tmp_path)
    parent_stat = mutants.stat()
    os.utime(
        mutants,
        ns=(parent_stat.st_atime_ns, parent_stat.st_mtime_ns + 2_000_000_000),
    )
    parent_metadata_changed = build_staging_context_evidence(tmp_path)
    fixture.chmod(0o444)
    read_only = build_staging_context_evidence(tmp_path)
    fixture.chmod(0o666)

    assert with_empty.digest != before.digest
    # A create/remove cycle entirely between two polling snapshots can be
    # indistinguishable on NTFS.  Test the contracts that are observable:
    # present topology, an explicit parent metadata change, and file mode.
    assert parent_metadata_changed.digest != restored.digest
    assert read_only.digest != parent_metadata_changed.digest


@pytest.mark.skipif(os.name != "nt", reason="Windows strict hardlink-count regression")
def test_strict_staging_evidence_keeps_binding_file_link_count(tmp_path: Path) -> None:
    mutants = tmp_path / "mutants"
    mutants.mkdir()
    staged = mutants / "module.py"
    staged.write_text("VALUE = 1\n", encoding="utf-8")
    real_fstat = os.fstat
    link_count_delta = 0

    def fstat_with_external_link_churn(fd: int) -> os.stat_result:
        current = real_fstat(fd)
        return cast(
            "os.stat_result",
            _StatWithAdjustedLinkCount(current, link_count_delta),
        )

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(stats_module.os, "fstat", fstat_with_external_link_churn)
        before = build_staging_context_evidence(tmp_path)
        link_count_delta = 1
        with_external_alias = build_staging_context_evidence(tmp_path)

        assert before.complete is True
        assert with_external_alias.complete is True
        assert with_external_alias.digest != before.digest


def test_staging_evidence_binds_every_remaining_staging_file(tmp_path: Path) -> None:
    mutants = tmp_path / "mutants"
    fixtures = mutants / "tests"
    fixtures.mkdir(parents=True)
    fixture = mutants / "runtime.json"
    stats_file = mutants / "mutmut-stats.json"
    nested_meta = fixtures / "runtime.meta"
    nested_stats = fixtures / "mutmut-stats.json"
    generated_meta = mutants / "module.py.meta"
    fixture.write_text('{"value": 1}\n', encoding="utf-8")
    stats_file.write_text('{"context": "first"}\n', encoding="utf-8")
    nested_meta.write_text("fixture one\n", encoding="utf-8")
    nested_stats.write_text('{"fixture": 1}\n', encoding="utf-8")
    generated_meta.write_text('{"generated_hash": "first"}\n', encoding="utf-8")

    before = build_staging_context_evidence(tmp_path)
    stats_file.write_text('{"context": "second"}\n', encoding="utf-8")
    mutable_output_changed = build_staging_context_evidence(tmp_path)
    nested_meta.write_text("fixture two\n", encoding="utf-8")
    nested_meta_changed = build_staging_context_evidence(tmp_path)
    nested_stats.write_text('{"fixture": 2}\n', encoding="utf-8")
    nested_stats_changed = build_staging_context_evidence(tmp_path)
    generated_meta.write_text('{"generated_hash": "second"}\n', encoding="utf-8")
    generated_meta_changed = build_staging_context_evidence(tmp_path)
    fixture.write_text('{"value": 2}\n', encoding="utf-8")
    fixture_changed = build_staging_context_evidence(tmp_path)

    assert before.complete is True
    assert mutable_output_changed.complete is True
    assert mutable_output_changed.digest != before.digest
    assert nested_meta_changed.complete is True
    assert nested_meta_changed.digest != before.digest
    assert nested_stats_changed.complete is True
    assert nested_stats_changed.digest != nested_meta_changed.digest
    assert generated_meta_changed.complete is True
    assert generated_meta_changed.digest != nested_stats_changed.digest
    assert fixture_changed.complete is True
    assert fixture_changed.digest != generated_meta_changed.digest


@pytest.mark.parametrize(
    "name",
    [
        ".coverage.mutmut",
        "_mutmut_phase_guard.py",
        "_mutmut_stats_plugin.py",
        "mutmut-cicd-stats.json",
        "mutmut-stats.json",
        ".mutmut_pytest_executed_deadbeef.sentinel",
        "mutmut_out_deadbeef.log",
        "mutmut_tests_deadbeef.txt",
    ],
)
def test_staging_output_names_are_bound_at_root_and_nested_paths(
    tmp_path: Path,
    name: str,
) -> None:
    mutants = tmp_path / "mutants"
    nested = mutants / "tests"
    nested.mkdir(parents=True)
    root_output = mutants / name
    nested_fixture = nested / name
    root_output.write_text("root one\n", encoding="utf-8")
    nested_fixture.write_text("nested one\n", encoding="utf-8")

    before = build_staging_context_evidence(tmp_path)
    root_output.write_text("root two\n", encoding="utf-8")
    root_changed = build_staging_context_evidence(tmp_path)
    nested_fixture.write_text("nested two\n", encoding="utf-8")
    nested_changed = build_staging_context_evidence(tmp_path)

    assert root_changed.complete is True
    assert root_changed.digest != before.digest
    assert nested_changed.complete is True
    assert nested_changed.digest != root_changed.digest


def test_resolved_generated_import_root_is_the_containment_authority(tmp_path: Path) -> None:
    project = tmp_path / "project"
    generated = project / "mutants"
    nested = generated / "src"
    unrelated = tmp_path / "dependency" / "mutants"
    nested.mkdir(parents=True)
    unrelated.mkdir(parents=True)

    assert stats_module._is_generated_import_root(generated.resolve(), generated) is True
    assert stats_module._is_generated_import_root(nested.resolve(), generated) is True
    assert stats_module._is_generated_import_root(unrelated.resolve(), generated) is False


@pytest.mark.skipif(os.name != "nt", reason="Windows Junction alias regression")
def test_generated_mutants_junction_alias_binds_unexpected_legacy_stats_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "real-project"
    mutants = project / "mutants"
    mutants.mkdir(parents=True)
    alias = tmp_path / "project-alias"
    cmd_executable = Path(os.environ.get("COMSPEC", r"C:\Windows\System32\cmd.exe"))
    created = subprocess.run(  # noqa: S603 - cmd builtin creates the test Junction
        [cmd_executable, "/d", "/u", "/c", "mklink", "/J", str(alias), str(project)],
        capture_output=True,
        encoding="utf-16-le",
        errors="replace",
        check=False,
    )
    if created.returncode != 0:
        pytest.skip(f"could not create Junction: {created.stdout}{created.stderr}")

    try:
        stats_file = mutants / "mutmut-stats.json"
        stats_file.write_text('{"context_fingerprint":"first"}\n', encoding="utf-8")
        monkeypatch.setattr(stats_module.importlib.metadata, "distributions", list)
        monkeypatch.setattr(
            stats_module.sys,
            "path",
            [str(alias / "mutants"), str(alias)],
        )

        before = _installed_distribution_basis(project, set())
        stats_file.write_text('{"context_fingerprint":"second"}\n', encoding="utf-8")
        after = _installed_distribution_basis(project, set())
    finally:
        if alias.exists() and alias.is_junction():
            alias.rmdir()

    assert before.reuse_safe is True
    assert after.reuse_safe is True
    assert after.digest != before.digest


def test_stats_context_is_stable_after_publishing_stats_into_generated_sys_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    source = project / "src"
    mutants = project / "mutants"
    source.mkdir(parents=True)
    mutants.mkdir()
    (source / "demo.py").write_text("VALUE = 1\n", encoding="utf-8")
    cache = project / ".mutmut-cache"
    cache.mkdir()
    stats_file = cache / "mutmut-stats.json"
    stats_file.write_text('{"context_fingerprint":"first"}\n', encoding="utf-8")
    monkeypatch.setattr(stats_module.importlib.metadata, "distributions", list)
    monkeypatch.setattr(stats_module.sys, "path", [str(mutants), str(project)])
    config = MutmutConfig(paths_to_mutate=["src"])

    before = build_stats_context_fingerprint(config, project_root=project)
    stats_file.write_text('{"context_fingerprint":"second"}\n', encoding="utf-8")
    after = build_stats_context_fingerprint(config, project_root=project)

    assert not before.startswith("no-reuse:")
    assert after == before


def test_database_exclusions_apply_to_the_project_sys_path_walk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    source = project / "src"
    source.mkdir(parents=True)
    runtime_input = source / "demo.py"
    runtime_input.write_text("VALUE = 1\n", encoding="utf-8")
    database = project / "custom-mutmut.sqlite"
    database.write_bytes(b"database-before")
    monkeypatch.setattr(stats_module.importlib.metadata, "distributions", list)
    monkeypatch.setattr(stats_module.sys, "path", [str(project)])
    config = MutmutConfig(paths_to_mutate=["src"])

    before = build_stats_context_fingerprint(
        config,
        project_root=project,
        excluded_paths=(database,),
    )
    database.write_bytes(b"database-after-with-different-size")
    after_database_write = build_stats_context_fingerprint(
        config,
        project_root=project,
        excluded_paths=(database,),
    )
    runtime_input.write_text("VALUE = 2\n", encoding="utf-8")
    after_runtime_write = build_stats_context_fingerprint(
        config,
        project_root=project,
        excluded_paths=(database,),
    )

    assert after_database_write == before
    assert after_runtime_write != after_database_write


def test_explicit_external_tree_hashes_generic_named_children_that_are_staged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    dependency = tmp_path / "dependency"
    source = project / "src"
    runtime_hook = dependency / "build" / "runtime_hook.py"
    source.mkdir(parents=True)
    runtime_hook.parent.mkdir(parents=True)
    (source / "demo.py").write_text("VALUE = 1\n", encoding="utf-8")
    runtime_hook.write_text("VALUE = 1\n", encoding="utf-8")
    (project / "mutants").mkdir()
    monkeypatch.chdir(project)
    monkeypatch.setattr(stats_module.importlib.metadata, "distributions", list)
    monkeypatch.setattr(stats_module.sys, "path", [str(project)])
    config = MutmutConfig(paths_to_mutate=["src"], extra_paths=["../dependency"])

    before = build_stats_context_fingerprint(config, project_root=project)
    copy_also_copy_files(config)
    staged = project / "mutants" / "dependency" / "build" / "runtime_hook.py"
    assert staged.read_text(encoding="utf-8") == "VALUE = 1\n"

    runtime_hook.write_text("VALUE = 2\n", encoding="utf-8")
    after = build_stats_context_fingerprint(config, project_root=project)

    assert not before.startswith("no-reuse:")
    assert not after.startswith("no-reuse:")
    assert after != before


def test_only_the_project_generated_mutants_tree_is_derived(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    project_mutants = project / "mutants"
    unrelated_mutants = tmp_path / "dependency" / "mutants"
    project_mutants.mkdir(parents=True)
    unrelated_mutants.mkdir(parents=True)
    module = unrelated_mutants / "dependency.py"
    module.write_text("VALUE = 1\n", encoding="utf-8")
    monkeypatch.setattr(stats_module.importlib.metadata, "distributions", list)
    monkeypatch.setattr(
        stats_module.sys,
        "path",
        [str(project_mutants), str(unrelated_mutants), str(project)],
    )

    before = _installed_distribution_basis(project, set())
    module.write_text("VALUE = 2\n", encoding="utf-8")
    after = _installed_distribution_basis(project, set())

    assert before.reuse_safe is True
    assert after.reuse_safe is True
    assert after.digest != before.digest


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
    expected = sorted(
        [environment.resolve(), project.resolve()],
        key=lambda item: (len(item.parts), os.path.normcase(str(item))),
    )
    assert walked == expected


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


def test_root_excluded_project_directory_on_sys_path_is_hashed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    import_root = project / "build"
    import_root.mkdir(parents=True)
    module = import_root / "runtime_hook.py"
    module.write_text("VALUE = 1\n", encoding="utf-8")
    monkeypatch.setattr(stats_module.importlib.metadata, "distributions", list)
    monkeypatch.setattr(stats_module.sys, "path", [str(project), str(import_root)])

    before = _installed_distribution_basis(project, set())
    module.write_text("VALUE = 2\n", encoding="utf-8")
    after = _installed_distribution_basis(project, set())

    assert before.reuse_safe is True
    assert after.reuse_safe is True
    assert after.digest != before.digest


def test_project_root_sys_path_hashes_importable_root_excluded_namespace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    importable_build = project / "build"
    importable_build.mkdir(parents=True)
    module = importable_build / "runtime_helper.py"
    module.write_text("VALUE = 1\n", encoding="utf-8")
    monkeypatch.setattr(stats_module.importlib.metadata, "distributions", list)
    monkeypatch.setattr(stats_module.sys, "path", [str(project)])

    before = _installed_distribution_basis(project, set())
    module.write_text("VALUE = 222\n", encoding="utf-8")
    after = _installed_distribution_basis(project, set())

    assert before.reuse_safe is True
    assert after.reuse_safe is True
    assert after.digest != before.digest


def test_project_root_importable_build_drift_is_classified_as_core(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    source = project / "src"
    importable_build = project / "build"
    source.mkdir(parents=True)
    importable_build.mkdir()
    (source / "target.py").write_text("VALUE = 1\n", encoding="utf-8")
    module = importable_build / "runtime_helper.py"
    module.write_text("VALUE = 1\n", encoding="utf-8")
    monkeypatch.setattr(stats_module.importlib.metadata, "distributions", list)
    monkeypatch.setattr(stats_module.sys, "path", [str(project)])
    config = MutmutConfig(paths_to_mutate=["src"])

    before = build_run_basis_evidence(config, project_root=project)
    module.write_text("VALUE = 2\n", encoding="utf-8")
    after = build_run_basis_evidence(config, project_root=project)

    assert before.core_complete is True
    assert after.core_complete is True
    assert after.core_digest != before.core_digest


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
