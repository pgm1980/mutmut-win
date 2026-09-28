"""Integration contracts: the gitignore boundary governs staging and basis.

MBR-2026-09-14-01: a correctly git-ignored ``tests/test_project/.lake`` tree
was enumerated, copied and hashed several times per run.  These tests pin the
fixed contract for the automatic staging mirror, configured inputs, the
staging copy phase and the run-basis fingerprint, including the dotenv
carve-out and the migration of pre-fix staged leftovers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from mutmut_win import file_setup
from mutmut_win.config import MutmutConfig
from mutmut_win.exceptions import StagingNamespaceCollisionError
from mutmut_win.file_setup import (
    _iter_automatic_staging_inputs,
    _iter_configured_staging_inputs,
    copy_also_copy_files,
    copy_src_dir,
    validate_staging_namespace,
)
from mutmut_win.gitignore_boundary import GitignoreBoundary
from mutmut_win.stats import build_run_basis_evidence

if TYPE_CHECKING:
    from pathlib import Path


def _make_project(
    root: Path,
    *,
    gitignore: str = ".lake/\n",
    with_lake: bool = True,
    lake_files: int = 3,
    lake_gitignore: str | None = None,
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
        if lake_gitignore is not None:
            (lake.parent / ".gitignore").write_text(lake_gitignore, encoding="utf-8")
            (lake.parent / "keep.txt").write_text("keep\n", encoding="utf-8")


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

    def test_forced_entry_still_respects_its_own_nested_gitignore(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``git add -f`` immunises against ANCESTRAL rules, not against own ones.

        The forced entry restarts the level list, so an ignore file *inside*
        the entry keeps governing it.  Every other fixture here uses a single
        unanchored root pattern, which matches under a truncated prefix just
        as well as under the correct one — so a wrong prefix or a wrongly
        reset level list stays invisible.  The anchored ``/build/`` below only
        matches when the entry's own ignore file is resolved relative to the
        entry itself.
        """
        project = tmp_path / "project"
        project.mkdir()
        _make_project(project, lake_gitignore="/build/\n")
        monkeypatch.chdir(project)
        config = MutmutConfig(also_copy=["tests/test_project/.lake"])
        planned = {
            str(source) for source, _target in _iter_configured_staging_inputs(config, frozenset())
        }
        # The entry escapes the ancestral ".lake/" rule ...
        assert any("keep.txt" in name for name in planned)
        # ... but its own anchored rule still prunes the build subtree.
        assert not any("blob_" in name for name in planned)


