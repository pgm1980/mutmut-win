"""Runtime-prefix classification of import roots (AR-10 / M-006, PERF-002).

``_import_root_boundary`` may only lift the project gitignore boundary for
runtime prefixes that are STRICTLY INSIDE the project (a project-internal
environment such as ``.venv`` or a venv with a custom folder name).  Prefixes
equal to, above (ancestors of), or outside the project must keep the regular
project boundary: a project located below an interpreter prefix is an
ordinary project import tree, and hashing it without the project gitignore
turns correctly ignored regular artifacts into new fingerprint drift.
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

from mutmut_win import stats as stats_module

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def _setup_project(tmp_path: Path, prefix_layout: str) -> tuple[Path, Path, Path | None]:
    """Create a project plus the interpreter-prefix location under test.

    ``embedded`` nests the project inside an interpreter directory (project
    BELOW the prefix); ``external`` keeps the prefix outside the project.
    """
    if prefix_layout == "embedded":
        project = tmp_path / "python314" / "project"
    else:
        project = tmp_path / "project"
    src = project / "src"
    (src / "pkg").mkdir(parents=True)
    (src / "pkg" / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
    (project / ".gitignore").write_text("*.log\n", encoding="utf-8")
    prefix = project.parent if prefix_layout == "embedded" else tmp_path / "external-python314"
    return project, src, prefix


def _patch_prefixes(monkeypatch: pytest.MonkeyPatch, prefix: Path) -> None:
    for attr in ("prefix", "exec_prefix", "base_prefix"):
        monkeypatch.setattr(stats_module.sys, attr, str(prefix))


def _hash_imports(project: Path, sys_path: list[str], monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setattr(stats_module.sys, "path", sys_path)
    hasher = hashlib.sha256()
    seen: set[Path] = set()
    covered = (
        (
            project.resolve(strict=True),
            stats_module._CONTEXT_ROOT_SKIP_DIRS,
        ),
    )
    stats_module._hash_effective_import_paths(hasher, project, seen, covered, set())
    return hasher.hexdigest()


class TestPrefixClassification:
    """Helper-level boundary decisions for the four prefix relations."""

    def test_prefix_equal_to_project_keeps_boundary(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        project, src, _ = _setup_project(tmp_path, "plain")
        boundary = stats_module.GitignoreBoundary.load(project)

        _patch_prefixes(monkeypatch, project)
        answer = stats_module._import_root_boundary(
            boundary, project.resolve(strict=True), src.resolve(strict=False)
        )

        assert answer is not None
        assert answer.excludes_file("debug.log") is True

    def test_prefix_ancestor_of_project_keeps_boundary(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """AR-10: a project below the interpreter prefix is no runtime tree."""
        project, src, prefix = _setup_project(tmp_path, "embedded")
        boundary = stats_module.GitignoreBoundary.load(project)

        _patch_prefixes(monkeypatch, prefix)
        answer = stats_module._import_root_boundary(
            boundary, project.resolve(strict=True), src.resolve(strict=False)
        )

        assert answer is not None
        assert answer.excludes_file("debug.log") is True

    def test_external_prefix_keeps_boundary(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        project, src, prefix = _setup_project(tmp_path, "plain")
        boundary = stats_module.GitignoreBoundary.load(project)

        _patch_prefixes(monkeypatch, prefix)
        answer = stats_module._import_root_boundary(
            boundary, project.resolve(strict=True), src.resolve(strict=False)
        )

        assert answer is not None
        assert answer.excludes_file("debug.log") is True

    def test_strictly_embedded_prefix_has_no_boundary(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A custom-named environment inside the project stays fully bound."""
        project, _, _ = _setup_project(tmp_path, "plain")
        site = project / "runtime-env" / "Lib" / "site-packages"
        site.mkdir(parents=True)
        boundary = stats_module.GitignoreBoundary.load(project)

        _patch_prefixes(monkeypatch, project / "runtime-env")
        answer = stats_module._import_root_boundary(
            boundary, project.resolve(strict=True), site.resolve(strict=False)
        )

        assert answer is None


class TestIgnoredArtifactFingerprintDrift:
    """An ignored regular artifact must not drift the effective import digest."""

    def test_ignored_artifact_under_ancestor_prefix_does_not_drift(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """AR-10: project below the interpreter prefix keeps its ignore limit."""
        project, src, prefix = _setup_project(tmp_path, "embedded")
        artifact = src / "debug.log"
        artifact.write_text("ignored payload v1\n", encoding="utf-8")

        _patch_prefixes(monkeypatch, prefix)
        before = _hash_imports(project, [str(src)], monkeypatch)
        artifact.write_text("ignored payload v2\n", encoding="utf-8")
        after = _hash_imports(project, [str(src)], monkeypatch)

        assert before == after

    def test_ignored_artifact_under_external_prefix_does_not_drift(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        project, src, prefix = _setup_project(tmp_path, "plain")
        artifact = src / "debug.log"
        artifact.write_text("ignored payload v1\n", encoding="utf-8")

        _patch_prefixes(monkeypatch, prefix)
        before = _hash_imports(project, [str(src)], monkeypatch)
        artifact.write_text("ignored payload v2\n", encoding="utf-8")
        after = _hash_imports(project, [str(src)], monkeypatch)

        assert before == after

    def test_embedded_env_content_still_binds_under_ancestor_prefix(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Guard: the stricter rule must not weaken genuinely embedded envs.

        Even while an outer interpreter prefix also contains the project, the
        ACTIVE environment strictly inside the project keeps its runtime
        classification: its content changes keep binding the digest.
        """
        project, _, _outer_prefix = _setup_project(tmp_path, "embedded")
        (project / ".gitignore").write_text("*.log\nruntime-env/\n", encoding="utf-8")
        site = project / "runtime-env" / "Lib" / "site-packages"
        site.mkdir(parents=True)
        plugin = site / "orphan_plugin.py"
        plugin.write_text("VALUE = 1\n", encoding="utf-8")

        _patch_prefixes(monkeypatch, project / "runtime-env")
        before = _hash_imports(project, [str(site)], monkeypatch)
        plugin.write_text("VALUE = 2\n", encoding="utf-8")
        after = _hash_imports(project, [str(site)], monkeypatch)

        assert after != before
