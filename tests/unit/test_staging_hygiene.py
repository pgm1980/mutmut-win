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

import hashlib
import json
import os
import stat
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from mutmut_win.config import MutmutConfig
from mutmut_win.exceptions import UnsafeStagingError
from mutmut_win.file_setup import (
    config_fingerprint_matches,
    copy_also_copy_files,
    copy_src_dir,
    create_mutants_for_file,
)
from mutmut_win.models import SourceFileMutationData

if TYPE_CHECKING:
    from pathlib import Path


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
