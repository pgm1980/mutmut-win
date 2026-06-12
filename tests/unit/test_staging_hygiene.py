"""Tests for staging hygiene (Issue #101, audit A3-FD-002/003/004/005/009, OS-008, CM-009).

The staging tree could be escaped (`..` paths wrote OUTSIDE mutants/,
sandbox-confirmed), haunted (deleted sources stayed as ghosts, their .meta
forever), stale (mtime-`>` missed restores with old timestamps; config
changes never invalidated the generation fast path), nested
(also_copy=['.'] mirrored mutants into itself), and brittle (a corrupted
.meta blocked every subsequent run; --force sold partial deletion as a
clean slate).
"""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING

from mutmut_win.config import MutmutConfig
from mutmut_win.file_setup import (
    config_fingerprint_matches,
    copy_also_copy_files,
    copy_src_dir,
    create_mutants_for_file,
)
from mutmut_win.models import SourceFileMutationData

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def _project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    src = tmp_path / "src"
    src.mkdir()
    (src / "mod.py").write_text("def f(a):\n    return a + 1\n", encoding="utf-8")
    return tmp_path


class TestPathContainment:
    def test_dotdot_in_also_copy_never_escapes_mutants(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # A3-FD-002 (sandbox-confirmed): Path("mutants") / "../outside"
        # resolves OUTSIDE the staging tree and the copy happily wrote there.
        project = tmp_path / "project"
        outside = tmp_path / "outside"
        project.mkdir()
        outside.mkdir()
        (outside / "data.py").write_text("x = 1\n", encoding="utf-8")
        monkeypatch.chdir(project)

        copy_also_copy_files(MutmutConfig(also_copy=["../outside"]))

        mutants = project / "mutants"
        # The sibling is staged INSIDE mutants/ under its own name...
        assert (mutants / "outside" / "data.py").exists()
        # ...and nothing was created next to the project root.
        assert not (tmp_path / "mutants").exists()

    def test_extra_paths_sibling_use_case_still_works(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The '..' sibling IS the Bug-#69 core use case — the containment fix
        # must keep it working (worker expects mutants/<name> on PYTHONPATH).
        project = tmp_path / "project"
        sibling = tmp_path / "benchmarks"
        project.mkdir()
        sibling.mkdir()
        (sibling / "bench.py").write_text("y = 2\n", encoding="utf-8")
        monkeypatch.chdir(project)

        copy_also_copy_files(MutmutConfig(extra_paths=["../benchmarks"]))

        assert (project / "mutants" / "benchmarks" / "bench.py").exists()


class TestNestingGuards:
    def test_dot_does_not_nest_mutants_into_itself(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # A3-FD-005: Path('.').name == '' defeated the skip-set guard;
        # also_copy=['.'] mirrored mutants/ (incl. .git) into mutants/mutants.
        _project(tmp_path, monkeypatch)
        (tmp_path / "mutants").mkdir()
        (tmp_path / "mutants" / "marker.txt").write_text("m", encoding="utf-8")

        copy_also_copy_files(MutmutConfig(also_copy=["."]))

        assert not (tmp_path / "mutants" / "mutants").exists()

    def test_mutants_itself_is_skipped(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _project(tmp_path, monkeypatch)
        (tmp_path / "mutants").mkdir()

        copy_also_copy_files(MutmutConfig(also_copy=["mutants"]))

        assert not (tmp_path / "mutants" / "mutants").exists()


class TestDeletionSync:
    def test_deleted_source_disappears_from_staging_with_its_meta(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # A3-FD-003 + the OS-012 remainder: ghosts of deleted sources stayed
        # in mutants/ forever (tests ran green against deleted modules) and
        # their .meta files survived with them.
        project = _project(tmp_path, monkeypatch)
        (project / "src" / "gone.py").write_text("def g(a):\n    return a\n", encoding="utf-8")
        cfg = MutmutConfig(paths_to_mutate=["src"])
        copy_src_dir(cfg)
        staged = project / "mutants" / "src" / "gone.py"
        assert staged.exists()
        (project / "mutants" / "src" / "gone.py.meta").write_text("{}", encoding="utf-8")

        (project / "src" / "gone.py").unlink()
        copy_src_dir(cfg)

        assert not staged.exists()
        assert not (project / "mutants" / "src" / "gone.py.meta").exists()
        # The surviving source is untouched.
        assert (project / "mutants" / "src" / "mod.py").exists()

    def test_unmanaged_artifacts_survive_the_sync(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        project = _project(tmp_path, monkeypatch)
        cfg = MutmutConfig(paths_to_mutate=["src"])
        copy_src_dir(cfg)
        notes = project / "mutants" / "src" / "notes.txt"  # not *.py — never touched
        notes.write_text("keep me", encoding="utf-8")

        copy_src_dir(cfg)

        assert notes.exists()


class TestRestoreInvalidation:
    def test_restore_with_old_timestamp_regenerates(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # A3-FD-004 (sandbox-confirmed): the old `source_mtime < target_mtime`
        # fast path missed restores with OLD timestamps — the stale mutant
        # universe survived silently. The fast path now compares EQUALITY
        # against the source fingerprint recorded in .meta at generation
        # time, so a turned-back clock is inequality and regenerates.
        project = _project(tmp_path, monkeypatch)
        source = project / "src" / "mod.py"
        output = project / "mutants" / "src" / "mod.py"
        output.parent.mkdir(parents=True)

        create_mutants_for_file(source, output)
        assert "a + 1" in output.read_text(encoding="utf-8")

        # Restore: different content, mtime turned BACK (older than before).
        source.write_text("def f(a):\n    return a - 1\n", encoding="utf-8")
        old = source.stat().st_mtime - 3600
        os.utime(source, (old, old))

        create_mutants_for_file(source, output)

        assert "a - 1" in output.read_text(encoding="utf-8")  # regenerated

    def test_unchanged_source_uses_the_fast_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The trampolined target is ALWAYS newer and bigger than the source —
        # the fingerprint comparison must not invalidate steady-state runs.
        project = _project(tmp_path, monkeypatch)
        source = project / "src" / "mod.py"
        output = project / "mutants" / "src" / "mod.py"
        output.parent.mkdir(parents=True)

        names_first, _, _ = create_mutants_for_file(source, output)
        trampolined = output.read_text(encoding="utf-8")

        names_second, _, took_fast = create_mutants_for_file(source, output)

        assert sorted(names_second) == sorted(names_first)
        assert output.read_text(encoding="utf-8") == trampolined  # not rewritten
        assert took_fast is True  # the #119 reuse signal


class TestConfigFingerprint:
    def test_first_run_writes_and_matches_thereafter(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _project(tmp_path, monkeypatch)
        (tmp_path / "mutants").mkdir()
        cfg = MutmutConfig(paths_to_mutate=["src"])

        assert config_fingerprint_matches(cfg) is False  # first run: no file yet
        assert config_fingerprint_matches(cfg) is True  # now persisted

    def test_universe_relevant_change_invalidates(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # A3-OS-008: toggling mutate_only_covered_lines (or editing
        # do_not_mutate) never invalidated the generation fast path — the
        # stale mutant universe survived without warning.
        _project(tmp_path, monkeypatch)
        (tmp_path / "mutants").mkdir()
        config_fingerprint_matches(MutmutConfig(paths_to_mutate=["src"]))

        changed = MutmutConfig(paths_to_mutate=["src"], do_not_mutate=["src/mod.py"])
        assert config_fingerprint_matches(changed) is False
        assert config_fingerprint_matches(changed) is True  # re-persisted

    def test_fast_path_is_bypassed_when_disallowed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        project = _project(tmp_path, monkeypatch)
        source = project / "src" / "mod.py"
        output = project / "mutants" / "src" / "mod.py"
        output.parent.mkdir(parents=True)

        names_first, _, _ = create_mutants_for_file(source, output)
        assert names_first
        # Record exit codes the way a finished run would (keeps the source
        # fingerprint the generator wrote into the .meta).
        sfd = SourceFileMutationData(path=str(source))
        sfd.load()
        sfd.exit_code_by_key = {f"src.mod.{n}": 1 for n in names_first}
        sfd.save()

        names_fast, _, fast_flag = create_mutants_for_file(source, output)
        assert names_fast == names_first  # sanity: fast path active
        assert fast_flag is True

        names_forced, _, forced_flag = create_mutants_for_file(
            source, output, allow_fast_path=False
        )
        assert sorted(names_forced) == sorted(names_first)  # regenerated for real
        assert forced_flag is False


class TestMetaRobustness:
    def test_corrupted_meta_warns_and_rebuilds_instead_of_blocking(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # A3-CM-009 (%TEMP%-experiment-confirmed): a truncated .meta raised
        # an uncaught JSONDecodeError and blocked EVERY subsequent run.
        _project(tmp_path, monkeypatch)
        sfd = SourceFileMutationData(path="src/mod.py")
        sfd.meta_path.parent.mkdir(parents=True, exist_ok=True)
        sfd.meta_path.write_text('{"exit_code_by_key": {"a": 1', encoding="utf-8")  # truncated

        sfd.load()  # must not raise

        assert sfd.exit_code_by_key == {}
        assert "corrupt" in capsys.readouterr().out.lower()
        assert not sfd.meta_path.exists()  # cleared so the fast path rebuilds

    def test_type_corrupt_meta_values_warn_and_rebuild(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # Issue #124 / B10: valid JSON with type-corrupt values (duration:
        # null → float(None) TypeError) used to escape the A3-CM-009 healing
        # and block every subsequent run — same warn+unlink+rebuild path now.
        _project(tmp_path, monkeypatch)
        sfd = SourceFileMutationData(path="src/mod.py")
        sfd.meta_path.parent.mkdir(parents=True, exist_ok=True)
        sfd.meta_path.write_text(
            '{"exit_code_by_key": {"a": 1}, "durations_by_key": {"a": null}}',
            encoding="utf-8",
        )

        sfd.load()  # must not raise

        assert sfd.exit_code_by_key == {}
        assert "corrupt" in capsys.readouterr().out.lower()
        assert not sfd.meta_path.exists()

    def test_save_is_atomic_via_tmp_and_replace(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _project(tmp_path, monkeypatch)
        sfd = SourceFileMutationData(path="src/mod.py")
        sfd.exit_code_by_key = {"src.mod.x_f__mutmut_1": 1}

        sfd.save()

        assert json.loads(sfd.meta_path.read_text(encoding="utf-8"))["exit_code_by_key"]
        leftovers = list(sfd.meta_path.parent.glob("*.tmp"))
        assert leftovers == []  # no temp residue


class TestForceHonesty:
    def test_partial_removal_is_reported_not_sold_as_clean(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        # A3-FD-009: rmtree(ignore_errors=True) + unconditional "Removed
        # mutants/" sold a partial deletion (files in use) as a clean slate.
        import shutil

        from click.testing import CliRunner

        import mutmut_win.cli as cli_module

        monkeypatch.chdir(tmp_path)
        (tmp_path / "mutants").mkdir()
        (tmp_path / "mutants" / "stuck.py").write_text("x", encoding="utf-8")
        monkeypatch.setattr(shutil, "rmtree", lambda *_a, **_k: None)  # deletion "fails"

        result = CliRunner().invoke(cli_module.cli, ["run", "--force", "--dry-run"])

        assert "could not fully remove" in result.output.lower()
        assert "removed mutants/" not in result.output.lower()
