"""Integration contracts: the gitignore boundary governs staging and basis.

MBR-2026-09-14-01: a correctly git-ignored ``tests/test_project/.lake`` tree
was enumerated, copied and hashed several times per run.  These tests pin the
fixed contract for the automatic staging mirror, configured inputs, the
staging copy phase and the run-basis fingerprint, including the dotenv
carve-out and the migration of pre-fix staged leftovers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from mutmut_win.config import MutmutConfig
from mutmut_win.file_setup import (
    _iter_automatic_staging_inputs,
    _iter_configured_staging_inputs,
    copy_also_copy_files,
)
from mutmut_win.stats import build_run_basis_evidence

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def _make_project(
    root: Path,
    *,
    gitignore: str = ".lake/\n",
    with_lake: bool = True,
    lake_files: int = 3,
) -> None:
    (root / ".gitignore").write_text(gitignore, encoding="utf-8")
    (root / "src").mkdir(parents=True, exist_ok=True)
    (root / "src" / "app.py").write_text("X = 1\n", encoding="utf-8")
    (root / "tests" / "unit").mkdir(parents=True, exist_ok=True)
    (root / "tests" / "unit" / "test_a.py").write_text(
        "def test_a() -> None:\n    assert True\n",
        encoding="utf-8",
    )
    (root / "pyproject.toml").write_text(
        "[project]\nname = 'fixture'\nversion = '0'\n",
        encoding="utf-8",
    )
    if with_lake:
        lake = root / "tests" / "test_project" / ".lake" / "build"
        lake.mkdir(parents=True, exist_ok=True)
        for index in range(lake_files):
            (lake / f"blob_{index}.bin").write_bytes(b"\0" * 16)


class TestAutomaticStagingInputs:
    def test_gitignored_subtree_is_not_planned(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        project = tmp_path / "project"
        project.mkdir()
        _make_project(project)
        monkeypatch.chdir(project)
        planned = {str(source) for source, _target in _iter_automatic_staging_inputs(frozenset())}
        assert not any(".lake" in name for name in planned)
        assert any("test_a.py" in name for name in planned)

    def test_project_without_gitignore_plans_everything(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        project = tmp_path / "project"
        project.mkdir()
        _make_project(project, gitignore="")
        (project / ".gitignore").unlink()
        monkeypatch.chdir(project)
        planned = {str(source) for source, _target in _iter_automatic_staging_inputs(frozenset())}
        assert any(".lake" in name for name in planned)


class TestConfiguredStagingInputs:
    def test_ignored_subtree_inside_configured_tree_is_pruned(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        project = tmp_path / "project"
        project.mkdir()
        _make_project(project)
        monkeypatch.chdir(project)
        config = MutmutConfig(also_copy=["tests/"])
        planned = {
            str(source) for source, _target in _iter_configured_staging_inputs(config, frozenset())
        }
        assert any("test_a.py" in name for name in planned)
        assert not any(".lake" in name for name in planned)

    def test_explicit_entry_pointing_at_ignored_tree_is_force_included(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        project = tmp_path / "project"
        project.mkdir()
        _make_project(project)
        monkeypatch.chdir(project)
        config = MutmutConfig(also_copy=["tests/test_project/.lake"])
        planned = {
            str(source) for source, _target in _iter_configured_staging_inputs(config, frozenset())
        }
        assert any(".lake" in name and "blob_0" in name for name in planned)


class TestCopyAlsoCopyFiles:
    def test_ignored_tree_is_not_copied(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        project = tmp_path / "project"
        project.mkdir()
        _make_project(project)
        (project / "mutants").mkdir()
        monkeypatch.chdir(project)
        # Mirror the effective post-load config: _apply_default_also_copy
        # runs in the pyproject loading pipeline, not on the bare model.
        config = MutmutConfig(also_copy=["tests/", "pyproject.toml"])
        copy_also_copy_files(config)
        assert (project / "mutants" / "tests" / "unit" / "test_a.py").exists()
        assert not (project / "mutants" / "tests" / "test_project").exists()

    def test_explicit_ignored_entry_is_copied(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        project = tmp_path / "project"
        project.mkdir()
        _make_project(project)
        (project / "mutants").mkdir()
        monkeypatch.chdir(project)
        config = MutmutConfig(also_copy=["tests/test_project/.lake"])
        copy_also_copy_files(config)
        staged_lake = project / "mutants" / "tests" / "test_project" / ".lake" / "build"
        assert (staged_lake / "blob_0.bin").exists()

    def test_prefix_staged_ignored_tree_is_removed_by_sync(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        project = tmp_path / "project"
        project.mkdir()
        _make_project(project, gitignore="")  # pre-fix: nothing ignored yet
        (project / "mutants").mkdir()
        monkeypatch.chdir(project)
        config = MutmutConfig(also_copy=["tests/"])
        copy_also_copy_files(config)
        staged_blob = (
            project / "mutants" / "tests" / "test_project" / ".lake" / "build" / "blob_0.bin"
        )
        assert staged_blob.exists()
        # Now the project learns to ignore .lake — the next sync must purge
        # the staged leftovers even though their live sources still exist.
        (project / ".gitignore").write_text(".lake/\n", encoding="utf-8")
        copy_also_copy_files(config)
        assert not staged_blob.exists()


class TestRunBasisEvidence:
    def _config(self) -> MutmutConfig:
        return MutmutConfig(
            paths_to_mutate=["src/app.py"],
            tests_dir=["tests/"],
        )

    def test_ignored_tree_does_not_change_the_digest(self, tmp_path: Path) -> None:
        project = tmp_path / "project"
        project.mkdir()
        _make_project(project)
        before = build_run_basis_evidence(self._config(), project)
        blob = project / "tests" / "test_project" / ".lake" / "build" / "blob_0.bin"
        blob.write_bytes(b"\xff" * 32)
        after = build_run_basis_evidence(self._config(), project)
        assert before.digest == after.digest

    def test_gitignored_dotenv_still_binds_the_basis(self, tmp_path: Path) -> None:
        project = tmp_path / "project"
        project.mkdir()
        _make_project(project, gitignore=".lake/\n.env\n")
        before = build_run_basis_evidence(self._config(), project)
        (project / ".env").write_text("SECRET=1\n", encoding="utf-8")
        after = build_run_basis_evidence(self._config(), project)
        assert before.digest != after.digest

    def test_gitignore_file_itself_binds_the_basis(self, tmp_path: Path) -> None:
        project = tmp_path / "project"
        project.mkdir()
        _make_project(project)
        before = build_run_basis_evidence(self._config(), project)
        (project / ".gitignore").write_text(".lake/\nbuild2/\n", encoding="utf-8")
        after = build_run_basis_evidence(self._config(), project)
        assert before.digest != after.digest