class TestIgnoredMutationRoot:
    """M-032: explicitly configured, git-ignored mutation roots are staged.

    The mutation search force-includes ``paths_to_mutate`` entries (``git add
    -f`` semantics via ``descend_forced``); the automatic mirror must walk the
    same surface through forced roots so mutation targets keep their non-.py
    resources in executable staging.
    """

    def _project(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        *,
        gitignore: str = "generated/\n",
    ) -> Path:
        project = tmp_path / "project"
        project.mkdir()
        (project / ".gitignore").write_text(gitignore, encoding="utf-8")
        (project / "src").mkdir()
        (project / "src" / "app.py").write_text("X = 1\n", encoding="utf-8")
        generated = project / "generated"
        generated.mkdir()
        (generated / "mod.py").write_text("Y = 2\n", encoding="utf-8")
        (generated / "data.json").write_text('{"value": 1}\n', encoding="utf-8")
        monkeypatch.chdir(project)
        return project

    def _forced_roots(self, project: Path, config: MutmutConfig) -> list[tuple[Path, object]]:
        boundary = GitignoreBoundary.load(project)
        return file_setup._forced_mutation_roots(config, boundary, project)

    def test_forced_root_resources_are_copied(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        project = self._project(tmp_path, monkeypatch)
        copy_src_dir(MutmutConfig(paths_to_mutate=["src", "generated"]))
        assert (project / "mutants" / "generated" / "mod.py").is_file()
        # The non-.py resource is the regression: the mutated module itself
        # appeared via the generator, its data fixture never did.
        assert (project / "mutants" / "generated" / "data.json").is_file()

    def test_forced_root_is_planned_by_the_namespace_preflight(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        project = self._project(tmp_path, monkeypatch)
        config = MutmutConfig(paths_to_mutate=["src", "generated"])
        planned = {
            str(source)
            for source, _target in _iter_automatic_staging_inputs(
                frozenset(), forced_roots=self._forced_roots(project, config)
            )
        }
        assert any("generated" in name and "data.json" in name for name in planned)
        validate_staging_namespace(config)  # the clean tree must not collide

    def test_preflight_and_copy_see_the_same_surface(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Q-14 consistency: planned inputs equal materialized mirror files."""
        project = self._project(tmp_path, monkeypatch)
        config = MutmutConfig(paths_to_mutate=["src", "generated"])
        planned = {
            file_setup._staging_key(target)
            for source, target in _iter_automatic_staging_inputs(
                frozenset(), forced_roots=self._forced_roots(project, config)
            )
            if source.is_file()
        }
        copy_src_dir(config)
        materialized = {
            file_setup._staging_key(staged.relative_to(project / "mutants"))
            for staged in (project / "mutants").rglob("*")
            if staged.is_file()
        }
        assert planned
        assert planned == materialized

    def test_forced_root_still_respects_its_own_gitignore(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        project = self._project(tmp_path, monkeypatch)
        cache = project / "generated" / "cache"
        cache.mkdir()
        (cache / "x.txt").write_text("cached\n", encoding="utf-8")
        (project / "generated" / ".gitignore").write_text("cache/\n", encoding="utf-8")
        copy_src_dir(MutmutConfig(paths_to_mutate=["src", "generated"]))
        assert (project / "mutants" / "generated" / "mod.py").is_file()
        assert not (project / "mutants" / "generated" / "cache").exists()

    def test_unconfigured_ignored_tree_stays_unstaged(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        project = self._project(tmp_path, monkeypatch, gitignore="generated/\nother/\n")
        other = project / "other"
        other.mkdir()
        (other / "keep.txt").write_text("other\n", encoding="utf-8")
        copy_src_dir(MutmutConfig(paths_to_mutate=["src", "generated"]))
        assert (project / "mutants" / "generated" / "data.json").is_file()
        assert not (project / "mutants" / "other").exists()

    def test_ignored_ancestor_is_forced_while_neighbour_stays_unstaged(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        project = self._project(tmp_path, monkeypatch, gitignore="build/\n")
        build_gen = project / "build" / "gen"
        build_gen.mkdir(parents=True)
        (build_gen / "g.py").write_text("G = 1\n", encoding="utf-8")
        neighbour = project / "build" / "other"
        neighbour.mkdir()
        (neighbour / "o.py").write_text("O = 1\n", encoding="utf-8")
        copy_src_dir(MutmutConfig(paths_to_mutate=["src", "build/gen"]))
        assert (project / "mutants" / "build" / "gen" / "g.py").is_file()
        assert not (project / "mutants" / "build" / "other").exists()

    def test_ignored_single_file_entry_is_staged(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        project = self._project(tmp_path, monkeypatch)
        (project / "generated" / "secret.py").write_text("S = 3\n", encoding="utf-8")
        copy_src_dir(MutmutConfig(paths_to_mutate=["src", "generated/secret.py"]))
        staged = project / "mutants" / "generated" / "secret.py"
        assert staged.is_file()
        assert staged.read_text(encoding="utf-8") == "S = 3\n"
        # The non-forced rest of the ignored tree stays out.
        assert not (project / "mutants" / "generated" / "data.json").exists()

    def test_live_sidecar_fixture_in_forced_root_is_rejected(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        project = self._project(tmp_path, monkeypatch)
        (project / "generated" / "mod.py.meta").write_text("{}", encoding="utf-8")
        config = MutmutConfig(paths_to_mutate=["src", "generated"])
        with pytest.raises(StagingNamespaceCollisionError):
            validate_staging_namespace(config)

    def test_ignored_mutation_root_bytes_bind_the_run_basis(self, tmp_path: Path) -> None:
        """stats.py hashes paths_to_mutate force-included (M-032 evidence)."""
        project = tmp_path / "project"
        project.mkdir()
        (project / ".gitignore").write_text("generated/\n", encoding="utf-8")
        (project / "src").mkdir()
        (project / "src" / "app.py").write_text("X = 1\n", encoding="utf-8")
        generated = project / "generated"
        generated.mkdir()
        (generated / "data.json").write_text('{"value": 1}\n', encoding="utf-8")
        config = MutmutConfig(
            paths_to_mutate=["src/app.py", "generated"],
            tests_dir=["tests/"],
        )
        before = build_run_basis_evidence(config, project)
        (generated / "data.json").write_text('{"value": 2}\n', encoding="utf-8")
        after = build_run_basis_evidence(config, project)
        assert before.digest != after.digest


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
