"""Import root gitignore policy and archive binding (M-006/M-007, issue #147).

M-006: project-internal venvs (.venv, venv, .tox, .nox, sys.prefix inside
the project) must NOT receive a gitignore boundary — their files are
execution inputs, not staged project trees, and must be fully bound.

M-007: ZIP archive subpaths on sys.path must bind the archive bytes, not
just the path text, to prevent silent reuse when the archive changes.

Tests call ``_hash_effective_import_paths`` directly with controlled inputs
to isolate the behaviour from ``_installed_distribution_basis`` (which has
many other ambient inputs).
"""

from __future__ import annotations

import hashlib
import zipfile
from typing import TYPE_CHECKING

import pytest

from mutmut_win import stats as stats_module

if TYPE_CHECKING:
    from pathlib import Path


def _make_venv(project: Path, name: str = ".venv") -> Path:
    """Create a minimal project-internal venv with site-packages."""
    site = project / name / "Lib" / "site-packages"
    site.mkdir(parents=True)
    return site


def _setup_isolated(project: Path, monkeypatch: pytest.MonkeyPatch, sys_path: list[str]) -> None:
    monkeypatch.chdir(project)
    monkeypatch.setattr(stats_module.sys, "path", sys_path)
    monkeypatch.setattr(
        "importlib.metadata.distributions",
        lambda **_kw: [],
    )


def _hash_imports(project: Path) -> tuple[bytes, bool]:
    """Call _hash_effective_import_paths with controlled inputs."""
    hasher = hashlib.sha256()
    seen: set[Path] = set()
    covered: tuple[tuple[Path, frozenset[str]], ...] = (
        (project.resolve(strict=True), stats_module._CONTEXT_ROOT_SKIP_DIRS),
    )
    excluded: set[Path] = set()
    reuse_safe = stats_module._hash_effective_import_paths(hasher, project, seen, covered, excluded)
    return hasher.hexdigest().encode(), reuse_safe


class TestProjectInternalVenvBound:
    """M-006: a git-ignored .venv's contents invalidate the basis."""

    @pytest.mark.parametrize("ignore_style", ["root", "inner-star"])
    def test_venv_content_changes_digest(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, ignore_style: str
    ) -> None:
        project = tmp_path / "project"
        project.mkdir()
        if ignore_style == "root":
            (project / ".gitignore").write_text(".venv/\n", encoding="utf-8")
        site = _make_venv(project)
        if ignore_style == "inner-star":
            (project / ".venv" / ".gitignore").write_text("*\n", encoding="utf-8")
        (site / "orphan_plugin.py").write_text("VALUE = 1\n", encoding="utf-8")
        (site / "orphan-hook.pth").write_text("import orphan_plugin\n", encoding="utf-8")

        _setup_isolated(project, monkeypatch, [str(project), str(site)])
        before, safe_before = _hash_imports(project)

        (site / "orphan_plugin.py").write_text("VALUE = 2\n", encoding="utf-8")
        after, _safe_after = _hash_imports(project)

        assert safe_before is True
        assert after != before

    def test_venv_pth_changes_digest(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        project = tmp_path / "project"
        project.mkdir()
        (project / ".gitignore").write_text(".venv/\n", encoding="utf-8")
        site = _make_venv(project)
        (site / "orphan_plugin.py").write_text("VALUE = 1\n", encoding="utf-8")
        (site / "orphan-hook.pth").write_text("import orphan_plugin\n", encoding="utf-8")

        _setup_isolated(project, monkeypatch, [str(project), str(site)])
        before, _ = _hash_imports(project)

        (site / "orphan-hook.pth").write_text("", encoding="utf-8")
        after, _ = _hash_imports(project)

        assert after != before

    def test_env_named_venv_with_sys_prefix(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A venv named 'env' (not in skip-dirs) via sys.prefix."""
        project = tmp_path / "project"
        project.mkdir()
        (project / ".gitignore").write_text("env/\n", encoding="utf-8")
        site = _make_venv(project, name="env")
        (site / "orphan_plugin.py").write_text("VALUE = 1\n", encoding="utf-8")

        venv_root = project / "env"
        _setup_isolated(project, monkeypatch, [str(project), str(site)])
        monkeypatch.setattr(stats_module.sys, "prefix", str(venv_root))
        before, _ = _hash_imports(project)

        (site / "orphan_plugin.py").write_text("VALUE = 2\n", encoding="utf-8")
        after, _ = _hash_imports(project)

        assert after != before

    def test_ignored_project_tree_still_pruned(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """MBR guard: ignored non-venv project trees stay pruned."""
        project = tmp_path / "project"
        project.mkdir()
        (project / ".gitignore").write_text(".lake/\n", encoding="utf-8")
        lake = project / ".lake" / "build"
        lake.mkdir(parents=True)
        (lake / "blob.bin").write_bytes(b"payload")

        _setup_isolated(project, monkeypatch, [str(project)])
        before, _ = _hash_imports(project)

        (lake / "blob.bin").write_bytes(b"changed")
        after, _ = _hash_imports(project)

        # .lake is an ignored project tree, not a runtime environment.
        assert before == after


class TestZipArchiveSubpath:
    """M-007: ZIP subpaths on sys.path bind the archive bytes."""

    def test_archive_change_invalidates_digest(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        project = tmp_path / "project"
        project.mkdir()
        archive = tmp_path / "external" / "plugins.zip"
        archive.parent.mkdir()

        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("vendor/plug.py", "VALUE = 1")

        vendor = archive / "vendor"
        _setup_isolated(project, monkeypatch, [str(project), str(vendor)])
        before, safe = _hash_imports(project)

        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("vendor/plug.py", "VALUE = 2")
        after, _ = _hash_imports(project)

        assert safe is True
        assert after != before

    def test_missing_entry_is_not_archive(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A truly absent sys.path entry is not misclassified as archive."""

        project = tmp_path / "project"
        project.mkdir()
        absent = tmp_path / "absent" / "sub"

        _setup_isolated(project, monkeypatch, [str(project), str(absent)])
        _, safe = _hash_imports(project)

        assert safe is True
        # Verify the absent path truly doesn't exist.
        assert not absent.exists()

    def test_regular_file_ancestor_bound(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A non-ZIP regular file as ancestor is bound (fail-closed)."""
        project = tmp_path / "project"
        project.mkdir()
        some_file = tmp_path / "external" / "data.bin"
        some_file.parent.mkdir()
        some_file.write_bytes(b"binary payload")

        subpath = some_file / "entry"
        _setup_isolated(project, monkeypatch, [str(project), str(subpath)])
        before, _ = _hash_imports(project)

        some_file.write_bytes(b"different payload")
        after, _ = _hash_imports(project)

        assert after != before
