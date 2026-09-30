"""M-020 (issue #160): ``--force`` cleanup must remove read-only staging.

Staging publishes the mirrored source mode, so a source file without
``S_IWRITE`` becomes a DOS read-only leaf under ``mutants/``. The cleanup
used ``shutil.rmtree(..., ignore_errors=True)`` — which replaces any
``onexc`` hook with a no-op — so such leaves survived every retry and the
run refused with the misleading "files in use?" diagnosis while ``mutants/``
remained partially deleted, blocking the documented ``run --force``
recovery path.

The ``mutants/`` root now goes through
``file_setup.remove_staging_root``: read-only leaves (files AND empty
read-only directories) are cleared through the established identity-checked
hook; unsafe leaves (hardlinked read-only files) are refused with their own
diagnosis; locked-but-writable leaves keep the retry/"files in use?"
semantics.
"""

from __future__ import annotations

import contextlib
import json
import os
import stat
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner
from hypothesis import given, settings
from hypothesis import strategies as st

from mutmut_win import cli
from mutmut_win.cli import cli as cli_entry
from mutmut_win.config import MutmutConfig
from mutmut_win.models import MutationRunResult
from tests.unit import windows_fs_util

_FILES_IN_USE_MESSAGE = (
    "Could not fully remove mutants/ (files in use?); refusing to run with stale state."
)


def _normcase_abspath(value: object) -> str:
    """Mirror the lexical root comparison used by the production hook."""
    return os.path.normcase(os.path.abspath(str(value)))  # noqa: PTH100


def _write_source(tmp_path: Path) -> None:
    source = tmp_path / "src" / "mod.py"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("def value():\n    return 1\n", encoding="utf-8")


def _invoke_force_run(*args: str) -> Any:
    orchestrator = MagicMock()
    orchestrator.run.return_value = MutationRunResult(total_mutants=1, killed=1)
    with (
        patch("mutmut_win.cli.load_config", return_value=MutmutConfig(paths_to_mutate=[])),
        patch("mutmut_win.cli.MutationOrchestrator", return_value=orchestrator),
        patch("mutmut_win.cli.PytestRunner"),
        patch("mutmut_win.cli.SpawnPoolExecutor"),
    ):
        return CliRunner().invoke(cli_entry, ["run", "--force", *args])


@pytest.fixture
def fast_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "_FORCE_CLEANUP_RETRY_DELAYS", (0.0, 0.0))


