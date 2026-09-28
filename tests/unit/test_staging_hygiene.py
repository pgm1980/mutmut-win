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

import contextlib
import hashlib
import json
import os
import shutil
import stat
from pathlib import Path
from unittest.mock import patch

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from mutmut_win.config import MutmutConfig
from mutmut_win.exceptions import StagingNamespaceCollisionError, UnsafeStagingError
from mutmut_win.file_setup import (
    config_fingerprint_matches,
    copy_also_copy_files,
    copy_src_dir,
    create_mutants_for_file,
    validate_staging_namespace,
)
from mutmut_win.models import SourceFileMutationData


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


class TestDeletedSourceSync:
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


@pytest.mark.skipif(os.name != "nt", reason="Windows read-only replacement semantics")
class TestReadOnlyStagingPublication:
    _READ_ONLY = stat.S_IREAD
    _WRITABLE = stat.S_IREAD | stat.S_IWRITE

    def test_read_only_python_source_can_be_staged_then_generated(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        project = _project(tmp_path, monkeypatch)
        source = project / "src" / "mod.py"
        staged = project / "mutants" / "src" / "mod.py"
        source.chmod(self._READ_ONLY)
        try:
            copy_src_dir(MutmutConfig(paths_to_mutate=["src"]))
            assert stat.S_IMODE(staged.stat().st_mode) & stat.S_IWRITE == 0

            mutant_names, _duration, _fast_path = create_mutants_for_file(source, staged)

            assert mutant_names
            assert "__mutmut" in staged.read_text(encoding="utf-8")
            assert stat.S_IMODE(source.stat().st_mode) & stat.S_IWRITE == 0
        finally:
            source.chmod(self._WRITABLE)
            if staged.exists():
                staged.chmod(self._WRITABLE)

    def test_read_only_also_copy_file_refreshes_and_preserves_source_mode(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        project = _project(tmp_path, monkeypatch)
        source = project / "runtime.cfg"
        staged = project / "mutants" / "runtime.cfg"
        source.write_text("OLD", encoding="utf-8")
        source.chmod(self._READ_ONLY)
        config = MutmutConfig(paths_to_mutate=["src"], also_copy=["runtime.cfg"])
        try:
            copy_also_copy_files(config)
            assert staged.read_text(encoding="utf-8") == "OLD"
            assert stat.S_IMODE(staged.stat().st_mode) & stat.S_IWRITE == 0

            source.chmod(self._WRITABLE)
            source.write_text("NEW-CONTENT", encoding="utf-8")
            source.chmod(self._READ_ONLY)
            copy_also_copy_files(config)

            assert staged.read_text(encoding="utf-8") == "NEW-CONTENT"
            assert stat.S_IMODE(staged.stat().st_mode) & stat.S_IWRITE == 0
        finally:
            source.chmod(self._WRITABLE)
            if staged.exists():
                staged.chmod(self._WRITABLE)

    def test_failed_atomic_text_publish_restores_old_read_only_mode(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import mutmut_win.file_setup as file_setup

        project = _project(tmp_path, monkeypatch)
        target = project / "mutants" / "generated.py"
        target.parent.mkdir()
        target.write_text("OLD", encoding="utf-8")
        target.chmod(self._READ_ONLY)
        modes_seen: list[int] = []

        def fail_publish(_path: Path, _payload: bytes) -> None:
            modes_seen.append(stat.S_IMODE(target.stat().st_mode))
            raise OSError("synthetic publication failure")

        monkeypatch.setattr(file_setup, "atomic_write_bytes", fail_publish)
        try:
            with pytest.raises(OSError, match="synthetic publication failure"):
                file_setup._atomic_write_text(target, "NEW")

            assert modes_seen
            assert modes_seen[0] & stat.S_IWRITE
            assert target.read_text(encoding="utf-8") == "OLD"
            assert stat.S_IMODE(target.stat().st_mode) & stat.S_IWRITE == 0
        finally:
            target.chmod(self._WRITABLE)

    def test_read_only_hardlink_publish_is_rejected_without_external_change(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import mutmut_win.file_setup as file_setup

        project = _project(tmp_path, monkeypatch)
        source = project / "replacement.txt"
        outside = tmp_path / "outside.txt"
        target = project / "mutants" / "linked.txt"
        target.parent.mkdir()
        source.write_text("REPLACEMENT", encoding="utf-8")
        outside.write_text("EXTERNAL", encoding="utf-8")
        os.link(outside, target)
        outside.chmod(self._READ_ONLY)
        try:
            with pytest.raises(UnsafeStagingError, match="hardlinks"):
                file_setup._copy_with_retry(source, target, max_attempts=1)

            assert outside.read_text(encoding="utf-8") == "EXTERNAL"
            assert target.samefile(outside)
            assert stat.S_IMODE(outside.stat().st_mode) & stat.S_IWRITE == 0
        finally:
            outside.chmod(self._WRITABLE)
            if target.exists():
                target.chmod(self._WRITABLE)

    def test_read_only_hardlink_cleanup_is_rejected_without_external_change(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import mutmut_win.file_setup as file_setup

        project = _project(tmp_path, monkeypatch)
        outside = tmp_path / "outside.txt"
        ghost = project / "mutants" / "ghost.txt"
        ghost.parent.mkdir()
        outside.write_text("EXTERNAL", encoding="utf-8")
        os.link(outside, ghost)
        outside.chmod(self._READ_ONLY)
        try:
            with pytest.raises(UnsafeStagingError, match="hardlinks"):
                file_setup._retry_readonly_removal(
                    os.unlink,
                    str(ghost),
                    PermissionError("synthetic Windows read-only failure"),
                )

            assert outside.read_text(encoding="utf-8") == "EXTERNAL"
            assert ghost.samefile(outside)
            assert stat.S_IMODE(outside.stat().st_mode) & stat.S_IWRITE == 0
        finally:
            outside.chmod(self._WRITABLE)
            if ghost.exists():
                ghost.chmod(self._WRITABLE)

    def test_failed_read_only_cleanup_restores_old_mode(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import mutmut_win.file_setup as file_setup

        project = _project(tmp_path, monkeypatch)
        ghost = project / "mutants" / "ghost.txt"
        ghost.parent.mkdir()
        ghost.write_text("OLD", encoding="utf-8")
        ghost.chmod(self._READ_ONLY)
        modes_seen: list[int] = []

        def fail_delete(_raw_path: str) -> None:
            modes_seen.append(stat.S_IMODE(ghost.stat().st_mode))
            raise OSError("synthetic deletion failure")

        try:
            with pytest.raises(OSError, match="synthetic deletion failure"):
                file_setup._retry_readonly_removal(
                    fail_delete,
                    str(ghost),
                    PermissionError("synthetic Windows read-only failure"),
                )

            assert modes_seen
            assert modes_seen[0] & stat.S_IWRITE
            assert ghost.read_text(encoding="utf-8") == "OLD"
            assert stat.S_IMODE(ghost.stat().st_mode) & stat.S_IWRITE == 0
        finally:
            ghost.chmod(self._WRITABLE)


class TestDeletionSync:
    def test_deleted_root_module_disappears_from_staging(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        project = _project(tmp_path, monkeypatch)
        helper = project / "helper.py"
        helper.write_text("VALUE = 1\n", encoding="utf-8")
        cfg = MutmutConfig(paths_to_mutate=["."])
        copy_src_dir(cfg)
        staged = project / "mutants" / "helper.py"
        assert staged.is_file()

        helper.unlink()
        copy_src_dir(cfg)

        assert not staged.exists()

    def test_unmanaged_artifacts_are_removed_from_tool_owned_staging(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        project = _project(tmp_path, monkeypatch)
        cfg = MutmutConfig(paths_to_mutate=["src"])
        copy_src_dir(cfg)
        notes = project / "mutants" / "src" / "notes.txt"
        notes.write_text("keep me", encoding="utf-8")

        copy_src_dir(cfg)

        assert not notes.exists()

    def test_deleted_non_python_fixture_disappears_from_staging(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        project = _project(tmp_path, monkeypatch)
        fixture = project / "fixtures" / "runtime.json"
        fixture.parent.mkdir()
        fixture.write_text('{"value": 1}\n', encoding="utf-8")
        cfg = MutmutConfig(paths_to_mutate=["src"])
        copy_src_dir(cfg)
        staged = project / "mutants" / "fixtures" / "runtime.json"
        assert staged.is_file()

        staged.chmod(0o444)
        fixture.chmod(0o666)
        fixture.unlink()
        copy_src_dir(cfg)

        assert not staged.exists()


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
        sfd = SourceFileMutationData(path="src/mod.py")
        sfd.load()
        sfd.exit_code_by_key = {f"src.mod.{n}": 1 for n in names_first}
        sfd.save()

        names_fast, _, fast_flag = create_mutants_for_file(source, output)
        assert names_fast == names_first  # sanity: fast path active
        assert fast_flag is True
        normalized = json.loads(sfd.meta_path.read_text(encoding="utf-8"))
        assert set(normalized["exit_code_by_key"].values()) == {None}
        assert normalized["durations_by_key"] == {}
        assert normalized["estimated_durations_by_key"] == {}
        assert normalized["type_check_error_by_key"] == {}

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
        assert "corrupt" in capsys.readouterr().err.lower()  # warnings live on stderr (#127/A6)
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
        assert "corrupt" in capsys.readouterr().err.lower()  # warnings live on stderr (#127/A6)
        assert not sfd.meta_path.exists()

    def test_type_corrupt_meta_resets_every_partially_loaded_field(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # Mutation hardening (#124): _reset_loaded_fields must clear EVERY
        # field load may have populated before the corruption hit — and the
        # corruption warning is pinned verbatim (diagnostics are contract).
        _project(tmp_path, monkeypatch)
        sfd = SourceFileMutationData(path="src/mod.py")
        sfd.meta_path.parent.mkdir(parents=True, exist_ok=True)
        sfd.meta_path.write_text(
            "{"
            '"exit_code_by_key": {"a": 1},'
            '"durations_by_key": {"a": 1.5},'
            '"type_check_error_by_key": {"a": "boom"},'
            '"estimated_durations_by_key": {"a": null},'
            '"source_mtime": 1.0, "source_size": 2'
            "}",
            encoding="utf-8",
        )

        sfd.load()  # estimated_durations hits float(None) AFTER other fields loaded

        assert sfd.exit_code_by_key == {}
        assert sfd.durations_by_key == {}
        assert sfd.estimated_time_of_tests_by_mutant == {}
        assert sfd.type_check_error_by_key == {}
        assert sfd.source_mtime is None
        assert sfd.source_size is None
        expected_warning = (
            f"Warning: corrupted meta file {sfd.meta_path} — rebuilding from scratch."
        )
        assert expected_warning in capsys.readouterr().err.splitlines()

    def test_meta_roundtrip_preserves_every_field(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Mutation hardening (#124): a full save→load roundtrip pins every
        # JSON key string and both fingerprint fields — key-string mutants
        # in save OR load break it.
        _project(tmp_path, monkeypatch)
        original = SourceFileMutationData(path="src/mod.py")
        # The class-method key carries ǁ (U+01C1): on non-UTF-8 locales an
        # encoding=None regression breaks THIS roundtrip, not just exotics.
        original.exit_code_by_key = {
            "mod.x_f__mutmut_1": 1,
            "mod.x_f__mutmut_2": None,
            "mod.xǁClsǁm__mutmut_1": 0,
        }
        original.durations_by_key = {"mod.x_f__mutmut_1": 2.5}
        original.estimated_time_of_tests_by_mutant = {"mod.x_f__mutmut_1": 0.75}
        original.type_check_error_by_key = {"mod.x_f__mutmut_2": "incompatible type"}
        original.source_mtime = 1718180000.125
        original.source_size = 6919
        original.meta_path.parent.mkdir(parents=True, exist_ok=True)

        original.save()
        loaded = SourceFileMutationData(path="src/mod.py")
        loaded.load()

        assert loaded.exit_code_by_key == original.exit_code_by_key
        assert loaded.durations_by_key == original.durations_by_key
        assert loaded.estimated_time_of_tests_by_mutant == (
            original.estimated_time_of_tests_by_mutant
        )
        assert loaded.type_check_error_by_key == original.type_check_error_by_key
        assert loaded.source_mtime == original.source_mtime
        assert loaded.source_size == original.source_size

    @given(
        exit_codes=st.dictionaries(
            st.text(min_size=1), st.one_of(st.none(), st.integers(-(2**31), 2**32)), max_size=4
        ),
        durations=st.dictionaries(
            st.text(min_size=1),
            st.floats(min_value=0.0, max_value=1e9, allow_nan=False, allow_infinity=False),
            max_size=4,
        ),
        mtime=st.one_of(
            st.none(),
            st.floats(min_value=0.0, max_value=4e9, allow_nan=False, allow_infinity=False),
        ),
        size=st.one_of(st.none(), st.integers(min_value=0, max_value=2**40)),
    )
    @settings(
        max_examples=25,
        deadline=None,
        # tmp_path/monkeypatch are function-scoped on purpose: every example
        # overwrites the SAME meta file, so reuse across examples is safe.
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_meta_roundtrip_property(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        exit_codes: dict[str, int | None],
        durations: dict[str, float],
        mtime: float | None,
        size: int | None,
    ) -> None:
        # CLAUDE.md serialisation invariant (hypothesis): save→load is the
        # identity for every well-formed meta payload. Setup is inline and
        # idempotent — hypothesis reuses the function-scoped tmp_path for
        # every example (the suppressed health check above).
        monkeypatch.chdir(tmp_path)
        original = SourceFileMutationData(path="src/mod.py")
        original.exit_code_by_key = exit_codes
        original.durations_by_key = durations
        original.source_mtime = mtime
        original.source_size = size
        original.meta_path.parent.mkdir(parents=True, exist_ok=True)

        original.save()
        loaded = SourceFileMutationData(path="src/mod.py")
        loaded.load()

        assert loaded.exit_code_by_key == exit_codes
        assert loaded.durations_by_key == durations
        assert loaded.source_mtime == mtime
        assert loaded.source_size == size

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


class TestWave3StagingHygiene:
    """Issue #129 / 360°-A8 + B6 + C2 + C4 — fingerprints and mirror truth."""

    def test_engine_version_change_invalidates_config_fingerprint(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # 360°-A8: upgrading mutmut-win used to leave the old mutant
        # universe (and its reuse candidates) silently in place — v2.13's
        # f-string mutants never appeared on unchanged files.
        _project(tmp_path, monkeypatch)
        cfg = MutmutConfig(paths_to_mutate=["src"])
        assert config_fingerprint_matches(cfg) is False  # first run persists
        assert config_fingerprint_matches(cfg) is True  # unchanged → fast path

        import mutmut_win

        monkeypatch.setattr(mutmut_win, "__version__", "99.0.0")
        assert config_fingerprint_matches(cfg) is False  # upgrade invalidates

    def test_backdated_restore_of_unmutated_mirror_is_synced(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # 360°-B6a: a git-restore with an OLD timestamp escaped the
        # mtime-'>' comparison — the staging kept serving the stale copy
        # and the clean run validated against outdated code.
        project = _project(tmp_path, monkeypatch)
        helper = project / "src" / "helper.py"
        helper.write_text("VALUE = 1\n", encoding="utf-8")
        # A nested package exercises the deletion-sync walk filter with a
        # non-empty dirs list (mutation hardening for the skip-set arg).
        (project / "src" / "pkg").mkdir()
        (project / "src" / "pkg" / "__init__.py").write_text("", encoding="utf-8")
        cfg = MutmutConfig(paths_to_mutate=["src"])
        copy_src_dir(cfg)
        staged = project / "mutants" / "src" / "helper.py"
        assert staged.read_text(encoding="utf-8") == "VALUE = 1\n"

        helper.write_text("VALUE = 2\n", encoding="utf-8")
        os.utime(helper, (1_000_000_000, 1_000_000_000))  # restore with OLD mtime
        copy_src_dir(cfg)

        assert staged.read_text(encoding="utf-8") == "VALUE = 2\n"

    def test_mutated_file_with_meta_keeps_newer_staging(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The '>' path must SURVIVE for mutated files: their staging is the
        # trampolined output (newer) and the .meta fingerprint is the truth
        # there — an equality mirror would overwrite the trampoline with
        # the plain source and break the forced-fail gate.
        project = _project(tmp_path, monkeypatch)
        cfg = MutmutConfig(paths_to_mutate=["src"])
        copy_src_dir(cfg)
        staged = project / "mutants" / "src" / "mod.py"
        staged.write_text("# trampolined output\n", encoding="utf-8")
        source_hash = hashlib.sha256((project / "src" / "mod.py").read_bytes()).hexdigest()
        SourceFileMutationData(
            path="src/mod.py",
            source_hash=source_hash,
            generation_fingerprint="a" * 64,
            generated_hash=hashlib.sha256(staged.read_bytes()).hexdigest(),
        ).save_generation_metadata()

        copy_src_dir(cfg)  # source unchanged since the first mirror

        assert staged.read_text(encoding="utf-8") == "# trampolined output\n"

    def test_also_copy_tree_syncs_updates_and_deletions(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # 360°-B6b + C2: copytree re-copied everything every run and never
        # deleted — removed test files kept RUNNING inside the staging.
        project = _project(tmp_path, monkeypatch)
        tests_src = project / "tests"
        tests_src.mkdir()
        (tests_src / "test_keep.py").write_text("def test_a(): pass\n", encoding="utf-8")
        (tests_src / "test_gone.py").write_text("def test_b(): pass\n", encoding="utf-8")
        cfg = MutmutConfig(paths_to_mutate=["src"], also_copy=["tests/"])
        copy_also_copy_files(cfg)
        staged_tests = project / "mutants" / "tests"
        assert (staged_tests / "test_gone.py").exists()

        (tests_src / "test_gone.py").unlink()
        (tests_src / "test_keep.py").write_text("def test_a(): assert True\n", encoding="utf-8")
        copy_also_copy_files(cfg)

        assert not (staged_tests / "test_gone.py").exists()  # deletion synced
        assert "assert True" in (staged_tests / "test_keep.py").read_text(encoding="utf-8")

    def test_also_copy_deletes_read_only_child_from_existing_mirror(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        project = _project(tmp_path, monkeypatch)
        fixtures = project / "fixtures"
        fixtures.mkdir()
        live = fixtures / "runtime.json"
        live.write_text('{"value": 1}\n', encoding="utf-8")
        cfg = MutmutConfig(paths_to_mutate=["src"], also_copy=["fixtures/"])
        copy_also_copy_files(cfg)
        staged = project / "mutants" / "fixtures" / "runtime.json"
        staged.chmod(0o444)
        live.unlink()

        copy_also_copy_files(cfg)

        assert not staged.exists()

    def test_legitimate_meta_fixture_is_independent_of_same_named_companion(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        project = _project(tmp_path, monkeypatch)
        live = project / "runtime"
        live_meta = project / "runtime.meta"
        live.write_text("runtime one\n", encoding="utf-8")
        live_meta.write_text('{"fixture": 1}\n', encoding="utf-8")
        cfg = MutmutConfig(paths_to_mutate=["src"])
        copy_src_dir(cfg)
        live.write_text("runtime two\n", encoding="utf-8")
        live_meta.write_text('{"fixture": 2}\n', encoding="utf-8")

        import mutmut_win.file_setup as file_setup_module

        real_walk = file_setup_module.os.walk

        def meta_first_walk(*args: object, **kwargs: object):
            for root, dirs, files in real_walk(*args, **kwargs):
                files.sort(key=lambda name: (not name.casefold().endswith(".meta"), name))
                yield root, dirs, files

        with patch("mutmut_win.file_setup.os.walk", side_effect=meta_first_walk):
            copy_src_dir(cfg)

        assert (project / "mutants" / "runtime").read_text(encoding="utf-8") == "runtime two\n"
        assert (project / "mutants" / "runtime.meta").read_text(encoding="utf-8") == (
            '{"fixture": 2}\n'
        )

    def test_deleted_meta_fixture_does_not_survive_live_companion(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        project = _project(tmp_path, monkeypatch)
        live = project / "data"
        live_meta = project / "data.meta"
        live.write_text("runtime\n", encoding="utf-8")
        live_meta.write_text('{"fixture": true}\n', encoding="utf-8")
        cfg = MutmutConfig(paths_to_mutate=["src"])
        copy_src_dir(cfg)
        staged_meta = project / "mutants" / "data.meta"
        assert staged_meta.is_file()

        live_meta.unlink()
        copy_src_dir(cfg)

        assert not staged_meta.exists()

    @pytest.mark.parametrize("source_name", ["other.py", "OTHER.PY"])
    def test_retained_meta_fixture_survives_deleted_unselected_python_companion(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        source_name: str,
    ) -> None:
        """CX221-067: expected user metadata owns its bytes independently."""
        project = _project(tmp_path, monkeypatch)
        fixtures = project / "fixtures"
        fixtures.mkdir()
        live_source = fixtures / source_name
        live_source.write_text("VALUE = 1\n", encoding="utf-8")
        live_meta = fixtures / f"{source_name}.meta"
        live_meta.write_bytes(b"LEGITIMATE-USER-FIXTURE")
        cfg = MutmutConfig(paths_to_mutate=["src"])
        copy_src_dir(cfg)
        staged_source = project / "mutants" / "fixtures" / source_name
        staged_meta = staged_source.with_name(f"{source_name}.meta")
        assert staged_meta.read_bytes() == live_meta.read_bytes()

        live_source.unlink()
        copy_src_dir(cfg)

        assert not staged_source.exists()
        assert live_meta.read_bytes() == b"LEGITIMATE-USER-FIXTURE"
        assert staged_meta.read_bytes() == live_meta.read_bytes()

    @pytest.mark.parametrize("mirror_field", ["also_copy", "extra_paths"])
    def test_configured_meta_fixture_survives_automatic_python_companion_cleanup(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        mirror_field: str,
    ) -> None:
        """The automatic mirror must not delete another mirror's metadata."""
        project = tmp_path / "project"
        project.mkdir()
        _project(project, monkeypatch)
        live_source = project / "other.py"
        live_source.write_text("VALUE = 1\n", encoding="utf-8")
        external = tmp_path / "external"
        external.mkdir()
        live_meta = external / "other.py.meta"
        live_meta.write_bytes(b"CONFIGURED-USER-FIXTURE")
        cfg = MutmutConfig(
            paths_to_mutate=["src"],
            **{mirror_field: ["../external/other.py.meta"]},
        )
        copy_src_dir(cfg)
        copy_also_copy_files(cfg)
        staged_meta = project / "mutants" / "other.py.meta"
        assert staged_meta.read_bytes() == live_meta.read_bytes()

        live_source.unlink()
        copy_src_dir(cfg)

        assert not (project / "mutants" / "other.py").exists()
        assert live_meta.read_bytes() == b"CONFIGURED-USER-FIXTURE"
        assert staged_meta.read_bytes() == live_meta.read_bytes()
        copy_also_copy_files(cfg)
        assert staged_meta.read_bytes() == live_meta.read_bytes()

    def test_missing_extra_path_removes_owned_non_python_staging(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        project = tmp_path / "project"
        project.mkdir()
        monkeypatch.chdir(project)
        (project / "src").mkdir()
        (project / "src" / "mod.py").write_text(
            "def f(a):\n    return a + 1\n",
            encoding="utf-8",
        )
        shared = tmp_path / "shared"
        shared.mkdir()
        (shared / "runtime.json").write_text('{"value": 1}\n', encoding="utf-8")
        cfg = MutmutConfig(paths_to_mutate=["src"], extra_paths=["../shared"])
        copy_src_dir(cfg)
        copy_also_copy_files(cfg)
        staged = project / "mutants" / "shared" / "runtime.json"
        assert staged.is_file()

        staged.chmod(0o444)
        (shared / "runtime.json").unlink()
        shared.rmdir()
        copy_src_dir(cfg)
        copy_also_copy_files(cfg)

        assert not (project / "mutants" / "shared").exists()

    def test_also_copy_skips_unchanged_files(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # C2: the sync must be mtime-aware — unchanged files are not
        # re-copied (observable via the copy primitive, since copy2
        # preserves mtimes and hides the difference).
        import mutmut_win.file_setup as fs

        project = _project(tmp_path, monkeypatch)
        tests_src = project / "tests"
        tests_src.mkdir()
        (tests_src / "test_keep.py").write_text("def test_a(): pass\n", encoding="utf-8")
        cfg = MutmutConfig(paths_to_mutate=["src"], also_copy=["tests/"])
        copy_also_copy_files(cfg)

        calls: list[str] = []
        real_copy = fs._copy_with_retry

        def spying_copy(src: Path, dst: Path, **kwargs: object) -> None:
            calls.append(str(src))
            real_copy(src, dst, **kwargs)

        monkeypatch.setattr(fs, "_copy_with_retry", spying_copy)
        copy_also_copy_files(cfg)

        assert [c for c in calls if "test_keep" in c] == []  # unchanged → untouched

    def test_also_copy_single_file_sync(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Mutation hardening (#129/C2): the single-file branch shares the
        # mirror rule — first copy, no re-copy when unchanged, re-copy on
        # change. (Trees are covered above; this pins the file branch.)
        import mutmut_win.file_setup as fs

        project = _project(tmp_path, monkeypatch)
        single = project / "extra.cfg"
        single.write_text("v1", encoding="utf-8")
        cfg = MutmutConfig(paths_to_mutate=["src"], also_copy=["extra.cfg"])
        copy_also_copy_files(cfg)
        staged = project / "mutants" / "extra.cfg"
        assert staged.read_text(encoding="utf-8") == "v1"  # first copy happened

        calls: list[str] = []
        real_copy = fs._copy_with_retry

        def spying_copy(src: Path, dst: Path, **kwargs: object) -> None:
            calls.append(str(src))
            real_copy(src, dst, **kwargs)

        monkeypatch.setattr(fs, "_copy_with_retry", spying_copy)
        copy_also_copy_files(cfg)
        assert [c for c in calls if "extra.cfg" in c] == []  # unchanged → untouched

        single.write_text("v2-changed", encoding="utf-8")
        copy_also_copy_files(cfg)
        assert staged.read_text(encoding="utf-8") == "v2-changed"  # change synced

    def test_tooling_dirs_are_not_mirrored(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # 360°-C4/MW220-044: Windows path names are case-insensitive, so
        # mixed-case aliases of tooling/cache trees must be skipped too.
        project = _project(tmp_path, monkeypatch)
        (project / "Node_Modules").mkdir()
        (project / "Node_Modules" / "big.js").write_text("x", encoding="utf-8")
        (project / ".ClAuDe").mkdir()
        (project / ".ClAuDe" / "settings.json").write_text("{}", encoding="utf-8")
        (project / ".VENV").mkdir()
        (project / ".VENV" / "pyvenv.cfg").write_text("home=x", encoding="utf-8")

        copy_src_dir(MutmutConfig(paths_to_mutate=["src"]))

        assert not (project / "mutants" / "Node_Modules").exists()
        assert not (project / "mutants" / ".ClAuDe").exists()
        assert not (project / "mutants" / ".VENV").exists()

    def test_mirror_unstatable_target_is_stale(self, tmp_path: Path) -> None:
        # Mutation hardening: a missing/unstatable target must refresh.
        from mutmut_win.file_setup import _mirror_is_stale

        src = tmp_path / "a.py"
        src.write_text("x", encoding="utf-8")
        assert _mirror_is_stale(src, tmp_path / "missing.py") is True

    def test_mirror_meta_owned_equal_content_hash_is_not_stale(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Generated staging is preserved only when metadata proves the exact
        # current source bytes; equal timestamps are not sufficient.
        from mutmut_win.file_setup import _mirror_is_stale

        src = tmp_path / "a.py"
        tgt = tmp_path / "mutants" / "staged.py"
        tgt.parent.mkdir()
        src.write_text("x", encoding="utf-8")
        tgt.write_text("trampolined", encoding="utf-8")
        source_hash = hashlib.sha256(src.read_bytes()).hexdigest()
        monkeypatch.chdir(tmp_path)
        SourceFileMutationData(
            path="staged.py",
            source_hash=source_hash,
            generation_fingerprint="a" * 64,
            generated_hash=hashlib.sha256(tgt.read_bytes()).hexdigest(),
        ).save_generation_metadata()
        os.utime(src, (1_000, 1_000))
        os.utime(tgt, (1_000, 1_000))
        assert _mirror_is_stale(src, tgt) is False

    def test_mirror_meta_owned_newer_source_is_stale(self, tmp_path: Path) -> None:
        from mutmut_win.file_setup import _mirror_is_stale

        src = tmp_path / "a.py"
        tgt = tmp_path / "staged.py"
        src.write_text("x", encoding="utf-8")
        tgt.write_text("trampolined", encoding="utf-8")
        tgt.with_name(tgt.name + ".meta").write_text("{}", encoding="utf-8")
        os.utime(tgt, (1_000, 1_000))
        os.utime(src, (2_000, 2_000))
        assert _mirror_is_stale(src, tgt) is True

    def test_mirror_plain_size_change_with_equal_mtime_is_stale(self, tmp_path: Path) -> None:
        # The size term is load-bearing: equal mtimes with different sizes
        # (content swap + timestamp restore) must refresh a plain mirror.
        from mutmut_win.file_setup import _mirror_is_stale

        src = tmp_path / "a.py"
        tgt = tmp_path / "staged.py"
        src.write_text("xx", encoding="utf-8")
        tgt.write_text("x", encoding="utf-8")
        os.utime(src, (1_000, 1_000))
        os.utime(tgt, (1_000, 1_000))
        assert _mirror_is_stale(src, tgt) is True


class TestForcedRootRetainPolicy:
    """AP-10 / M-032: the M-002 retain policy governs forced roots too.

    A git-ignored mutation root configured via ``paths_to_mutate`` must keep
    its generator output and own ``.meta`` sidecar across ``copy_src_dir``
    (including the ``_sync_deleted_sources`` pass) while it remains a selected
    mutation target outside coverage mode.
    """

    def _project(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
        project = tmp_path / "project"
        project.mkdir()
        (project / ".gitignore").write_text("generated/\n", encoding="utf-8")
        (project / "src").mkdir()
        (project / "src" / "mod.py").write_text("def f(a):\n    return a + 1\n", encoding="utf-8")
        generated = project / "generated"
        generated.mkdir()
        (generated / "gmod.py").write_text("def g(a):\n    return a - 1\n", encoding="utf-8")
        monkeypatch.chdir(project)
        return project

    def test_generated_output_and_sidecar_survive_copy_src_dir(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        project = self._project(tmp_path, monkeypatch)
        cfg = MutmutConfig(paths_to_mutate=["src", "generated"], max_children=1)
        copy_src_dir(cfg)
        staged = _simulate_generated_target(project, "generated/gmod.py")

        copy_src_dir(cfg)

        assert staged.read_text(encoding="utf-8") == _GENERATED_BYTES
        assert staged.with_name(staged.name + ".meta").exists()

    def test_coverage_mode_restores_original_in_forced_root(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        project = self._project(tmp_path, monkeypatch)
        cfg = MutmutConfig(paths_to_mutate=["src", "generated"], max_children=1)
        copy_src_dir(cfg)
        staged = _simulate_generated_target(project, "generated/gmod.py")

        coverage_cfg = MutmutConfig(
            paths_to_mutate=["src", "generated"],
            max_children=1,
            mutate_only_covered_lines=True,
        )
        copy_src_dir(coverage_cfg)

        live_bytes = (project / "generated" / "gmod.py").read_bytes()
        assert staged.read_bytes() == live_bytes
        assert not staged.with_name(staged.name + ".meta").exists()

    def test_deleted_forced_root_source_is_cleaned_up(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        project = self._project(tmp_path, monkeypatch)
        cfg = MutmutConfig(paths_to_mutate=["src", "generated"], max_children=1)
        copy_src_dir(cfg)
        staged = project / "mutants" / "generated" / "gmod.py"

        (project / "generated" / "gmod.py").unlink()
        copy_src_dir(cfg)

        assert not staged.exists()
        assert not staged.with_name(staged.name + ".meta").exists()

    def test_revert_a_b_a_in_forced_configured_mirror_restores_live_bytes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The AP-02 A→B→A revert contract, repeated in the ignored root."""
        project = self._project(tmp_path, monkeypatch)
        source = project / "generated" / "gmod.py"
        cfg = MutmutConfig(also_copy=["generated"], max_children=1)
        copy_src_dir(cfg)
        copy_also_copy_files(cfg)
        staged = _simulate_generated_target(project, "generated/gmod.py")

        source.write_text("B = 2\n", encoding="utf-8")
        copy_also_copy_files(cfg)
        source.write_text("A = 1\n", encoding="utf-8")
        copy_also_copy_files(cfg)

        assert staged.read_bytes() == source.read_bytes()
        assert not staged.with_name(staged.name + ".meta").exists()


class TestVanishedLiveInputs:
    """M-033: vanished project inputs are not namespace collisions.

    ``_same_live_input`` collapsed "identity not determinable" into
    "different live sources", so a file deleted between the input freeze and
    the comparison produced a false ``StagingNamespaceCollisionError`` with a
    factually wrong remedy.
    """

    def _project(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
        project = tmp_path / "project"
        project.mkdir()
        (project / "src").mkdir()
        (project / "src" / "mod.py").write_text("def f(a):\n    return a + 1\n", encoding="utf-8")
        tests = project / "tests"
        tests.mkdir()
        (tests / "test_keep.py").write_text("def test_a(): pass\n", encoding="utf-8")
        (tests / "test_gone.py").write_text("def test_b(): pass\n", encoding="utf-8")
        monkeypatch.chdir(project)
        return project

    def _freeze_then_delete(
        self,
        monkeypatch: pytest.MonkeyPatch,
        project: Path,
        victims: tuple[str, ...] = ("tests/test_gone.py",),
    ) -> list[str]:
        """Freeze the automatic inputs, then delete *victims* before compare.

        Returns the victims that were part of the frozen plan, so a test can
        prove the vanished file was actually enumerated.
        """
        import mutmut_win.file_setup as file_setup

        original = file_setup._iter_automatic_staging_inputs
        frozen_victims: list[str] = []

        def freeze_and_vanish(excluded_resolved: frozenset[Path], **kwargs: object):
            frozen = list(original(excluded_resolved, **kwargs))
            for victim in victims:
                if any(source == Path(victim) for source, _target in frozen):
                    frozen_victims.append(victim)
                (project / victim).unlink()
            return iter(frozen)

        monkeypatch.setattr(file_setup, "_iter_automatic_staging_inputs", freeze_and_vanish)
        return frozen_victims

    def test_vanished_automatic_input_under_configured_root_is_not_a_collision(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        project = self._project(tmp_path, monkeypatch)
        frozen_victims = self._freeze_then_delete(monkeypatch, project)
        config = MutmutConfig(paths_to_mutate=["src"], also_copy=["tests/"])
        validate_staging_namespace(config)  # must not raise
        # The trigger's shape is proven: the vanished file WAS planned, and
        # expected_source (absolute, mapped from the configured also_copy
        # root) and automatic_source (relative) denote the SAME deleted file
        # — both sides of the comparison are gone.
        assert "tests/test_gone.py" in frozen_victims
        assert not (project / "tests" / "test_gone.py").exists()

    def test_vanished_planned_input_pair_is_not_a_collision(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Loop 1: a file planned by two mirrors vanishes after the freeze."""
        import mutmut_win.file_setup as file_setup

        project = self._project(tmp_path, monkeypatch)
        original_automatic = file_setup._iter_automatic_staging_inputs
        original_configured = file_setup._iter_configured_staging_inputs

        def freeze_automatic(excluded_resolved: frozenset[Path], **kwargs: object):
            return iter(list(original_automatic(excluded_resolved, **kwargs)))

        def freeze_configured(config: MutmutConfig, excluded_resolved: frozenset[Path]):
            frozen = list(original_configured(config, excluded_resolved))
            (project / "tests" / "test_gone.py").unlink()
            return iter(frozen)

        monkeypatch.setattr(file_setup, "_iter_automatic_staging_inputs", freeze_automatic)
        monkeypatch.setattr(file_setup, "_iter_configured_staging_inputs", freeze_configured)
        config = MutmutConfig(paths_to_mutate=["src"], also_copy=["tests/", "tests/test_gone.py"])
        validate_staging_namespace(config)  # must not raise

    def test_permission_error_stays_a_collision(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Fail-closed: an unprovable identity must not pass as vanished."""
        project = self._project(tmp_path, monkeypatch)
        self._freeze_then_delete(monkeypatch, project)
        real_samefile = Path.samefile

        def refusing_samefile(self: Path, other: str | Path) -> bool:
            if "test_gone" in str(self) or "test_gone" in str(other):
                raise PermissionError("identity not provable")
            return real_samefile(self, other)

        monkeypatch.setattr(Path, "samefile", refusing_samefile)
        config = MutmutConfig(paths_to_mutate=["src"], also_copy=["tests/"])
        with pytest.raises(StagingNamespaceCollisionError):
            validate_staging_namespace(config)

    def test_configured_side_missing_automatic_existing_stays_a_collision(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A vanished configured source with a live automatic mirror erases
        that mirror's staging in the configured sync — that stays a collision."""
        project = self._project(tmp_path, monkeypatch)
        fixtures = project / "fixtures"
        fixtures.mkdir()
        (fixtures / "data.bin").write_bytes(b"DATA")
        shared = tmp_path / "shared" / "fixtures"
        shared.mkdir(parents=True)
        (shared / "data.bin").write_bytes(b"SHARED")
        self._freeze_then_delete(monkeypatch, project, victims=())
        (shared / "data.bin").unlink()  # the configured side is now missing
        config = MutmutConfig(paths_to_mutate=["src"], also_copy=["../shared/fixtures"])
        with pytest.raises(StagingNamespaceCollisionError):
            validate_staging_namespace(config)

    def test_live_input_relation_states(self, tmp_path: Path) -> None:
        """Direct contract of _live_input_relation (M-033)."""
        import mutmut_win.file_setup as file_setup

        left = tmp_path / "left.bin"
        right = tmp_path / "right.bin"
        left.write_bytes(b"L")
        right.write_bytes(b"R")
        assert file_setup._live_input_relation(left, right) == "different"
        assert file_setup._live_input_relation(left, left) == "same"
        hardlink = tmp_path / "hardlink.bin"
        os.link(left, hardlink)
        assert file_setup._live_input_relation(left, hardlink) == "same"

        gone_left = tmp_path / "gone-left.bin"
        gone_right = tmp_path / "gone-right.bin"
        assert file_setup._live_input_relation(gone_left, right) == "left_missing"
        assert file_setup._live_input_relation(left, gone_right) == "right_missing"
        assert file_setup._live_input_relation(gone_left, gone_right) == "both_missing"

        # Thin wrapper equivalence for the unchanged call sites.
        assert file_setup._same_live_input(left, left) is True
        assert file_setup._same_live_input(left, right) is False

    @given(
        left_exists=st.booleans(),
        right_exists=st.booleans(),
        same_object=st.sampled_from(["same-path", "hardlink", "different"]),
    )
    @settings(
        max_examples=25,
        deadline=None,
        # tmp_path is function-scoped on purpose: every example recreates the
        # same short paths (see the cleanup below).
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_live_input_relation_property(
        self, tmp_path: Path, left_exists: bool, right_exists: bool, same_object: str
    ) -> None:
        """Existence and identity fully determine the relation verdict."""
        import mutmut_win.file_setup as file_setup

        # Clean slate: hypothesis reuses the function-scoped tmp_path and a
        # previous example may have left a (hard-linked) right.bin behind.
        for residue in ("left.bin", "right.bin"):
            with contextlib.suppress(FileNotFoundError):
                (tmp_path / residue).unlink()
        left = tmp_path / "left.bin"
        left.write_bytes(b"L")
        right: Path = left
        if same_object == "hardlink":
            right = tmp_path / "right.bin"
            os.link(left, right)
        elif same_object == "different":
            right = tmp_path / "right.bin"
            right.write_bytes(b"R")
        same_path = right is left
        if same_path and left_exists != right_exists:
            # One physical path cannot vanish on only one side.
            left_exists = right_exists = left_exists and right_exists
        if not left_exists:
            left.unlink()
        if not right_exists and not same_path:
            right.unlink()

        relation = file_setup._live_input_relation(left, right)

        if left_exists and right_exists:
            assert relation == ("same" if same_object != "different" else "different")
        elif left_exists:
            assert relation == "right_missing"
        elif right_exists:
            assert relation == "left_missing"
        else:
            assert relation == "both_missing"


class TestStagingTypeSwitch:
    """M-030 / Q-13: file<->directory switches are reconciled, not fatal.

    A live path that switched kind between runs used to abort with a raw
    ``FileExistsError`` (``mkdir`` over a staged file) or ``PermissionError``
    (``os.replace`` onto a staged directory) long before the deletion pass
    could clean up.
    """

    def _project(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
        project = tmp_path / "project"
        project.mkdir()
        (project / "src").mkdir()
        (project / "src" / "mod.py").write_text("def f(a):\n    return a + 1\n", encoding="utf-8")
        monkeypatch.chdir(project)
        return project

    def test_file_to_directory_switch_in_automatic_mirror(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        project = self._project(tmp_path, monkeypatch)
        thing = project / "thing"
        thing.write_text("x", encoding="utf-8")
        cfg = MutmutConfig(paths_to_mutate=["src"])
        copy_src_dir(cfg)
        assert (project / "mutants" / "thing").is_file()

        thing.unlink()
        thing.mkdir()
        (thing / "data.txt").write_text("d", encoding="utf-8")
        copy_src_dir(cfg)  # pre-fix: FileExistsError from mkdir

        assert (project / "mutants" / "thing" / "data.txt").is_file()

    def test_directory_to_file_switch_in_automatic_mirror(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import mutmut_win.file_setup as file_setup

        monkeypatch.setattr(file_setup.time, "sleep", lambda _seconds: None)
        project = self._project(tmp_path, monkeypatch)
        thing = project / "thing"
        thing.mkdir()
        (thing / "data.txt").write_text("d", encoding="utf-8")
        cfg = MutmutConfig(paths_to_mutate=["src"])
        copy_src_dir(cfg)
        assert (project / "mutants" / "thing").is_dir()

        shutil.rmtree(thing)
        thing.write_text("x", encoding="utf-8")
        copy_src_dir(cfg)  # pre-fix: OSError after the replace retries

        staged = project / "mutants" / "thing"
        assert staged.is_file()
        assert staged.read_text(encoding="utf-8") == "x"

    def test_nested_type_switch_roundtrip(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """File 'a' becomes directory 'a/b/' and back (ergänzung (b))."""
        project = self._project(tmp_path, monkeypatch)
        live = project / "a"
        live.write_text("F", encoding="utf-8")
        cfg = MutmutConfig(paths_to_mutate=["src"])
        copy_src_dir(cfg)
        assert (project / "mutants" / "a").is_file()

        live.unlink()
        (live / "b").mkdir(parents=True)
        (live / "b" / "c.txt").write_text("C", encoding="utf-8")
        copy_src_dir(cfg)
        assert (project / "mutants" / "a" / "b" / "c.txt").is_file()

        shutil.rmtree(live)
        live.write_text("F2", encoding="utf-8")
        copy_src_dir(cfg)
        staged = project / "mutants" / "a"
        assert staged.is_file()
        assert staged.read_text(encoding="utf-8") == "F2"
        assert not (project / "mutants" / "a" / "b").exists()

    def test_type_switch_inside_configured_tree(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """_sync_tree path without any preceding automatic copy (ergänzung (f))."""
        project = self._project(tmp_path, monkeypatch)
        sub = project / "fixtures" / "sub"
        sub.parent.mkdir()
        sub.write_text("as-file", encoding="utf-8")
        cfg = MutmutConfig(paths_to_mutate=["src"], also_copy=["fixtures"])
        copy_also_copy_files(cfg)
        assert (project / "mutants" / "fixtures" / "sub").is_file()

        sub.unlink()
        sub.mkdir()
        (sub / "nested.txt").write_text("n", encoding="utf-8")
        copy_also_copy_files(cfg)

        assert (project / "mutants" / "fixtures" / "sub" / "nested.txt").is_file()

    def test_type_switch_on_configured_file_entry(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        project = self._project(tmp_path, monkeypatch)
        entry = project / "fixtures" / "cfg"
        entry.parent.mkdir()
        entry.write_text("v1", encoding="utf-8")
        cfg = MutmutConfig(paths_to_mutate=["src"], also_copy=["fixtures/cfg"])
        copy_also_copy_files(cfg)
        assert (project / "mutants" / "fixtures" / "cfg").is_file()

        entry.unlink()
        entry.mkdir()
        (entry / "nested.txt").write_text("n", encoding="utf-8")
        copy_also_copy_files(cfg)
        assert (project / "mutants" / "fixtures" / "cfg" / "nested.txt").is_file()

        shutil.rmtree(entry)
        entry.write_text("v2", encoding="utf-8")
        copy_also_copy_files(cfg)
        staged = project / "mutants" / "fixtures" / "cfg"
        assert staged.is_file()
        assert staged.read_text(encoding="utf-8") == "v2"

    def test_configured_tree_root_that_was_a_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Directory branch of copy_also_copy_files over a staged file (erg. (g))."""
        project = self._project(tmp_path, monkeypatch)
        fixtures = project / "fixtures"
        fixtures.write_text("was-a-file", encoding="utf-8")
        cfg = MutmutConfig(paths_to_mutate=["src"], also_copy=["fixtures"])
        copy_also_copy_files(cfg)
        assert (project / "mutants" / "fixtures").is_file()

        fixtures.unlink()
        fixtures.mkdir()
        (fixtures / "data.txt").write_text("d", encoding="utf-8")
        copy_also_copy_files(cfg)

        assert (project / "mutants" / "fixtures" / "data.txt").is_file()

    def test_read_only_staged_file_is_replaced_on_switch(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        project = self._project(tmp_path, monkeypatch)
        thing = project / "thing"
        thing.write_text("x", encoding="utf-8")
        cfg = MutmutConfig(paths_to_mutate=["src"])
        copy_src_dir(cfg)
        staged = project / "mutants" / "thing"
        staged.chmod(0o444)

        thing.unlink()
        thing.mkdir()
        (thing / "data.txt").write_text("d", encoding="utf-8")
        copy_src_dir(cfg)

        assert (project / "mutants" / "thing" / "data.txt").is_file()

    def test_junction_staged_entry_with_wrong_kind_is_unsafe(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import _winapi

        import mutmut_win.file_setup as file_setup

        project = self._project(tmp_path, monkeypatch)
        thing = project / "thing"
        thing.write_text("x", encoding="utf-8")
        cfg = MutmutConfig(paths_to_mutate=["src"])
        copy_src_dir(cfg)
        staged = project / "mutants" / "thing"
        staged.unlink()
        junction_target = tmp_path / "junction-target"
        junction_target.mkdir()
        try:
            _winapi.CreateJunction(str(junction_target), str(staged))
        except AttributeError, OSError, NotImplementedError:
            # Junction creation unavailable in this environment: simulate the
            # reparse verdict the destination guard would produce.
            real_check = file_setup._is_link_or_reparse

            def junction_verdict(path: Path) -> bool:
                return path == staged or real_check(path)

            monkeypatch.setattr(file_setup, "_is_link_or_reparse", junction_verdict)

        thing.unlink()
        thing.mkdir()
        (thing / "data.txt").write_text("d", encoding="utf-8")
        with pytest.raises(UnsafeStagingError):
            copy_src_dir(cfg)

    def test_reconcile_guards_root_and_persistent_state(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import mutmut_win.file_setup as file_setup

        project = self._project(tmp_path, monkeypatch)
        mutants_root = project / "mutants"
        mutants_root.mkdir()
        fingerprint = mutants_root / ".mutmut-config-fingerprint"
        fingerprint.write_text("fp", encoding="utf-8")

        # The staging root itself stays effect-less for directories ...
        file_setup._reconcile_staging_kind(
            mutants_root, want_directory=True, mutants_root=mutants_root
        )
        assert mutants_root.is_dir()
        # ... but is never replaced by a file, and persistent state files at
        # the root are explicitly excluded from reconciliation.
        with pytest.raises(UnsafeStagingError):
            file_setup._reconcile_staging_kind(
                mutants_root, want_directory=False, mutants_root=mutants_root
            )
        with pytest.raises(UnsafeStagingError):
            file_setup._reconcile_staging_kind(
                fingerprint, want_directory=False, mutants_root=mutants_root
            )
        assert fingerprint.read_text(encoding="utf-8") == "fp"

    @given(
        states=st.lists(
            st.sampled_from(["file", "dir", "absent"]),
            min_size=2,
            max_size=4,
        )
    )
    @settings(max_examples=15, deadline=None)
    def test_type_state_sequence_property(self, states: list[str]) -> None:
        """After every copy_src_dir the staged kind mirrors the live kind and
        no raw OSError escapes the copy phase."""
        import contextlib
        import tempfile

        live_root = Path(tempfile.mkdtemp(prefix="mutmut-kind-prop-"))
        try:
            (live_root / "src").mkdir()
            (live_root / "src" / "mod.py").write_text("X = 1\n", encoding="utf-8")
            cfg = MutmutConfig(paths_to_mutate=["src"], max_children=1)
            live = live_root / "thing"
            staged = live_root / "mutants" / "thing"
            with contextlib.chdir(live_root):
                for state in states:
                    if live.is_dir():
                        shutil.rmtree(live)
                    elif live.exists() or live.is_symlink():
                        live.unlink()
                    if state == "file":
                        live.write_text("F", encoding="utf-8")
                    elif state == "dir":
                        live.mkdir()
                        (live / "data.txt").write_text("D", encoding="utf-8")
                    copy_src_dir(cfg)
                    if state == "file":
                        assert staged.is_file()
                        assert staged.read_text(encoding="utf-8") == "F"
                    elif state == "dir":
                        assert staged.is_dir()
                        assert (staged / "data.txt").is_file()
                    else:
                        assert not staged.exists()
        finally:
            shutil.rmtree(live_root, ignore_errors=True)


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
        source = tmp_path / "src" / "mod.py"
        source.parent.mkdir()
        source.write_text("def value():\n    return 1\n", encoding="utf-8")
        (tmp_path / "mutants").mkdir()
        (tmp_path / "mutants" / "stuck.py").write_text("x", encoding="utf-8")
        monkeypatch.setattr(shutil, "rmtree", lambda *_a, **_k: None)  # deletion "fails"

        result = CliRunner().invoke(cli_module.cli, ["run", "--force", "--dry-run"])

        assert "could not fully remove" in result.output.lower()
        assert "removed mutants/" not in result.output.lower()


# ---------------------------------------------------------------------------
# Retain policy for generator output (M-002 / M-031, issue #144)
# ---------------------------------------------------------------------------

_GENERATED_BYTES = "# trampolined generator output\n"


def _simulate_generated_target(
    project: Path, rel_path: str, *, generated: str = _GENERATED_BYTES
) -> Path:
    """Q-12 helper: trampolined bytes plus an owned sidecar for *rel_path*."""
    live = project / rel_path
    staged = project / "mutants" / rel_path
    assert staged.is_file(), "simulate generation after an initial copy run"
    staged.write_text(generated, encoding="utf-8")
    SourceFileMutationData(
        path=rel_path,
        source_hash=hashlib.sha256(live.read_bytes()).hexdigest(),
        generation_fingerprint="a" * 64,
        generated_hash=hashlib.sha256(staged.read_bytes()).hexdigest(),
    ).save_generation_metadata()
    return staged


class TestRetainPolicy:
    """M-002: generator output survives only for retained targets; M-031:
    proven-own sidecars survive configured-mirror deletion passes."""

    def test_coverage_mode_restores_unmutated_bytes_and_drops_sidecar(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        project = _project(tmp_path, monkeypatch)
        cfg = MutmutConfig(paths_to_mutate=["src"], max_children=1)
        copy_src_dir(cfg)
        staged = _simulate_generated_target(project, "src/mod.py")

        coverage_cfg = MutmutConfig(
            paths_to_mutate=["src"], max_children=1, mutate_only_covered_lines=True
        )
        copy_src_dir(coverage_cfg)

        live_bytes = (project / "src" / "mod.py").read_bytes()
        assert staged.read_bytes() == live_bytes
        assert not staged.with_name(staged.name + ".meta").exists()

    def test_deselected_target_restores_original_and_drops_owned_sidecar(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        project = _project(tmp_path, monkeypatch)
        cfg = MutmutConfig(paths_to_mutate=["src"], max_children=1)
        copy_src_dir(cfg)
        staged = _simulate_generated_target(project, "src/mod.py")

        deselected = MutmutConfig(
            paths_to_mutate=["src"], max_children=1, do_not_mutate=["src/mod.py"]
        )
        copy_src_dir(deselected)

        live_bytes = (project / "src" / "mod.py").read_bytes()
        assert staged.read_bytes() == live_bytes
        assert not staged.with_name(staged.name + ".meta").exists()

    def test_selected_target_without_coverage_keeps_generated_bytes_over_two_runs(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        project = _project(tmp_path, monkeypatch)
        cfg = MutmutConfig(paths_to_mutate=["src"], max_children=1)
        copy_src_dir(cfg)
        staged = _simulate_generated_target(project, "src/mod.py")

        copy_src_dir(cfg)
        copy_src_dir(cfg)

        assert staged.read_text(encoding="utf-8") == _GENERATED_BYTES
        assert staged.with_name(staged.name + ".meta").exists()

    def test_sync_tree_only_run_restores_deselected_target(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Isolated _sync_tree path: only copy_also_copy_files runs."""
        project = _project(tmp_path, monkeypatch)
        tests_pkg = project / "tests" / "pkg"
        tests_pkg.mkdir(parents=True)
        (tests_pkg / "mod.py").write_text("def g(a):\n    return a - 1\n", encoding="utf-8")
        selected = MutmutConfig(paths_to_mutate=["tests/pkg"], also_copy=["tests"], max_children=1)
        copy_also_copy_files(selected)
        staged = _simulate_generated_target(project, "tests/pkg/mod.py")

        deselected = MutmutConfig(
            paths_to_mutate=["tests/pkg"],
            also_copy=["tests"],
            max_children=1,
            do_not_mutate=["tests/pkg/mod.py"],
        )
        copy_also_copy_files(deselected)

        live_bytes = (tests_pkg / "mod.py").read_bytes()
        assert staged.read_bytes() == live_bytes
        assert not staged.with_name(staged.name + ".meta").exists()

    def test_deselected_also_copy_file_entry_restores_original(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        project = _project(tmp_path, monkeypatch)
        data_dir = project / "data"
        data_dir.mkdir()
        (data_dir / "helper.py").write_text("VALUE = 1\n", encoding="utf-8")
        selected = MutmutConfig(
            paths_to_mutate=["data/helper.py"], also_copy=["data/helper.py"], max_children=1
        )
        copy_src_dir(selected)
        copy_also_copy_files(selected)
        staged = _simulate_generated_target(project, "data/helper.py")

        deselected = MutmutConfig(also_copy=["data/helper.py"], max_children=1)
        copy_also_copy_files(deselected)

        live_bytes = (data_dir / "helper.py").read_bytes()
        assert staged.read_bytes() == live_bytes
        assert not staged.with_name(staged.name + ".meta").exists()

    def test_configured_mirror_keeps_owned_generation_sidecar(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """M-031: the deletion pass of a configured mirror keeps own sidecars."""
        project = _project(tmp_path, monkeypatch)
        tests_pkg = project / "tests" / "pkg"
        tests_pkg.mkdir(parents=True)
        (tests_pkg / "mod.py").write_text("def g(a):\n    return a - 1\n", encoding="utf-8")
        cfg = MutmutConfig(paths_to_mutate=["tests/pkg"], also_copy=["tests"], max_children=1)
        copy_src_dir(cfg)
        copy_also_copy_files(cfg)
        staged = _simulate_generated_target(project, "tests/pkg/mod.py")

        copy_src_dir(cfg)
        copy_also_copy_files(cfg)

        sidecar = staged.with_name(staged.name + ".meta")
        assert sidecar.exists()
        from mutmut_win.models import read_owned_source_metadata

        assert read_owned_source_metadata(sidecar) is not None

    def test_owned_sidecar_without_live_companion_is_removed_in_configured_mirror(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        project = _project(tmp_path, monkeypatch)
        tests_pkg = project / "tests" / "pkg"
        tests_pkg.mkdir(parents=True)
        (tests_pkg / "mod.py").write_text("def g(a):\n    return a - 1\n", encoding="utf-8")
        cfg = MutmutConfig(paths_to_mutate=["tests/pkg"], also_copy=["tests"], max_children=1)
        copy_src_dir(cfg)
        copy_also_copy_files(cfg)
        staged = _simulate_generated_target(project, "tests/pkg/mod.py")
        sidecar = staged.with_name(staged.name + ".meta")
        assert sidecar.exists()

        (tests_pkg / "mod.py").unlink()  # companion disappears from the live tree
        copy_also_copy_files(cfg)

        assert not sidecar.exists()
        assert not staged.exists()

    def test_revert_a_b_a_in_configured_mirror_restores_live_bytes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Gegenprüfung 1: no stale sidecar may outlive refreshed bytes."""
        project = _project(tmp_path, monkeypatch)
        tests_pkg = project / "tests" / "pkg"
        tests_pkg.mkdir(parents=True)
        source = tests_pkg / "mod.py"
        source.write_text("A = 1\n", encoding="utf-8")
        cfg = MutmutConfig(also_copy=["tests"], max_children=1)
        copy_src_dir(cfg)
        copy_also_copy_files(cfg)
        staged = _simulate_generated_target(project, "tests/pkg/mod.py")

        source.write_text("B = 2\n", encoding="utf-8")
        copy_also_copy_files(cfg)
        source.write_text("A = 1\n", encoding="utf-8")
        copy_also_copy_files(cfg)

        assert staged.read_bytes() == source.read_bytes()
        assert not staged.with_name(staged.name + ".meta").exists()

    @given(
        coverage_mode=st.booleans(),
        selection=st.sets(st.sampled_from(["mod1", "mod2", "mod3"]), min_size=0, max_size=3),
    )
    @settings(
        max_examples=25,
        deadline=None,
    )
    def test_retain_policy_property(self, coverage_mode: bool, selection: set[str]) -> None:
        """After a follow-up run, generated bytes survive iff selected and not
        coverage mode; everything else carries live bytes and no own sidecar."""
        import contextlib
        import tempfile

        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            package = root / "src"
            package.mkdir()
            for index in (1, 2, 3):
                (package / f"mod{index}.py").write_text(
                    f"def f{index}(a):\n    return a + {index}\n", encoding="utf-8"
                )
            with contextlib.chdir(root):
                cfg = MutmutConfig(paths_to_mutate=["src"], max_children=1)
                copy_src_dir(cfg)
                for index in (1, 2, 3):
                    _simulate_generated_target(root, f"src/mod{index}.py")

                do_not = [
                    f"src/mod{index}.py" for index in (1, 2, 3) if f"mod{index}" not in selection
                ]
                followup = MutmutConfig(
                    paths_to_mutate=["src"],
                    max_children=1,
                    do_not_mutate=do_not,
                    mutate_only_covered_lines=coverage_mode,
                )
                copy_src_dir(followup)

                for index in (1, 2, 3):
                    staged = root / "mutants" / f"src/mod{index}.py"
                    retained = (f"mod{index}" in selection) and not coverage_mode
                    if retained:
                        assert staged.read_text(encoding="utf-8") == _GENERATED_BYTES
                        assert staged.with_name(staged.name + ".meta").exists()
                    else:
                        live = (package / f"mod{index}.py").read_bytes()
                        assert staged.read_bytes() == live
                        assert not staged.with_name(staged.name + ".meta").exists()
