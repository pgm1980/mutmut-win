"""Unit tests for mutmut_win.file_setup."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from mutmut_win.config import MutmutConfig
from mutmut_win.constants import configured_staging_relative_path
from mutmut_win.exceptions import StagingNamespaceCollisionError, UnsafeStagingError
from mutmut_win.file_setup import (
    copy_also_copy_files,
    copy_src_dir,
    create_mutants_for_file,
    get_mutant_name,
    setup_source_paths,
    strip_prefix,
    validate_staging_namespace,
    walk_all_files,
    walk_source_files,
    write_all_mutants_to_file,
)
from mutmut_win.orchestrator import MutationOrchestrator

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _config(**overrides: Any) -> MutmutConfig:
    defaults: dict[str, Any] = {"max_children": 1}
    defaults.update(overrides)
    return MutmutConfig(**defaults)


_SIMPLE_SOURCE = "def add(a, b):\n    return a + b\n"


@pytest.mark.skipif(os.name != "nt", reason="Windows anchored-path semantics")
@pytest.mark.parametrize("raw_path", [r"\live_probe", r"C:live_probe"])
def test_configured_staging_path_rejects_anchored_non_absolute_windows_path(
    tmp_path: Path,
    raw_path: str,
) -> None:
    assert configured_staging_relative_path(raw_path, project_root=tmp_path) is None


# ---------------------------------------------------------------------------
# walk_all_files
# ---------------------------------------------------------------------------


class TestWalkAllFiles:
    def test_walks_directory(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / "a.py").write_text("", encoding="utf-8")
        (tmp_path / "b.txt").write_text("", encoding="utf-8")

        cfg = _config(paths_to_mutate=["."])
        files = list(walk_all_files(cfg))
        filenames = [f for _, f in files]
        assert "a.py" in filenames
        assert "b.txt" in filenames

    def test_file_symlink_outside_project_is_not_walked(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        src = tmp_path / "src"
        src.mkdir()
        outside = tmp_path.parent / f"{tmp_path.name}-outside.py"
        outside.write_text("SECRET = True\n", encoding="utf-8")
        link = src / "leak.py"
        try:
            try:
                link.symlink_to(outside)
            except OSError as exc:
                pytest.skip(f"file symlinks unavailable on this host: {exc}")

            config = _config(paths_to_mutate=["src"])
            with pytest.warns(RuntimeWarning, match=r"Skipping linked or redirected.*leak\.py"):
                assert list(walk_source_files(config)) == []
            with pytest.warns(RuntimeWarning, match=r"Skipping linked or redirected.*leak\.py"):
                copy_src_dir(config)
            assert not (tmp_path / "mutants" / "src" / "leak.py").exists()
        finally:
            outside.unlink(missing_ok=True)

    def test_single_file_path(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / "single.py").write_text("", encoding="utf-8")

        cfg = _config(paths_to_mutate=["single.py"])
        results = list(walk_all_files(cfg))
        assert len(results) == 1
        assert results[0] == ("", "single.py")

    def test_nonexistent_path_yields_nothing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        cfg = _config(paths_to_mutate=["does_not_exist"])
        results = list(walk_all_files(cfg))
        assert results == []

    def test_nested_directories(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "nested.py").write_text("", encoding="utf-8")

        cfg = _config(paths_to_mutate=["."])
        files = list(walk_all_files(cfg))
        filenames = [f for _, f in files]
        assert "nested.py" in filenames


# ---------------------------------------------------------------------------
# walk_source_files
# ---------------------------------------------------------------------------


class TestWalkSourceFiles:
    def test_yields_only_py_files(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / "a.py").write_text("", encoding="utf-8")
        (tmp_path / "b.txt").write_text("", encoding="utf-8")
        (tmp_path / "c.pyi").write_text("", encoding="utf-8")

        cfg = _config(paths_to_mutate=["."])
        paths = list(walk_source_files(cfg))
        names = [p.name for p in paths]
        assert "a.py" in names
        assert "b.txt" not in names
        assert "c.pyi" not in names

    def test_returns_path_objects(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / "x.py").write_text("", encoding="utf-8")
        cfg = _config(paths_to_mutate=["."])
        paths = list(walk_source_files(cfg))
        assert all(isinstance(p, Path) for p in paths)

    def test_windows_uppercase_python_suffix_reaches_mutation_selection(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        source = tmp_path / "src" / "MODULE.PY"
        source.parent.mkdir()
        source.write_text(_SIMPLE_SOURCE, encoding="utf-8")
        cfg = _config(paths_to_mutate=["src/MODULE.PY"])

        assert list(walk_source_files(cfg)) == [Path("src/MODULE.PY")]
        assert cfg.should_ignore_for_mutation(Path("src/MODULE.PY")) is False
        result = MutationOrchestrator(
            cfg,
            runner=MagicMock(),
            executor=MagicMock(),
        ).dry_run()
        assert result.total_mutants > 0
        assert not (tmp_path / "mutants").exists()


# ---------------------------------------------------------------------------
# copy_src_dir
# ---------------------------------------------------------------------------


class TestCopySrcDir:
    def test_copies_files_to_mutants_dir(self, tmp_path: Path) -> None:
        # Use a relative path for paths_to_mutate so copy_src_dir mirrors
        # it under mutants/<relative_path>/.
        src = tmp_path / "src_pkg"
        src.mkdir()
        (src / "foo.py").write_text(_SIMPLE_SOURCE, encoding="utf-8")

        original_cwd = Path.cwd()
        os.chdir(tmp_path)
        try:
            cfg = _config(paths_to_mutate=["src_pkg"])
            copy_src_dir(cfg)
            mutants_dir = tmp_path / "mutants"
            assert any(p.name == "foo.py" for p in mutants_dir.rglob("*.py"))
        finally:
            os.chdir(original_cwd)

    def test_skips_unchanged_files_but_heals_tampered_mirrors(self, tmp_path: Path) -> None:
        # Issue #129 / 360°-B6a flipped the mirror rule for files WITHOUT a
        # .meta sibling: the staging copy must equal the source (mtime+size
        # fingerprint). An unchanged source is not re-copied; a tampered or
        # stale staging copy (the old test pinned it as untouchable) is
        # healed back to the source of truth.
        src = tmp_path / "src_pkg"
        src.mkdir()
        source_file = src / "bar.py"
        source_file.write_text(_SIMPLE_SOURCE, encoding="utf-8")

        original_cwd = Path.cwd()
        os.chdir(tmp_path)
        try:
            cfg = _config(paths_to_mutate=["src_pkg"])
            copy_src_dir(cfg)

            targets = list((tmp_path / "mutants").rglob("bar.py"))
            assert targets
            staged = targets[0]
            staged_mtime = staged.stat().st_mtime

            # Unchanged source → mirror untouched (mtime equality holds).
            copy_src_dir(cfg)
            assert staged.stat().st_mtime == staged_mtime

            # Tampered mirror (no .meta) → healed back to the source.
            staged.write_text("OVERWRITTEN", encoding="utf-8")
            copy_src_dir(cfg)
            assert staged.read_text(encoding="utf-8") == _SIMPLE_SOURCE
        finally:
            os.chdir(original_cwd)

    def test_refresh_replaces_hardlink_without_writing_its_other_name(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        source = tmp_path / "src" / "mod.py"
        source.parent.mkdir()
        source.write_text("VALUE = 'source'\n", encoding="utf-8")
        victim = tmp_path / "victim.py"
        victim.write_text("VALUE = 'victim'\n", encoding="utf-8")
        staged = tmp_path / "mutants" / "src" / "mod.py"
        staged.parent.mkdir(parents=True)
        os.link(victim, staged)

        copy_src_dir(_config(paths_to_mutate=["src"]))

        assert victim.read_text(encoding="utf-8") == "VALUE = 'victim'\n"
        assert staged.read_text(encoding="utf-8") == "VALUE = 'source'\n"

    def test_refresh_rejects_file_symlink_destination(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        source = tmp_path / "src" / "mod.py"
        source.parent.mkdir()
        source.write_text("VALUE = 'source'\n", encoding="utf-8")
        victim = tmp_path / "victim.py"
        victim.write_text("VALUE = 'victim'\n", encoding="utf-8")
        staged = tmp_path / "mutants" / "src" / "mod.py"
        staged.parent.mkdir(parents=True)
        try:
            staged.symlink_to(victim)
        except OSError as exc:
            pytest.skip(f"file symlinks unavailable on this host: {exc}")

        with pytest.raises(UnsafeStagingError, match="symlink/junction"):
            copy_src_dir(_config(paths_to_mutate=["src"]))

        assert victim.read_text(encoding="utf-8") == "VALUE = 'victim'\n"

    def test_changed_conftest_is_mirrored_without_obsolete_cache_warning(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # The stats context digest now includes conftest.py, so the mirror only
        # needs to report the update; the old "not fingerprinted / --force"
        # warning would be false and undermine the new cache contract.
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        conftest = tests_dir / "conftest.py"
        conftest.write_text(
            "import pytest\n\n\n@pytest.fixture\ndef cases():\n    return [3]\n",
            encoding="utf-8",
        )

        original_cwd = Path.cwd()
        os.chdir(tmp_path)
        try:
            cfg = _config(paths_to_mutate=["src_pkg"])
            copy_src_dir(cfg)  # initial mirror
            capsys.readouterr()  # discard the first-copy output

            # Widen the fixture (changes size → stale mirror) and re-sync.
            conftest.write_text(
                "import pytest\n\n\n@pytest.fixture\ndef cases():\n    return [3, 0]\n",
                encoding="utf-8",
            )
            copy_src_dir(cfg)
            out = capsys.readouterr().out
        finally:
            os.chdir(original_cwd)

        assert "conftest.py" in out
        assert "updated" in out.lower()
        assert "not fingerprinted" not in out.lower()

    def test_workspace_run_lock_artifacts_are_never_staged(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".MUTMUT-WIN.RUN.LOCK").write_text("owner", encoding="utf-8")
        (tmp_path / ".Mutmut-Win.Run.Lock.Guard").write_bytes(b"\0")

        copy_src_dir(_config(paths_to_mutate=["."]))

        assert not (tmp_path / "mutants" / ".MUTMUT-WIN.RUN.LOCK").exists()
        assert not (tmp_path / "mutants" / ".Mutmut-Win.Run.Lock.Guard").exists()

    @pytest.mark.parametrize(
        "relative_collision",
        [
            "sitecustomize.py",
            "SRC/SITECUSTOMIZE.PY",
            "_mutmut_stats_plugin.py",
            "src/_MUTMUT_STATS_PLUGIN.PY",
            "source/_mutmut_phase_guard.py",
            "src/_mutmut_phase_guard/__init__.py",
            "src/_mutmut_phase_guard.pyd",
            "src/_mutmut_stats_plugin/data.json",
            ".mutmut-config-fingerprint",
            "mutmut-cicd-stats.json",
        ],
    )
    def test_reserved_staging_inputs_fail_before_copy(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        relative_collision: str,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        selected = tmp_path / "src" / "selected.py"
        selected.parent.mkdir()
        selected.write_text(_SIMPLE_SOURCE, encoding="utf-8")
        collision = tmp_path / relative_collision
        collision.parent.mkdir(parents=True, exist_ok=True)
        collision.write_bytes(b"PROJECT-FIXTURE")

        with pytest.raises(
            StagingNamespaceCollisionError,
            match="reserved staging namespace",
        ):
            copy_src_dir(_config(paths_to_mutate=["src/selected.py"]))

        assert collision.read_bytes() == b"PROJECT-FIXTURE"
        assert not (tmp_path / "mutants").exists()

    @pytest.mark.parametrize(
        "relative_collision",
        [".mutmut-config-fingerprint", "mutmut-cicd-stats.json"],
    )
    def test_reserved_staging_directory_fails_before_materialization(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        relative_collision: str,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        selected = tmp_path / "src" / "selected.py"
        selected.parent.mkdir()
        selected.write_text(_SIMPLE_SOURCE, encoding="utf-8")
        collision = tmp_path / relative_collision
        collision.mkdir()

        with pytest.raises(StagingNamespaceCollisionError, match="reserved staging namespace"):
            copy_src_dir(_config(paths_to_mutate=["src/selected.py"]))

        assert collision.is_dir()
        assert not (tmp_path / "mutants").exists()

    def test_selected_source_metadata_name_fails_before_copy(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        selected = tmp_path / "src" / "mod.py"
        selected.parent.mkdir()
        selected.write_text(_SIMPLE_SOURCE, encoding="utf-8")
        legitimate_metadata = tmp_path / "src" / "mod.py.meta"
        legitimate_metadata.write_bytes(b"PROJECT-FIXTURE-METADATA")

        with pytest.raises(
            StagingNamespaceCollisionError,
            match=r"mod\.py\.meta.*mutation metadata",
        ):
            copy_src_dir(_config(paths_to_mutate=["src/mod.py"]))

        assert legitimate_metadata.read_bytes() == b"PROJECT-FIXTURE-METADATA"
        assert not (tmp_path / "mutants").exists()

    def test_unselected_source_metadata_name_remains_a_normal_fixture(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        selected = tmp_path / "src" / "selected.py"
        selected.parent.mkdir()
        selected.write_text(_SIMPLE_SOURCE, encoding="utf-8")
        unselected = tmp_path / "fixtures" / "other.py"
        unselected.parent.mkdir()
        unselected.write_text(_SIMPLE_SOURCE, encoding="utf-8")
        legitimate_metadata = tmp_path / "fixtures" / "other.py.meta"
        legitimate_metadata.write_bytes(b"PROJECT-FIXTURE-METADATA")

        copy_src_dir(_config(paths_to_mutate=["src/selected.py"]))

        assert (
            tmp_path / "mutants" / "fixtures" / "other.py.meta"
        ).read_bytes() == b"PROJECT-FIXTURE-METADATA"

    def test_configured_sibling_file_cannot_map_onto_reserved_root(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        selected = tmp_path / "src" / "selected.py"
        selected.parent.mkdir()
        selected.write_text(_SIMPLE_SOURCE, encoding="utf-8")
        sibling_root = tmp_path.parent / f"{tmp_path.name}-sibling"
        sibling_root.mkdir()
        sibling = sibling_root / "_mutmut_stats_plugin.py"
        sibling.write_bytes(b"PROJECT-SIBLING-PLUGIN")
        try:
            config = _config(
                paths_to_mutate=["src/selected.py"],
                also_copy=[f"../{sibling_root.name}/{sibling.name}"],
            )
            with pytest.raises(
                StagingNamespaceCollisionError,
                match="pytest statistics plugin",
            ):
                validate_staging_namespace(config)
        finally:
            sibling.unlink(missing_ok=True)
            sibling_root.rmdir()

        assert not (tmp_path / "mutants").exists()

    @pytest.mark.parametrize("shared_filename", [True, False])
    def test_configured_sibling_tree_cannot_overlap_automatic_project_namespace(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        shared_filename: bool,
    ) -> None:
        project = tmp_path / "project"
        project.mkdir()
        monkeypatch.chdir(project)
        selected = project / "src" / "selected.py"
        selected.parent.mkdir()
        selected.write_text(_SIMPLE_SOURCE, encoding="utf-8")
        local_root = project / "shared"
        local_root.mkdir()
        local_name = "common.py" if shared_filename else "local.py"
        (local_root / local_name).write_text("ORIGIN = 'local'\n", encoding="utf-8")
        sibling_root = tmp_path / "shared"
        sibling_root.mkdir()
        sibling_name = "common.py" if shared_filename else "sibling.py"
        (sibling_root / sibling_name).write_text("ORIGIN = 'sibling'\n", encoding="utf-8")
        config = _config(
            paths_to_mutate=["src/selected.py"],
            extra_paths=["../shared"],
        )

        with pytest.raises(
            StagingNamespaceCollisionError,
            match=r"shared.*automatic project input|common\.py.*another live staging input",
        ):
            validate_staging_namespace(config)

        assert not (project / "mutants").exists()

    def test_two_configured_roots_cannot_form_one_hybrid_staging_namespace(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        project = tmp_path / "project"
        project.mkdir()
        monkeypatch.chdir(project)
        for parent, filename in (("left", "left.py"), ("right", "right.py")):
            source_root = tmp_path / parent / "shared"
            source_root.mkdir(parents=True)
            (source_root / filename).write_text(f"ORIGIN = {parent!r}\n", encoding="utf-8")
        config = _config(
            also_copy=["../left/shared", "../right/shared"],
        )

        with pytest.raises(StagingNamespaceCollisionError, match="configured staging input"):
            validate_staging_namespace(config)

        assert not (project / "mutants").exists()

    def test_repeated_configuration_of_same_live_root_remains_unambiguous(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        shared = tmp_path / "shared"
        shared.mkdir()
        (shared / "module.py").write_text("VALUE = 1\n", encoding="utf-8")

        validate_staging_namespace(
            _config(
                also_copy=["shared"],
                extra_paths=["shared"],
            )
        )

        assert not (tmp_path / "mutants").exists()

    @pytest.mark.parametrize(
        ("config_field", "target_name", "nested_name"),
        [
            ("extra_paths", "shared", "payload.py"),
            ("also_copy", "shared.py", None),
        ],
    )
    def test_missing_sibling_cannot_erase_automatic_live_input_before_copy(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        config_field: str,
        target_name: str,
        nested_name: str | None,
    ) -> None:
        project = tmp_path / "project"
        project.mkdir()
        monkeypatch.chdir(project)
        selected = project / "src" / "selected.py"
        selected.parent.mkdir()
        selected.write_text(_SIMPLE_SOURCE, encoding="utf-8")
        local_input = project / target_name
        if nested_name is None:
            local_input.write_text("ORIGIN = 'automatic'\n", encoding="utf-8")
        else:
            local_input.mkdir()
            (local_input / nested_name).write_text("ORIGIN = 'automatic'\n", encoding="utf-8")
        missing_sibling = tmp_path / target_name
        assert not missing_sibling.exists()

        staging = project / "mutants"
        staging.mkdir()
        sentinel = staging / "sentinel.bin"
        sentinel.write_bytes(b"PREEXISTING-STAGING")
        config = _config(
            paths_to_mutate=["src/selected.py"],
            **{config_field: [f"../{target_name}"]},
        )

        with pytest.raises(
            StagingNamespaceCollisionError,
            match=r"automatic project input",
        ):
            copy_src_dir(config)

        assert sentinel.read_bytes() == b"PREEXISTING-STAGING"
        assert [path.relative_to(staging) for path in staging.rglob("*")] == [Path("sentinel.bin")]

    def test_disjoint_missing_configured_input_remains_optional(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        source = tmp_path / "src" / "selected.py"
        source.parent.mkdir()
        source.write_text(_SIMPLE_SOURCE, encoding="utf-8")

        validate_staging_namespace(
            _config(
                paths_to_mutate=["src/selected.py"],
                also_copy=["optional-missing.cfg"],
            )
        )

        assert not (tmp_path / "mutants").exists()

    def test_missing_nested_duplicate_of_same_configured_tree_remains_valid(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        tests_root = tmp_path / "tests"
        tests_root.mkdir()
        (tests_root / "test_live.py").write_text("def test_live(): pass\n", encoding="utf-8")

        validate_staging_namespace(
            _config(
                also_copy=["tests", "tests/optional_missing"],
            )
        )

        assert not (tmp_path / "mutants").exists()

    def test_extra_path_import_root_cannot_shadow_internal_helper(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        selected = tmp_path / "src" / "selected.py"
        selected.parent.mkdir()
        selected.write_text(_SIMPLE_SOURCE, encoding="utf-8")
        sibling_root = tmp_path.parent / f"{tmp_path.name}-extra"
        sibling_root.mkdir()
        plugin = sibling_root / "_mutmut_stats_plugin.py"
        plugin.write_bytes(b"PROJECT-SIBLING-PLUGIN")
        try:
            config = _config(
                paths_to_mutate=["src/selected.py"],
                extra_paths=[f"../{sibling_root.name}"],
            )
            with pytest.raises(
                StagingNamespaceCollisionError,
                match="pytest statistics plugin",
            ):
                validate_staging_namespace(config)
        finally:
            plugin.unlink(missing_ok=True)
            sibling_root.rmdir()

        assert not (tmp_path / "mutants").exists()

    @pytest.mark.parametrize("method_name", ["run", "dry_run"])
    def test_programmatic_entrypoints_reject_namespace_before_state_writes(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        method_name: str,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        source = tmp_path / "src" / "mod.py"
        source.parent.mkdir()
        source.write_text(_SIMPLE_SOURCE, encoding="utf-8")
        (tmp_path / "src" / "mod.py.meta").write_text("fixture", encoding="utf-8")
        monkeypatch.setattr("mutmut_win.orchestrator._ensure_supported_pytest", lambda: None)
        orchestrator = MutationOrchestrator(
            _config(paths_to_mutate=["src/mod.py"]),
            runner=MagicMock(),
            executor=MagicMock(),
        )

        with pytest.raises(StagingNamespaceCollisionError):
            getattr(orchestrator, method_name)()

        assert not (tmp_path / "mutants").exists()
        assert not (tmp_path / ".mutmut-cache").exists()

    @pytest.mark.parametrize("directory_name", ["build", "dist", "html", "bug_reporting", "_docs"])
    def test_generic_tool_directory_name_is_excluded_only_at_workspace_root(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        directory_name: str,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        root_tool_file = tmp_path / directory_name / "artifact.py"
        root_tool_file.parent.mkdir()
        root_tool_file.write_text("ROOT_TOOL_STATE = True\n", encoding="utf-8")
        nested_source = tmp_path / "src" / "package" / directory_name / "feature.py"
        nested_source.parent.mkdir(parents=True)
        nested_source.write_text("VALUE = 1\n", encoding="utf-8")

        copy_src_dir(_config(paths_to_mutate=["src"]))

        assert not (tmp_path / "mutants" / directory_name / "artifact.py").exists()
        assert (tmp_path / "mutants" / "src" / "package" / directory_name / "feature.py").is_file()

    def test_hidden_tool_directory_remains_excluded_when_nested(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        nested_tool_state = tmp_path / "src" / "package" / ".claude" / "secret.txt"
        nested_tool_state.parent.mkdir(parents=True)
        nested_tool_state.write_text("TOKEN=sentinel\n", encoding="utf-8")
        source = tmp_path / "src" / "package" / "feature.py"
        source.write_text("VALUE = 1\n", encoding="utf-8")

        copy_src_dir(_config(paths_to_mutate=["src"]))

        assert not (tmp_path / "mutants" / "src" / "package" / ".claude").exists()
        assert (tmp_path / "mutants" / "src" / "package" / "feature.py").is_file()

    def test_deleted_automatic_package_directory_restores_import_parity(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)

        def find_spec_is_absent(import_root: Path) -> bool:
            probe = subprocess.run(  # noqa: S603 - fixed interpreter and probe
                [
                    sys.executable,
                    "-I",
                    "-c",
                    (
                        "import importlib.util, sys; "
                        f"sys.path.insert(0, {str(import_root)!r}); "
                        "print(importlib.util.find_spec('ghostpkg') is None)"
                    ),
                ],
                cwd=tmp_path,
                capture_output=True,
                encoding="utf-8",
                check=True,
                timeout=30,
            )
            return probe.stdout.strip() == "True"

        package = tmp_path / "ghostpkg"
        package.mkdir()
        (package / "old.py").write_text("VALUE = 'stale'\n", encoding="utf-8")
        config = _config(paths_to_mutate=["ghostpkg"])

        copy_src_dir(config)
        staged_package = tmp_path / "mutants" / "ghostpkg"
        assert (staged_package / "old.py").is_file()
        assert not find_spec_is_absent(tmp_path)
        assert not find_spec_is_absent(tmp_path / "mutants")

        (package / "old.py").unlink()
        package.rmdir()
        copy_src_dir(config)

        assert (tmp_path / "mutants").is_dir()
        assert not staged_package.exists()
        assert find_spec_is_absent(tmp_path)
        assert find_spec_is_absent(tmp_path / "mutants")

    def test_empty_automatic_namespace_is_materialized_on_first_run(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        namespace = tmp_path / "empty_namespace"
        namespace.mkdir()

        copy_src_dir(_config(paths_to_mutate=["."]))

        staged_namespace = tmp_path / "mutants" / "empty_namespace"
        assert staged_namespace.is_dir()
        probe = subprocess.run(  # noqa: S603 - fixed interpreter and probe
            [
                sys.executable,
                "-I",
                "-c",
                (
                    "import importlib.util, sys; "
                    f"sys.path.insert(0, {str(tmp_path / 'mutants')!r}); "
                    "print(importlib.util.find_spec('empty_namespace') is not None)"
                ),
            ],
            cwd=tmp_path,
            capture_output=True,
            encoding="utf-8",
            check=True,
            timeout=30,
        )
        assert probe.stdout.strip() == "True"

    def test_empty_configured_namespace_tracks_live_topology(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        project = tmp_path / "project"
        project.mkdir()
        monkeypatch.chdir(project)
        selected = project / "src" / "selected.py"
        selected.parent.mkdir()
        selected.write_text(_SIMPLE_SOURCE, encoding="utf-8")
        external_root = tmp_path / "external"
        namespace = external_root / "configured_namespace"
        namespace.mkdir(parents=True)
        config = _config(
            paths_to_mutate=["src/selected.py"],
            extra_paths=["../external"],
        )

        copy_src_dir(config)
        copy_also_copy_files(config)

        staged_external = project / "mutants" / "external"
        staged_namespace = staged_external / "configured_namespace"
        assert staged_namespace.is_dir()

        namespace.rmdir()
        copy_src_dir(config)
        copy_also_copy_files(config)

        assert external_root.is_dir()
        assert staged_external.is_dir()
        assert not staged_namespace.exists()

    def test_empty_cleanup_preserves_explicit_configured_mirror_root(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        source = tmp_path / "src" / "selected.py"
        source.parent.mkdir()
        source.write_text(_SIMPLE_SOURCE, encoding="utf-8")
        configured = tmp_path / "fixtures"
        configured_package = configured / "ghostpkg"
        configured_package.mkdir(parents=True)
        (configured_package / "payload.txt").write_text("fixture\n", encoding="utf-8")
        config = _config(
            paths_to_mutate=["src/selected.py"],
            also_copy=["fixtures"],
        )

        copy_src_dir(config)
        copy_also_copy_files(config)
        staged_configured = tmp_path / "mutants" / "fixtures"
        staged_package = staged_configured / "ghostpkg"
        assert (staged_package / "payload.txt").is_file()

        (configured_package / "payload.txt").unlink()
        configured_package.rmdir()
        copy_src_dir(config)
        copy_also_copy_files(config)

        assert configured.is_dir()
        assert staged_configured.is_dir()
        assert not staged_package.exists()
        assert list(staged_configured.iterdir()) == []

    def test_automatic_root_mirror_excludes_dotenv_secrets_but_keeps_template(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".ENV").write_text("TOKEN=secret\n", encoding="utf-8")
        (tmp_path / ".Env.Production").write_text("TOKEN=prod\n", encoding="utf-8")
        (tmp_path / ".Env.Example").write_text("TOKEN=replace-me\n", encoding="utf-8")
        (tmp_path / "nested").mkdir()
        (tmp_path / "nested" / ".Env.Local").write_text("TOKEN=nested\n", encoding="utf-8")
        (tmp_path / "nested" / ".Env.Sample").write_text("TOKEN=replace-me\n", encoding="utf-8")
        # Heal a secret mirrored by a pre-fix run even though the root grab-bag
        # intentionally has no general deletion synchronization.
        (tmp_path / "mutants" / "nested").mkdir(parents=True)
        (tmp_path / "mutants" / "nested" / ".ENV.Stale").write_text("TOKEN=old\n", encoding="utf-8")

        copy_src_dir(_config(paths_to_mutate=["."]))

        assert not (tmp_path / "mutants" / ".ENV").exists()
        assert not (tmp_path / "mutants" / ".Env.Production").exists()
        assert (tmp_path / "mutants" / ".Env.Example").is_file()
        assert not (tmp_path / "mutants" / "nested" / ".Env.Local").exists()
        assert not (tmp_path / "mutants" / "nested" / ".ENV.Stale").exists()
        assert (tmp_path / "mutants" / "nested" / ".Env.Sample").is_file()


# ---------------------------------------------------------------------------
# copy_also_copy_files
# ---------------------------------------------------------------------------


class TestCopyAlsoCopyFiles:
    @pytest.mark.skipif(os.name != "nt", reason="Windows Junction regression")
    def test_nested_destination_junction_cannot_escape_staging(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        source = tmp_path / "tests" / "pkg" / "test_mod.py"
        source.parent.mkdir(parents=True)
        source.write_text("def test_ok(): pass\n", encoding="utf-8")
        victim_dir = tmp_path / "junction-target"
        victim_dir.mkdir()
        victim = victim_dir / "test_mod.py"
        victim.write_text("DO_NOT_OVERWRITE\n", encoding="utf-8")
        junction = tmp_path / "mutants" / "tests" / "pkg"
        junction.parent.mkdir(parents=True)
        cmd_executable = Path(os.environ.get("COMSPEC", r"C:\Windows\System32\cmd.exe"))
        created = subprocess.run(  # noqa: S603 - cmd builtin creates the test Junction
            [
                cmd_executable,
                "/d",
                "/u",
                "/c",
                "mklink",
                "/J",
                str(junction),
                str(victim_dir),
            ],
            capture_output=True,
            encoding="utf-16-le",
            errors="replace",
            check=False,
        )
        if created.returncode != 0:
            pytest.skip(f"could not create Junction: {created.stdout}{created.stderr}")

        try:
            with pytest.raises(UnsafeStagingError, match="symlink/junction"):
                copy_also_copy_files(_config(also_copy=["tests"]))
            victim_content = victim.read_text(encoding="utf-8")
        finally:
            if junction.exists() and junction.is_junction():
                junction.rmdir()

        assert victim_content == "DO_NOT_OVERWRITE\n"

    def test_nested_destination_symlink_cannot_escape_staging(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        source = tmp_path / "tests" / "pkg" / "test_mod.py"
        source.parent.mkdir(parents=True)
        source.write_text("def test_ok(): pass\n", encoding="utf-8")
        victim_dir = tmp_path / "victim-dir"
        victim_dir.mkdir()
        victim = victim_dir / "test_mod.py"
        victim.write_text("DO_NOT_OVERWRITE\n", encoding="utf-8")
        redirected = tmp_path / "mutants" / "tests" / "pkg"
        redirected.parent.mkdir(parents=True)
        try:
            redirected.symlink_to(victim_dir, target_is_directory=True)
        except OSError as exc:
            pytest.skip(f"directory symlinks unavailable on this host: {exc}")

        with pytest.raises(UnsafeStagingError, match="symlink/junction"):
            copy_also_copy_files(_config(also_copy=["tests"]))

        assert victim.read_text(encoding="utf-8") == "DO_NOT_OVERWRITE\n"

    def test_copies_file(self, tmp_path: Path) -> None:
        # Use a relative path so the file is mirrored under mutants/<relpath>.
        extra = tmp_path / "extra.cfg"
        extra.write_text("[section]\nkey=val\n", encoding="utf-8")

        original_cwd = Path.cwd()
        os.chdir(tmp_path)
        try:
            # mutants/ must exist before copy_also_copy_files (copy_src_dir creates it).
            (tmp_path / "mutants").mkdir()
            cfg = _config(also_copy=["extra.cfg"])
            copy_also_copy_files(cfg)
            assert (tmp_path / "mutants" / "extra.cfg").exists()
        finally:
            os.chdir(original_cwd)

    def test_explicit_caller_owned_state_exclusion_cannot_be_reintroduced(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        database = tmp_path / "custom.db"
        database.write_bytes(b"live database")
        staged = tmp_path / "mutants" / "custom.db"
        staged.parent.mkdir()
        staged.write_bytes(b"stale database")

        copy_also_copy_files(
            _config(also_copy=["custom.db"]),
            excluded_paths=(database,),
        )

        assert not staged.exists()

    def test_directory_mirror_prunes_nested_caller_owned_state_exclusion(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        fixtures = tmp_path / "fixtures"
        fixtures.mkdir()
        database = fixtures / "custom.db"
        database.write_bytes(b"live database")
        (fixtures / "payload.txt").write_text("bound input\n", encoding="utf-8")
        staged = tmp_path / "mutants" / "fixtures"
        staged.mkdir(parents=True)
        (staged / "custom.db").write_bytes(b"stale database")

        copy_also_copy_files(
            _config(also_copy=["fixtures"]),
            excluded_paths=(database,),
        )

        assert not (staged / "custom.db").exists()
        assert (staged / "payload.txt").read_text(encoding="utf-8") == "bound input\n"

    def test_skips_nonexistent_path(self, tmp_path: Path) -> None:
        original_cwd = Path.cwd()
        os.chdir(tmp_path)
        try:
            cfg = _config(also_copy=["does_not_exist.cfg"])
            # Should not raise.
            copy_also_copy_files(cfg)
        finally:
            os.chdir(original_cwd)

    def test_copies_directory(self, tmp_path: Path) -> None:
        # Use a relative path for the directory.
        extra_dir = tmp_path / "extra_dir"
        extra_dir.mkdir()
        (extra_dir / "conf.txt").write_text("cfg", encoding="utf-8")

        original_cwd = Path.cwd()
        os.chdir(tmp_path)
        try:
            cfg = _config(also_copy=["extra_dir"])
            copy_also_copy_files(cfg)
            assert (tmp_path / "mutants" / "extra_dir" / "conf.txt").exists()
        finally:
            os.chdir(original_cwd)

    def test_top_level_venv_is_skipped(self, tmp_path: Path) -> None:
        """Bug #67/H-05: a top-level ``.venv`` in ``also_copy`` must be ignored.

        The pre-Sprint-25 implementation only skipped ``.venv`` directories that
        appeared as *children* of a copied directory (via the ``shutil.copytree``
        ignore callback). A user who configured ``also_copy = [".venv"]``
        directly would still get the entire virtualenv mirrored under
        ``mutants/.venv`` — slow at best, broken on Windows with symlinked
        ``Scripts/python.exe`` at worst.
        """
        (tmp_path / ".venv").mkdir()
        (tmp_path / ".venv" / "pyvenv.cfg").write_text("home = …\n", encoding="utf-8")
        (tmp_path / "mutants").mkdir()

        original_cwd = Path.cwd()
        os.chdir(tmp_path)
        try:
            cfg = _config(also_copy=[".venv"])
            copy_also_copy_files(cfg)
            assert not (tmp_path / "mutants" / ".venv").exists(), (
                "Top-level .venv in also_copy was mirrored into mutants/ — Bug #67 regression."
            )
        finally:
            os.chdir(original_cwd)

    def test_nested_venv_inside_copied_directory_is_skipped(self, tmp_path: Path) -> None:
        """A ``.venv`` inside a copied parent directory must also be ignored.

        Regression guard for the existing ``shutil.copytree`` ignore callback.
        """
        project = tmp_path / "project"
        project.mkdir()
        (project / "main.py").write_text("print('hi')\n", encoding="utf-8")
        (project / ".venv").mkdir()
        (project / ".venv" / "pyvenv.cfg").write_text("home = …\n", encoding="utf-8")
        (tmp_path / "mutants").mkdir()

        original_cwd = Path.cwd()
        os.chdir(tmp_path)
        try:
            cfg = _config(also_copy=["project"])
            copy_also_copy_files(cfg)
            assert (tmp_path / "mutants" / "project" / "main.py").exists()
            assert not (tmp_path / "mutants" / "project" / ".venv").exists(), (
                "Nested .venv under a copied directory was mirrored — Bug #67 regression."
            )
        finally:
            os.chdir(original_cwd)


# ---------------------------------------------------------------------------
# setup_source_paths
# ---------------------------------------------------------------------------


class TestSetupSourcePaths:
    def test_adds_mutants_paths_to_sys_path(self, tmp_path: Path) -> None:
        mutants_src = tmp_path / "mutants" / "src"
        mutants_src.mkdir(parents=True)

        original_cwd = Path.cwd()
        original_path = sys.path[:]
        os.chdir(tmp_path)
        try:
            setup_source_paths()
            inserted = [p for p in sys.path if "mutants" in p]
            assert any("src" in p for p in inserted)
        finally:
            os.chdir(original_cwd)
            sys.path[:] = original_path

    def test_removes_original_src_from_sys_path(self, tmp_path: Path) -> None:
        original_cwd = Path.cwd()
        original_path = sys.path[:]
        os.chdir(tmp_path)
        try:
            # Inject the 'src' path so setup_source_paths can remove it.
            src_abs = str((tmp_path / "src").absolute())
            sys.path.insert(0, src_abs)
            setup_source_paths()
            # The original src should be gone.
            assert src_abs not in sys.path
        finally:
            os.chdir(original_cwd)
            sys.path[:] = original_path


# ---------------------------------------------------------------------------
# strip_prefix
# ---------------------------------------------------------------------------


class TestStripPrefix:
    def test_strips_matching_prefix(self) -> None:
        assert strip_prefix("src.foo.bar", prefix="src.") == "foo.bar"

    def test_returns_unchanged_when_no_match(self) -> None:
        assert strip_prefix("foo.bar", prefix="src.") == "foo.bar"

    def test_empty_prefix(self) -> None:
        assert strip_prefix("anything", prefix="") == "anything"

    def test_empty_string(self) -> None:
        assert strip_prefix("", prefix="src.") == ""


# ---------------------------------------------------------------------------
# get_mutant_name
# ---------------------------------------------------------------------------


class TestGetMutantName:
    def test_basic_path(self) -> None:
        path = Path("src") / "my_lib" / "utils.py"
        result = get_mutant_name(path, "add__mutmut_1")
        assert result == "my_lib.utils.add__mutmut_1"

    def test_init_module_collapsed(self) -> None:
        path = Path("src") / "my_lib" / "__init__.py"
        result = get_mutant_name(path, "foo__mutmut_1")
        assert result == "my_lib.foo__mutmut_1"

    def test_no_src_prefix(self) -> None:
        path = Path("lib") / "utils.py"
        result = get_mutant_name(path, "func__mutmut_2")
        assert result == "lib.utils.func__mutmut_2"

    def test_deep_nesting(self) -> None:
        path = Path("src") / "a" / "b" / "c.py"
        result = get_mutant_name(path, "x__mutmut_3")
        assert result == "a.b.c.x__mutmut_3"

    def test_source_root_is_stripped(self) -> None:
        # 360°-A3 (#126): source/ is a supported staging root everywhere
        # else (copy roots, PYTHONPATH, sitecustomize) — its prefix must
        # strip exactly like src., or every mutant ends up 'no tests'.
        path = Path("source") / "pkg" / "mod.py"
        result = get_mutant_name(path, "x_f__mutmut_1")
        assert result == "pkg.mod.x_f__mutmut_1"

    def test_only_one_root_prefix_is_stripped(self) -> None:
        # src/source/… must become source.… — one strip, no cascade.
        path = Path("src") / "source" / "mod.py"
        result = get_mutant_name(path, "x_f__mutmut_1")
        assert result == "source.mod.x_f__mutmut_1"

    def test_flat_layout_keeps_full_module_path(self) -> None:
        path = Path("mypkg") / "mod.py"
        result = get_mutant_name(path, "x_f__mutmut_1")
        assert result == "mypkg.mod.x_f__mutmut_1"

    @pytest.mark.skipif(os.name != "nt", reason="Windows path casing contract")
    def test_uppercase_source_root_and_init_stem_match_runtime_name(self) -> None:
        path = Path("SRC") / "pkg" / "__INIT__.PY"
        result = get_mutant_name(path, "value__mutmut_1")
        assert result == "pkg.value__mutmut_1"

    @pytest.mark.skipif(os.name != "nt", reason="Windows path casing contract")
    def test_uppercase_source_root_init_mutant_is_activated(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        relative_source = Path("SRC") / "pkg" / "__INIT__.PY"
        relative_source.parent.mkdir(parents=True)
        relative_source.write_text("def value():\n    return 1\n", encoding="utf-8")
        config = _config(paths_to_mutate=["SRC"])

        assert list(walk_source_files(config)) == [relative_source]

        generated = Path("mutants") / relative_source
        generated.parent.mkdir(parents=True)
        local_names, warnings, took_fast_path = create_mutants_for_file(
            relative_source,
            generated,
        )
        assert local_names
        assert warnings == []
        assert took_fast_path is False

        qualified_name = get_mutant_name(relative_source, local_names[0])
        import_code = (
            "import sys; "
            f"sys.path.insert(0, {str((tmp_path / 'mutants' / 'SRC').resolve())!r}); "
            "import pkg; "
            "print(pkg.value())"
        )

        def run_with(mutant_name: str) -> str:
            env = os.environ.copy()
            env["MUTANT_UNDER_TEST"] = mutant_name
            completed = subprocess.run(  # noqa: S603 - fixed interpreter and code
                [sys.executable, "-c", import_code],
                cwd=tmp_path,
                env=env,
                capture_output=True,
                encoding="utf-8",
                check=True,
                timeout=30,
            )
            return completed.stdout.strip()

        assert qualified_name.startswith("pkg.")
        assert ".__INIT__." not in qualified_name
        assert run_with(qualified_name) != run_with("")


# ---------------------------------------------------------------------------
# write_all_mutants_to_file
# ---------------------------------------------------------------------------


class TestWriteAllMutantsToFile:
    def test_writes_mutated_output(self, tmp_path: Path) -> None:
        from io import StringIO

        buf = StringIO()
        names = write_all_mutants_to_file(
            out=buf,
            source=_SIMPLE_SOURCE,
            filename=tmp_path / "foo.py",
        )
        content = buf.getvalue()
        assert len(content) > 0
        assert len(names) > 0

    def test_returns_mutant_names_list(self, tmp_path: Path) -> None:
        from io import StringIO

        buf = StringIO()
        names = write_all_mutants_to_file(
            out=buf,
            source=_SIMPLE_SOURCE,
            filename=tmp_path / "foo.py",
        )
        assert isinstance(names, list)
        assert all(isinstance(n, str) for n in names)


# ---------------------------------------------------------------------------
# create_mutants_for_file
# ---------------------------------------------------------------------------


class TestCreateMutantsForFile:
    @pytest.fixture(autouse=True)
    def _isolated_staging(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)

    def test_creates_output_file(self, tmp_path: Path) -> None:
        src = tmp_path / "foo.py"
        src.write_text(_SIMPLE_SOURCE, encoding="utf-8")
        output = tmp_path / "mutants" / "foo.py"
        output.parent.mkdir(parents=True, exist_ok=True)

        names, warns, _ = create_mutants_for_file(src, output)
        assert output.exists()
        assert len(names) > 0
        assert warns == []

    def test_pep263_cp1252_source_is_generated_and_importable(self, tmp_path: Path) -> None:
        source_text = "# coding: cp1252\nLABEL = 'café'\n\ndef add(value):\n    return value + 1\n"
        src = tmp_path / "legacy.py"
        src.write_bytes(source_text.encode("cp1252"))
        output = tmp_path / "mutants" / "legacy.py"

        names, warns, _ = create_mutants_for_file(src, output)

        assert names
        assert warns == []
        compile(output.read_bytes(), str(output), "exec")
        assert b"caf\xe9" in output.read_bytes()

    def test_generated_unicode_identifiers_upgrade_internal_staging_cookie(
        self, tmp_path: Path
    ) -> None:
        source_text = (
            "# coding: cp1252\nclass Café:\n    def add(self, value):\n        return value + 1\n"
        )
        src = tmp_path / "legacy_class.py"
        src.write_bytes(source_text.encode("cp1252"))
        output = tmp_path / "mutants" / "legacy_class.py"

        names, warns, _ = create_mutants_for_file(src, output)

        assert names
        assert warns == []
        staged = output.read_bytes()
        assert b"coding: utf-8" in staged.splitlines()[0]
        compile(staged, str(output), "exec")

    def test_utf8_fallback_counts_only_lf_delimited_pep263_lines(self, tmp_path: Path) -> None:
        source_text = (
            "# marker contains NEL: a\x85b\n"
            "# coding: latin-1\n"
            "class Café:\n"
            "    def add(self, value):\n"
            "        return value + 1\n"
        )
        src = tmp_path / "legacy_nel.py"
        src.write_bytes(source_text.encode("latin-1"))
        output = tmp_path / "mutants" / "legacy_nel.py"

        names, warns, _ = create_mutants_for_file(src, output)

        assert names
        assert warns == []
        staged = output.read_bytes()
        first_line, cookie_line, _body = staged.split(b"\n", maxsplit=2)
        assert b"a\xc2\x85b" in first_line
        assert cookie_line.rstrip(b"\r") == b"# coding: utf-8"
        compile(staged, str(output), "exec")

    def test_returns_qualified_method_names(self, tmp_path: Path) -> None:
        src = tmp_path / "foo.py"
        src.write_text(_SIMPLE_SOURCE, encoding="utf-8")
        output = tmp_path / "mutants" / "foo_mutated.py"

        names, _, _ = create_mutants_for_file(src, output)
        # Each name should contain the mutmut marker.
        assert all("__mutmut_" in n for n in names)

    def test_no_mutants_for_trivial_code(self, tmp_path: Path) -> None:
        src = tmp_path / "trivial.py"
        src.write_text("x = 1\n", encoding="utf-8")
        output = tmp_path / "mutants" / "trivial_out.py"

        names, _, _ = create_mutants_for_file(src, output)
        # Trivial assignment may produce 0 or more mutants — just ensure
        # no exception is raised and the return types are correct.
        assert isinstance(names, list)

    def test_reuses_names_if_source_unmodified(self, tmp_path: Path) -> None:
        """When the mutant file is newer than the source, return existing names from .meta."""
        src = tmp_path / "mod.py"
        src.write_text(_SIMPLE_SOURCE, encoding="utf-8")
        output = tmp_path / "mutants" / "mod_out.py"

        # First run: generate mutants normally.
        names_first, _, took_fast_first = create_mutants_for_file(src, output)
        assert len(names_first) > 0
        assert took_fast_first is False

        # Make output much newer than source (simulates "already mutated").
        future_mtime = src.stat().st_mtime + 3600
        os.utime(output, (future_mtime, future_mtime))

        # Second run: fast-path should return the same names from .meta.
        names_second, _, took_fast_second = create_mutants_for_file(src, output)
        assert names_second == names_first
        assert took_fast_second is True  # the #119 reuse signal

    def test_handles_syntax_error_gracefully(self, tmp_path: Path) -> None:
        src = tmp_path / "bad.py"
        # Intentionally invalid Python that libcst cannot parse.
        src.write_text("def broken(\n    pass\n", encoding="utf-8")
        output = tmp_path / "mutants" / "bad_out.py"

        # Should not raise; may return empty names with a warning.
        names, _warns, _ = create_mutants_for_file(src, output)
        assert isinstance(names, list)

    def test_saves_meta_file(self, tmp_path: Path) -> None:
        original_cwd = Path.cwd()
        os.chdir(tmp_path)
        try:
            src = tmp_path / "meta_test.py"
            src.write_text(_SIMPLE_SOURCE, encoding="utf-8")
            output = tmp_path / "mutants" / "meta_out.py"

            names, _, _ = create_mutants_for_file(src, output)
            if names:
                # Meta file should be created relative to cwd.
                meta = Path("mutants/meta_out.py.meta")
                assert meta.exists()
        finally:
            os.chdir(original_cwd)