@pytest.mark.usefixtures("fast_retries")
class TestForceRemovesReadOnlyLeaves:
    def test_force_removes_read_only_staging_leaf(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        _write_source(tmp_path)
        staging_leaf = tmp_path / "mutants" / "src" / "mod.py"
        staging_leaf.parent.mkdir(parents=True)
        staging_leaf.write_text("def value():\n    return 2\n", encoding="utf-8")
        staging_leaf.chmod(stat.S_IREAD)
        try:
            result = _invoke_force_run()
        finally:
            with contextlib.suppress(OSError):
                staging_leaf.chmod(stat.S_IREAD | stat.S_IWRITE)

        assert result.exit_code == 0, result.output
        assert "Removed mutants/" in result.output
        assert not (tmp_path / "mutants").exists()

    def test_force_removes_empty_read_only_directory(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        _write_source(tmp_path)
        readonly_dir = tmp_path / "mutants" / "ro_dir"
        readonly_dir.mkdir(parents=True)
        readonly_dir.chmod(stat.S_IREAD)
        try:
            result = _invoke_force_run()
        finally:
            with contextlib.suppress(OSError):
                readonly_dir.chmod(stat.S_IREAD | stat.S_IWRITE)

        assert result.exit_code == 0, result.output
        assert not (tmp_path / "mutants").exists()


@pytest.mark.usefixtures("fast_retries")
class TestUnsafeLeavesAreRefused:
    def test_read_only_hardlinked_leaf_is_refused_without_external_change(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        _write_source(tmp_path)
        inside = tmp_path / "mutants" / "inside.txt"
        inside.parent.mkdir(parents=True)
        outside = tmp_path / "outside.txt"
        outside.write_text("shared payload", encoding="utf-8")
        os.link(outside, inside)
        # chmod is link-global: BOTH names now carry the read-only attribute.
        inside.chmod(stat.S_IREAD)
        try:
            result = _invoke_force_run()
            assert result.exit_code == 1
            assert "hardlinks" in result.output
            assert "Refusing --force cleanup of mutants/" in result.output
            assert outside.read_text(encoding="utf-8") == "shared payload"
            assert outside.stat().st_file_attributes & stat.FILE_ATTRIBUTE_READONLY
            assert inside.exists()
        finally:
            with contextlib.suppress(OSError):
                inside.chmod(stat.S_IREAD | stat.S_IWRITE)
                outside.chmod(stat.S_IREAD | stat.S_IWRITE)

    def test_read_only_hardlinked_leaf_json_stays_machine_readable(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        _write_source(tmp_path)
        inside = tmp_path / "mutants" / "inside.txt"
        inside.parent.mkdir(parents=True)
        outside = tmp_path / "outside.txt"
        outside.write_text("shared payload", encoding="utf-8")
        os.link(outside, inside)
        inside.chmod(stat.S_IREAD)
        try:
            result = _invoke_force_run("--output", "json")
        finally:
            with contextlib.suppress(OSError):
                inside.chmod(stat.S_IREAD | stat.S_IWRITE)
                outside.chmod(stat.S_IREAD | stat.S_IWRITE)

        assert result.exit_code == 1
        payload = json.loads(result.stdout)
        assert payload["exit_code"] == 1
        assert "hardlinks" in payload["error"]


@pytest.mark.usefixtures("fast_retries")
class TestLockedWritableLeavesKeepRetrySemantics:
    def test_sharing_violation_keeps_files_in_use_diagnosis(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        _write_source(tmp_path)
        leaf = tmp_path / "mutants" / "src" / "mod.py"
        leaf.parent.mkdir(parents=True)
        leaf.write_text("def value():\n    return 2\n", encoding="utf-8")
        mode_before = leaf.stat().st_mode
        with windows_fs_util.sharing_violation_holder(leaf):
            result = _invoke_force_run()

        assert result.exit_code == 1
        assert _FILES_IN_USE_MESSAGE in result.output
        assert leaf.stat().st_mode == mode_before


@pytest.mark.usefixtures("fast_retries")
class TestRootErrorsAreNotAttributeFixed:
    def test_root_permission_error_is_raised_without_chmod(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        root = tmp_path / "mutants"
        (root / "src").mkdir(parents=True)
        (root / "src" / "mod.py").write_text("x = 1\n", encoding="utf-8")
        root_lexical = _normcase_abspath(root)

        real_rmdir = os.rmdir

        def refusing_rmdir(path: object, *args: object, **kwargs: object) -> None:
            if _normcase_abspath(path) == root_lexical:
                raise PermissionError(5, "Access is denied")
            real_rmdir(path, *args, **kwargs)  # type: ignore[arg-type]

        chmod_targets: list[Path] = []
        real_chmod = Path.chmod

        def spying_chmod(self: Path, *args: object, **kwargs: object) -> None:
            chmod_targets.append(self)
            real_chmod(self, *args, **kwargs)  # type: ignore[arg-type]

        with (
            patch("os.rmdir", side_effect=refusing_rmdir),
            patch.object(Path, "chmod", spying_chmod),
        ):
            assert cli._remove_force_cleanup_root(Path("mutants")) is False

        assert root.exists()
        assert not [target for target in chmod_targets if _normcase_abspath(target) == root_lexical]


@given(
    st.lists(
        st.tuples(
            st.lists(st.sampled_from(["a", "b", "c"]), min_size=1, max_size=3),
            st.booleans(),
        ),
        max_size=6,
    )
)
@settings(max_examples=25, deadline=None)
def test_arbitrary_read_only_mix_is_removed(entries: list[tuple[list[str], bool]]) -> None:
    """Property: any mix of read-only leaves/dirs under mutants/ is removable."""
    original_cwd = Path.cwd()
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temporary:
        root = Path(temporary)
        try:
            with contextlib.chdir(root):
                (root / "src").mkdir(exist_ok=True)
                (root / "src" / "mod.py").write_text("def v():\n    return 1\n", encoding="utf-8")
                for index, (parts, readonly) in enumerate(entries):
                    directory = root / "mutants" / Path(*parts)
                    directory.mkdir(parents=True, exist_ok=True)
                    leaf = directory / f"m{index}.py"
                    leaf.write_text(f"x{index} = 1\n", encoding="utf-8")
                    if readonly:
                        leaf.chmod(stat.S_IREAD)
                with patch.object(cli, "_FORCE_CLEANUP_RETRY_DELAYS", (0.0, 0.0)):
                    assert cli._remove_force_cleanup_root(Path("mutants")) is True
                assert not (root / "mutants").exists()
        finally:
            # Restore writability so the TemporaryDirectory cleanup can cope
            # with any leftover read-only leaf after a failed property step.
            for path in root.rglob("mutants"):
                with contextlib.suppress(OSError):
                    path.chmod(stat.S_IREAD | stat.S_IWRITE)
            os.chdir(original_cwd)
